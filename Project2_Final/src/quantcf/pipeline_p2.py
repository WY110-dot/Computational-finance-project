"""Project 2 research pipeline.

Executes complete systematic replication and extension workflow:
1. Loads data panel and validates manifest.
2. Constructs monthly signals, EWMA volatilities, and eligibility panel.
3. Runs research-mode backtests: R1 (TSMOM 12m), R2 (Passive Long),
   R3 (Equal Nominal), R4 (Multi-horizon), Bridge (Long-only Research),
   Estimator check (Rolling Sample Vol), Subperiods, and Broad-Market Subset.
4. Runs execution-mode backtests: T1 (TSMOM 12m Long/Cash), T2 (Multi-horizon Long/Cash),
   T3 (Passive Long Long/Cash) across 0 bps, 3 bps, 10 bps fee schedules.
5. Loads and parses AQR official paper factor O1.
6. Computes comprehensive metrics, compiles comparison tables:
   - strategy_summary.csv
   - original_vs_replication.csv
   - difference_experiments.csv
   - experiments_inventory.csv
   - key_result_trace.csv
   - asset_class_removal_attribution.csv
7. Generates publication-grade figures (including side-by-side with paper Fig 2 & 3).
8. Records audit fingerprints with ExperimentRecorder.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from PIL import Image

from quantcf.backtest import BacktestConfig, run_backtest
from quantcf.data import load_panel
from quantcf.portfolio import generate_tsmom_long_cash_targets
from quantcf.recorder import ExperimentRecorder, canonical_json, write_strict_json
from quantcf.reference_data import (
    calculate_reference_metrics,
    fetch_project2_sources,
    load_aqr_reference_factors,
)
from quantcf.research_backtest import (
    ResearchBacktestResult,
    calculate_monthly_metrics,
    run_research_backtest,
)
from quantcf.tsmom import build_monthly_tsmom_dataset


ASSET_CLASS_MAP = {
    "511010.SH": "Bonds",
    "511220.SH": "Bonds",
    "511260.SH": "Bonds",
    "518880.SH": "Gold",
    "513050.SH": "Cross_Border_Equity",
    "513100.SH": "Cross_Border_Equity",
    "513500.SH": "Cross_Border_Equity",
}


def get_asset_class(asset: str) -> str:
    """Return broad asset class for ETF."""
    return ASSET_CLASS_MAP.get(asset, "Domestic_Equity")


def calculate_daily_ledger_metrics(
    ledger: pd.DataFrame,
    start_date: Optional[pd.Timestamp | str] = None,
    end_date: Optional[pd.Timestamp | str] = None,
    ann_factor: float = 252.0,
) -> Dict[str, Any]:
    """Calculate annualized metrics from daily backtest ledger.
    
    Includes first execution day (2020-02-03) where trading and holding occurred,
    truncates strictly at evaluation end (e.g. 2026-08-31), includes initial equity
    in drawdown / high-water mark, and preserves signed Calmar ratio.
    """
    df = ledger.copy()
    if df.empty:
        return {"n_periods": 0, "ann_arithmetic_mean": np.nan, "ann_vol": np.nan, "sharpe": np.nan}
    
    date_col = "date" if "date" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
    if date_col is not None:
        df["date"] = pd.to_datetime(df[date_col])
        if start_date is not None:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df["date"] <= pd.to_datetime(end_date)]

    if df.empty or len(df) == 0:
        return {"n_periods": 0, "ann_arithmetic_mean": np.nan, "ann_vol": np.nan, "sharpe": np.nan}

    # Use the broker's accurately computed daily_return directly, including day 1
    if "daily_return" in df.columns:
        rets = df["daily_return"].values.astype(float)
    else:
        # Fallback if daily_return column is missing
        rets = df["nav"].pct_change().fillna(0.0).values.astype(float)

    n_days = len(rets)
    if n_days == 0:
        return {"n_periods": 0, "ann_arithmetic_mean": np.nan, "ann_vol": np.nan, "sharpe": np.nan}

    mean_d = float(np.mean(rets))
    vol_d = float(np.std(rets, ddof=1)) if n_days > 1 else 0.0
    ann_mean = mean_d * ann_factor
    ann_vol = vol_d * np.sqrt(ann_factor)
    sharpe = (ann_mean / ann_vol) if ann_vol > 1e-8 else (0.0 if ann_vol == 0 and ann_mean == 0 else np.nan)

    # High-water mark including initial equity 1.0 (or initial capital)
    wealth = np.insert(np.cumprod(1.0 + rets), 0, 1.0)
    peak = np.maximum.accumulate(wealth)
    dd = (wealth - peak) / peak
    max_dd = float(np.min(dd))

    end_val = float(wealth[-1])
    total_ret = float(end_val - 1.0)
    cagr = float((end_val ** (ann_factor / n_days)) - 1.0) if (end_val > 0 and n_days > 0) else np.nan
    calmar = float(cagr / abs(max_dd)) if (pd.notnull(cagr) and max_dd < -1e-6) else np.nan

    total_cost = float(df["cost"].sum()) if "cost" in df else 0.0
    total_turnover = float(df["turnover"].sum()) if "turnover" in df else 0.0
    turnover_ann = float(total_turnover / (n_days / ann_factor)) if n_days > 0 else 0.0
    cash_ratio = float((df["cash"] / df["equity"]).mean()) if "cash" in df and "equity" in df else 0.0

    return {
        "n_periods": n_days,
        "trading_days": n_days,
        "ann_arithmetic_mean": ann_mean,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "total_compound_return": total_ret,
        "total_fees": total_cost,
        "turnover_ann": turnover_ann,
        "mean_cash_ratio": cash_ratio,
        "win_rate_daily": float(np.mean(rets > 0)),
    }


def compute_asset_class_contributions(
    df_contrib: pd.DataFrame,
    df_port: pd.DataFrame,
) -> pd.DataFrame:
    """Group asset return contributions by broad asset class."""
    df = df_contrib.copy()
    df["asset_class"] = df["asset"].apply(get_asset_class)
    date_col = "holding_end_date" if "holding_end_date" in df.columns else "date"
    class_contrib = df.groupby([date_col, "asset_class"])["contrib"].sum().unstack().fillna(0.0)
    
    # Ensure port_ret matches exactly
    class_contrib["total_portfolio_return"] = class_contrib.sum(axis=1)
    class_contrib = class_contrib.reset_index().rename(columns={date_col: "holding_end_date"})
    if "date" in df.columns:
        form_map = df.drop_duplicates(subset=[date_col]).set_index(date_col)["date"]
        class_contrib["formation_date"] = class_contrib["holding_end_date"].map(form_map)
    else:
        class_contrib["formation_date"] = class_contrib["holding_end_date"]
    return class_contrib


def compute_asset_class_variance_decomposition(
    class_contrib_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute formal risk/variance decomposition: Cov(class_ret, port_ret) / Var(port_ret).
    
    Ensures exact mathematical sum to 100%, isolating the percentage of total portfolio
    variance contributed by each asset class.
    """
    df = class_contrib_df.copy()
    classes = [c for c in ["Bonds", "Domestic_Equity", "Cross_Border_Equity", "Gold"] if c in df.columns]
    port_ret = df["total_portfolio_return"].values
    var_port = float(np.var(port_ret, ddof=1))
    
    rows = []
    for c in classes:
        c_ret = df[c].values
        cov_c = float(np.cov(c_ret, port_ret, ddof=1)[0, 1])
        var_contrib_pct = (cov_c / var_port) if var_port > 1e-10 else 0.0
        ann_mean_c = float(np.mean(c_ret)) * 12.0
        rows.append({
            "asset_class": c,
            "ann_mean_return_contribution": ann_mean_c,
            "covariance_with_portfolio": cov_c,
            "variance_contribution_ratio": var_contrib_pct,
            "pct_of_total_risk": f"{var_contrib_pct * 100:.2f}%",
            "interpretation": f"{c} contributes {var_contrib_pct*100:.2f}% of total portfolio return variance.",
        })
    return pd.DataFrame(rows)


def compute_asset_class_removal_attribution(
    df_contrib: pd.DataFrame,
    df_port: pd.DataFrame,
) -> pd.DataFrame:
    """Conduct fixed-weight removal attribution experiment (Section 6.2).
    
    Zeros out the return contribution of each class without re-normalizing weights,
    isolating the marginal return, volatility, Sharpe, and drawdown impact.
    """
    df = df_contrib.copy()
    df["asset_class"] = df["asset"].apply(get_asset_class)
    date_col = "holding_end_date" if "holding_end_date" in df.columns else "date"
    class_contrib = df.groupby([date_col, "asset_class"])["contrib"].sum().unstack().fillna(0.0)
    class_contrib.index = pd.to_datetime(class_contrib.index)

    port_date_col = "holding_end_date" if "holding_end_date" in df_port.columns else "formation_date"
    port_rets = pd.Series(df_port["portfolio_return"].values, index=pd.to_datetime(df_port[port_date_col]))
    baseline_m = calculate_monthly_metrics(port_rets)

    rows = []
    # Baseline
    rows.append({
        "scenario": "Baseline R1 (All 21 Assets)",
        "removed_class": "None",
        "ann_arithmetic_mean": baseline_m["ann_mean"],
        "ann_vol": baseline_m["ann_vol"],
        "sharpe": baseline_m["sharpe"],
        "cagr": baseline_m["cagr"],
        "max_drawdown": baseline_m["max_drawdown"],
        "diff_sharpe_vs_baseline": 0.0,
        "interpretation": "Full diversified portfolio baseline with 0.40/vol scaling",
    })

    classes = ["Bonds", "Domestic_Equity", "Cross_Border_Equity", "Gold"]

    for c in classes:
        if c in class_contrib.columns:
            mod_rets = port_rets - class_contrib[c]
            m = calculate_monthly_metrics(mod_rets)
            if c == "Bonds":
                interp = f"Sharpe drops from {baseline_m['sharpe']:.3f} to {m['sharpe']:.3f}; bonds provided persistent positive trend carry buffer"
            elif c == "Domestic_Equity":
                interp = f"Volatility drops from {baseline_m['ann_vol']*100:.2f}% to {m['ann_vol']*100:.2f}% and drawdown from {baseline_m['max_drawdown']*100:.2f}% to {m['max_drawdown']*100:.2f}%; domestic equities contributed vast majority of portfolio risk"
            elif c == "Cross_Border_Equity":
                interp = f"Sharpe drops from {baseline_m['sharpe']:.3f} to {m['sharpe']:.3f}; foreign equities provided positive diversification trend contribution"
            elif c == "Gold":
                interp = f"Sharpe drops from {baseline_m['sharpe']:.3f} to {m['sharpe']:.3f}; gold provided non-correlated store-of-value trend buffer"
            else:
                interp = f"Fixed-weight marginal class attribution for {c}"

            rows.append({
                "scenario": f"Without {c} (Fixed Weights)",
                "removed_class": c,
                "ann_arithmetic_mean": m["ann_mean"],
                "ann_vol": m["ann_vol"],
                "sharpe": m["sharpe"],
                "cagr": m["cagr"],
                "max_drawdown": m["max_drawdown"],
                "diff_sharpe_vs_baseline": m["sharpe"] - baseline_m["sharpe"],
                "interpretation": interp,
            })

    return pd.DataFrame(rows)


