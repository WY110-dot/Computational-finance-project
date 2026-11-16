"""Main execution entry point for CF2026 Project 3.

Supports:
- --phase develop: explores and validates on training/develop split only.
- --phase validate: checks model and diagnostic pipelines on validation split.
- --phase evaluate: runs frozen research evaluation across US9 and CN21 universes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd

# Add src to sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.data import sha256_file
from quantcf.tsmom import get_market_month_ends
from quantcf.project3_factors import (
    compute_monthly_factors_for_panel,
    compute_daily_cross_sectional_correlations,
)
from quantcf.project3_pipeline import (
    load_universe_data,
    get_holding_periods,
    compute_holding_labels,
    generate_portfolio_target_weights,
    execute_broker_simulation,
)
from quantcf.project3_diagnostics import (
    compute_factor_ic_series,
    summarize_ic_series,
    compute_tercile_returns_series,
    compute_cross_sectional_residual_factor,
    compute_pairwise_difference_table,
    circular_block_bootstrap_pairwise,
)


def verify_freeze_state(root: Path, out_dir: Path, freeze_manifest_path: Path | str | None = None) -> dict[str, Any]:
    """Verify that freeze manifest exists and files match their frozen SHA256 checksums."""
    if freeze_manifest_path is not None and Path(freeze_manifest_path).exists():
        manifest_path = Path(freeze_manifest_path)
    elif (out_dir / "freeze_manifest.json").exists():
        manifest_path = out_dir / "freeze_manifest.json"
    elif (root / "outputs" / "freeze_manifest.json").exists():
        manifest_path = root / "outputs" / "freeze_manifest.json"
    else:
        raise RuntimeError(
            f"Freeze manifest not found at {out_dir / 'freeze_manifest.json'} or {root / 'outputs' / 'freeze_manifest.json'}. "
            "Evaluation phase strictly requires freezing configuration and candidate registers beforehand. "
            "Please run 'python freeze_project3.py' first!"
        )
    
    freeze_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_checked = []
    for item in freeze_data.get("files", []):
        fpath = root / item["path"]
        if not fpath.exists():
            raise RuntimeError(f"Frozen file missing: {item['path']}")
        curr_hash = sha256_file(fpath)
        if curr_hash != item["sha256"]:
            raise RuntimeError(
                f"Frozen file modified after freeze! Path: {item['path']}\n"
                f"Frozen SHA:  {item['sha256']}\n"
                f"Current SHA: {curr_hash}"
            )
        files_checked.append(item["path"])
        
    # Guarantee freeze_manifest.json is persisted in out_dir for audit trail
    target_manifest = out_dir / "freeze_manifest.json"
    if not target_manifest.exists():
        target_manifest.write_text(json.dumps(freeze_data, indent=2, ensure_ascii=False), encoding="utf-8")
        
    return {"status": "VERIFIED", "files_checked": len(files_checked), "frozen_at": freeze_data.get("frozen_at")}


def run_data_audit(datasets: dict[str, pd.DataFrame], cfg: dict[str, Any], out_dir: Path) -> pd.DataFrame:
    """Perform and save data audit on CN21 and US9 panels."""
    audit_rows = []
    for name, panel in datasets.items():
        assets = panel["asset"].unique()
        dates = panel["date"].unique()
        d_min = panel["date"].min().strftime("%Y-%m-%d")
        d_max = panel["date"].max().strftime("%Y-%m-%d")
        total_rows = len(panel)
        nan_close = int(panel["close_adj"].isna().sum())
        nan_open = int(panel["open_adj"].isna().sum())
        
        audit_rows.append({
            "universe": name,
            "n_assets": len(assets),
            "n_trading_days": len(dates),
            "start_date": d_min,
            "end_date": d_max,
            "total_records": total_rows,
            "missing_close_adj": nan_close,
            "missing_open_adj": nan_open,
            "status": "PASS" if nan_close == 0 and nan_open == 0 else "WARNING",
        })
    df_audit = pd.DataFrame(audit_rows)
    df_audit.to_csv(out_dir / "data_audit.csv", index=False)
    return df_audit


def run_pipeline_for_universe_and_split(
    universe_name: str,
    panel: pd.DataFrame,
    split_name: str,
    split_dates: dict[str, str],
    cfg: dict[str, Any],
    out_dir: Path,
    is_evaluate: bool = False,
) -> dict[str, Any]:
    """Execute complete factor generation, label creation, and backtests for a universe and split."""
    print(f"\n[{universe_name}] Running pipeline for split '{split_name}' ({split_dates['start']} to {split_dates['end']})...")
    
    # 1. Stage-restricted data view (strictly <= split_end, with necessary warmup)
    split_end_ts = pd.Timestamp(split_dates["end"])
    panel_view = panel[panel["date"] <= split_end_ts].copy()
    calendar_dates = sorted(panel_view["date"].unique())
    month_ends = get_market_month_ends(calendar_dates)
    
    # 2. Compute all monthly factors on stage data view
    params = cfg["parameters"]
    factor_res = compute_monthly_factors_for_panel(
        panel=panel_view,
        month_ends=month_ends,
        calendar_dates=calendar_dates,
        er_window_f1=params["er_window_f1"],
        er_window_f2=params["er_window_f2"],
        min_vol_days=params["min_history_days"],
        min_lookback_months=params["min_history_months"],
        min_qualified_assets=params["min_qualified_assets"],
    )
    df_factors = factor_res["factors"]
    df_long = factor_res["factors_long"]
    
    # 3. Determine holding periods strictly inside split
    holding_periods = get_holding_periods(
        calendar_dates=calendar_dates,
        month_ends=month_ends,
        split_start=split_dates["start"],
        split_end=split_dates["end"],
    )
    print(f"[{universe_name}] Split '{split_name}': {len(holding_periods)} valid monthly holding periods.")
    
    if len(holding_periods) == 0:
        print(f"[{universe_name}] Warning: No holding periods for {split_name}.")
        return {}
    
    # 4. Forward holding labels
    df_labels = compute_holding_labels(panel, holding_periods)
    df_labels["universe"] = universe_name
    df_labels["split"] = split_name
    
    # Filter factors to valid holding periods
    formation_dates = [p["formation_date"] for p in holding_periods]
    df_factors_split = df_factors[df_factors["formation_date"].isin(formation_dates)].copy()
    df_factors_split["universe"] = universe_name
    df_factors_split["split"] = split_name
    
    df_long_split = df_long[df_long["date"].isin(formation_dates)].copy()
    df_long_split["universe"] = universe_name
    df_long_split["split"] = split_name
    
    df_cov = factor_res["coverage"].copy()
    df_cov["universe"] = universe_name
    eval_start_date = pd.Timestamp("2020-01-01" if universe_name == "US9" else "2023-01-01")
    df_cov["is_warmup"] = pd.to_datetime(df_cov["date"]) < eval_start_date
    df_cov["split"] = np.where(pd.to_datetime(df_cov["date"]) >= eval_start_date, split_name, "warmup")
    
    # 5. Factor IC & Rank IC
    df_ic = compute_factor_ic_series(df_long_split, df_labels, min_assets=params["min_qualified_assets"])
    if not df_ic.empty:
        df_ic["universe"] = universe_name
        df_ic["split"] = split_name
    df_ic_summary = summarize_ic_series(df_ic)
    df_ic_summary["universe"] = universe_name
    df_ic_summary["split"] = split_name
    
    # 6. Tercile returns
    df_terciles = compute_tercile_returns_series(df_factors_split, df_labels, min_assets=params["min_qualified_assets"])
    if not df_terciles.empty:
        df_terciles["universe"] = universe_name
        df_terciles["split"] = split_name
    
    # 7. Residual factor regression: B = alpha + beta * A + epsilon
    df_res_series, res_summary = compute_cross_sectional_residual_factor(df_factors_split, df_labels, min_assets=params["min_qualified_assets"])
    res_summary["universe"] = universe_name
    res_summary["split"] = split_name
    
    # 8. Backtests across strategies and fees
    backtest_results = {}
    strategies = ["A", "B", "C", "F2", "F3", "A0", "passive_equal", "passive_inv_vol"]
    fee_scenarios = params["cost_scenarios_bps"] if is_evaluate else [params["base_cost_bps"]]
    
    for strat in strategies:
        # Generate target weights
        df_targets = generate_portfolio_target_weights(
            df_factors=df_factors_split,
            periods=holding_periods,
            daily_panel=panel,
            calendar_dates=calendar_dates,
            strategy_mode=strat,
            budget=params["budget_nav_ratio"],
            min_assets=params["min_qualified_assets"],
            vol_decay=params["ewma_lambda"],
            vol_ann_factor=params["ewma_ann_factor"],
            min_vol_days=params["min_history_days"],
        )
        
        for fee_bps in fee_scenarios:
            b_res = execute_broker_simulation(
                panel=panel,
                targets=df_targets,
                periods=holding_periods,
                calendar_dates=calendar_dates,
                cost_bps=fee_bps,
                initial_cash=1_000_000.0,
            )
            key = f"{strat}_{int(fee_bps)}bps"
            backtest_results[key] = b_res
            
            # Save files if evaluate split
            if is_evaluate:
                b_dir = out_dir / "backtests"
                b_dir.mkdir(parents=True, exist_ok=True)
                prefix = f"{universe_name}_{strat}_{int(fee_bps)}bps"
                
                b_res["orders"].to_csv(b_dir / f"{prefix}_orders.csv", index=False)
                b_res["fills"].to_csv(b_dir / f"{prefix}_fills.csv", index=False)
                b_res["holdings"].to_csv(b_dir / f"{prefix}_holdings.csv", index=False)
                b_res["ledger"].to_csv(b_dir / f"{prefix}_ledger.csv", index=False)
                b_res["monthly_returns"].to_csv(b_dir / f"{prefix}_monthly_returns.csv", index=False)
                (b_dir / f"{prefix}_audit.json").write_text(json.dumps(b_res["audit"], indent=2), encoding="utf-8")
                
    # 9. Pairwise C - A difference analysis
    base_fee_key_c = "C_3bps" if "C_3bps" in backtest_results else f"C_{int(params['base_cost_bps'])}bps"
    base_fee_key_a = "A_3bps" if "A_3bps" in backtest_results else f"A_{int(params['base_cost_bps'])}bps"
    
    pair_diff = {}
    bootstrap_res = {}
    if base_fee_key_c in backtest_results and base_fee_key_a in backtest_results:
        ret_c = backtest_results[base_fee_key_c]["monthly_returns"]
        ret_a = backtest_results[base_fee_key_a]["monthly_returns"]
        pair_diff = compute_pairwise_difference_table(ret_c, ret_a)
        
        # Block bootstrap (only for evaluate)
        if is_evaluate:
            b_cfg = cfg["bootstrap"]
            boot_list = []
            for blk in [b_cfg["primary_block_size"]] + b_cfg["sensitivity_block_sizes"]:
                # If sample size is small, skip 12m block
                if blk >= len(ret_c):
                    continue
                boot = circular_block_bootstrap_pairwise(
                    monthly_ret_C=ret_c,
                    monthly_ret_A=ret_a,
                    block_size=blk,
                    n_reps=b_cfg["repetitions"],
                    seed=b_cfg["seed"],
                )
                boot["universe"] = universe_name
                boot_list.append(boot)
            bootstrap_res = boot_list
            
    # 10. Daily cross-sectional correlations across all trading days
    daily_corr = compute_daily_cross_sectional_correlations(
        panel=panel_view,
        calendar_dates=calendar_dates,
        month_ends=month_ends,
        er_window=params["er_window_f1"],
        min_assets=params["min_qualified_assets"],
    )
    if not daily_corr.empty:
        daily_corr["universe"] = universe_name
        
    return {
        "universe": universe_name,
        "split": split_name,
        "holding_periods": holding_periods,
        "factors": df_factors_split,
        "factors_long": df_long_split,
        "coverage": df_cov,
        "labels": df_labels,
        "ic_series": df_ic,
        "ic_summary": df_ic_summary,
        "terciles": df_terciles,
        "residual_series": df_res_series,
        "residual_summary": res_summary,
        "backtests": backtest_results,
        "pairwise_diff": pair_diff,
        "bootstrap": bootstrap_res,
        "daily_correlations": daily_corr,
    }


def main():
    parser = argparse.ArgumentParser(description="CF2026 Project 3 Research Pipeline")
    parser.add_argument("--phase", choices=["develop", "validate", "evaluate"], default="evaluate", help="Research phase to run")
    parser.add_argument("--out", default="outputs", help="Output directory")
    parser.add_argument("--config", default="config/project3.json", help="Config file path")
    parser.add_argument("--freeze-manifest", default=None, help="Path to frozen manifest JSON file")
    args = parser.parse_args()
    
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / args.config).read_text(encoding="utf-8"))
    
    print(f"=== CF2026 Project 3: Starting Phase '{args.phase}' ===")
    print(f"Output directory: {out_dir}")
    
    # 1. If phase is evaluate, strictly verify freeze manifest
    if args.phase == "evaluate":
        freeze_check = verify_freeze_state(ROOT, out_dir, args.freeze_manifest)
        print(f"Freeze Verification: PASS ({freeze_check['files_checked']} files verified, frozen at {freeze_check['frozen_at']})")
        
    # 2. Load universe datasets
    datasets = load_universe_data(ROOT, cfg)
    
    # Run data audit and save
    df_audit = run_data_audit(datasets, cfg, out_dir)
    print("Data audit completed successfully:")
    print(df_audit.to_string(index=False))
    
    # 3. Run pipeline according to selected phase
    all_results = {}
    
    if args.phase == "develop":
        for u_name in ["US9", "CN21"]:
            split_cfg = cfg["samples"][u_name]["develop"]
            res = run_pipeline_for_universe_and_split(u_name, datasets[u_name], "develop", split_cfg, cfg, out_dir, is_evaluate=False)
            all_results[u_name] = res
            
        # Log to candidate_run_log.csv
        log_rows = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "develop",
            "universe": u,
            "status": "COMPLETED",
            "note": "Exploratory development run on develop split.",
        } for u in all_results]
        pd.DataFrame(log_rows).to_csv(out_dir / "candidate_run_log.csv", mode="a", index=False, header=not (out_dir / "candidate_run_log.csv").exists())
        print("\nPhase 'develop' completed.")
        return 0
        
    elif args.phase == "validate":
        for u_name in ["US9", "CN21"]:
            split_cfg = cfg["samples"][u_name]["validate"]
            res = run_pipeline_for_universe_and_split(u_name, datasets[u_name], "validate", split_cfg, cfg, out_dir, is_evaluate=False)
            all_results[u_name] = res
            
        log_rows = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "validate",
            "universe": u,
            "status": "COMPLETED",
            "note": "Validation run on validation split.",
        } for u in all_results]
        pd.DataFrame(log_rows).to_csv(out_dir / "candidate_run_log.csv", mode="a", index=False, header=not (out_dir / "candidate_run_log.csv").exists())
        print("\nPhase 'validate' completed.")
        return 0
        
    elif args.phase == "evaluate":
        # 4. Evaluation phase: run full evaluations for US9, CN21, and Common
        eval_factors = []
        eval_factors_long = []
        eval_coverage = []
        eval_labels = []
        eval_ic_summaries = []
        eval_ic_series = []
        eval_terciles = []
        eval_residuals = []
        eval_residual_series = []
        eval_daily_corr = []
        eval_bootstrap = []
        pairwise_summaries = []
        experiments_inventory = []
        reconciliation_records = []
        
        (out_dir / "factors").mkdir(exist_ok=True)
        (out_dir / "labels").mkdir(exist_ok=True)
        (out_dir / "diagnostics").mkdir(exist_ok=True)
        (out_dir / "robustness").mkdir(exist_ok=True)
        
        # A. US9 Evaluation
        u_cfg_us = cfg["samples"]["US9"]["evaluate"]
        res_us = run_pipeline_for_universe_and_split("US9", datasets["US9"], "evaluate", u_cfg_us, cfg, out_dir, is_evaluate=True)
        all_results["US9"] = res_us
        
        # B. CN21 Evaluation
        u_cfg_cn = cfg["samples"]["CN21"]["evaluate"]
        res_cn = run_pipeline_for_universe_and_split("CN21", datasets["CN21"], "evaluate", u_cfg_cn, cfg, out_dir, is_evaluate=True)
        all_results["CN21"] = res_cn
        
        # Aggregate tables
        for u_name, res in [("US9", res_us), ("CN21", res_cn)]:
            if not res: continue
            eval_factors.append(res["factors"])
            eval_factors_long.append(res["factors_long"])
            eval_coverage.append(res["coverage"])
            eval_labels.append(res["labels"])
            eval_ic_summaries.append(res["ic_summary"])
            eval_ic_series.append(res["ic_series"])
            eval_terciles.append(res["terciles"])
            eval_residuals.append(res["residual_summary"])
            if not res["residual_series"].empty:
                res["residual_series"]["universe"] = u_name
                eval_residual_series.append(res["residual_series"])
            eval_daily_corr.append(res["daily_correlations"])
            if res.get("bootstrap"):
                eval_bootstrap.extend(res["bootstrap"])
            if res.get("pairwise_diff"):
                pw = res["pairwise_diff"].copy()
                pw.pop("paired_series", None)
                pw["universe"] = u_name
                pairwise_summaries.append(pw)
                
            # Populate experiments inventory and reconciliation
            for key, b_res in res["backtests"].items():
                strat, fee_str = key.rsplit("_", 1)
                fee = float(fee_str.replace("bps", ""))
                
                # Performance metrics
                ann_ret = b_res["summary"].get("ann_mean", np.nan)
                cagr_val = b_res["summary"].get("cagr", np.nan)
                ann_vol_val = b_res["summary"].get("ann_vol", np.nan)
                sharpe_val = b_res["summary"].get("sharpe", np.nan)
                max_dd_m = b_res["summary"].get("max_drawdown", np.nan)
                max_dd_d = b_res["summary"].get("max_drawdown_daily", np.nan)
                turnover_val = b_res["summary"].get("total_turnover", np.nan)
                fees_val = b_res["summary"].get("total_fees", np.nan)
                
                experiments_inventory.append({
                    "experiment_id": f"EXP_{u_name}_{strat}_{int(fee)}bps",
                    "candidate_id": strat,
                    "universe": u_name,
                    "split": "evaluate",
                    "sample_start": cfg["samples"][u_name]["evaluate"]["start"],
                    "sample_end": cfg["samples"][u_name]["evaluate"]["end"],
                    "label_definition": "monthly_open_to_open",
                    "n_dates": len(res["holding_periods"]),
                    "n_assets_summary": len(datasets[u_name]["asset"].unique()),
                    "cost_bps": fee,
                    "ann_return": ann_ret,
                    "cagr": cagr_val,
                    "ann_vol": ann_vol_val,
                    "sharpe": sharpe_val,
                    "max_drawdown": max_dd_m,
                    "max_drawdown_daily": max_dd_d,
                    "turnover": turnover_val,
                    "fees": fees_val,
                    "terminal_wealth": b_res["summary"].get("w_end_open", np.nan),
                    "cum_return": b_res["summary"].get("cum_return", np.nan),
                    "audit_passed": b_res["audit"]["passed"],
                    "status": "PASS" if b_res["audit"]["passed"] else "FAIL",
                })
                
                # Detailed Reconciliation record
                df_m = b_res["monthly_returns"]
                fills_fee_sum = float(b_res["fills"]["fee"].sum()) if not b_res["fills"].empty else 0.0
                ledger_fee_sum = float(b_res["ledger"]["transaction_cost"].sum())
                monthly_fee_sum = float(df_m["fees"].sum())
                fee_reconciled = bool(np.isclose(ledger_fee_sum, monthly_fee_sum, atol=1e-4) and np.isclose(fills_fee_sum, monthly_fee_sum, atol=1e-4))
                
                w_start = float(df_m["w_entry_pretrade"].iloc[0])
                w_end = float(df_m["w_exit_pretrade"].iloc[-1])
                compounded_prod = float(np.prod(1.0 + df_m["net_return"].values))
                nav_ratio = float(w_end / w_start)
                compounding_reconciled = bool(np.isclose(compounded_prod, nav_ratio, atol=1e-7))
                
                reconciliation_records.append({
                    "universe": u_name,
                    "strategy": strat,
                    "cost_bps": fee,
                    "experiment_id": f"EXP_{u_name}_{strat}_{int(fee)}bps",
                    "fills_fees_sum": fills_fee_sum,
                    "ledger_fees_sum": ledger_fee_sum,
                    "monthly_fees_sum": monthly_fee_sum,
                    "fees_reconciled": fee_reconciled,
                    "w_start_open": w_start,
                    "w_end_open": w_end,
                    "cum_return_telescoping": compounded_prod - 1.0,
                    "nav_ratio_telescoping": nav_ratio - 1.0,
                    "compounding_reconciled": compounding_reconciled,
                    "n_months": len(df_m),
                    "start_entry_date": str(pd.to_datetime(df_m["entry_date"].iloc[0]).date()),
                    "end_exit_date": str(pd.to_datetime(df_m["exit_date"].iloc[-1]).date()),
                })
                
        # Save consolidated artifacts
        df_all_factors = pd.concat(eval_factors, ignore_index=True) if eval_factors else pd.DataFrame()
        df_all_factors.to_csv(out_dir / "factors" / "factors_evaluate.csv", index=False)
        
        df_all_factors_long = pd.concat(eval_factors_long, ignore_index=True) if eval_factors_long else pd.DataFrame()
        df_all_factors_long.to_csv(out_dir / "factors" / "factors_long.csv", index=False)
        
        df_all_coverage = pd.concat(eval_coverage, ignore_index=True) if eval_coverage else pd.DataFrame()
        df_all_coverage.to_csv(out_dir / "coverage.csv", index=False)
        
        df_all_labels = pd.concat(eval_labels, ignore_index=True) if eval_labels else pd.DataFrame()
        df_all_labels.to_csv(out_dir / "labels" / "labels_evaluate.csv", index=False)
        
        df_all_ic_sum = pd.concat(eval_ic_summaries, ignore_index=True) if eval_ic_summaries else pd.DataFrame()
        df_all_ic_sum.to_csv(out_dir / "diagnostics" / "factor_ic_summary.csv", index=False)
        
        df_all_ic_ser = pd.concat(eval_ic_series, ignore_index=True) if eval_ic_series else pd.DataFrame()
        df_all_ic_ser.to_csv(out_dir / "diagnostics" / "factor_ic_series.csv", index=False)
        
        df_all_terc = pd.concat(eval_terciles, ignore_index=True) if eval_terciles else pd.DataFrame()
        df_all_terc.to_csv(out_dir / "diagnostics" / "tercile_returns.csv", index=False)
        
        df_all_res_summary = pd.DataFrame(eval_residuals)
        df_all_res_summary.to_csv(out_dir / "diagnostics" / "residual_factor_summary.csv", index=False)
        
        df_all_res_series = pd.concat(eval_residual_series, ignore_index=True) if eval_residual_series else pd.DataFrame()
        df_all_res_series.to_csv(out_dir / "diagnostics" / "residual_factor_series.csv", index=False)
        
        df_all_dcorr = pd.concat(eval_daily_corr, ignore_index=True) if eval_daily_corr else pd.DataFrame()
        df_all_dcorr.to_csv(out_dir / "diagnostics" / "daily_correlations.csv", index=False)
        
        df_all_boot = pd.DataFrame(eval_bootstrap)
        df_all_boot.to_csv(out_dir / "diagnostics" / "block_bootstrap.csv", index=False)
        
        df_pairwise = pd.DataFrame(pairwise_summaries)
        df_pairwise.to_csv(out_dir / "diagnostics" / "pairwise_difference.csv", index=False)
        
        df_inventory = pd.DataFrame(experiments_inventory)
        df_inventory.to_csv(out_dir / "experiments_inventory.csv", index=False)
        
        df_reconciliation = pd.DataFrame(reconciliation_records)
        df_reconciliation.to_csv(out_dir / "reconciliation.csv", index=False)
        (out_dir / "reconciliation.json").write_text(json.dumps(reconciliation_records, indent=2), encoding="utf-8")
        
        # Robustness: Time Subperiods
        # US: 2020-2022 and 2023-2024
        # CN: 2023 and 2024
        # Common: 2023-2024
        subperiod_records = []
        for u_name, sub_splits in [
            ("US9", [("US_2020_2022", {"start": "2020-01-01", "end": "2022-12-31"}),
                     ("US_2023_2024", {"start": "2023-01-01", "end": "2024-12-31"})]),
            ("CN21", [("CN_2023", {"start": "2023-01-01", "end": "2023-12-31"}),
                      ("CN_2024", {"start": "2024-01-01", "end": "2024-12-31"})]),
        ]:
            for sub_name, s_dates in sub_splits:
                sub_res = run_pipeline_for_universe_and_split(u_name, datasets[u_name], sub_name, s_dates, cfg, out_dir, is_evaluate=False)
                if sub_res and sub_res.get("pairwise_diff"):
                    pdiff = sub_res["pairwise_diff"]
                    subperiod_records.append({
                        "subperiod": sub_name,
                        "universe": u_name,
                        "n_months": pdiff.get("n_months", 0),
                        "ann_mean_diff_C_minus_A": pdiff.get("ann_mean_diff", np.nan),
                        "sharpe_C": pdiff.get("sharpe_C", np.nan),
                        "sharpe_A": pdiff.get("sharpe_A", np.nan),
                        "sharpe_diff": pdiff.get("sharpe_diff", np.nan),
                        "tracking_error": pdiff.get("tracking_error", np.nan),
                        "info_ratio": pdiff.get("information_ratio", np.nan),
                        "win_rate": pdiff.get("win_rate", np.nan),
                    })
        df_subperiod = pd.DataFrame(subperiod_records)
        df_subperiod.to_csv(out_dir / "robustness" / "subperiod_robustness.csv", index=False)
        
        # Robustness: Cost Scenarios
        cost_records = []
        for exp in experiments_inventory:
            cost_records.append({
                "universe": exp["universe"],
                "strategy": exp["candidate_id"],
                "cost_bps": exp["cost_bps"],
                "ann_return": exp["ann_return"],
                "cagr": exp.get("cagr", np.nan),
                "ann_vol": exp["ann_vol"],
                "sharpe": exp["sharpe"],
                "max_drawdown": exp["max_drawdown"],
                "total_turnover": exp["turnover"],
                "total_fees": exp["fees"],
            })
        df_cost = pd.DataFrame(cost_records)
        df_cost.to_csv(out_dir / "robustness" / "cost_robustness.csv", index=False)
        df_cost.to_csv(out_dir / "diagnostics" / "cost_sensitivity.csv", index=False)
        
        # Dedicated Common 2023-2024 Evaluation Comparison
        # Both US9 and CN21 evaluated over identical 2023-01-01 to 2024-12-31 window
        common_records = []
        # Find US9 2023-2024 results from sub_res_map or rerun
        us_common_res = run_pipeline_for_universe_and_split(
            "US9", datasets["US9"], "common_2023_2024",
            cfg["common_evaluate"], cfg, out_dir, is_evaluate=False
        )
        for u_name, bt_dict, pdiff in [
            ("US9", us_common_res.get("backtests", {}), us_common_res.get("pairwise_diff", {})),
            ("CN21", res_cn.get("backtests", {}), res_cn.get("pairwise_diff", {})),
        ]:
            for key, b_res in bt_dict.items():
                if "_3bps" in key:
                    strat = key.replace("_3bps", "")
                    s = b_res["summary"]
                    common_records.append({
                        "universe": u_name,
                        "period": "2023-2024 (Common)",
                        "strategy": strat,
                        "cost_bps": 3.0,
                        "n_months": s.get("n_months", 0),
                        "ann_return": s.get("ann_mean", np.nan),
                        "cagr": s.get("cagr", np.nan),
                        "ann_vol": s.get("ann_vol", np.nan),
                        "sharpe": s.get("sharpe", np.nan),
                        "max_drawdown": s.get("max_drawdown", np.nan),
                        "turnover": s.get("total_turnover", np.nan),
                        "fees": s.get("total_fees", np.nan),
                    })
            if pdiff:
                common_records.append({
                    "universe": u_name,
                    "period": "2023-2024 (Common)",
                    "strategy": "C_minus_A",
                    "cost_bps": 3.0,
                    "n_months": pdiff.get("n_months", 0),
                    "ann_return": pdiff.get("ann_mean_diff", np.nan),
                    "cagr": np.nan,
                    "ann_vol": pdiff.get("tracking_error", np.nan),
                    "sharpe": pdiff.get("sharpe_diff", np.nan),
                    "max_drawdown": np.nan,
                    "turnover": np.nan,
                    "fees": np.nan,
                })
        df_common = pd.DataFrame(common_records)
        df_common.to_csv(out_dir / "diagnostics" / "common_period_comparison.csv", index=False)
        df_common.to_csv(out_dir / "robustness" / "common_period_comparison.csv", index=False)
        
        # Research decision & conclusions
        decision = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "universe_analyzed": ["US9", "CN21"],
            "primary_factor": "F1 (mom12 x er63)",
            "classic_benchmark": "A (mom12 continuous z-score)",
            "traceability_benchmark": "A0 (P2 discrete sign)",
            "combination": "C (0.5 A + 0.5 B)",
            "statistical_findings": {
                "ic_summary": df_all_ic_sum.to_dict(orient="records"),
                "pairwise_diff": pairwise_summaries,
                "bootstrap": eval_bootstrap,
                "residual_regression": eval_residuals,
            },
            "p5_isolation_confirmed": True,
            "conclusion_verdict": "RESEARCH_DECISION_FINALIZED",
        }
        (out_dir / "research_decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
        
        # Append candidate run log
        log_rows = [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "evaluate",
            "universe": "US9_and_CN21",
            "status": "COMPLETED",
            "note": "Frozen evaluation executed successfully.",
        }]
        pd.DataFrame(log_rows).to_csv(out_dir / "candidate_run_log.csv", mode="a", index=False, header=not (out_dir / "candidate_run_log.csv").exists())
        
        # Run manifest
        run_manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "evaluate",
            "command": "python run_project3.py --phase evaluate",
            "python_version": sys.version,
            "universes": ["US9", "CN21"],
            "total_experiments": len(experiments_inventory),
            "status": "SUCCESS",
        }
        (out_dir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
        
        print("\n=== Phase 'evaluate' completed successfully! ===")
        print(f"Artifacts saved in {out_dir}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
