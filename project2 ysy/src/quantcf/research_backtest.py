"""Research-mode backtest engine implementing paper-style theoretical portfolios.

Implements:
1. R1: 12-month TSMOM with ex-ante volatility scaling (primary replication).
2. R2: Passive long portfolio with identical risk budget (benchmark).
3. R3: Equal nominal weights (s/N without volatility scaling).
4. R4: Multi-horizon (3/6/12m) trend combination (autonomous extension).
5. Bridge: Long-only theoretical portfolio isolating shorting constraint.
6. Estimator comparison: Rolling sample volatility vs EWMA.
7. Single-asset strategy returns for Fig. 2 replication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


@dataclass
class ResearchBacktestResult:
    """Encapsulates theoretical research backtest outputs."""

    strategy_name: str
    mode: str
    monthly_portfolio: pd.DataFrame
    monthly_weights: pd.DataFrame
    asset_contributions: pd.DataFrame
    single_asset_returns: pd.DataFrame
    single_asset_metrics: pd.DataFrame
    summary_metrics: Dict[str, Any]


def calculate_monthly_metrics(
    returns_series: pd.Series,
    strict_continuity: bool = True,
) -> Dict[str, Any]:
    """Calculate standard monthly metrics matching paper standards (annualized by 12).
    
    Includes initial capital (1.0) in high-water mark / drawdown computation,
    preserves correct algebraic sign for Calmar ratio (negative CAGR yields negative Calmar),
    and validates monthly index continuity to prevent compounding across gaps.
    """
    if returns_series is None or len(returns_series) == 0:
        return {
            "n_months": 0,
            "ann_mean": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "cagr": np.nan,
            "max_drawdown": np.nan,
            "calmar": np.nan,
            "skewness": np.nan,
            "positive_ratio": np.nan,
            "is_continuous": False,
        }

    has_nans = bool(returns_series.isna().any())
    s_clean = returns_series.dropna()
    n = len(s_clean)
    if n == 0:
        return {
            "n_months": 0,
            "ann_mean": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "cagr": np.nan,
            "max_drawdown": np.nan,
            "calmar": np.nan,
            "skewness": np.nan,
            "positive_ratio": np.nan,
            "is_continuous": False,
        }

    mean_m = float(s_clean.mean())
    vol_m = float(s_clean.std(ddof=1)) if n > 1 else 0.0
    ann_mean = mean_m * 12.0
    ann_vol = vol_m * np.sqrt(12.0)
    sharpe = (ann_mean / ann_vol) if ann_vol > 1e-8 else (0.0 if ann_vol == 0 and ann_mean == 0 else np.nan)

    # Monthly calendar continuity check
    is_continuous = True
    gap_reason = None
    if has_nans:
        is_continuous = False
        gap_reason = "Missing return observations (NaN) detected in monthly sequence."
    elif isinstance(returns_series.index, pd.DatetimeIndex):
        if returns_series.index.has_duplicates:
            is_continuous = False
            gap_reason = "Duplicate dates detected in monthly DatetimeIndex."
        elif not returns_series.index.is_monotonic_increasing:
            is_continuous = False
            gap_reason = "DatetimeIndex is not monotonically increasing."
        else:
            periods = returns_series.index.to_period("M")
            if len(periods) > 1:
                diffs = (periods[1:] - periods[:-1]).map(lambda x: x.n if hasattr(x, "n") else 1)
                if (diffs != 1).any():
                    is_continuous = False
                    gap_reason = "Non-consecutive months detected in monthly DatetimeIndex."
    else:
        # If not already a DatetimeIndex, attempt to parse index if string dates; otherwise reject continuity
        try:
            parsed_idx = pd.to_datetime(returns_series.index)
            periods = parsed_idx.to_period("M")
            if len(periods) > 1:
                diffs = (periods[1:] - periods[:-1]).map(lambda x: x.n if hasattr(x, "n") else 1)
                if (diffs != 1).any():
                    is_continuous = False
                    gap_reason = "Non-consecutive months detected in parsed index."
        except Exception:
            is_continuous = False
            gap_reason = "Series index is not a DatetimeIndex; monthly continuity cannot be verified."

    if not is_continuous and strict_continuity:
        cagr = np.nan
        max_dd = np.nan
        calmar = np.nan
        total_compound_ret = np.nan
    else:
        vals = s_clean.values
        has_ruin = bool(np.any(vals <= -1.0))
        # Form wealth series with initial capital 1.0 at index 0
        cum_wealth = np.insert(np.cumprod(1.0 + vals), 0, 1.0)
        peak = np.maximum.accumulate(cum_wealth)
        dd = (cum_wealth - peak) / peak
        max_dd = float(np.min(dd))
        end_val = float(cum_wealth[-1])

        if has_ruin or end_val <= 0:
            cagr = np.nan
            max_dd = -1.0
            calmar = np.nan
            total_compound_ret = -1.0
        else:
            cagr = float((end_val ** (12.0 / n)) - 1.0)
            total_compound_ret = float(end_val - 1.0)
            # Calmar preserves sign: negative CAGR produces negative Calmar
            calmar = float(cagr / abs(max_dd)) if (pd.notnull(cagr) and max_dd < -1e-6) else np.nan

    skew = float(s_clean.skew()) if n > 2 else 0.0
    pos_ratio = float((s_clean > 0).mean())

    return {
        "n_months": n,
        "mean_monthly": mean_m,
        "vol_monthly": vol_m,
        "ann_mean": ann_mean,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "skewness": skew,
        "positive_ratio": pos_ratio,
        "total_compound_return": total_compound_ret if is_continuous or not strict_continuity else np.nan,
        "is_continuous": is_continuous,
        "gap_warning": gap_reason,
    }


def run_research_backtest(
    signals_df: pd.DataFrame,
    strategy_mode: str = "tsmom12",
    target_volatility: float = 0.40,
    min_eligible_assets: int = 6,
    use_sample_vol: bool = False,
    asset_subset: Optional[List[str]] = None,
    evaluation_start: Optional[pd.Timestamp | str] = None,
    evaluation_end: Optional[pd.Timestamp | str] = None,
) -> ResearchBacktestResult:
    """Run monthly research-mode backtest.
    
    Parameters
    ----------
    signals_df : pd.DataFrame
        Output of `build_monthly_tsmom_dataset['signals_df']`.
    strategy_mode : str
        One of:
        - 'tsmom12': Eq. (5) 12m TSMOM with 0.40/sigma scaling (R1).
        - 'passive_long': Benchmark with signs fixed to +1 and 0.40/sigma scaling (R2).
        - 'equal_nominal': 12m TSMOM with s/N equal nominal weighting (R3).
        - 'multi_horizon': 3/6/12m equal weighted combination with 0.40/sigma scaling (R4).
        - 'long_only_bridge': max(s12, 0) with 0.40/sigma scaling (Bridge).
    """
    df = signals_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    if evaluation_start is not None:
        df = df[df["date"] >= pd.to_datetime(evaluation_start)]
    if evaluation_end is not None:
        df = df[df["date"] <= pd.to_datetime(evaluation_end)]

    if asset_subset is not None:
        df = df[df["asset"].isin(asset_subset)]

    dates = sorted(df["date"].unique())

    port_records = []
    weight_records = []
    contrib_records = []
    single_asset_records = []

    vol_col = "sigma_sample" if use_sample_vol else "sigma_ewma"

    for dt in dates:
        dt_df = df[df["date"] == dt].copy()
        dt_df["vol_used"] = dt_df[vol_col]
        
        # 1. Formation eligibility: depends STRICTLY on formation-time data
        formation_col = "formation_eligible" if "formation_eligible" in dt_df.columns else "is_eligible"
        valid_formation_mask = (
            dt_df[formation_col]
            & dt_df["vol_used"].notnull()
            & (dt_df["vol_used"] > 0)
        )
        formation_df = dt_df[valid_formation_mask].copy()
        n_formation = len(formation_df)
        is_qualified = n_formation >= min_eligible_assets

        if not is_qualified:
            # Active qualification rule: insufficient assets at formation date -> Hold 100% Cash
            next_dt = dt_df["next_month_date"].iloc[0] if (len(dt_df) > 0 and "next_month_date" in dt_df.columns and pd.notnull(dt_df["next_month_date"].iloc[0])) else ((pd.to_datetime(dt).to_period("M") + 1).to_timestamp(how="end").normalize())
            port_records.append({
                "formation_date": dt,
                "holding_end_date": next_dt,
                "n_eligible": n_formation,
                "is_qualified": False,
                "is_valid_month": True,
                "status": "INSUFFICIENT_ASSETS_CASH",
                "portfolio_return": 0.0,
                "gross_exposure": 0.0,
                "net_exposure": 0.0,
                "max_single_exposure": 0.0,
            })
            continue

        # 2. Compute formation target weights using N_m = n_formation (strictly at formation time)
        if strategy_mode == "tsmom12":
            signals = formation_df["s12"].values
            weights = (1.0 / n_formation) * signals * (target_volatility / formation_df["vol_used"].values)
        elif strategy_mode == "passive_long":
            signals = np.ones(n_formation, dtype=float)
            weights = (1.0 / n_formation) * signals * (target_volatility / formation_df["vol_used"].values)
        elif strategy_mode == "equal_nominal":
            signals = formation_df["s12"].values
            weights = (1.0 / n_formation) * signals
        elif strategy_mode == "multi_horizon":
            signals = formation_df["signal_multi"].values
            weights = (1.0 / n_formation) * signals * (target_volatility / formation_df["vol_used"].values)
        elif strategy_mode == "long_only_bridge":
            signals = np.maximum(formation_df["s12"].values, 0.0)
            weights = (1.0 / n_formation) * signals * (target_volatility / formation_df["vol_used"].values)
        else:
            raise ValueError(f"Unknown strategy_mode: {strategy_mode}")

        formation_df["weight"] = weights
        formation_df["signal_used"] = signals

        # Single-asset strategy weights (NOT divided by N_m)
        single_weights = signals * (target_volatility / formation_df["vol_used"].values) if strategy_mode != "equal_nominal" else signals
        formation_df["single_weight"] = single_weights

        # 3. Inspect holding period results (ex-post evaluation)
        # Check whether any asset in the formation portfolio is missing its subsequent holding return
        missing_holding_assets = formation_df[formation_df["next_month_ret"].isnull()]["asset"].tolist()
        has_missing_holding = len(missing_holding_assets) > 0
        next_dt = formation_df["next_month_date"].iloc[0] if ("next_month_date" in formation_df.columns and len(formation_df) > 0 and pd.notnull(formation_df["next_month_date"].iloc[0])) else ((pd.to_datetime(dt).to_period("M") + 1).to_timestamp(how="end").normalize())

        if has_missing_holding:
            # Cannot observe full portfolio holding return; do NOT shrink N_m or fill zero silently
            port_records.append({
                "formation_date": dt,
                "holding_end_date": next_dt,
                "n_eligible": n_formation,
                "is_qualified": True,
                "is_valid_month": False,
                "status": f"MISSING_HOLDING_RETURN: {missing_holding_assets}",
                "portfolio_return": np.nan,
                "gross_exposure": float(np.sum(np.abs(weights))),
                "net_exposure": float(np.sum(weights)),
                "max_single_exposure": float(np.max(np.abs(weights))) if len(weights) > 0 else 0.0,
            })
            for _, row in formation_df.iterrows():
                weight_records.append({
                    "date": dt,
                    "formation_date": dt,
                    "holding_end_date": next_dt,
                    "asset": row["asset"],
                    "weight": row["weight"],
                    "signal": row["signal_used"],
                    "vol": row["vol_used"],
                })
            continue

        # Holding returns are fully observed
        formation_df["contrib"] = formation_df["weight"] * formation_df["next_month_ret"]
        formation_df["single_strategy_return"] = formation_df["single_weight"] * formation_df["next_month_ret"]

        for _, row in formation_df.iterrows():
            weight_records.append({
                "date": dt,
                "formation_date": dt,
                "holding_end_date": next_dt,
                "asset": row["asset"],
                "weight": row["weight"],
                "signal": row["signal_used"],
                "vol": row["vol_used"],
            })
            contrib_records.append({
                "date": dt,
                "formation_date": dt,
                "holding_end_date": next_dt,
                "asset": row["asset"],
                "contrib": row["contrib"],
            })
            single_asset_records.append({
                "date": dt,
                "formation_date": dt,
                "holding_end_date": next_dt,
                "asset": row["asset"],
                "single_strategy_return": row["single_strategy_return"],
                "asset_raw_return": row["next_month_ret"],
            })

        port_ret = float(formation_df["contrib"].sum())
        gross_exp = float(np.sum(np.abs(weights)))
        net_exp = float(np.sum(weights))
        max_exp = float(np.max(np.abs(weights))) if len(weights) > 0 else 0.0

        port_records.append({
            "formation_date": dt,
            "holding_end_date": next_dt,
            "n_eligible": n_formation,
            "is_qualified": True,
            "is_valid_month": True,
            "status": "COMPLETE",
            "portfolio_return": port_ret,
            "gross_exposure": gross_exp,
            "net_exposure": net_exp,
            "max_single_exposure": max_exp,
        })

    df_port = pd.DataFrame(port_records)
    df_weights = pd.DataFrame(weight_records)
    df_contrib = pd.DataFrame(contrib_records)
    df_single = pd.DataFrame(single_asset_records)

    # Compute overall portfolio summary metrics
    if len(df_port) > 0:
        df_port = df_port.sort_values("holding_end_date").reset_index(drop=True)
        port_dates = pd.to_datetime(df_port["holding_end_date"])
        port_ret_series = pd.Series(
            df_port["portfolio_return"].values,
            index=port_dates,
            name="portfolio_return",
        )
        summary_m = calculate_monthly_metrics(port_ret_series)
        summary_m["mean_gross_exposure"] = float(df_port["gross_exposure"].mean())
        summary_m["mean_net_exposure"] = float(df_port["net_exposure"].mean())
        summary_m["mean_eligible_assets"] = float(df_port["n_eligible"].mean())
    else:
        summary_m = {"n_months": 0}

    # Compute per-asset metrics for Fig. 2
    single_metrics_list = []
    if len(df_single) > 0:
        for asset, grp in df_single.groupby("asset"):
            grp_sorted = grp.sort_values("holding_end_date").reset_index(drop=True)
            holding_dates = pd.to_datetime(grp_sorted["holding_end_date"])
            strat_series = pd.Series(
                grp_sorted["single_strategy_return"].values,
                index=holding_dates,
                name="single_strategy_return",
            )
            m = calculate_monthly_metrics(strat_series)
            m["asset"] = asset
            # Also calculate passive buy-and-hold metrics
            raw_series = pd.Series(
                grp_sorted["asset_raw_return"].values,
                index=holding_dates,
                name="asset_raw_return",
            )
            m_raw = calculate_monthly_metrics(raw_series)
            m["raw_ann_mean"] = m_raw["ann_mean"]
            m["raw_ann_vol"] = m_raw["ann_vol"]
            m["raw_sharpe"] = m_raw["sharpe"]
            single_metrics_list.append(m)

    df_single_metrics = pd.DataFrame(single_metrics_list)
    if len(df_single_metrics) > 0:
        df_single_metrics = df_single_metrics.sort_values("sharpe", ascending=False).reset_index(drop=True)

    return ResearchBacktestResult(
        strategy_name=strategy_mode,
        mode="research",
        monthly_portfolio=df_port,
        monthly_weights=df_weights,
        asset_contributions=df_contrib,
        single_asset_returns=df_single,
        single_asset_metrics=df_single_metrics,
        summary_metrics=summary_m,
    )