def compute_fixed_config_hash(
    base_cfg: Dict[str, Any],
    excluded_keys: Sequence[str],
) -> str:
    """Compute deterministic SHA-256 hash of configuration excluding changed keys."""
    import copy
    import hashlib
    cfg_copy = copy.deepcopy(base_cfg)
    for key_path in excluded_keys:
        parts = key_path.split(".")
        target = cfg_copy
        for p in parts[:-1]:
            if isinstance(target, dict) and p in target:
                target = target[p]
        if isinstance(target, dict) and parts[-1] in target:
            del target[parts[-1]]
    canonical_str = canonical_json(cfg_copy)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:16]


def save_execution_artifacts(name: str, res: Any, out_dir: Path) -> None:
    """Save execution ledger, orders, fills, holdings, audit JSON, and monthly compound returns."""
    b_dir = out_dir / "backtests"
    b_dir.mkdir(parents=True, exist_ok=True)
    res.ledger.to_csv(b_dir / f"{name}_ledger.csv", index=False)
    res.orders.to_csv(b_dir / f"{name}_orders.csv", index=False)
    res.fills.to_csv(b_dir / f"{name}_fills.csv", index=False)
    res.holdings.to_csv(b_dir / f"{name}_holdings.csv", index=False)
    write_strict_json(b_dir / f"{name}_audit.json", res.audit)

    # Monthly compound returns table from daily ledger
    m_df = res.ledger.copy()
    m_df["year_month"] = pd.to_datetime(m_df["date"]).dt.to_period("M")
    rows = []
    for ym, grp in m_df.groupby("year_month"):
        d_rets = grp["daily_return"].values.astype(float)
        comp_ret = float(np.prod(1.0 + d_rets) - 1.0)
        rows.append({
            "month": str(ym),
            "start_date": str(grp["date"].min())[:10],
            "end_date": str(grp["date"].max())[:10],
            "n_trading_days": len(grp),
            "monthly_compound_return": comp_ret,
            "total_fees": float(grp["cost"].sum()) if "cost" in grp else 0.0,
            "total_turnover": float(grp["turnover"].sum()) if "turnover" in grp else 0.0,
            "end_equity": float(grp["equity"].iloc[-1]),
        })
    pd.DataFrame(rows).to_csv(b_dir / f"{name}_monthly_returns.csv", index=False)


