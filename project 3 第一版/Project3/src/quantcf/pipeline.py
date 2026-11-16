"""End-to-end research pipeline for the final course submission.

The orchestration layer is intentionally thin: market data, factor formulas,
portfolio construction, broker accounting, diagnostics and reporting remain
separate modules.  This file only wires those audited components together and
writes deterministic, inspectable artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, BacktestResult, rerun_without_fees, run_backtest
from .data import load_panel, verify_source_manifest, write_shareable_sample
from .diagnostics import DiagnosticResult, analyze_factors
from .factors import calculate_factors, next_open_forward_labels
from .metrics import calculate_metrics
from .portfolio import PortfolioConfig, generate_equal_weight_targets, generate_target_weights
from .recorder import ExperimentRecorder, sha256_file, to_json_safe, write_strict_json
from .report import ReportInputs, generate_report


PIPELINE_VERSION = "1.0.0"


@dataclass(frozen=True)
class StrategySpec:
    """A controlled strategy variant used by the final experiment."""

    name: str
    factor: str | None
    frequency: str
    capacity_limited: bool
    role: str


def project_root() -> Path:
    """Return the repository root independently of the current directory."""

    return Path(__file__).resolve().parents[2]


def _resolve_from_root(value: str | Path, root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def load_config(config_path: str | Path | None = None) -> tuple[dict[str, Any], Path, Path]:
    """Load the strict JSON configuration and return it with resolved paths."""

    root = project_root()
    path = _resolve_from_root(config_path or "config/default.json", root).resolve()
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load project configuration: {path}") from exc
    required = {"data", "factors", "strategy", "execution", "metrics"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"configuration is missing sections: {missing}")
    return config, path, root


def _write_csv(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.12g")
    return path


def _write_parquet(frame: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return path


def _quality_for_report(quality: Mapping[str, Any], panel: pd.DataFrame) -> dict[str, Any]:
    """Add compact aliases used by the report without discarding full audit data."""

    result = dict(quality)
    raw = quality.get("raw_snapshot_audit")
    raw_rows = raw.get("rows") if isinstance(raw, Mapping) else quality.get("rows")
    result.update(
        {
            "raw_rows": int(raw_rows or len(panel)),
            "clean_rows": int(len(panel)),
            "calendar_days": int(pd.DatetimeIndex(panel["date"]).nunique()),
            "duplicate_rows": int(panel.duplicated(["date", "asset"]).sum()),
            "invalid_rows": int(
                (
                    ~np.isfinite(pd.to_numeric(panel["open_adj"], errors="coerce"))
                    | ~np.isfinite(pd.to_numeric(panel["close_adj"], errors="coerce"))
                ).sum()
            ),
        }
    )
    return result


def _strategy_specs(config: Mapping[str, Any]) -> list[StrategySpec]:
    strategy = config["strategy"]
    baseline = str(strategy.get("baseline_frequency", "monthly"))
    experiment = str(strategy.get("experiment_frequency", "weekly"))
    benchmark = str(strategy.get("benchmark_frequency", baseline))
    primary = str(strategy.get("primary_factor", "momentum"))
    return [
        StrategySpec(f"{primary}_{baseline}", primary, baseline, False, "primary"),
        StrategySpec(f"{primary}_{experiment}", primary, experiment, False, "frequency_control"),
        StrategySpec(f"reversal_{experiment}", "reversal", experiment, False, "factor_comparison"),
        StrategySpec(
            f"low_volatility_{experiment}",
            "low_volatility",
            experiment,
            False,
            "factor_comparison",
        ),
        StrategySpec(
            f"{primary}_{experiment}_liquidity",
            primary,
            experiment,
            True,
            "liquidity_extension",
        ),
        StrategySpec(f"equal_weight_{benchmark}", None, benchmark, False, "benchmark"),
    ]


def _factor_scores(factors: pd.DataFrame, name: str) -> pd.DataFrame:
    scores = factors.loc[factors["factor"] == name, ["date", "asset", "score"]].copy()
    if scores.empty:
        raise ValueError(f"no scores were produced for factor {name!r}")
    return scores


def _portfolio_config(config: Mapping[str, Any], frequency: str) -> PortfolioConfig:
    strategy = config["strategy"]
    factors = config["factors"]
    return PortfolioConfig(
        top_n=int(strategy.get("top_n", 5)),
        invest_fraction=float(strategy.get("invest_fraction", 0.99)),
        min_assets=int(factors.get("min_assets", 6)),
        frequency=frequency,
    )


def _targets_for_spec(
    spec: StrategySpec,
    factors: pd.DataFrame,
    pivots: Mapping[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    config: Mapping[str, Any],
    backtest_config: BacktestConfig,
) -> pd.DataFrame:
    portfolio_config = _portfolio_config(config, spec.frequency)
    if spec.factor is None:
        eligibility = pivots["close_adj"].where(pivots["close_adj"].notna())
        return generate_equal_weight_targets(
            eligibility,
            calendar=calendar,
            config=portfolio_config,
            start=backtest_config.start,
            end=backtest_config.end,
        )
    return generate_target_weights(
        _factor_scores(factors, spec.factor),
        calendar=calendar,
        config=portfolio_config,
        start=backtest_config.start,
        end=backtest_config.end,
    )


def _flatten_strategy_metrics(
    spec: StrategySpec,
    net: BacktestResult,
    gross: BacktestResult,
) -> dict[str, Any]:
    net_metrics = calculate_metrics(net)
    gross_metrics = calculate_metrics(gross)
    row: dict[str, Any] = {
        "strategy": spec.name,
        "factor": spec.factor or "equal_weight",
        "frequency": spec.frequency,
        "role": spec.role,
        "capacity_limited": spec.capacity_limited,
        "audit_passed": bool(net.audit.get("passed")) and bool(gross.audit.get("passed")),
    }
    row.update(net_metrics)
    row.update({f"gross_{key}": value for key, value in gross_metrics.items()})
    row["fee_return_drag"] = float(
        gross_metrics["cumulative_return"] - net_metrics["cumulative_return"]
    )
    row["terminal_wealth_drag"] = float(
        gross_metrics["terminal_equity"] - net_metrics["terminal_equity"]
    )
    return row


def _write_backtest_result(directory: Path, targets: pd.DataFrame, result: BacktestResult) -> list[Path]:
    paths = [
        _write_csv(targets, directory / "targets.csv"),
        _write_csv(result.ledger, directory / "ledger.csv"),
        _write_csv(result.orders, directory / "orders.csv"),
        _write_csv(result.fills, directory / "fills.csv"),
        _write_csv(result.holdings, directory / "holdings.csv"),
    ]
    paths.append(write_strict_json(directory / "audit.json", result.audit))
    return paths


def _audit_summary(audits: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    max_error = 0.0
    violation_totals = {"timing": 0, "capacity": 0, "missing_open": 0, "rejected_order_fee": 0}
    for audit in audits.values():
        errors = audit.get("max_errors", {})
        if isinstance(errors, Mapping):
            finite = [float(value) for value in errors.values() if value is not None and np.isfinite(value)]
            max_error = max([max_error, *finite])
        violations = audit.get("violations", {})
        if isinstance(violations, Mapping):
            for key in violation_totals:
                violation_totals[key] += int(violations.get(key, 0) or 0)
    passed_by_strategy = {name: bool(audit.get("passed")) for name, audit in audits.items()}
    return {
        "all_passed": bool(passed_by_strategy) and all(passed_by_strategy.values()),
        "strategies_audited": len(passed_by_strategy),
        "maximum_accounting_error": max_error,
        "timing_violations": violation_totals["timing"],
        "missing_open_violations": violation_totals["missing_open"],
        "capacity_violations": violation_totals["capacity"],
        "rejected_order_fee_violations": violation_totals["rejected_order_fee"],
        "passed_by_strategy": passed_by_strategy,
    }


def _make_figures(
    equity_curves: pd.DataFrame,
    diagnostics: DiagnosticResult,
    output_directory: Path,
) -> list[Path]:
    """Save submission-friendly static plots in addition to report-internal plots."""

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    output_directory.mkdir(parents=True, exist_ok=True)
    colours = ["#126477", "#E07A5F", "#3D8D7A", "#7A6FAC", "#D6A84B", "#506784"]
    paths: list[Path] = []

    wide = equity_curves.pivot(index="date", columns="strategy", values="nav").sort_index()
    figure, axis = plt.subplots(figsize=(10.5, 5.2))
    for index, name in enumerate(wide.columns):
        axis.plot(wide.index, wide[name], label=name, linewidth=1.35, color=colours[index % len(colours)])
    axis.axhline(1.0, color="#8B98A1", linestyle="--", linewidth=0.8)
    axis.set_title("Audited net asset value")
    axis.set_ylabel("NAV")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, fontsize=8, ncol=2)
    figure.tight_layout()
    equity_path = output_directory / "equity_curves.png"
    figure.savefig(equity_path, dpi=180, facecolor="white")
    plt.close(figure)
    paths.append(equity_path)

    rank_ic = diagnostics.ic_timeseries.copy()
    if not rank_ic.empty:
        rank_ic["date"] = pd.to_datetime(rank_ic["date"])
        rank_ic = rank_ic.loc[rank_ic["horizon"] == rank_ic["horizon"].max()]
        figure, axis = plt.subplots(figsize=(10.5, 4.8))
        for index, (name, group) in enumerate(rank_ic.groupby("factor", sort=True)):
            series = group.sort_values("date").set_index("date")["rank_ic"].rolling(20, min_periods=5).mean()
            axis.plot(series.index, series, label=name, linewidth=1.25, color=colours[index % len(colours)])
        axis.axhline(0.0, color="#8B98A1", linewidth=0.8)
        axis.set_title("20-session rolling Rank IC")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False, fontsize=8)
        figure.tight_layout()
        ic_path = output_directory / "rank_ic.png"
        figure.savefig(ic_path, dpi=180, facecolor="white")
        plt.close(figure)
        paths.append(ic_path)

    groups = diagnostics.group_summary.copy()
    if not groups.empty:
        groups = groups.loc[groups["horizon"] == groups["horizon"].max()]
        figure, axis = plt.subplots(figsize=(8.5, 4.8))
        for index, (name, group) in enumerate(groups.groupby("factor", sort=True)):
            group = group.sort_values("group")
            axis.plot(
                group["group"],
                group["mean_return"] * 100.0,
                marker="o",
                label=name,
                color=colours[index % len(colours)],
            )
        axis.axhline(0.0, color="#8B98A1", linewidth=0.8)
        axis.set_title("Formation-time group return")
        axis.set_xlabel("Quantile (low to high)")
        axis.set_ylabel("Mean forward return (%)")
        axis.grid(alpha=0.2)
        axis.legend(frameon=False, fontsize=8)
        figure.tight_layout()
        group_path = output_directory / "group_returns.png"
        figure.savefig(group_path, dpi=180, facecolor="white")
        plt.close(figure)
        paths.append(group_path)
    return paths


def _key_artifact_hashes(output_directory: Path) -> dict[str, str]:
    candidates = (
        "config.json",
        "data_quality.json",
        "factors/factors.parquet",
        "factors/labels.parquet",
        "diagnostics/ic_summary.csv",
        "diagnostics/group_summary.csv",
        "strategy_summary.csv",
        "equity_curves.csv",
        "audit_summary.json",
    )
    return {
        relative: sha256_file(output_directory / relative)
        for relative in candidates
        if (output_directory / relative).is_file()
    }


def _basic_verification(output_directory: Path, root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    required = [
        "config.json",
        "data_quality.json",
        "strategy_summary.csv",
        "equity_curves.csv",
        "audit_summary.json",
        "factors/factors.parquet",
        "factors/labels.parquet",
        "diagnostics/ic_summary.csv",
    ]
    missing = [name for name in required if not (output_directory / name).is_file()]
    audit = json.loads((output_directory / "audit_summary.json").read_text(encoding="utf-8")) if not missing else {}
    manifest_path = _resolve_from_root(config["data"]["manifest"], root)
    source_verified = False
    source_error: str | None = None
    try:
        verify_source_manifest(manifest_path)
        source_verified = True
    except Exception as exc:  # pragma: no cover - surfaced in verification output
        source_error = f"{type(exc).__name__}: {exc}"
    result = {
        "pipeline_version": PIPELINE_VERSION,
        "passed": not missing and bool(audit.get("all_passed")) and source_verified,
        "required_artifacts_present": not missing,
        "missing_artifacts": missing,
        "all_backtest_audits_passed": bool(audit.get("all_passed")),
        "source_manifest_verified": source_verified,
        "source_manifest_error": source_error,
        "deterministic_rerun_checked": False,
        "deterministic_rerun_match": None,
        "artifact_sha256": _key_artifact_hashes(output_directory),
    }
    write_strict_json(output_directory / "verification.json", result)
    return result


def _report_inputs(output_directory: Path) -> ReportInputs:
    return ReportInputs(
        config=output_directory / "config.json",
        manifest=output_directory / "run_manifest.json",
        data_quality=output_directory / "data_quality.json",
        factor_summary=output_directory / "diagnostics" / "distribution.csv",
        ic_summary=output_directory / "diagnostics" / "ic_summary.csv",
        ic_timeseries=output_directory / "diagnostics" / "ic_timeseries.csv",
        group_summary=output_directory / "diagnostics" / "group_summary.csv",
        spread_summary=output_directory / "diagnostics" / "spread_summary.csv",
        rank_dynamics=output_directory / "diagnostics" / "rank_dynamics.csv",
        strategy_summary=output_directory / "strategy_summary.csv",
        equity_curves=output_directory / "equity_curves.csv",
        experiment_summary=output_directory / "experiment_summary.csv",
        liquidity_summary=output_directory / "liquidity_summary.csv",
        audit_summary=output_directory / "audit_summary.json",
        limitations=[
            "固定 ETF 资产池不能消除幸存者偏差，历史结果只代表该资产池与样本区间。",
            "日频下一开盘成交忽略集合竞价申报限制、盘口深度、涨跌停和日内冲击。",
            "流动性预算使用成交日前可得的历史成交额，仅用于执行敏感性分析。",
            "当前实验为历史回放而非真正未见样本外检验，不应把历史最优方案外推。",
            "IC 与分组标签存在重叠，自相关和多重研究选择使统计结论以描述性解释为主。",
        ],
        source_notes=[
            "数据：Tushare Pro fund_daily 与 fund_adj；本地原始快照及 SHA-256 清单是复现基准。",
            "Alphalens：https://github.com/quantopian/alphalens（IC、分组收益、换手诊断思想）。",
            "Qlib：https://github.com/microsoft/qlib（松耦合工作流、配置和实验记录思想）。",
            "Backtrader：https://github.com/mementum/backtrader（策略、经纪商、成交与分析器分层思想）。",
            "AI 辅助：用于任务拆解、代码/测试/文档草拟与排版；实证数字来自固定快照和可复运行代码，提交者仍须亲自理解与复核。",
        ],
    )


def build_report_from_outputs(
    out_dir: str | Path = "outputs",
    pdf_path: str | Path | None = None,
) -> Path:
    """Build the evidence-backed PDF from an existing completed output directory."""

    root = project_root()
    output_directory = _resolve_from_root(out_dir, root).resolve()
    destination = (
        _resolve_from_root(pdf_path, root).resolve()
        if pdf_path is not None
        else root / "output" / "pdf" / "CF2026_Project1_Final_Report.pdf"
    )
    required = ["config.json", "strategy_summary.csv", "audit_summary.json", "run_manifest.json"]
    missing = [name for name in required if not (output_directory / name).is_file()]
    if missing:
        raise FileNotFoundError(f"report inputs are missing from {output_directory}: {missing}")
    return generate_report(destination, _report_inputs(output_directory))


def run_pipeline(
    config_path: str | Path | None = None,
    out_dir: str | Path = "outputs",
    generate_pdf: bool = True,
    *,
    record_run: bool = True,
) -> dict[str, Any]:
    """Run data validation, diagnostics, all backtests, audit and optional PDF."""

    config, resolved_config, root = load_config(config_path)
    output_directory = _resolve_from_root(out_dir, root).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    for name in ("data", "factors", "diagnostics", "backtests", "figures", "pdf"):
        (output_directory / name).mkdir(parents=True, exist_ok=True)
    write_strict_json(output_directory / "config.json", config)

    data_cfg = config["data"]
    raw_paths = {
        "prices": _resolve_from_root(data_cfg["prices_snapshot"], root),
        "adjustments": _resolve_from_root(data_cfg["adjustment_snapshot"], root),
        "source_manifest": _resolve_from_root(data_cfg["manifest"], root),
    }
    source_paths = {
        "config": resolved_config,
        "pyproject": root / "pyproject.toml",
        "research_protocol": root / "RESEARCH_PROTOCOL.md",
        "ai_assistance": root / "AI_ASSISTANCE.md",
    }
    recorder: ExperimentRecorder | None = None
    if record_run:
        recorder = ExperimentRecorder(
            output_directory / "runs",
            config,
            data_paths=raw_paths,
            source_paths=source_paths,
            run_name="final-project",
        ).start()

    try:
        panel, pivots, quality = load_panel(root, config)
        quality_for_report = _quality_for_report(quality, panel)
        data_paths = [
            _write_parquet(panel, output_directory / "data" / "clean_panel.parquet"),
            write_shareable_sample(panel, output_directory / "data" / "shareable_sample.csv"),
            write_strict_json(output_directory / "data_quality.json", quality_for_report),
        ]

        factor_cfg = config["factors"]
        factors = calculate_factors(panel, windows=factor_cfg.get("windows"))
        labels = next_open_forward_labels(panel, factor_cfg.get("label_horizons", (1, 5)))
        factor_paths = [
            _write_parquet(factors, output_directory / "factors" / "factors.parquet"),
            _write_parquet(labels, output_directory / "factors" / "labels.parquet"),
        ]

        diagnostic_factors = factors[["date", "asset", "factor", "raw_value", "is_valid"]]
        diagnostics = analyze_factors(
            diagnostic_factors,
            labels=labels,
            horizons=factor_cfg.get("label_horizons", (1, 5)),
            n_groups=int(factor_cfg.get("groups", 5)),
            min_assets=int(factor_cfg.get("min_assets", 6)),
            start=data_cfg.get("start"),
            end=data_cfg.get("end"),
        )
        diagnostic_paths = list(diagnostics.save(output_directory / "diagnostics").values())

        backtest_config = BacktestConfig.from_mapping(config)
        calendar = pd.DatetimeIndex(sorted(pd.to_datetime(panel["date"]).unique()))
        strategy_rows: list[dict[str, Any]] = []
        equity_rows: list[pd.DataFrame] = []
        audit_details: dict[str, Mapping[str, Any]] = {}
        all_artifacts: list[Path] = [*data_paths, *factor_paths, *diagnostic_paths]

        for spec in _strategy_specs(config):
            targets = _targets_for_spec(spec, factors, pivots, calendar, config, backtest_config)
            net = run_backtest(
                panel,
                targets,
                backtest_config,
                capacity_limited=spec.capacity_limited,
            )
            gross = rerun_without_fees(
                panel,
                targets,
                backtest_config,
                capacity_limited=spec.capacity_limited,
            )
            strategy_rows.append(_flatten_strategy_metrics(spec, net, gross))
            audit_details[spec.name] = net.audit
            audit_details[f"{spec.name}__gross"] = gross.audit
            net_directory = output_directory / "backtests" / spec.name / "net"
            gross_directory = output_directory / "backtests" / spec.name / "gross_zero_fee"
            all_artifacts.extend(_write_backtest_result(net_directory, targets, net))
            all_artifacts.extend(_write_backtest_result(gross_directory, targets, gross))
            curve = net.ledger[["date", "equity", "nav", "daily_return"]].copy()
            curve.insert(1, "strategy", spec.name)
            equity_rows.append(curve)

        strategy_summary = pd.DataFrame(strategy_rows)
        equity_curves = pd.concat(equity_rows, ignore_index=True)
        strategy_path = _write_csv(strategy_summary, output_directory / "strategy_summary.csv")
        equity_path = _write_csv(equity_curves, output_directory / "equity_curves.csv")
        all_artifacts.extend([strategy_path, equity_path])

        strategy_cfg = config["strategy"]
        primary = str(strategy_cfg.get("primary_factor", "momentum"))
        baseline = f"{primary}_{strategy_cfg.get('baseline_frequency', 'monthly')}"
        experiment = f"{primary}_{strategy_cfg.get('experiment_frequency', 'weekly')}"
        limited = f"{experiment}_liquidity"
        experiment_summary = strategy_summary.loc[
            strategy_summary["strategy"].isin([baseline, experiment])
        ].copy()
        experiment_path = _write_csv(experiment_summary, output_directory / "experiment_summary.csv")
        all_artifacts.append(experiment_path)

        unlimited_row = strategy_summary.set_index("strategy").loc[experiment]
        limited_row = strategy_summary.set_index("strategy").loc[limited]
        liquidity_summary = pd.DataFrame(
            [
                {
                    "unlimited_strategy": experiment,
                    "limited_strategy": limited,
                    "unlimited_cumulative_return": unlimited_row["cumulative_return"],
                    "limited_cumulative_return": limited_row["cumulative_return"],
                    "return_difference": limited_row["cumulative_return"] - unlimited_row["cumulative_return"],
                    "unlimited_fill_ratio": unlimited_row["aggregate_fill_ratio"],
                    "limited_fill_ratio": limited_row["aggregate_fill_ratio"],
                    "limited_unfilled_notional": limited_row["requested_notional"]
                    - limited_row["filled_reference_notional"],
                }
            ]
        )
        liquidity_path = _write_csv(liquidity_summary, output_directory / "liquidity_summary.csv")
        all_artifacts.append(liquidity_path)

        audit_summary = _audit_summary(audit_details)
        audit_path = write_strict_json(output_directory / "audit_summary.json", audit_summary)
        audit_detail_path = write_strict_json(output_directory / "backtests" / "audits.json", audit_details)
        all_artifacts.extend([audit_path, audit_detail_path])
        figure_paths = _make_figures(equity_curves, diagnostics, output_directory / "figures")
        all_artifacts.extend(figure_paths)
        verification = _basic_verification(output_directory, root, config)
        # Verification is deliberately post-run evidence: a later deterministic
        # rerun updates this file, so it must not be frozen inside the experiment
        # artifact manifest with a hash that would immediately become stale.

        if not audit_summary["all_passed"]:
            raise AssertionError("one or more independent backtest audits failed")

        if recorder is not None:
            for artifact in all_artifacts:
                recorder.record_artifact(
                    artifact,
                    logical_name=artifact.relative_to(output_directory).as_posix(),
                )
            recorder.record_metrics(
                {
                    "strategies": strategy_rows,
                    "audit_summary": audit_summary,
                    "verification": verification,
                }
            )
            shutil.copy2(recorder.manifest_path, output_directory / "run_manifest.json")
            shutil.copy2(recorder.artifact_manifest_path, output_directory / "artifact_manifest.json")
        else:
            fallback_manifest = {
                "schema_version": 1,
                "run_id": "unrecorded-verification-run",
                "status": "completed",
                "experiment_fingerprint": None,
                "hashes": {},
                "research_start": data_cfg.get("start"),
                "research_end": data_cfg.get("end"),
            }
            write_strict_json(output_directory / "run_manifest.json", fallback_manifest)

        report_path: Path | None = None
        if generate_pdf:
            report_path = build_report_from_outputs(output_directory)
            all_artifacts.append(report_path)
            if recorder is not None:
                recorder.record_artifact(report_path, logical_name="pdf/final_report.pdf", role="report")

        if recorder is not None:
            recorder.finalize(
                status="completed",
                metadata={
                    "pipeline_version": PIPELINE_VERSION,
                    "research_start": data_cfg.get("start"),
                    "research_end": data_cfg.get("end"),
                },
            )
            shutil.copy2(recorder.manifest_path, output_directory / "run_manifest.json")
            shutil.copy2(recorder.artifact_manifest_path, output_directory / "artifact_manifest.json")

        verification = _basic_verification(output_directory, root, config)
        return {
            "output_directory": str(output_directory),
            "report": str(report_path) if report_path else None,
            "strategy_summary": strategy_rows,
            "audit_summary": audit_summary,
            "verification": verification,
            "run_id": recorder.run_id if recorder is not None else None,
        }
    except Exception as exc:
        if recorder is not None and not getattr(recorder, "_finalised", False):
            recorder.finalize(
                status="failed",
                metadata={"error_type": type(exc).__name__, "error": str(exc)},
            )
        raise


def verify_outputs(
    out_dir: str | Path = "outputs",
    config_path: str | Path | None = None,
    rerun: bool = False,
) -> dict[str, Any]:
    """Verify source hashes, account audits and optionally deterministic rerun."""

    config, resolved_config, root = load_config(config_path)
    output_directory = _resolve_from_root(out_dir, root).resolve()
    if not output_directory.is_dir():
        raise FileNotFoundError(output_directory)
    result = _basic_verification(output_directory, root, config)
    if rerun and result["passed"]:
        try:
            with tempfile.TemporaryDirectory(prefix="quantcf-verify-", dir=str(output_directory.parent)) as temp:
                repeat_directory = Path(temp) / "outputs"
                run_pipeline(resolved_config, repeat_directory, generate_pdf=False, record_run=False)
                left = pd.read_csv(output_directory / "strategy_summary.csv")
                right = pd.read_csv(repeat_directory / "strategy_summary.csv")
                left = left.sort_values("strategy").reset_index(drop=True)
                right = right.sort_values("strategy").reset_index(drop=True)
                pd.testing.assert_frame_equal(
                    left,
                    right,
                    check_dtype=False,
                    check_exact=False,
                    rtol=1e-11,
                    atol=1e-10,
                )
                left_curve = pd.read_csv(output_directory / "equity_curves.csv")
                right_curve = pd.read_csv(repeat_directory / "equity_curves.csv")
                pd.testing.assert_frame_equal(
                    left_curve,
                    right_curve,
                    check_dtype=False,
                    check_exact=False,
                    rtol=1e-11,
                    atol=1e-9,
                )
            result["deterministic_rerun_checked"] = True
            result["deterministic_rerun_match"] = True
        except Exception as exc:  # the failure is preserved as evidence, not hidden
            result["deterministic_rerun_checked"] = True
            result["deterministic_rerun_match"] = False
            result["deterministic_rerun_error"] = f"{type(exc).__name__}: {exc}"
            result["passed"] = False
    default_report = root / "output" / "pdf" / "CF2026_Project1_Final_Report.pdf"
    if default_report.is_file():
        result["report_sha256"] = sha256_file(default_report)
    write_strict_json(output_directory / "verification.json", result)
    return to_json_safe(result)


__all__ = [
    "PIPELINE_VERSION",
    "StrategySpec",
    "build_report_from_outputs",
    "load_config",
    "project_root",
    "run_pipeline",
    "verify_outputs",
]
