"""Project 3 Factor calculation engine: momentum, path efficiency, and combinations."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd


def calculate_er(
    prices: np.ndarray | Sequence[float] | pd.Series,
    window: int,
    tol: float = 1e-12,
) -> Tuple[float, bool]:
    """Calculate Perry Kaufman's Efficiency Ratio (ER) over trailing window.
    
    Parameters
    ----------
    prices : array-like
        Chronological prices of length >= window + 1 (oldest to newest).
    window : int
        Number of daily return intervals (e.g., 63 or 126).
    tol : float
        Numerical tolerance for floating point bounds.
        
    Returns
    -------
    er : float
        Efficiency ratio in [0, 1].
    is_flat : bool
        True if path was completely flat (total price movement is zero).
    """
    arr = np.asarray(prices, dtype=float)
    if len(arr) < window + 1:
        return np.nan, False
    
    # Slice the last window + 1 prices
    sub = arr[-(window + 1):]
    if np.any(np.isnan(sub)) or np.any(sub <= 0):
        return np.nan, False
    
    # Daily log returns
    log_rets = np.diff(np.log(sub))
    net_change = abs(float(np.sum(log_rets)))
    total_change = float(np.sum(np.abs(log_rets)))
    
    if total_change == 0.0:
        return 0.0, True  # Flat path
    
    er = net_change / total_change
    if er < -tol or er > 1.0 + tol:
        raise ValueError(f"Efficiency Ratio {er} severely out of bounds [0, 1]")
    
    return float(np.clip(er, 0.0, 1.0)), False


def winsorize_and_zscore(
    series: pd.Series,
    std_n: float = 3.0,
    eps: float = 1e-12,
) -> pd.Series:
    """Winsorize series to mean +/- std_n * std (ddof=0) and cross-sectionally z-score.
    
    Parameters
    ----------
    series : pd.Series
        Cross-sectional factor values for a given date.
    std_n : float
        Multiplier for winsorization bounds (default 3.0).
    eps : float
        Threshold below which standard deviation is considered zero.
        
    Returns
    -------
    pd.Series
        Standardized scores with mean=0 and std=1, or NaN if std < eps.
    """
    res = pd.Series(index=series.index, dtype=float)
    valid = series.dropna()
    if len(valid) < 2:
        return res
    
    vals = valid.to_numpy(dtype=float)
    mu = float(np.mean(vals))
    sigma = float(np.std(vals, ddof=0))
    
    if sigma < eps:
        # Cross-sectional variance degenerate
        return res
    
    lower = mu - std_n * sigma
    upper = mu + std_n * sigma
    clipped = np.clip(vals, lower, upper)
    
    mu_win = float(np.mean(clipped))
    sigma_win = float(np.std(clipped, ddof=0))
    if sigma_win < eps:
        return res
    
    z = (clipped - mu_win) / sigma_win
    res.loc[valid.index] = z
    return res


def compute_monthly_factors_for_panel(
    panel: pd.DataFrame,
    month_ends: List[pd.Timestamp],
    calendar_dates: List[pd.Timestamp],
    er_window_f1: int = 63,
    er_window_f2: int = 126,
    min_vol_days: int = 252,
    min_lookback_months: int = 13,
    min_qualified_assets: int = 6,
) -> Dict[str, Any]:
    """Compute monthly factors A, A0, F1, F2, F3, and C for all month-ends.
    
    Parameters
    ----------
    panel : pd.DataFrame
        Daily panel with ['date', 'asset', 'close_adj', 'open_adj'].
    month_ends : list of pd.Timestamp
        All chronological market month ends.
    calendar_dates : list of pd.Timestamp
        All active trading dates.
    """
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    assert panel["date"].max() <= pd.Timestamp("2024-12-31"), (
        f"P5 Quarantine Violation: Panel max date {panel['date'].max()} exceeds 2024-12-31"
    )
    piv_close = panel.pivot(index="date", columns="asset", values="close_adj").sort_index()
    piv_open = panel.pivot(index="date", columns="asset", values="open_adj").sort_index()
    
    # Store results
    records = []
    flat_path_records = []
    coverage_records = []
    
    month_ends = sorted(month_ends)
    m_idx_map = {m: i for i, m in enumerate(month_ends)}
    
    for t in month_ends:
        idx = m_idx_map[t]
        if idx < 12:
            # Need 12 months prior
            continue
        
        t_minus_12 = month_ends[idx - 12]
        
        # Check assets qualified at date t
        # Criteria:
        # 1. Price available at t and t_minus_12
        # 2. At least min_vol_days continuous daily close prices up to t
        qual_assets = []
        raw_m12 = {}
        raw_er63 = {}
        raw_er126 = {}
        raw_f1 = {}
        raw_f2 = {}
        raw_f3 = {}
        raw_a0 = {}
        
        for asset in piv_close.columns:
            s_close = piv_close[asset].loc[:t].dropna()
            if len(s_close) < min_vol_days:
                continue
            
            p_t = s_close.get(t, np.nan)
            p_t12 = piv_close[asset].get(t_minus_12, np.nan)
            if np.isnan(p_t) or np.isnan(p_t12) or p_t <= 0 or p_t12 <= 0:
                continue
            
            # Check continuous daily observations up to t
            # Look backwards from t in active trading days
            # To ensure no missing dates, check trailing trading days
            trailing_dates = [d for d in calendar_dates if d <= t]
            if len(trailing_dates) < min_vol_days:
                continue
            
            # Sub-series on trailing trading dates
            tail_dates = trailing_dates[-min_vol_days:]
            tail_prices = piv_close[asset].reindex(tail_dates)
            if tail_prices.isna().any():
                continue
            
            # All conditions met!
            m12 = float(p_t / p_t12 - 1.0)
            a0 = 1.0 if m12 > 0 else (-1.0 if m12 < 0 else 0.0)
            
            # ER 63 and ER 126
            er63, is_flat_63 = calculate_er(tail_prices.values, er_window_f1)
            er126, is_flat_126 = calculate_er(tail_prices.values, er_window_f2)
            
            if np.isnan(er63) or np.isnan(er126):
                continue
            
            if is_flat_63:
                flat_path_records.append({"date": t, "asset": asset, "window": er_window_f1})
            if is_flat_126:
                flat_path_records.append({"date": t, "asset": asset, "window": er_window_f2})
            
            qual_assets.append(asset)
            raw_m12[asset] = m12
            raw_a0[asset] = a0
            raw_er63[asset] = er63
            raw_er126[asset] = er126
            raw_f1[asset] = m12 * er63
            raw_f2[asset] = m12 * er126
            raw_f3[asset] = m12 * (1.0 - er63)
            
        # Detailed reason tracking for excluded assets
        excluded_dict = {}
        for asset in piv_close.columns:
            if asset in qual_assets:
                continue
            s_close = piv_close[asset].loc[:t].dropna()
            if len(s_close) < min_vol_days:
                excluded_dict[asset] = "insufficient_history"
            elif t not in piv_close.index or t_minus_12 not in piv_close.index or np.isnan(piv_close.loc[t, asset]) or np.isnan(piv_close.loc[t_minus_12, asset]):
                excluded_dict[asset] = "missing_12m_price"
            else:
                excluded_dict[asset] = "missing_daily_price_in_window"

        # Single-factor raw availability count on date t
        m12_avail = sum(1 for a in piv_close.columns if t in piv_close.index and t_minus_12 in piv_close.index and not np.isnan(piv_close.loc[t, a]) and not np.isnan(piv_close.loc[t_minus_12, a]))
        er63_avail = sum(1 for a in piv_close.columns if len(piv_close[a].loc[:t].dropna()) >= er_window_f1 + 1)
        er126_avail = sum(1 for a in piv_close.columns if len(piv_close[a].loc[:t].dropna()) >= er_window_f2 + 1)
        flat_count_63 = sum(1 for r in flat_path_records if r["date"] == t and r["window"] == er_window_f1)
        flat_count_126 = sum(1 for r in flat_path_records if r["date"] == t and r["window"] == er_window_f2)

        coverage_records.append({
            "date": t,
            "formation_date": t,
            "total_assets": len(piv_close.columns),
            "qualified_assets": len(qual_assets),
            "coverage_ratio": float(len(qual_assets) / len(piv_close.columns)),
            "min_assets_met": len(qual_assets) >= min_qualified_assets,
            "is_sufficient": len(qual_assets) >= min_qualified_assets,
            "raw_m12_count": m12_avail,
            "raw_er63_count": er63_avail,
            "raw_er126_count": er126_avail,
            "raw_f1_count": len(qual_assets),
            "raw_f2_count": len(qual_assets),
            "raw_f3_count": len(qual_assets),
            "raw_a0_count": m12_avail,
            "flat_path_count_63": flat_count_63,
            "flat_path_count_126": flat_count_126,
            "excluded_count": len(piv_close.columns) - len(qual_assets),
            "excluded_reasons": json.dumps(excluded_dict) if excluded_dict else "none",
        })
        
        if len(qual_assets) < min_qualified_assets:
            continue
        
        # Standardize cross-sectionally
        s_m12 = pd.Series(raw_m12)
        s_f1 = pd.Series(raw_f1)
        s_f2 = pd.Series(raw_f2)
        s_f3 = pd.Series(raw_f3)
        s_a0 = pd.Series(raw_a0)
        s_er63 = pd.Series(raw_er63)
        s_er126 = pd.Series(raw_er126)
        
        # Z-scores
        z_A = winsorize_and_zscore(s_m12)
        z_B = winsorize_and_zscore(s_f1)
        z_F2 = winsorize_and_zscore(s_f2)
        z_F3 = winsorize_and_zscore(s_f3)
        
        # Combo C
        c_raw = 0.5 * z_A + 0.5 * z_B
        z_C = winsorize_and_zscore(c_raw)
        
        for asset in qual_assets:
            records.append({
                "formation_date": t,
                "asset": asset,
                "m12_raw": raw_m12[asset],
                "a0_raw": raw_a0[asset],
                "er63_raw": raw_er63[asset],
                "er126_raw": raw_er126[asset],
                "f1_raw": raw_f1[asset],
                "f2_raw": raw_f2[asset],
                "f3_raw": raw_f3[asset],
                "A": z_A.get(asset, np.nan),
                "B": z_B.get(asset, np.nan),
                "F2": z_F2.get(asset, np.nan),
                "F3": z_F3.get(asset, np.nan),
                "C": z_C.get(asset, np.nan),
                "A0": s_a0.get(asset, np.nan),
            })
            
    df_factors = pd.DataFrame(records)
    df_coverage = pd.DataFrame(coverage_records)
    df_flat = pd.DataFrame(flat_path_records)
    
    # Also create standard long table: date, asset, factor, value
    long_list = []
    if not df_factors.empty:
        for factor_name in ["A", "B", "C", "F2", "F3", "A0"]:
            sub = df_factors[["formation_date", "asset", factor_name]].copy()
            sub.columns = ["date", "asset", "value"]
            sub["factor"] = factor_name
            long_list.append(sub[["date", "asset", "factor", "value"]])
    df_long = pd.concat(long_list, ignore_index=True) if long_list else pd.DataFrame(columns=["date", "asset", "factor", "value"])
    
    return {
        "factors": df_factors,
        "factors_long": df_long,
        "coverage": df_coverage,
        "flat_paths": df_flat,
    }


def compute_daily_cross_sectional_correlations(
    panel: pd.DataFrame,
    calendar_dates: List[pd.Timestamp],
    month_ends: List[pd.Timestamp],
    er_window: int = 63,
    min_assets: int = 6,
) -> pd.DataFrame:
    """Compute daily cross-sectional correlation between continuous momentum and F1.
    
    As required by professor PDF page 6:
    For any trading day d, continuous momentum is:
        m12(i,d) = P(i,d) / P(i, month-end 12 months prior to month(d)) - 1
    and ER_63(i,d) uses trailing 63 trading days up to d.
    F1(i,d) = m12(i,d) * ER_63(i,d).
    """
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    assert panel["date"].max() <= pd.Timestamp("2024-12-31"), (
        f"P5 Quarantine Violation: Panel max date {panel['date'].max()} exceeds 2024-12-31"
    )
    piv_close = panel.pivot(index="date", columns="asset", values="close_adj").sort_index()
    
    month_ends = sorted(month_ends)
    # Map calendar month (Period('M')) to its month end date
    m_to_end = {m.to_period("M"): m for m in month_ends}
    
    corr_records = []
    calendar_dates = sorted(calendar_dates)
    
    for d in calendar_dates:
        cur_period = d.to_period("M")
        prior_12_period = cur_period - 12
        if prior_12_period not in m_to_end:
            continue
        
        t_ref = m_to_end[prior_12_period]
        if t_ref not in piv_close.index or d not in piv_close.index:
            continue
        
        # Trailing trading days up to d
        sub_dates = [dt for dt in calendar_dates if dt <= d]
        if len(sub_dates) < er_window + 1:
            continue
        
        er_dates = sub_dates[-(er_window + 1):]
        tail_prices = piv_close.reindex(er_dates)
        
        m12_vals = {}
        f1_vals = {}
        
        for asset in piv_close.columns:
            p_d = piv_close.loc[d, asset]
            p_ref = piv_close.loc[t_ref, asset]
            if np.isnan(p_d) or np.isnan(p_ref) or p_d <= 0 or p_ref <= 0:
                continue
            
            p_series = tail_prices[asset].dropna()
            if len(p_series) < er_window + 1:
                continue
            
            er, _ = calculate_er(p_series.values, er_window)
            if np.isnan(er):
                continue
            
            m12 = float(p_d / p_ref - 1.0)
            m12_vals[asset] = m12
            f1_vals[asset] = m12 * er
            
        if len(m12_vals) < min_assets:
            continue
        
        s_m = pd.Series(m12_vals)
        s_f = pd.Series(f1_vals)
        
        p_corr = float(s_m.corr(s_f, method="pearson"))
        s_corr = float(s_m.corr(s_f, method="spearman"))
        
        corr_records.append({
            "date": d,
            "n_assets": len(m12_vals),
            "pearson_corr": p_corr,
            "spearman_corr": s_corr,
            "is_month_end": d in month_ends,
        })
        
    return pd.DataFrame(corr_records)