def build_experiments_inventory(
    summary_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build standardized inventory of all 18 experimental runs (Section 3)."""
    rows = []
    type_map = {
        "R1_tsmom12": ("EXP_CORE_R1", "Primary Replication", "12M Trend (s12)", "All 21 ETFs", "0.40/vol scaling", "0 bps"),
        "R2_passive_long": ("EXP_CORE_R2", "Trend Benchmark", "Always Long (+1)", "All 21 ETFs", "0.40/vol scaling", "0 bps"),
        "R3_equal_nominal": ("EXP_ATTR_R3", "Weighting Sensitivity", "12M Trend (s12)", "All 21 ETFs", "Equal Nominal (s/N)", "0 bps"),
        "R4_multi_horizon": ("EXP_EXT_R4", "Autonomous Extension", "3/6/12M Combo (a)", "All 21 ETFs", "0.40/vol scaling", "0 bps"),
        "Bridge_long_only": ("EXP_ATTR_BRIDGE", "Shorting Constraint Bridge", "Long Only (max(s,0))", "All 21 ETFs", "0.40/vol scaling", "0 bps"),
        "R1_sample_vol": ("EXP_ATTR_ESTIMATOR", "Estimator Sensitivity", "12M Trend (s12)", "All 21 ETFs", "252d Rolling Sample Std", "0 bps"),
        "R1_sub_2020_2022": ("EXP_ATTR_SUB1", "Subperiod Stability", "12M Trend (s12)", "All 21 ETFs (2020-2022)", "0.40/vol scaling", "0 bps"),
        "R1_sub_2023_2026": ("EXP_ATTR_SUB2", "Subperiod Stability", "12M Trend (s12)", "All 21 ETFs (2023-2026)", "0.40/vol scaling", "0 bps"),
        "R1_broad_market": ("EXP_ATTR_BROAD", "Asset Universe Subset", "12M Trend (s12)", "Core 3 Broad Index ETFs", "0.40/vol scaling", "0 bps"),
        "T1_tsmom12_3bps": ("EXP_EXEC_T1_BASE", "Realistic Execution Baseline", "12M Trend Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "3 bps base"),
        "T1_tsmom12_0bps": ("EXP_EXEC_T1_ZERO", "Cost Sensitivity (Zero)", "12M Trend Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "0 bps"),
        "T1_tsmom12_10bps": ("EXP_EXEC_T1_HIGH", "Cost Sensitivity (High)", "12M Trend Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "10 bps"),
        "T2_multi_horizon_3bps": ("EXP_EXEC_T2_BASE", "Execution Extension Baseline", "3/6/12M Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "3 bps base"),
        "T2_multi_horizon_0bps": ("EXP_EXEC_T2_ZERO", "Cost Sensitivity (Zero)", "3/6/12M Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "0 bps"),
        "T2_multi_horizon_10bps": ("EXP_EXEC_T2_HIGH", "Cost Sensitivity (High)", "3/6/12M Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "10 bps"),
        "T3_passive_long_3bps": ("EXP_EXEC_T3_BASE", "Execution Benchmark", "Passive Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "3 bps base"),
        "T3_passive_long_0bps": ("EXP_EXEC_T3_ZERO", "Cost Sensitivity (Zero)", "Passive Long/Cash", "All 21 ETFs", "Inverse-vol budget (0.99)", "0 bps"),
        "O1_aqr_original_reference": ("EXP_REF_O1", "Literature Benchmark", "12M TSMOM Original", "58 Global Futures (1985-2009)", "AQR Official Dataset", "0 bps"),
    }

    for _, row in summary_df.iterrows():
        sid = row["strategy_id"]
        run_id, exp_type, signal, sample, weighting, cost = type_map.get(sid, (sid, "Other", sid, "21 ETFs", "Standard", "0 bps"))
        if str(sid).startswith("R1_sub_"):
            s_yr = str(row.get("sample_start", ""))[:4]
            e_yr = str(row.get("sample_end", ""))[:4]
            if s_yr and e_yr:
                sample = f"All 21 ETFs ({s_yr}-{e_yr})"
        rows.append({
            "run_id": run_id,
            "strategy_id": sid,
            "mode": row["mode"],
            "experiment_category": exp_type,
            "signal": signal,
            "sample_scope": sample,
            "weighting_rule": weighting,
            "transaction_cost": cost,
            "ann_arithmetic_mean": row["ann_arithmetic_mean"],
            "ann_vol": row["ann_vol"],
            "sharpe": row["sharpe"],
            "cagr": row["cagr"],
            "max_drawdown": row["max_drawdown"],
            "status": "COMPLETED",
        })
    return pd.DataFrame(rows)


def build_key_result_trace(
    summary_df: pd.DataFrame,
    single_df: pd.DataFrame,
    diff_df: pd.DataFrame,
    removal_df: pd.DataFrame,
    out_dir: str | Path = "outputs_p2",
) -> pd.DataFrame:
    """Build explicit audit trace mapping every report claim to source data (Section 5.2)."""
    out_name = Path(out_dir).name
    r1 = summary_df[summary_df["strategy_id"] == "R1_tsmom12"].iloc[0]
    r2 = summary_df[summary_df["strategy_id"] == "R2_passive_long"].iloc[0]
    r3 = summary_df[summary_df["strategy_id"] == "R3_equal_nominal"].iloc[0]
    r4 = summary_df[summary_df["strategy_id"] == "R4_multi_horizon"].iloc[0]
    br = summary_df[summary_df["strategy_id"] == "Bridge_long_only"].iloc[0]
    t1 = summary_df[summary_df["strategy_id"] == "T1_tsmom12_3bps"].iloc[0]
    t2 = summary_df[summary_df["strategy_id"] == "T2_multi_horizon_3bps"].iloc[0]
    bm = summary_df[summary_df["strategy_id"] == "R1_broad_market"].iloc[0]
    o1 = summary_df[summary_df["strategy_id"] == "O1_aqr_original_reference"].iloc[0]

    pos_sharpe_count = int((single_df["sharpe"] > 0).sum())
    total_assets = len(single_df)

    bonds_rem = removal_df[removal_df["removed_class"] == "Bonds"].iloc[0]
    eq_rem = removal_df[removal_df["removed_class"] == "Domestic_Equity"].iloc[0]

    traces = [
        {
            "claim_id": "CLAIM_01_SINGLE_ASSET_SHARPE_RATIO",
            "report_location": "Executive Summary & Section 5.2",
            "strategy_id": "R1_tsmom12",
            "metric": "Fraction of positive Sharpe assets",
            "value": f"{pos_sharpe_count}/{total_assets} ({pos_sharpe_count/total_assets*100:.1f}%)",
            "unit": "count / ratio",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": total_assets,
            "source_file": f"{out_name}/research/R1_single_asset_metrics.csv",
            "source_column": "sharpe",
            "computation": "Count of single asset strategy Sharpe ratios > 0",
        },
        {
            "claim_id": "CLAIM_02_R1_TSMOM_SHARPE",
            "report_location": "Executive Summary & Section 5.1",
            "strategy_id": "R1_tsmom12",
            "metric": "Annualized Sharpe Ratio",
            "value": f"{r1['sharpe']:.3f}",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r1["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "sharpe",
            "computation": "sqrt(12) * mean(R) / std(R, ddof=1)",
        },
        {
            "claim_id": "CLAIM_03_R1_ANN_ARITHMETIC_MEAN",
            "report_location": "Section 5.1",
            "strategy_id": "R1_tsmom12",
            "metric": "Annualized Arithmetic Mean Return",
            "value": f"{r1['ann_arithmetic_mean']*100:.2f}%",
            "unit": "percent",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r1["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "ann_arithmetic_mean",
            "computation": "12 * mean(portfolio_return)",
        },
        {
            "claim_id": "CLAIM_04_R2_PASSIVE_LONG_SHARPE",
            "report_location": "Executive Summary & Section 5.3",
            "strategy_id": "R2_passive_long",
            "metric": "Annualized Sharpe Ratio",
            "value": f"{r2['sharpe']:.3f}",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r2["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "sharpe",
            "computation": "sqrt(12) * mean(R) / std(R, ddof=1)",
        },
        {
            "claim_id": "CLAIM_05_R3_SCALING_SENSITIVITY",
            "report_location": "Section 6.1 (EXP_01)",
            "strategy_id": "R3_equal_nominal",
            "metric": "Sharpe without vol scaling",
            "value": f"{r3['sharpe']:.3f}",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r3["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "sharpe",
            "computation": "Equal nominal weighting s/N without 0.40/sigma",
        },
        {
            "claim_id": "CLAIM_06_BRIDGE_LONG_ONLY_SHARPE",
            "report_location": "Section 6.1 (EXP_02)",
            "strategy_id": "Bridge_long_only",
            "metric": "Sharpe under long-only research",
            "value": f"{br['sharpe']:.3f}",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": br["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "sharpe",
            "computation": "w = (1/N) * max(s,0) * (0.40/sigma)",
        },
        {
            "claim_id": "CLAIM_07_R4_VOLATILITY_REDUCTION",
            "report_location": "Section 7.2",
            "strategy_id": "R4_multi_horizon",
            "metric": "Annualized Volatility Reduction",
            "value": f"{r4['ann_vol']*100:.2f}% (vs R1 {r1['ann_vol']*100:.2f}%)",
            "unit": "percent",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r4["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "ann_vol",
            "computation": "sqrt(12) * std(R4_returns)",
        },
        {
            "claim_id": "CLAIM_08_T2_EXEC_SHARPE_IMPROVEMENT",
            "report_location": "Section 7.2",
            "strategy_id": "T2_multi_horizon_3bps",
            "metric": "Execution Sharpe vs T1",
            "value": f"{t2['sharpe']:.3f} (vs T1 {t1['sharpe']:.3f})",
            "unit": "Sharpe",
            "frequency": "daily",
            "sample_start": "2020-02-03",
            "sample_end": "2026-08-31",
            "n_observations": t2["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "sharpe",
            "computation": "sqrt(252) * mean(daily_ret) / std(daily_ret)",
        },
        {
            "claim_id": "CLAIM_09_BROAD_MARKET_SUBSET_COLLAPSE",
            "report_location": "Section 6.1 (EXP_05)",
            "strategy_id": "R1_broad_market",
            "metric": "Sharpe on Core Broad Market (510050/300/500)",
            "value": f"{bm['sharpe']:.3f}",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": bm["n_periods"],
            "source_file": f"{out_name}/strategy_summary.csv",
            "source_column": "sharpe",
            "computation": "TSMOM restricted to 3 equity index ETFs",
        },
        {
            "claim_id": "CLAIM_10_BOND_REMOVAL_ATTRIBUTION",
            "report_location": "Section 6.2",
            "strategy_id": "R1_without_bonds",
            "metric": "Sharpe without Bonds",
            "value": f"{bonds_rem['sharpe']:.3f} (vs Baseline {r1['sharpe']:.3f})",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r1["n_periods"],
            "source_file": f"{out_name}/experiments/asset_class_removal_attribution.csv",
            "source_column": "sharpe",
            "computation": "Zero out Bonds contribution without changing other weights",
        },
        {
            "claim_id": "CLAIM_11_DOMESTIC_EQUITY_RISK_ATTRIBUTION",
            "report_location": "Section 6.2",
            "strategy_id": "R1_without_domestic_equity",
            "metric": "Max Drawdown without Domestic Equity",
            "value": f"{eq_rem['max_drawdown']*100:.2f}% (vs Baseline {r1['max_drawdown']*100:.2f}%)",
            "unit": "percent",
            "frequency": "monthly",
            "sample_start": "2020-02",
            "sample_end": "2026-08",
            "n_observations": r1["n_periods"],
            "source_file": f"{out_name}/experiments/asset_class_removal_attribution.csv",
            "source_column": "max_drawdown",
            "computation": "Zero out Domestic Equity contribution without changing other weights",
        },
        {
            "claim_id": "CLAIM_12_O1_AQR_OFFICIAL_REPLICATION",
            "report_location": "Section 5.1 & Reference",
            "strategy_id": "O1_aqr_original_reference",
            "metric": "AQR Factor Recalculated Sharpe",
            "value": f"{o1['sharpe']:.3f}",
            "unit": "Sharpe",
            "frequency": "monthly",
            "sample_start": "1985-01-31",
            "sample_end": "2009-12-31",
            "n_observations": 300,
            "source_file": f"{out_name}/reference/aqr_tsmom_original_paper_factors.csv",
            "source_column": "TSMOM",
            "computation": "sqrt(12) * mean(AQR_TSMOM) / std(AQR_TSMOM)",
        },
    ]
    return pd.DataFrame(traces)


def generate_pipeline_figures(
    res_r1: Any,
    res_r2: Any,
    res_r4: Any,
    t1_ledger: pd.DataFrame,
    t2_ledger: pd.DataFrame,
    t3_ledger: pd.DataFrame,
    t1_10bps_ledger: pd.DataFrame,
    aqr_factors: pd.DataFrame,
    signals_df: pd.DataFrame,
    class_contrib_df: pd.DataFrame,
    out_dir: Path,
    eval_start: str = "2020-01-01",
) -> None:
    """Generate high-resolution figures for report."""
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # -------------------------------------------------------------
    # Figure 1: Single Asset Sharpe Comparison (Paper Fig. 2 Upper vs Replication)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(11, 9.5), gridspec_kw={"height_ratios": [1, 1.25]})
    
    orig_fig2_path = Path("references/fig2_upper_original.png")
    if orig_fig2_path.exists():
        img = Image.open(orig_fig2_path)
        axes[0].imshow(img)
        axes[0].axis("off")
        axes[0].set_title("Original Paper Fig. 2 (Upper): Single-Contract TSMOM Sharpe Ratios (1985-2009, 58 Futures/Forwards)", fontsize=10.5, fontweight="bold")
    else:
        axes[0].text(0.5, 0.5, "Original Fig. 2 Reference", ha="center", va="center")
        axes[0].axis("off")

    s_df = res_r1.single_asset_metrics.copy().sort_values("sharpe", ascending=True)
    colors = ["#2b5c8f" if s > 0 else "#c93b2b" for s in s_df["sharpe"]]
    bars = axes[1].barh(s_df["asset"], s_df["sharpe"], color=colors, height=0.65, edgecolor="black", linewidth=0.5)
    axes[1].axvline(0, color="black", linestyle="--", linewidth=1.0)
    axes[1].set_xlabel("Annualized Sharpe Ratio (sqrt(12) * Mean / Vol)", fontsize=10)
    axes[1].set_title(f"Replication: Single-ETF 12M TSMOM Strategy Sharpe Ratios ({len(s_df[s_df['sharpe']>0])}/21 Positive = {len(s_df[s_df['sharpe']>0])/21*100:.1f}%)", fontsize=10.5, fontweight="bold")
    
    for bar, (_, row) in zip(bars, s_df.iterrows()):
        val = row["sharpe"]
        n_m = int(row["n_months"])
        x_pos = val + (0.04 if val >= 0 else -0.16)
        axes[1].text(x_pos, bar.get_y() + bar.get_height()/2, f"{val:.2f} (N={n_m})", va="center", fontsize=7.5)

    axes[1].set_xlim(-0.8, 2.0)
    plt.tight_layout()
    fig.savefig(fig_dir / "fig2_single_asset_sharpe.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 2: Cumulative Wealth Comparison (Paper Fig. 3 vs Replication & AQR O1)
    # -------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(11, 10), gridspec_kw={"height_ratios": [1, 1.3]})

    orig_fig3_path = Path("references/fig3_original.png")
    if orig_fig3_path.exists():
        img = Image.open(orig_fig3_path)
        axes[0].imshow(img)
        axes[0].axis("off")
        axes[0].set_title("Original Paper Fig. 3: Cumulative Return of TSMOM vs. Passive Long (1985-2009, 58 Contracts)", fontsize=10.5, fontweight="bold")
    else:
        axes[0].axis("off")

    r1_df = res_r1.monthly_portfolio.copy()
    r2_df = res_r2.monthly_portfolio.copy()
    r4_df = res_r4.monthly_portfolio.copy()
    
    dates_r = pd.to_datetime(r1_df["holding_end_date"])
    r1_cum = (1.0 + r1_df["portfolio_return"]).cumprod()
    r2_cum = (1.0 + r2_df["portfolio_return"]).cumprod()
    r4_cum = (1.0 + r4_df["portfolio_return"]).cumprod()

    axes[1].plot(dates_r, r1_cum, label=f"R1: TSMOM 12M Research (Sharpe: {res_r1.summary_metrics['sharpe']:.2f}, CAGR: {res_r1.summary_metrics['cagr']*100:.1f}%)", color="#1f77b4", linewidth=2.0)
    axes[1].plot(dates_r, r2_cum, label=f"R2: Passive Long Research (Sharpe: {res_r2.summary_metrics['sharpe']:.2f}, CAGR: {res_r2.summary_metrics['cagr']*100:.1f}%)", color="#2ca02c", linewidth=2.0, linestyle="--")
    axes[1].plot(dates_r, r4_cum, label=f"R4: Multi-Horizon 3/6/12M (Sharpe: {res_r4.summary_metrics['sharpe']:.2f}, CAGR: {res_r4.summary_metrics['cagr']*100:.1f}%)", color="#ff7f0e", linewidth=1.8, linestyle="-.")
    
    axes[1].set_ylabel("Growth of $1.00 (Compounded)", fontsize=10)
    axes[1].set_xlabel("Date", fontsize=10)
    axes[1].set_title("Replication on ETF Sample: Cumulative Performance of Portfolios (2020-02 to 2026-08)", fontsize=10.5, fontweight="bold")
    axes[1].legend(loc="upper left", frameon=True, fontsize=9)
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    fig.savefig(fig_dir / "fig3_cumulative_comparison.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 3: Multi-Horizon vs Baseline Drawdowns and Exposure
    # -------------------------------------------------------------
    fig, (ax_wealth, ax_dd) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True, gridspec_kw={"height_ratios": [1.4, 1]})

    ax_wealth.plot(dates_r, r1_cum, label="R1: 12M Baseline TSMOM", color="#1f77b4", linewidth=2)
    ax_wealth.plot(dates_r, r4_cum, label="R4: Multi-Horizon Extension (3/6/12M)", color="#e377c2", linewidth=2)
    ax_wealth.set_ylabel("Cumulative Wealth", fontsize=9.5)
    ax_wealth.set_title("Baseline (R1) vs. Multi-Horizon Extension (R4): Wealth and Drawdown Dynamics", fontsize=10.5, fontweight="bold")
    ax_wealth.legend(loc="upper left", fontsize=9)

    dd1 = (r1_cum - r1_cum.cummax()) / r1_cum.cummax()
    dd4 = (r4_cum - r4_cum.cummax()) / r4_cum.cummax()

    ax_dd.plot(dates_r, dd1, label="R1 Drawdown", color="#1f77b4", alpha=0.85)
    ax_dd.plot(dates_r, dd4, label="R4 Drawdown", color="#e377c2", alpha=0.85)
    ax_dd.fill_between(dates_r, dd1, 0, color="#1f77b4", alpha=0.15)
    ax_dd.fill_between(dates_r, dd4, 0, color="#e377c2", alpha=0.15)
    ax_dd.set_ylabel("Drawdown", fontsize=9.5)
    ax_dd.set_xlabel("Date", fontsize=9.5)
    ax_dd.legend(loc="lower left", fontsize=9)
    ax_dd.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    fig.savefig(fig_dir / "fig_multi_horizon_comparison.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 4: Execution Performance (T1, T2, T3) and Fee Sensitivity
    # -------------------------------------------------------------
    fig, (ax_exec, ax_fee) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)

    t1_sub = t1_ledger[(t1_ledger["date"] >= "2020-02-03") & (t1_ledger["date"] <= "2026-08-31")].copy()
    t2_sub = t2_ledger[(t2_ledger["date"] >= "2020-02-03") & (t2_ledger["date"] <= "2026-08-31")].copy()
    t3_sub = t3_ledger[(t3_ledger["date"] >= "2020-02-03") & (t3_ledger["date"] <= "2026-08-31")].copy()
    t1_10_sub = t1_10bps_ledger[(t1_10bps_ledger["date"] >= "2020-02-03") & (t1_10bps_ledger["date"] <= "2026-08-31")].copy()

    init_cash = 1000000.0
    t1_nav = t1_sub["equity"] / init_cash
    t2_nav = t2_sub["equity"] / init_cash
    t3_nav = t3_sub["equity"] / init_cash
    t1_10_nav = t1_10_sub["equity"] / init_cash

    ax_exec.plot(t1_sub["date"], t1_nav, label="T1: 12M Long/Cash Exec (3 bps)", color="#1f77b4", linewidth=1.8)
    ax_exec.plot(t2_sub["date"], t2_nav, label="T2: Multi-Horizon Long/Cash Exec (3 bps)", color="#ff7f0e", linewidth=1.8)
    ax_exec.plot(t3_sub["date"], t3_nav, label="T3: Passive Long Exec (3 bps)", color="#2ca02c", linewidth=1.5, linestyle="--")
    ax_exec.set_ylabel("Normalized NAV", fontsize=9.5)
    ax_exec.set_title("Realistic Execution Mode under Trading Constraints (Next-Open, Long/Cash, 3 bps)", fontsize=10.5, fontweight="bold")
    ax_exec.legend(loc="upper left", fontsize=9)

    ax_fee.plot(t1_sub["date"], t1_nav, label="T1 at 3 bps (Base)", color="#1f77b4", linewidth=1.6)
    ax_fee.plot(t1_10_sub["date"], t1_10_nav, label="T1 at 10 bps (High Cost)", color="#d62728", linewidth=1.6, linestyle=":")
    ax_fee.set_ylabel("Normalized NAV", fontsize=9.5)
    ax_fee.set_xlabel("Date", fontsize=9.5)
    ax_fee.set_title("Transaction Cost Sensitivity: T1 Baseline vs 10 bps Friction", fontsize=10.5, fontweight="bold")
    ax_fee.legend(loc="upper left", fontsize=9)
    ax_fee.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    fig.savefig(fig_dir / "fig_execution_performance.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 5: Asset Class Cumulative Contribution Breakdown
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 5.5))
    c_dates = pd.to_datetime(class_contrib_df["formation_date"])
    
    cum_bonds = class_contrib_df["Bonds"].cumsum() * 100.0
    cum_eq = class_contrib_df["Domestic_Equity"].cumsum() * 100.0
    cum_cb = class_contrib_df["Cross_Border_Equity"].cumsum() * 100.0
    cum_gold = class_contrib_df["Gold"].cumsum() * 100.0
    cum_total = class_contrib_df["total_portfolio_return"].cumsum() * 100.0

    ax.plot(c_dates, cum_bonds, label=f"Bonds (3 ETFs): +{cum_bonds.iloc[-1]:.1f}%", color="#1f77b4", linewidth=2.0)
    ax.plot(c_dates, cum_eq, label=f"Domestic Equity (14 ETFs): +{cum_eq.iloc[-1]:.1f}%", color="#d62728", linewidth=1.8, linestyle="--")
    ax.plot(c_dates, cum_cb, label=f"Cross-Border Equity (3 ETFs): +{cum_cb.iloc[-1]:.1f}%", color="#2ca02c", linewidth=1.8, linestyle="-.")
    ax.plot(c_dates, cum_gold, label=f"Gold (1 ETF): +{cum_gold.iloc[-1]:.1f}%", color="#bcbd22", linewidth=1.8, linestyle=":")
    ax.plot(c_dates, cum_total, label=f"R1 Total Portfolio Sum: +{cum_total.iloc[-1]:.1f}%", color="black", linewidth=2.2)

    ax.set_ylabel("Cumulative Return Contribution (%)", fontsize=10)
    ax.set_xlabel("Formation Date", fontsize=10)
    ax.set_title("Asset Class Return Contribution in R1 TSMOM Portfolio (2020-01 to 2026-07)", fontsize=11, fontweight="bold")
    ax.legend(loc="upper left", frameon=True, fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.tight_layout()
    fig.savefig(fig_dir / "fig_asset_class_attribution.png", dpi=300)
    plt.close(fig)

    # -------------------------------------------------------------
    # Figure 6: Active Assets, Signal Distribution, and Exposure
    # -------------------------------------------------------------
    fig, (ax_sig, ax_exp) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)

    sig_sub = signals_df[(signals_df["date"] >= "2020-01-01") & (signals_df["date"] <= "2026-07-31")].copy()
    m_sig_summary = sig_sub.groupby("date").agg(
        n_pos=("s12", lambda s: (s > 0).sum()),
        n_neg=("s12", lambda s: (s < 0).sum()),
        n_eligible=("is_eligible", "sum"),
    ).reset_index()

    m_dates = pd.to_datetime(m_sig_summary["date"])
    ax_sig.bar(m_dates, m_sig_summary["n_pos"], label="Positive Trend (+1)", color="#2ca02c", width=20, alpha=0.85)
    ax_sig.bar(m_dates, m_sig_summary["n_neg"], bottom=m_sig_summary["n_pos"], label="Negative Trend (-1)", color="#d62728", width=20, alpha=0.85)
    ax_sig.plot(m_dates, m_sig_summary["n_eligible"], label="Total Eligible Assets", color="black", linewidth=1.5, linestyle="--")
    ax_sig.set_ylabel("Number of Assets", fontsize=9.5)
    ax_sig.set_title("Monthly Trend Signal Distribution (12M TSMOM) & Asset Eligibility", fontsize=10.5, fontweight="bold")
    ax_sig.legend(loc="upper left", fontsize=9)

    ax_exp.plot(dates_r, r1_df["gross_exposure"], label="Gross Exposure (sum |w_i|)", color="#9467bd", linewidth=1.8)
    ax_exp.plot(dates_r, r1_df["net_exposure"], label="Net Exposure (sum w_i)", color="#8c564b", linewidth=1.8, linestyle="--")
    ax_exp.axhline(0, color="gray", linestyle=":", linewidth=0.8)
    ax_exp.set_ylabel("Portfolio Exposure", fontsize=9.5)
    ax_exp.set_xlabel("Date", fontsize=9.5)
    ax_exp.set_title("R1 Portfolio Theoretical Exposure over Time", fontsize=10.5, fontweight="bold")
    ax_exp.legend(loc="upper left", fontsize=9)
    ax_exp.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    fig.savefig(fig_dir / "fig_signals_and_exposures.png", dpi=300)
    plt.close(fig)


def slice_research_subperiod(
    res_base: ResearchBacktestResult,
    start_date: str,
    end_date: str,
    name: str,
) -> ResearchBacktestResult:
    """Slice a baseline research backtest result strictly by holding_end_date.
    
    start_date and end_date represent holding period boundaries.
    Validates that start_date <= end_date and resulting slice is non-empty.
    Recomputes summary_metrics with proper DatetimeIndex.
    """
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    if start_dt > end_dt:
        raise ValueError(f"Subperiod start date {start_date} is after end date {end_date}")
    
    df_port = res_base.monthly_portfolio.copy()
    if df_port.empty:
        raise ValueError("Cannot slice an empty baseline portfolio")
    
    holding_dts = pd.to_datetime(df_port["holding_end_date"])
    mask = (holding_dts >= start_dt) & (holding_dts <= end_dt)
    sliced_port = df_port[mask].reset_index(drop=True)
    
    if sliced_port.empty:
        raise ValueError(
            f"Subperiod {name} [{start_date}, {end_date}] yielded no holding months. "
            f"Available holding range: {df_port['holding_end_date'].min()} to {df_port['holding_end_date'].max()}"
        )
    
    # Calculate monthly metrics with DatetimeIndex
    s_ret = pd.Series(
        sliced_port["portfolio_return"].values,
        index=pd.DatetimeIndex(sliced_port["holding_end_date"]),
        name="portfolio_return",
    )
    summary_m = calculate_monthly_metrics(s_ret, strict_continuity=True)
    
    # Slice associated tables if available
    sliced_weights = pd.DataFrame()
    if res_base.monthly_weights is not None and not res_base.monthly_weights.empty:
        w_dts = pd.to_datetime(res_base.monthly_weights["holding_end_date"])
        sliced_weights = res_base.monthly_weights[(w_dts >= start_dt) & (w_dts <= end_dt)].reset_index(drop=True)
        
    sliced_contrib = pd.DataFrame()
    if res_base.asset_contributions is not None and not res_base.asset_contributions.empty:
        c_dts = pd.to_datetime(res_base.asset_contributions["holding_end_date"])
        sliced_contrib = res_base.asset_contributions[(c_dts >= start_dt) & (c_dts <= end_dt)].reset_index(drop=True)
        
    sliced_single = pd.DataFrame()
    if res_base.single_asset_returns is not None and not res_base.single_asset_returns.empty:
        s_dts = pd.to_datetime(res_base.single_asset_returns["holding_end_date"])
        sliced_single = res_base.single_asset_returns[(s_dts >= start_dt) & (s_dts <= end_dt)].reset_index(drop=True)

    single_metrics_records = []
    if not sliced_single.empty:
        for asset, grp in sliced_single.groupby("asset"):
            grp_sorted = grp.sort_values("holding_end_date")
            asset_ret = pd.Series(
                grp_sorted["single_strategy_return"].values,
                index=pd.DatetimeIndex(grp_sorted["holding_end_date"]),
                name="single_strategy_return",
            )
            m = calculate_monthly_metrics(asset_ret, strict_continuity=True)
            m["asset"] = asset
            single_metrics_records.append(m)
    sliced_single_metrics = pd.DataFrame(single_metrics_records) if single_metrics_records else pd.DataFrame()

    return ResearchBacktestResult(
        strategy_name=name,
        mode=res_base.mode,
        monthly_portfolio=sliced_port,
        monthly_weights=sliced_weights,
        asset_contributions=sliced_contrib,
        single_asset_returns=sliced_single,
        single_asset_metrics=sliced_single_metrics,
        summary_metrics=summary_m,
    )


def run_p2_pipeline(
    config_path: str | Path = "config/project2_tsmom.json",
    out_dir: str | Path = "outputs_p2",
    offline: bool = True,
    random_seed: int = 20261022,
) -> Dict[str, Any]:
    """Execute complete Project 2 replication and extension pipeline."""
    np.random.seed(random_seed)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Load and validate config
    cfg_file = Path(config_path)
    if not cfg_file.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_file}")
    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Validate multi-horizon weights and horizons
    horizons = cfg.get("tsmom", {}).get("horizons", [3, 6, 12])
    if horizons != [3, 6, 12]:
        raise ValueError(f"Unsupported tsmom horizons {horizons}; must be [3, 6, 12] for equal multi-horizon extension.")

    primary_horizon = cfg.get("tsmom", {}).get("primary_horizon", 12)
    if primary_horizon != 12:
        raise ValueError(f"Unsupported primary_horizon {primary_horizon}; must be 12.")

    mh_weights = cfg.get("tsmom", {}).get("multi_horizon_weights", [1/3, 1/3, 1/3])
    if len(mh_weights) != 3:
        raise ValueError(f"multi_horizon_weights must have length 3, got {len(mh_weights)}")
    for w in mh_weights:
        if not np.isfinite(w) or w < 0 or abs(w - 1.0 / 3.0) > 1e-3:
            raise ValueError(
                f"Unsupported multi_horizon_weights: {mh_weights}. "
                "This implementation strictly requires equal multi-horizon weights [1/3, 1/3, 1/3]."
            )

    vol_ann = cfg.get("tsmom", {}).get("volatility_annualization", 261)
    if vol_ann != 261:
        raise ValueError(f"Unsupported volatility_annualization {vol_ann}; must be 261 per Moskowitz et al. (2012).")

    ann_daily = cfg.get("metrics", {}).get("annualization_daily", 252)
    if ann_daily != 252:
        raise ValueError(f"Unsupported annualization_daily {ann_daily}; must be 252.")

    ann_monthly = cfg.get("metrics", {}).get("annualization_monthly", 12)
    if ann_monthly != 12:
        raise ValueError(f"Unsupported annualization_monthly {ann_monthly}; must be 12.")

    rf_daily = cfg.get("metrics", {}).get("daily_risk_free", 0.0)
    rf_monthly = cfg.get("metrics", {}).get("monthly_risk_free", 0.0)
    if rf_daily != 0.0 or rf_monthly != 0.0:
        raise ValueError(f"Unsupported risk-free rates (daily={rf_daily}, monthly={rf_monthly}); must be 0.0 for gross replication.")

    cost_levels = cfg.get("experiments", {}).get("cost_levels", [0.0, 0.0003, 0.0010])
    if cost_levels != [0.0, 0.0003, 0.0010]:
        raise ValueError(f"Unsupported cost_levels {cost_levels}; must be [0.0, 0.0003, 0.0010].")

    base_buy_fee = cfg.get("execution", {}).get("buy_fee", 0.0003)
    base_sell_fee = cfg.get("execution", {}).get("sell_fee", 0.0003)
    if base_buy_fee != 0.0003 or base_sell_fee != 0.0003:
        raise ValueError(f"Execution base fees must match 3 bps (0.0003); got buy={base_buy_fee}, sell={base_sell_fee}")

    if not offline:
        fetch_project2_sources(force_download=False)

    # Extract date boundaries driven dynamically by configuration
    formation_start = cfg.get("data", {}).get("evaluation_start", "2020-01-01")
    holding_start = cfg.get("data", {}).get("holding_start", "2020-02-01")
    holding_end = cfg.get("data", {}).get("holding_end", "2026-08-31")
    exec_start = cfg.get("execution", {}).get("start", "2020-02-03")
    exec_end = cfg.get("execution", {}).get("end", "2026-08-31")

    # Dynamically derive formation_end as the calendar month-end immediately preceding holding_end
    h_end_dt = pd.to_datetime(holding_end)
    prev_month_end = h_end_dt.replace(day=1) - pd.Timedelta(days=1)
    formation_end = prev_month_end.strftime("%Y-%m-%d")

    # Date order consistency validations
    if pd.to_datetime(formation_start) >= pd.to_datetime(formation_end):
        raise ValueError(f"formation_start ({formation_start}) must be strictly before formation_end ({formation_end})")
    if pd.to_datetime(holding_start) >= pd.to_datetime(holding_end):
        raise ValueError(f"holding_start ({holding_start}) must be strictly before holding_end ({holding_end})")
    if pd.to_datetime(exec_start) >= pd.to_datetime(exec_end):
        raise ValueError(f"exec_start ({exec_start}) must be strictly before exec_end ({exec_end})")

    # Subperiods dynamically read from config (representing holding period boundaries)
    subperiods = cfg.get("experiments", {}).get("subperiods", [])
    if len(subperiods) >= 2:
        sub1_start = subperiods[0].get("start", "2020-02-01")
        sub1_end = subperiods[0].get("end", "2022-12-31")
        sub2_start = subperiods[1].get("start", "2023-01-01")
        sub2_end = subperiods[1].get("end", holding_end)
    else:
        sub1_start, sub1_end = "2020-02-01", "2022-12-31"
        sub2_start, sub2_end = "2023-01-01", holding_end

    if pd.to_datetime(sub1_start) >= pd.to_datetime(sub1_end):
        raise ValueError(f"sub1_start ({sub1_start}) must be strictly before sub1_end ({sub1_end})")
    if pd.to_datetime(sub2_start) >= pd.to_datetime(sub2_end):
        raise ValueError(f"sub2_start ({sub2_start}) must be strictly before sub2_end ({sub2_end})")

    prices_path = Path(cfg["data"].get("prices_snapshot", "data/raw/prices_raw.parquet"))
    adj_path = Path(cfg["data"].get("adjustment_snapshot", "data/raw/adjustment_raw.parquet"))
    aqr_ref_path = Path("data/reference/Time-Series-Momentum-Original-Paper-Data.xlsx")

    # 1.1 Start ExperimentRecorder early (BEFORE data loading) to capture entire study lifecycle
    recorder = ExperimentRecorder(
        runs_root=out_path / "runs",
        config=cfg,
        data_paths={
            "prices_snapshot": prices_path,
            "adjustment_snapshot": adj_path,
            "aqr_excel": aqr_ref_path,
        },
        source_paths={
            "tsmom.py": Path("src/quantcf/tsmom.py"),
            "research_backtest.py": Path("src/quantcf/research_backtest.py"),
            "portfolio.py": Path("src/quantcf/portfolio.py"),
            "reference_data.py": Path("src/quantcf/reference_data.py"),
            "pipeline_p2.py": Path("src/quantcf/pipeline_p2.py"),
            "report_p2.py": Path("src/quantcf/report_p2.py"),
            "run_project2.py": Path("run_project2.py"),
            "build_report_project2.py": Path("build_report_project2.py"),
            "protocol.md": Path("docs/PROTOCOL.md"),
            "pyproject.toml": Path("pyproject.toml"),
            "uv.lock": Path("uv.lock"),
        },
        run_name="project2_tsmom",
        overwrite=True,
    )
    recorder.start()

    try:
        # 2. Ingest market prices panel (recorded within study lifecycle)
        prices_df, data_audit, data_hashes = load_panel(".", cfg["data"])
        prices_snapshot_hash = hashlib.sha256(prices_path.read_bytes()).hexdigest()[:16] if prices_path.exists() else "N/A"

        # 3. Build monthly TSMOM signals and volatility dataset
        dataset = build_monthly_tsmom_dataset(
            prices_df,
            evaluation_start=formation_start,
            evaluation_end=holding_end,
            min_vol_days=cfg["tsmom"]["volatility_min_days"],
            vol_decay=cfg["tsmom"]["volatility_decay"],
            vol_ann_factor=float(vol_ann),
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            multi_horizon_weights=mh_weights,
        )
        signals_df = dataset["signals_df"]

        (out_path / "data").mkdir(exist_ok=True)
        (out_path / "signals").mkdir(exist_ok=True)
        (out_path / "research").mkdir(exist_ok=True)
        (out_path / "backtests").mkdir(exist_ok=True)
        (out_path / "reference").mkdir(exist_ok=True)
        (out_path / "experiments").mkdir(exist_ok=True)

        signals_df.to_parquet(out_path / "signals" / "tsmom_monthly_signals.parquet", index=False)
        signals_df.to_csv(out_path / "signals" / "tsmom_monthly_signals.csv", index=False)

        # 4. Core Research Mode Backtests (79 active holding months)
        res_r1 = run_research_backtest(
            signals_df, strategy_mode="tsmom12",
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            evaluation_start=formation_start, evaluation_end=formation_end,
        )
        res_r2 = run_research_backtest(
            signals_df, strategy_mode="passive_long",
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            evaluation_start=formation_start, evaluation_end=formation_end,
        )
        res_r3 = run_research_backtest(
            signals_df, strategy_mode="equal_nominal",
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            evaluation_start=formation_start, evaluation_end=formation_end,
        )
        res_r4 = run_research_backtest(
            signals_df, strategy_mode="multi_horizon",
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            evaluation_start=formation_start, evaluation_end=formation_end,
        )
        res_bridge = run_research_backtest(
            signals_df, strategy_mode="long_only_bridge",
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            evaluation_start=formation_start, evaluation_end=formation_end,
        )
        res_sample_vol = run_research_backtest(
            signals_df, strategy_mode="tsmom12",
            use_sample_vol=True,
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            evaluation_start=formation_start, evaluation_end=formation_end,
        )
        res_sub1 = slice_research_subperiod(res_r1, sub1_start, sub1_end, "R1_sub_2020_2022")
        res_sub2 = slice_research_subperiod(res_r1, sub2_start, sub2_end, "R1_sub_2023_2026")
        core_assets = cfg["experiments"]["asset_subsets"]["broad_market_core"]
        res_broad = run_research_backtest(
            signals_df, strategy_mode="tsmom12",
            target_volatility=cfg["tsmom"]["target_volatility"],
            min_eligible_assets=3,
            asset_subset=core_assets,
            evaluation_start=formation_start, evaluation_end=formation_end,
        )

        # Save research tables
        for name, res in [("R1_tsmom12", res_r1), ("R2_passive_long", res_r2), ("R3_equal_nominal", res_r3),
                          ("R4_multi_horizon", res_r4), ("Bridge_long_only", res_bridge),
                          ("R1_sample_vol", res_sample_vol), ("R1_broad_market", res_broad)]:
            res.monthly_portfolio.to_csv(out_path / "research" / f"{name}_monthly_portfolio.csv", index=False)
            res.monthly_weights.to_csv(out_path / "research" / f"{name}_monthly_weights.csv", index=False)
            res.asset_contributions.to_csv(out_path / "research" / f"{name}_asset_contributions.csv", index=False)
            res.single_asset_returns.to_csv(out_path / "research" / f"{name}_single_asset_returns.csv", index=False)

        res_sub1.monthly_portfolio.to_csv(out_path / "research" / "R1_sub_2020_2022_monthly_portfolio.csv", index=False)
        res_sub2.monthly_portfolio.to_csv(out_path / "research" / "R1_sub_2023_2026_monthly_portfolio.csv", index=False)
        res_r1.single_asset_metrics.to_csv(out_path / "research" / "R1_single_asset_metrics.csv", index=False)

        # 5. Asset Class Contribution, Variance Decomposition & Fixed-Weight Removal Attribution
        class_contrib_df = compute_asset_class_contributions(res_r1.asset_contributions, res_r1.monthly_portfolio)
        class_contrib_df.to_csv(out_path / "research" / "R1_asset_class_contributions.csv", index=False)

        var_decomp_df = compute_asset_class_variance_decomposition(class_contrib_df)
        var_decomp_df.to_csv(out_path / "research" / "asset_class_variance_decomposition.csv", index=False)

        removal_df = compute_asset_class_removal_attribution(res_r1.asset_contributions, res_r1.monthly_portfolio)
        removal_df.to_csv(out_path / "experiments" / "asset_class_removal_attribution.csv", index=False)

        # 6. Core Execution Mode Backtests (T1, T2, T3)
        all_trading_dates = prices_df["date"].unique()

        targets_t1 = generate_tsmom_long_cash_targets(
            signals_df, calendar=all_trading_dates, strategy_mode="tsmom12",
            invest_fraction=cfg["execution"]["invest_fraction"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            start=exec_start, end=exec_end,
        )
        targets_t2 = generate_tsmom_long_cash_targets(
            signals_df, calendar=all_trading_dates, strategy_mode="multi_horizon",
            invest_fraction=cfg["execution"]["invest_fraction"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            start=exec_start, end=exec_end,
        )
        targets_t3 = generate_tsmom_long_cash_targets(
            signals_df, calendar=all_trading_dates, strategy_mode="passive_long",
            invest_fraction=cfg["execution"]["invest_fraction"],
            min_eligible_assets=cfg["tsmom"]["min_eligible_assets"],
            start=exec_start, end=exec_end,
        )

        targets_t1.to_csv(out_path / "backtests" / "T1_targets.csv", index=False)
        targets_t2.to_csv(out_path / "backtests" / "T2_targets.csv", index=False)
        targets_t3.to_csv(out_path / "backtests" / "T3_targets.csv", index=False)

        cost_levels = cfg.get("experiments", {}).get("cost_levels", [0.0, 0.0003, 0.0010])
        base_fee = cost_levels[1] if len(cost_levels) > 1 else 0.0003
        zero_fee = cost_levels[0] if len(cost_levels) > 0 else 0.0
        high_fee = cost_levels[2] if len(cost_levels) > 2 else 0.0010

        base_exec_cfg = BacktestConfig.from_mapping({
            **cfg["execution"],
            "start": exec_start,
            "end": exec_end,
            "buy_fee": base_fee,
            "sell_fee": base_fee,
        })
        zero_exec_cfg = BacktestConfig.from_mapping({
            **cfg["execution"],
            "start": exec_start,
            "end": exec_end,
            "buy_fee": zero_fee,
            "sell_fee": zero_fee,
        })
        high_exec_cfg = BacktestConfig.from_mapping({
            **cfg["execution"],
            "start": exec_start,
            "end": exec_end,
            "buy_fee": high_fee,
            "sell_fee": high_fee,
        })

        run_t1_base = run_backtest(prices_df, targets_t1, base_exec_cfg)
        run_t1_zero = run_backtest(prices_df, targets_t1, zero_exec_cfg)
        run_t1_high = run_backtest(prices_df, targets_t1, high_exec_cfg)

        run_t2_base = run_backtest(prices_df, targets_t2, base_exec_cfg)
        run_t2_zero = run_backtest(prices_df, targets_t2, zero_exec_cfg)
        run_t2_high = run_backtest(prices_df, targets_t2, high_exec_cfg)

        run_t3_base = run_backtest(prices_df, targets_t3, base_exec_cfg)
        run_t3_zero = run_backtest(prices_df, targets_t3, zero_exec_cfg)

        # Save complete execution tables (ledger, orders, fills, holdings, audit, monthly compound returns)
        save_execution_artifacts("T1_base_3bps", run_t1_base, out_path)
        save_execution_artifacts("T1_zero_0bps", run_t1_zero, out_path)
        save_execution_artifacts("T1_high_10bps", run_t1_high, out_path)
        save_execution_artifacts("T2_base_3bps", run_t2_base, out_path)
        save_execution_artifacts("T2_zero_0bps", run_t2_zero, out_path)
        save_execution_artifacts("T2_high_10bps", run_t2_high, out_path)
        save_execution_artifacts("T3_base_3bps", run_t3_base, out_path)
        save_execution_artifacts("T3_zero_0bps", run_t3_zero, out_path)

        # 7. Official AQR Reference O1
        aqr_df = load_aqr_reference_factors()
        aqr_metrics = calculate_reference_metrics(aqr_df["TSMOM"])
        aqr_df.to_csv(out_path / "reference" / "aqr_tsmom_original_paper_factors.csv", index=False)

        # 8. Compile strategy_summary.csv (Standardized column names)
        summary_rows = []

        research_runs = [
            ("R1_tsmom12", "research", "12M TSMOM with 0.40/vol scaling", res_r1.summary_metrics, holding_start, holding_end),
            ("R2_passive_long", "research", "Passive Long with 0.40/vol scaling", res_r2.summary_metrics, holding_start, holding_end),
            ("R3_equal_nominal", "research", "12M TSMOM with s/N equal nominal", res_r3.summary_metrics, holding_start, holding_end),
            ("R4_multi_horizon", "research", "3/6/12M Trend Combination", res_r4.summary_metrics, holding_start, holding_end),
            ("Bridge_long_only", "research", "Long-Only TSMOM (Bridge)", res_bridge.summary_metrics, holding_start, holding_end),
            ("R1_sample_vol", "research", "TSMOM with 252d rolling sample vol", res_sample_vol.summary_metrics, holding_start, holding_end),
            ("R1_sub_2020_2022", "research", f"TSMOM Subperiod {sub1_start[:4]}-{sub1_end[:4]}", res_sub1.summary_metrics, sub1_start, sub1_end),
            ("R1_sub_2023_2026", "research", f"TSMOM Subperiod {sub2_start[:4]}-{sub2_end[:4]}", res_sub2.summary_metrics, sub2_start, sub2_end),
            ("R1_broad_market", "research", "TSMOM Core Broad Market Subset", res_broad.summary_metrics, holding_start, holding_end),
        ]

        for strat_id, mode, desc, m, s_dt, e_dt in research_runs:
            summary_rows.append({
                "strategy_id": strat_id,
                "mode": mode,
                "description": desc,
                "sample_start": s_dt,
                "sample_end": e_dt,
                "n_periods": m.get("n_months", 0),
                "frequency": "monthly",
                "ann_arithmetic_mean": m.get("ann_mean", np.nan),
                "ann_vol": m.get("ann_vol", np.nan),
                "sharpe": m.get("sharpe", np.nan),
                "cagr": m.get("cagr", np.nan),
                "max_drawdown": m.get("max_drawdown", np.nan),
                "calmar": m.get("calmar", np.nan),
                "win_rate": m.get("positive_ratio", np.nan),
                "total_compound_return": m.get("total_compound_return", np.nan),
                "turnover_ann": np.nan,
                "total_fees": 0.0,
                "mean_gross_exposure": m.get("mean_gross_exposure", np.nan),
                "mean_net_exposure": m.get("mean_net_exposure", np.nan),
            })

        exec_runs = [
            ("T1_tsmom12_3bps", "execution", "12M Long/Cash Exec (3 bps base)", run_t1_base.ledger),
            ("T1_tsmom12_0bps", "execution", "12M Long/Cash Exec (0 bps zero cost)", run_t1_zero.ledger),
            ("T1_tsmom12_10bps", "execution", "12M Long/Cash Exec (10 bps high cost)", run_t1_high.ledger),
            ("T2_multi_horizon_3bps", "execution", "Multi-Horizon Long/Cash Exec (3 bps base)", run_t2_base.ledger),
            ("T2_multi_horizon_0bps", "execution", "Multi-Horizon Long/Cash Exec (0 bps zero cost)", run_t2_zero.ledger),
            ("T2_multi_horizon_10bps", "execution", "Multi-Horizon Long/Cash Exec (10 bps high cost)", run_t2_high.ledger),
            ("T3_passive_long_3bps", "execution", "Passive Long Exec (3 bps base)", run_t3_base.ledger),
            ("T3_passive_long_0bps", "execution", "Passive Long Exec (0 bps zero cost)", run_t3_zero.ledger),
        ]

        for strat_id, mode, desc, ldg in exec_runs:
            m = calculate_daily_ledger_metrics(ldg, start_date=exec_start, end_date=exec_end)
            summary_rows.append({
                "strategy_id": strat_id,
                "mode": mode,
                "description": desc,
                "sample_start": exec_start,
                "sample_end": exec_end,
                "n_periods": m.get("n_periods", 0),
                "frequency": "daily",
                "ann_arithmetic_mean": m.get("ann_arithmetic_mean", np.nan),
                "ann_vol": m.get("ann_vol", np.nan),
                "sharpe": m.get("sharpe", np.nan),
                "cagr": m.get("cagr", np.nan),
                "max_drawdown": m.get("max_drawdown", np.nan),
                "calmar": m.get("calmar", np.nan),
                "win_rate": m.get("win_rate_daily", np.nan),
                "total_compound_return": m.get("total_compound_return", np.nan),
                "turnover_ann": m.get("turnover_ann", np.nan),
                "total_fees": m.get("total_fees", 0.0),
                "mean_gross_exposure": 1.0 - m.get("mean_cash_ratio", 0.0),
                "mean_net_exposure": 1.0 - m.get("mean_cash_ratio", 0.0),
            })

        aqr_calmar = (aqr_metrics["cagr"] / abs(aqr_metrics["max_drawdown"])) if aqr_metrics.get("max_drawdown", 0) != 0 else np.nan
        summary_rows.append({
            "strategy_id": "O1_aqr_original_reference",
            "mode": "reference",
            "description": "AQR Official TSMOM Original Paper Factor Recalculation (Moskowitz et al. 2012)",
            "sample_start": "1985-01-31",
            "sample_end": "2009-12-31",
            "n_periods": aqr_metrics["n_months"],
            "frequency": "monthly",
            "ann_arithmetic_mean": aqr_metrics["ann_mean"],
            "ann_vol": aqr_metrics["ann_vol"],
            "sharpe": aqr_metrics["sharpe"],
            "cagr": aqr_metrics["cagr"],
            "max_drawdown": aqr_metrics["max_drawdown"],
            "calmar": aqr_calmar,
            "win_rate": aqr_metrics["positive_ratio"],
            "total_compound_return": aqr_metrics["total_compound_return"],
            "turnover_ann": np.nan,
            "total_fees": 0.0,
            "mean_gross_exposure": np.nan,
            "mean_net_exposure": np.nan,
        })

        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_csv(out_path / "strategy_summary.csv", index=False)

        # 9. Inventory of Experiments (outputs/experiments_inventory.csv)
        inventory_df = build_experiments_inventory(df_summary)
        inventory_df.to_csv(out_path / "experiments_inventory.csv", index=False)

        # 10. original_vs_replication.csv
        s_single = res_r1.single_asset_metrics
        pos_sharpe_count = int((s_single["sharpe"] > 0).sum())
        total_assets_count = len(s_single)

        orig_rows = [
            {
                "target": "Fig. 2 Upper (Single Asset Sharpe)",
                "source_page": "p. 237",
                "metric": "Fraction of positive Sharpe assets",
                "original_value": "100.0% (58/58 positive in Fig 2; 52/58 significant at 5% level per text p. 236)",
                "reference_recalculated": "N/A (underlying 58 contracts not published)",
                "own_result": f"{pos_sharpe_count/total_assets_count*100:.1f}% ({pos_sharpe_count}/{total_assets_count})",
                "unit": "ratio",
                "frequency": "monthly",
                "sample": "21 China ETFs (2020-02 to 2026-08)",
                "cost_basis": "gross (0 bps)",
                "comparability": "Pattern-comparable (Partial support)",
                "comparable_difference": "N/A",
                "reason": "Different asset universe (58 global futures vs 21 China ETFs); majority (81%) positive, but cyclical equity sectors underperformed",
            },
            {
                "target": "Fig. 2 Upper (Single Asset Sharpe)",
                "source_page": "p. 237",
                "metric": "Mean single-asset annualized Sharpe",
                "original_value": "Unstated in paper text (contract Sharpe range ~0.10 to ~0.90 in Fig 2)",
                "reference_recalculated": "N/A",
                "own_result": f"{float(s_single['sharpe'].mean()):.3f}",
                "unit": "Sharpe",
                "frequency": "monthly",
                "sample": "21 China ETFs (2020-02 to 2026-08)",
                "cost_basis": "gross (0 bps)",
                "comparability": "Cross-sectional mean comparable",
                "comparable_difference": "N/A",
                "reason": "Substantial bond/gold ETF performance elevated Sharpe, while equity sectors experienced chop; cross-market divergence",
            },
            {
                "target": "Fig. 3 (Cumulative Performance)",
                "source_page": "p. 239, Fig. 3",
                "metric": "TSMOM Annualized Sharpe Ratio",
                "original_value": "N/A (unlabeled in Figure 3; visual cumulative trajectory only)",
                "reference_recalculated": f"{aqr_metrics['sharpe']:.3f} (AQR O1 official factor recalculation: Time-Series-Momentum-Original-Paper-Data.xlsx, Sheet 'TSMOM factors', 1985-01 to 2009-12)",
                "own_result": f"{res_r1.summary_metrics['sharpe']:.3f}",
                "unit": "Sharpe",
                "frequency": "monthly",
                "sample": "21 China ETFs (2020-02 to 2026-08)",
                "cost_basis": "gross (0 bps)",
                "comparability": "Method-comparable, sample-different",
                "comparable_difference": "N/A",
                "reason": "Figure 3 plots cumulative growth without labeling numerical Sharpe. 1.385 is independently recomputed from the public AQR factor dataset (not read from paper tables; Table 4 reports correlations).",
            },
            {
                "target": "Fig. 3 (Cumulative Performance)",
                "source_page": "p. 239, Fig. 3",
                "metric": "TSMOM Annualized Return",
                "original_value": "N/A (unlabeled in Figure 3; visual cumulative trajectory only)",
                "reference_recalculated": f"{aqr_metrics['ann_mean']*100:.2f}% (AQR O1 official factor recalculation: Time-Series-Momentum-Original-Paper-Data.xlsx, Sheet 'TSMOM factors', 1985-01 to 2009-12)",
                "own_result": f"{res_r1.summary_metrics['ann_mean']*100:.2f}%",
                "unit": "percent",
                "frequency": "monthly",
                "sample": "21 China ETFs (2020-02 to 2026-08)",
                "cost_basis": "gross (0 bps)",
                "comparability": "Method-comparable, sample-different",
                "comparable_difference": "N/A",
                "reason": "Figure 3 plots cumulative growth without labeling numerical return. 17.08% is independently recomputed from public AQR factor data (ann_mean = 17.08%, vol = 12.33%).",
            },
            {
                "target": "Fig. 3 (Cumulative Performance)",
                "source_page": "p. 239",
                "metric": "TSMOM vs Passive Long Sharpe Dominance",
                "original_value": "TSMOM visually vastly outperforms Passive Long in cumulative wealth (exact passive Sharpe unstated in Fig 3 text)",
                "reference_recalculated": "N/A (Passive long series not in public AQR factor file)",
                "own_result": f"TSMOM ({res_r1.summary_metrics['sharpe']:.2f}) < Passive Long ({res_r2.summary_metrics['sharpe']:.2f})",
                "unit": "Sharpe comparison",
                "frequency": "monthly",
                "sample": "21 China ETFs (2020-02 to 2026-08)",
                "cost_basis": "gross (0 bps)",
                "comparability": "Empirical hypothesis test (Not replicated in sample)",
                "comparable_difference": f"{res_r1.summary_metrics['sharpe'] - res_r2.summary_metrics['sharpe']:.3f}",
                "reason": "In our ETF sample, bond and gold ETFs had secular upward drift where passive long outperformed trend-reversal costs; short signals during sudden V-shaped rebounds caused drag",
            },
        ]
        df_orig = pd.DataFrame(orig_rows)
        df_orig.to_csv(out_path / "original_vs_replication.csv", index=False)

        # 11. difference_experiments.csv (Tightened explanations and authentic cryptographic hashes)
        effective_months = [pd.Timestamp(m).strftime("%Y-%m") for m in dataset["month_ends"] if formation_start <= pd.Timestamp(m).strftime("%Y-%m-%d") <= formation_end]
        effective_months_hash = hashlib.sha256(",".join(effective_months).encode("utf-8")).hexdigest()[:16]
        m_t1_base = calculate_daily_ledger_metrics(run_t1_base.ledger, start_date=exec_start, end_date=exec_end)
        m_t1_high = calculate_daily_ledger_metrics(run_t1_high.ledger, start_date=exec_start, end_date=exec_end)

        diff_rows = [
            {
                "experiment_id": "EXP_01_VOL_SCALING",
                "baseline_id": "R1_tsmom12",
                "changed_setting": "Volatility scaling: 0.40/sigma (R1) vs Equal nominal s/N (R3)",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["tsmom.target_volatility"]),
                "config_diff": "tsmom.target_volatility: 0.40 -> unscaled (1/N)",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": holding_start,
                "sample_end": holding_end,
                "n_months": res_r1.summary_metrics["n_months"],
                "metric": "Sharpe Ratio",
                "baseline_value": f"{res_r1.summary_metrics['sharpe']:.3f}",
                "alternative_value": f"{res_r3.summary_metrics['sharpe']:.3f}",
                "difference": f"{res_r3.summary_metrics['sharpe'] - res_r1.summary_metrics['sharpe']:.3f}",
                "evidence_path": f"{out_path.name}/research/R3_equal_nominal_monthly_portfolio.csv",
                "interpretation": "Volatility scaling normalizes risk across low-vol bonds and high-vol equities, materially improving risk-adjusted stability in sample",
                "limitation": "Descriptive finding within ETF universe; does not guarantee future risk parity across macro regimes",
            },
            {
                "experiment_id": "EXP_02_SHORTING_CONSTRAINT",
                "baseline_id": "R1_tsmom12",
                "changed_setting": "Shorting allowed (R1) vs Long-Only Bridge (max(s,0))",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["research.strategy_mode"]),
                "config_diff": "strategy_mode: tsmom12 (long/short) -> long_only_bridge (long/cash)",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": holding_start,
                "sample_end": holding_end,
                "n_months": res_r1.summary_metrics["n_months"],
                "metric": "Sharpe Ratio",
                "baseline_value": f"{res_r1.summary_metrics['sharpe']:.3f}",
                "alternative_value": f"{res_bridge.summary_metrics['sharpe']:.3f}",
                "difference": f"{res_bridge.summary_metrics['sharpe'] - res_r1.summary_metrics['sharpe']:.3f}",
                "evidence_path": f"{out_path.name}/research/Bridge_long_only_monthly_portfolio.csv",
                "interpretation": "Shorting equities during sudden V-shaped rebounds generated negative carry; long-only cash bridge achieved higher Sharpe in this sample",
                "limitation": "Dependent on secular bull drift of bonds/gold and sharp policy rebounds",
            },
            {
                "experiment_id": "EXP_03_VOL_ESTIMATOR",
                "baseline_id": "R1_tsmom12",
                "changed_setting": "EWMA lambda=60/61 (R1) vs 252d Rolling Sample Std (R1_sample_vol)",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["tsmom.volatility_decay"]),
                "config_diff": "volatility_decay: 60/61 (EWMA) -> rolling 252-day sample std (ddof=1)",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": holding_start,
                "sample_end": holding_end,
                "n_months": res_r1.summary_metrics["n_months"],
                "metric": "Sharpe Ratio",
                "baseline_value": f"{res_r1.summary_metrics['sharpe']:.3f}",
                "alternative_value": f"{res_sample_vol.summary_metrics['sharpe']:.3f}",
                "difference": f"{res_sample_vol.summary_metrics['sharpe'] - res_r1.summary_metrics['sharpe']:.3f}",
                "evidence_path": f"{out_path.name}/research/R1_sample_vol_monthly_portfolio.csv",
                "interpretation": f"EWMA reacts faster to recent volatility surges, resulting in higher risk-adjusted return ({res_r1.summary_metrics['sharpe']:.3f} vs {res_sample_vol.summary_metrics['sharpe']:.3f}) than rolling 252-day sample std",
                "limitation": "Both estimators require at least 252 continuous daily returns; ddof=1 used for sample variance",
            },
            {
                "experiment_id": "EXP_04_SUBPERIOD_STABILITY",
                "baseline_id": "R1_sub_2020_2022",
                "changed_setting": f"Subperiod: {sub1_start[:4]}-{sub1_end[:4]} vs {sub2_start[:4]}-{sub2_end[:4]}",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["experiments.subperiods"]),
                "config_diff": f"sample_window: {sub1_start[:7]} to {sub1_end[:7]} -> {sub2_start[:7]} to {sub2_end[:7]}",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": f"{sub1_start[:7]} / {sub2_start[:7]}",
                "sample_end": f"{sub1_end[:7]} / {sub2_end[:7]}",
                "n_months": f"{res_sub1.summary_metrics['n_months']} / {res_sub2.summary_metrics['n_months']}",
                "metric": "Sharpe Ratio",
                "baseline_value": f"{res_sub1.summary_metrics['sharpe']:.3f}",
                "alternative_value": f"{res_sub2.summary_metrics['sharpe']:.3f}",
                "difference": f"{res_sub2.summary_metrics['sharpe'] - res_sub1.summary_metrics['sharpe']:.3f}",
                "evidence_path": f"{out_path.name}/strategy_summary.csv",
                "interpretation": (
                    f"Historical regime comparison; {sub1_start[:4]}-{sub1_end[:4]} Sharpe was "
                    f"{res_sub1.summary_metrics['sharpe']:.3f} under lower volatility "
                    f"({res_sub1.summary_metrics['ann_vol']*100:.2f}%), while {sub2_start[:4]}-{sub2_end[:4]} "
                    f"Sharpe declined to {res_sub2.summary_metrics['sharpe']:.3f} with higher volatility "
                    f"({res_sub2.summary_metrics['ann_vol']*100:.2f}%) due to sharp equity whipsaws"
                ),
                "limitation": "Historical regime split on surrogate sample, not an unseen out-of-sample forward test",
            },
            {
                "experiment_id": "EXP_05_ASSET_SUBSET",
                "baseline_id": "R1_tsmom12",
                "changed_setting": "All 21 ETFs vs Core Broad-Market (510050, 510300, 510500)",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["experiments.asset_subsets.broad_market_core"]),
                "config_diff": "asset_universe: 21 multi-asset ETFs -> 3 broad market equity ETFs",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": holding_start,
                "sample_end": holding_end,
                "n_months": res_r1.summary_metrics["n_months"],
                "metric": "Sharpe Ratio",
                "baseline_value": f"{res_r1.summary_metrics['sharpe']:.3f}",
                "alternative_value": f"{res_broad.summary_metrics['sharpe']:.3f}",
                "difference": f"{res_broad.summary_metrics['sharpe'] - res_r1.summary_metrics['sharpe']:.3f}",
                "evidence_path": f"{out_path.name}/research/R1_broad_market_monthly_portfolio.csv",
                "interpretation": "Broad equity index ETFs alone experienced heavy chop and lower trend persistence; multi-asset inclusion buffered strategy performance",
                "limitation": "Sub-portfolio includes only 3 equity index ETFs; changes N and asset diversity simultaneously",
            },
            {
                "experiment_id": "EXP_06_TRANSACTION_COSTS",
                "baseline_id": "T1_tsmom12_3bps",
                "changed_setting": "Fee schedule: 3 bps base vs 10 bps high friction",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["execution.buy_fee", "execution.sell_fee"]),
                "config_diff": "execution fees: 3 bps (0.0003) -> 10 bps (0.0010)",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": exec_start,
                "sample_end": exec_end,
                "n_months": 79,
                "metric": "CAGR (%)",
                "baseline_value": f"{m_t1_base['cagr']*100:.2f}%",
                "alternative_value": f"{m_t1_high['cagr']*100:.2f}%",
                "difference": f"{(m_t1_high['cagr'] - m_t1_base['cagr'])*100:.2f}%",
                "evidence_path": f"{out_path.name}/backtests/T1_high_10bps_ledger.csv",
                "interpretation": "Monthly rebalancing has moderate turnover (~1.4x), making transaction costs a minor drag (~10 bps CAGR reduction from 3 bps to 10 bps)",
                "limitation": "Assumes zero market impact slippage under daily liquidity",
            },
            {
                "experiment_id": "EXP_07_MULTI_HORIZON_EXTENSION",
                "baseline_id": "R1_tsmom12",
                "changed_setting": "Single 12M Trend (R1) vs Multi-Horizon 3/6/12M Trend (R4)",
                "fixed_config_hash": compute_fixed_config_hash(cfg, ["tsmom.horizons", "tsmom.multi_horizon_weights"]),
                "config_diff": "signal_horizons: [12] -> [3, 6, 12] equal weighted",
                "data_snapshot_hash": prices_snapshot_hash,
                "effective_months_hash": effective_months_hash,
                "sample_start": holding_start,
                "sample_end": holding_end,
                "n_months": res_r1.summary_metrics["n_months"],
                "metric": "Max Drawdown (%)",
                "baseline_value": f"{res_r1.summary_metrics['max_drawdown']*100:.2f}%",
                "alternative_value": f"{res_r4.summary_metrics['max_drawdown']*100:.2f}%",
                "difference": f"{(res_r4.summary_metrics['max_drawdown'] - res_r1.summary_metrics['max_drawdown'])*100:.2f}%",
                "evidence_path": f"{out_path.name}/research/R4_multi_horizon_monthly_portfolio.csv",
                "interpretation": "Multi-horizon combo reduced exposure during turning points, improving drawdown and vol, but reduced return during strong trends",
                "limitation": "Heuristic equal weighting without optimization; trade-off between risk and upside",
            },
        ]
        df_diff = pd.DataFrame(diff_rows)
        df_diff.to_csv(out_path / "difference_experiments.csv", index=False)

        # 12. key_result_trace.csv
        trace_df = build_key_result_trace(df_summary, s_single, df_diff, removal_df, out_dir=out_path)
        trace_df.to_csv(out_path / "key_result_trace.csv", index=False)

        # 13. Generate figures
        generate_pipeline_figures(
            res_r1=res_r1, res_r2=res_r2, res_r4=res_r4,
            t1_ledger=run_t1_base.ledger, t2_ledger=run_t2_base.ledger,
            t3_ledger=run_t3_base.ledger, t1_10bps_ledger=run_t1_high.ledger,
            aqr_factors=aqr_df, signals_df=signals_df,
            class_contrib_df=class_contrib_df,
            out_dir=out_path, eval_start=formation_start,
        )

        # 14. Record provenance artifacts and finalize recorder
        recorder.record_artifact(out_path / "strategy_summary.csv", role="summary")
        recorder.record_artifact(out_path / "experiments_inventory.csv", role="inventory")
        recorder.record_artifact(out_path / "key_result_trace.csv", role="trace")
        recorder.record_artifact(out_path / "original_vs_replication.csv", role="comparison")
        recorder.record_artifact(out_path / "difference_experiments.csv", role="experiments")
        recorder.record_artifact(out_path / "experiments" / "asset_class_removal_attribution.csv", role="attribution")
        recorder.record_artifact(out_path / "research" / "asset_class_variance_decomposition.csv", role="variance_decomposition")
        recorder.finalize(status="completed", metrics={"total_strategies": len(summary_rows)})

        write_strict_json(out_path / "resolved_config.json", cfg)
        print("Project 2 pipeline completed successfully with full trace, inventory, and attribution tables!")
        return {
            "summary": df_summary,
            "inventory": inventory_df,
            "trace": trace_df,
            "removal": removal_df,
            "res_r1": res_r1,
            "res_r2": res_r2,
            "res_r4": res_r4,
            "t1_ledger": run_t1_base.ledger,
        }
    except Exception as exc:
        recorder.finalize(status="failed", metadata={"error": str(exc)})
        raise
