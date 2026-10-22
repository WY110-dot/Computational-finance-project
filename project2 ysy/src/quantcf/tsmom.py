"""Time Series Momentum (TSMOM) signal and volatility calculation module.

Implements pure mathematical functions according to Moskowitz, Ooi & Pedersen (2012):
1. Natural month-end detection and return computation.
2. Exponentially weighted moving average (EWMA) volatility with finite-history weights.
3. 12-month and multi-horizon (3/6/12m) trend signals.
4. Dynamic qualification and eligibility checks.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd


LAMBDA_DEFAULT = 60.0 / 61.0  # ~0.9836065573770492
ANN_FACTOR_VOL = 261.0        # Annualization factor for volatility in paper


def calculate_ewma_mean_and_variance(
    returns: np.ndarray | List[float],
    decay: float = LAMBDA_DEFAULT,
) -> Tuple[float, float]:
    """Calculate finite-history exponentially weighted mean and variance.
    
    Parameters
    ----------
    returns : array-like
        Chronological sequence of daily returns: oldest at index 0, newest at index -1.
    decay : float
        Decay factor lambda (default 60/61).
        
    Returns
    -------
    (mean, variance) : Tuple[float, float]
    
    Notes
    -----
    Indexing: j=0 is the newest observation (index -1 in returns),
    j=n-1 is the oldest observation (index 0 in returns).
    Weights: a_j = (1 - lambda) * lambda^j / (1 - lambda^n).
    """
    arr = np.asarray(returns, dtype=float)
    if len(arr) == 0:
        return np.nan, np.nan

    n = len(arr)
    # j from 0 (newest) to n-1 (oldest)
    j = np.arange(n, dtype=float)
    
    # Unnormalized weights: lambda^j
    weights_unnorm = np.power(decay, j)
    # Sum of weights: (1 - lambda^n) / (1 - lambda) if decay != 1
    if abs(decay - 1.0) < 1e-12:
        weights = np.ones(n) / n
    else:
        norm_factor = (1.0 - np.power(decay, n)) / (1.0 - decay)
        weights = weights_unnorm / norm_factor

    # arr[::-1] reverses so index 0 is the newest return, aligning with j
    rev_arr = arr[::-1]
    mean = float(np.sum(weights * rev_arr))
    variance = float(np.sum(weights * np.square(rev_arr - mean)))
    return mean, variance


def calculate_ewma_volatility(
    returns: np.ndarray | List[float],
    decay: float = LAMBDA_DEFAULT,
    min_days: int = 252,
    ann_factor: float = ANN_FACTOR_VOL,
) -> float:
    """Calculate annualized EWMA volatility.
    
    Requires at least `min_days` continuous daily returns.
    """
    arr = np.asarray(returns, dtype=float)
    # Must have no NaNs and at least min_days
    if len(arr) < min_days or np.any(np.isnan(arr)):
        return np.nan

    _, var = calculate_ewma_mean_and_variance(arr, decay=decay)
    if var <= 0 or np.isnan(var):
        return np.nan
    return float(np.sqrt(ann_factor * var))


def calculate_sample_volatility(
    returns: np.ndarray | List[float],
    min_days: int = 252,
    ann_factor: float = ANN_FACTOR_VOL,
) -> float:
    """Calculate alternative rolling sample standard deviation for attribution.
    
    Standard unbiased sample variance (ddof=1) calculated strictly over the
    rolling last `min_days` (default 252) continuous daily returns, annualized
    by ann_factor (default 261).
    """
    arr = np.asarray(returns, dtype=float)
    if len(arr) < min_days:
        return np.nan
    sub = arr[-min_days:]
    if np.any(np.isnan(sub)):
        return np.nan
    var = float(np.var(sub, ddof=1))
    if var <= 0 or np.isnan(var):
        return np.nan
    return float(np.sqrt(ann_factor * var))


def get_market_month_ends(
    trading_dates: Iterable[pd.Timestamp | str],
    evaluation_end: Optional[pd.Timestamp | str] = None,
) -> List[pd.Timestamp]:
    """Find the exact market calendar month-end trading days.
    
    Parameters
    ----------
    trading_dates : Iterable of dates
        Union calendar of all active trading days.
    evaluation_end : optional date
        Cutoff date; months with month-ends after this date are excluded.
    """
    dates = pd.to_datetime(pd.Series(list(trading_dates))).drop_duplicates().sort_values()
    if evaluation_end is not None:
        eval_cutoff = pd.to_datetime(evaluation_end)
        dates = dates[dates <= eval_cutoff]

    # Group by (year, month) and take the maximum trading date
    df_dates = pd.DataFrame({"date": dates, "year_month": dates.dt.to_period("M")})
    month_ends = df_dates.groupby("year_month")["date"].max().tolist()
    return sorted(month_ends)


def calculate_momentum_sign(ret: float) -> int:
    """Map cumulative return to momentum direction: +1, -1, or 0."""
    if np.isnan(ret):
        return 0
    if ret > 0:
        return 1
    elif ret < 0:
        return -1
    return 0


def calculate_multi_horizon_signal(
    s3: float | int,
    s6: float | int,
    s12: float | int,
    weights: Optional[Sequence[float]] = None,
) -> float:
    """Combine 3m, 6m, 12m momentum signs into multi-horizon signal a_{i,m}.
    
    Parameters
    ----------
    s3, s6, s12 : float or int
        Momentum directions (+1, -1, 0) for 3m, 6m, 12m.
    weights : Optional[Sequence[float]]
        Weights for (s3, s6, s12). If provided, must be length 3, finite,
        non-negative, and sum to 1.0 within 1e-4. Default is equal weighting [1/3, 1/3, 1/3].
    """
    if np.isnan(s3) or np.isnan(s6) or np.isnan(s12):
        return np.nan
    if weights is None:
        return float((s3 + s6 + s12) / 3.0)
    if len(weights) != 3:
        raise ValueError(f"Multi-horizon weights must have length 3, got {len(weights)}")
    w0, w1, w2 = float(weights[0]), float(weights[1]), float(weights[2])
    if not (np.isfinite(w0) and np.isfinite(w1) and np.isfinite(w2)):
        raise ValueError(f"Multi-horizon weights must be finite, got {weights}")
    if w0 < 0 or w1 < 0 or w2 < 0:
        raise ValueError(f"Multi-horizon weights must be non-negative, got {weights}")
    if abs(w0 + w1 + w2 - 1.0) > 1e-4:
        raise ValueError(f"Multi-horizon weights must sum to 1.0, got sum={w0+w1+w2}")
    return float(w0 * s3 + w1 * s6 + w2 * s12)


def extract_continuous_daily_returns_before_date(
    daily_returns_series: pd.Series,
    cutoff_date: pd.Timestamp,
    max_days: Optional[int] = None,
) -> np.ndarray:
    """Extract continuous valid daily returns up to cutoff_date.
    
    If there is any missing return or gap in the series, the continuous
    segment stops at the break.
    """
    sub = daily_returns_series.loc[:cutoff_date]
    if len(sub) == 0:
        return np.array([], dtype=float)

    # Work backwards from the newest date
    vals = sub.values[::-1]
    valid_count = 0
    for v in vals:
        if np.isnan(v):
            break
        valid_count += 1
        if max_days is not None and valid_count >= max_days:
            break

    if valid_count == 0:
        return np.array([], dtype=float)

    # Return chronological order: oldest to newest
    return vals[:valid_count][::-1]


def build_monthly_tsmom_dataset(
    daily_df: pd.DataFrame,
    evaluation_start: pd.Timestamp | str = "2020-02-01",
    evaluation_end: pd.Timestamp | str = "2026-08-31",
    min_vol_days: int = 252,
    vol_decay: float = LAMBDA_DEFAULT,
    vol_ann_factor: float = ANN_FACTOR_VOL,
    target_volatility: float = 0.40,
    min_eligible_assets: int = 6,
    multi_horizon_weights: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Construct full monthly signals, volatilities, and eligibility panel.
    
    Parameters
    ----------
    daily_df : pd.DataFrame
        Daily panel containing ['date', 'asset', 'close_adj', 'open_adj', 'ret_total'].
    """
    if multi_horizon_weights is not None:
        if len(multi_horizon_weights) != 3:
            raise ValueError(f"multi_horizon_weights must have length 3, got {len(multi_horizon_weights)}")
        for w in multi_horizon_weights:
            if not np.isfinite(w) or w < 0 or abs(w - 1.0 / 3.0) > 1e-3:
                raise ValueError(
                    f"Unsupported multi_horizon_weights: {multi_horizon_weights}. "
                    "This research implementation strictly requires equal multi-horizon weights [1/3, 1/3, 1/3]."
                )

    eval_start_dt = pd.to_datetime(evaluation_start)
    eval_end_dt = pd.to_datetime(evaluation_end)

    # 1. Market month ends
    all_dates = pd.to_datetime(daily_df["date"]).unique()
    month_ends = get_market_month_ends(all_dates, evaluation_end=eval_end_dt)
    month_end_set = set(month_ends)

    # 2. Daily price pivot matrices
    pvt_adj_close = daily_df.pivot(index="date", columns="asset", values="close_adj").sort_index()
    pvt_adj_open = daily_df.pivot(index="date", columns="asset", values="open_adj").sort_index()
    
    # Calculate daily returns: strictly pct_change with no fill_method
    pvt_daily_ret = pvt_adj_close.pct_change(fill_method=None)

    # Month-end price matrix
    m_prices = pvt_adj_close.loc[pvt_adj_close.index.intersection(month_ends)].sort_index()
    
    assets = sorted(daily_df["asset"].unique())
    records = []

    # Map month end to its index
    for m_idx, m_date in enumerate(month_ends):
        # We need past 12 months (requires 13 continuous month-ends)
        for asset in assets:
            rec = {
                "date": m_date,
                "asset": asset,
                "month_idx": m_idx,
                "eval_eligible": (m_date >= eval_start_dt and m_date <= eval_end_dt),
            }

            # Month-end price
            p_m = m_prices.loc[m_date, asset] if (m_date in m_prices.index and asset in m_prices.columns) else np.nan
            rec["price_adj_close"] = float(p_m) if pd.notnull(p_m) else np.nan

            # 1m, 3m, 6m, 12m historical cumulative returns
            # 1m return
            if m_idx >= 1:
                p_m1 = m_prices.iloc[m_idx - 1][asset]
                rec["ret_1m"] = float(p_m / p_m1 - 1.0) if (pd.notnull(p_m) and pd.notnull(p_m1) and p_m1 > 0) else np.nan
            else:
                rec["ret_1m"] = np.nan

            # 3m return
            if m_idx >= 3:
                # Check all 4 month ends (m-3, m-2, m-1, m) are valid
                window_3 = m_prices.iloc[m_idx - 3 : m_idx + 1][asset]
                if len(window_3) == 4 and window_3.notnull().all() and window_3.iloc[0] > 0:
                    rec["ret_3m"] = float(window_3.iloc[-1] / window_3.iloc[0] - 1.0)
                else:
                    rec["ret_3m"] = np.nan
            else:
                rec["ret_3m"] = np.nan

            # 6m return
            if m_idx >= 6:
                window_6 = m_prices.iloc[m_idx - 6 : m_idx + 1][asset]
                if len(window_6) == 7 and window_6.notnull().all() and window_6.iloc[0] > 0:
                    rec["ret_6m"] = float(window_6.iloc[-1] / window_6.iloc[0] - 1.0)
                else:
                    rec["ret_6m"] = np.nan
            else:
                rec["ret_6m"] = np.nan

            # 12m return
            if m_idx >= 12:
                window_12 = m_prices.iloc[m_idx - 12 : m_idx + 1][asset]
                if len(window_12) == 13 and window_12.notnull().all() and window_12.iloc[0] > 0:
                    rec["ret_12m"] = float(window_12.iloc[-1] / window_12.iloc[0] - 1.0)
                else:
                    rec["ret_12m"] = np.nan
            else:
                rec["ret_12m"] = np.nan

            # Momentum signs
            rec["s3"] = calculate_momentum_sign(rec["ret_3m"]) if pd.notnull(rec["ret_3m"]) else np.nan
            rec["s6"] = calculate_momentum_sign(rec["ret_6m"]) if pd.notnull(rec["ret_6m"]) else np.nan
            rec["s12"] = calculate_momentum_sign(rec["ret_12m"]) if pd.notnull(rec["ret_12m"]) else np.nan

            # Multi-horizon signal
            if pd.notnull(rec["s3"]) and pd.notnull(rec["s6"]) and pd.notnull(rec["s12"]):
                rec["signal_multi"] = calculate_multi_horizon_signal(
                    rec["s3"], rec["s6"], rec["s12"], weights=multi_horizon_weights
                )
            else:
                rec["signal_multi"] = np.nan

            # Volatility estimation from continuous daily returns up to m_date
            if asset in pvt_daily_ret.columns:
                daily_s = pvt_daily_ret[asset]
                cont_rets = extract_continuous_daily_returns_before_date(daily_s, m_date)
                rec["n_daily_returns"] = len(cont_rets)
                rec["sigma_ewma"] = calculate_ewma_volatility(
                    cont_rets, decay=vol_decay, min_days=min_vol_days, ann_factor=vol_ann_factor
                )
                rec["sigma_sample"] = calculate_sample_volatility(
                    cont_rets, min_days=min_vol_days, ann_factor=vol_ann_factor
                )
            else:
                rec["n_daily_returns"] = 0
                rec["sigma_ewma"] = np.nan
                rec["sigma_sample"] = np.nan

            # Next month return: return from m_date to m_{idx+1}
            if m_idx + 1 < len(month_ends):
                next_m_date = month_ends[m_idx + 1]
                p_next = m_prices.loc[next_m_date, asset] if (next_m_date in m_prices.index and asset in m_prices.columns) else np.nan
                if pd.notnull(p_m) and pd.notnull(p_next) and p_m > 0:
                    rec["next_month_ret"] = float(p_next / p_m - 1.0)
                    rec["next_month_date"] = next_m_date
                else:
                    rec["next_month_ret"] = np.nan
                    rec["next_month_date"] = next_m_date
            else:
                rec["next_month_ret"] = np.nan
                rec["next_month_date"] = pd.NaT

            # Single asset formation eligibility for month m
            # Strictly depends ONLY on historical formation-time data, completely
            # independent of future holding-period realization or availability.
            is_formation_eligible = (
                pd.notnull(rec["ret_12m"])
                and pd.notnull(rec["sigma_ewma"])
                and rec["sigma_ewma"] > 0
                and pd.notnull(rec["price_adj_close"])
                and rec["price_adj_close"] > 0
            )
            rec["formation_eligible"] = bool(is_formation_eligible)
            rec["is_eligible"] = bool(is_formation_eligible)  # backward-compatible alias
            rec["holding_return_observed"] = bool(pd.notnull(rec["next_month_ret"]))
            records.append(rec)

    df_signals = pd.DataFrame(records)
    
    # Calculate monthly number of eligible assets N_m strictly at formation time
    m_counts = df_signals.groupby("date")["formation_eligible"].sum().rename("n_eligible_assets")
    df_signals = df_signals.merge(m_counts, on="date", how="left")
    df_signals["is_month_qualified"] = df_signals["n_eligible_assets"] >= min_eligible_assets

    return {
        "signals_df": df_signals,
        "month_ends": month_ends,
        "pvt_adj_close": pvt_adj_close,
        "pvt_adj_open": pvt_adj_open,
        "pvt_daily_ret": pvt_daily_ret,
    }

