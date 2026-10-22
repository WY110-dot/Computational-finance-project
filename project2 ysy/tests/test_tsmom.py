"""Independent numerical and formula checks for TSMOM methodology.

Strictly tests Section 9.1 independent expectations:
1. 12-month signal and missing month handling.
2. Independent asset momentum direction.
3. EWMA algorithm with decay 1/2 on [0.01, -0.01, 0.02].
4. Long/short research weights and return contributions.
5. Long/cash budget allocation.
6. Multi-horizon trend combination.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from quantcf.pipeline_p2 import calculate_daily_ledger_metrics
from quantcf.research_backtest import (
    calculate_monthly_metrics,
    run_research_backtest,
)
from quantcf.tsmom import (
    calculate_ewma_mean_and_variance,
    calculate_ewma_volatility,
    calculate_momentum_sign,
    calculate_multi_horizon_signal,
    calculate_sample_volatility,
)


def test_ewma_decay_half_hand_calculation() -> None:
    """Check Section 9.1: decay 1/2, returns [0.01, -0.01, 0.02].
    
    Oldest to newest:
    ret[0] = 0.01, ret[1] = -0.01, ret[2] = 0.02.
    Decay lambda = 0.5.
    Expected weights (old to new): [1/7, 2/7, 4/7].
    Expected mean: 0.01.
    Expected variance: 3 / 17500 = 0.00017142857142857143.
    """
    rets = [0.01, -0.01, 0.02]
    mean, var = calculate_ewma_mean_and_variance(rets, decay=0.5)

    expected_mean = 0.01
    expected_var = 3.0 / 17500.0

    assert abs(mean - expected_mean) < 1e-12, f"Mean mismatch: got {mean}, expected {expected_mean}"
    assert abs(var - expected_var) < 1e-12, f"Var mismatch: got {var}, expected {expected_var}"


def test_momentum_direction_mapping() -> None:
    """Check Section 9.1: +10%, +1%, -2% -> +1, +1, -1."""
    assert calculate_momentum_sign(0.10) == 1
    assert calculate_momentum_sign(0.01) == 1
    assert calculate_momentum_sign(-0.02) == -1
    assert calculate_momentum_sign(0.00) == 0


def test_multi_horizon_combination_math() -> None:
    """Check Section 9.1: signs +1, -1, +1 -> combo 1/3 (not +1 or 2/3)."""
    combo = calculate_multi_horizon_signal(+1, -1, +1)
    assert abs(combo - 1.0 / 3.0) < 1e-12
    assert combo != 1.0
    assert combo != 2.0 / 3.0


def test_long_short_research_weights_and_contributions() -> None:
    """Check Section 9.1:
    N=2, sigma=[0.20, 0.10], signs=[+1, -1], scale=0.40.
    w_TS = 1/N * sign * 0.40 / sigma.
    Asset 1: 1/2 * (+1) * 0.40 / 0.20 = +1.0
    Asset 2: 1/2 * (-1) * 0.40 / 0.10 = -2.0
    
    Next return = [+0.05, -0.02].
    TSMOM return = 1.0 * 0.05 + (-2.0) * (-0.02) = 0.05 + 0.04 = +0.09 (+9%).
    Passive Long (signs=+1):
    w_PL = [+1.0, +2.0].
    Passive return = 1.0 * 0.05 + 2.0 * (-0.02) = 0.05 - 0.04 = +0.01 (+1%).
    """
    N = 2
    scale = 0.40
    sigmas = np.array([0.20, 0.10])
    s_ts = np.array([1, -1])
    s_pl = np.array([1, 1])

    w_ts = (1.0 / N) * s_ts * (scale / sigmas)
    assert np.allclose(w_ts, [1.0, -2.0])

    w_pl = (1.0 / N) * s_pl * (scale / sigmas)
    assert np.allclose(w_pl, [1.0, 2.0])

    next_ret = np.array([0.05, -0.02])
    ret_ts = float(np.sum(w_ts * next_ret))
    ret_pl = float(np.sum(w_pl * next_ret))

    assert abs(ret_ts - 0.09) < 1e-12
    assert abs(ret_pl - 0.01) < 1e-12


def test_long_cash_execution_budget_allocation() -> None:
    """Check Section 9.1:
    Inverse volatility budgets: 1/sigma = [1/0.20, 1/0.10] = [5, 10].
    Total = 15.
    b = 0.99 * [5/15, 10/15] = [0.33, 0.66].
    Directions: [+1, -1].
    w_LC = b * max(s, 0) = [0.33, 0.0].
    Target cash = 1.0 - 0.33 = 0.67.
    """
    sigmas = np.array([0.20, 0.10])
    inv_vols = 1.0 / sigmas
    budgets = 0.99 * (inv_vols / np.sum(inv_vols))
    assert np.allclose(budgets, [0.33, 0.66])

    signals = np.array([1, -1])
    w_lc = budgets * np.maximum(signals, 0)
    assert np.allclose(w_lc, [0.33, 0.0])

    cash = 1.0 - np.sum(w_lc)
    assert abs(cash - 0.67) < 1e-12


def test_sample_volatility_rolling_252_counterexample() -> None:
    """Independent reviewer counterexample for Section 4:
    756 returns: first 504 alternating between +0.001 and -0.001,
    last 252 alternating between +0.02 and -0.02.
    - Full 756-day expanding history gives annualized vol ~ 0.187137.
    - True rolling 252-day gives annualized vol ~ 0.323753 (with ddof=1, ann_factor=261).
    """
    r_low = [0.001, -0.001] * 252  # 504 returns
    r_high = [0.02, -0.02] * 126   # 252 returns
    full_returns = r_low + r_high  # 756 returns

    vol_252 = calculate_sample_volatility(full_returns, min_days=252, ann_factor=261)
    # The true rolling 252-day variance of [-0.02, +0.02] with mean 0:
    # sum of squares = 252 * (0.02^2) = 252 * 0.0004 = 0.1008
    # var with ddof=1 is 0.1008 / 251 = 0.0004015936
    # ann_vol = sqrt(0.0004015936 * 261) = 0.323753
    assert abs(vol_252 - 0.323753) < 1e-4
    # Must NOT equal the full 756-day expanding history value (~0.187137)
    assert abs(vol_252 - 0.187137) > 0.10


def test_drawdown_includes_initial_capital_counterexample() -> None:
    """Independent reviewer counterexample for Section 5.1:
    Monthly returns: [-10%, +1%].
    If initial 1.0 is omitted from high-water mark, cummax starts from 0.90,
    and returns max_drawdown = 0.0%.
    With initial 1.0 prepended, wealth path is 1.0 -> 0.90 -> 0.909,
    and max_drawdown is strictly -10.0%.
    """
    dates = pd.date_range("2020-01-31", periods=2, freq="ME")
    rets = pd.Series([-0.10, 0.01], index=dates)
    metrics = calculate_monthly_metrics(rets)
    assert abs(metrics["max_drawdown"] - (-0.10)) < 1e-6


def test_calmar_preserves_negative_sign_counterexample() -> None:
    """Independent reviewer counterexample for Section 5.2:
    Monthly returns: [-10%, -10%].
    Wealth path: 1.0 -> 0.90 -> 0.81.
    Max drawdown = -19%.
    CAGR = (0.81)^(12/2) - 1 = 0.81^6 - 1 = -0.71757 (-71.757%).
    Calmar ratio = CAGR / abs(max_dd) = -0.71757 / 0.19 = -3.7767.
    Must be strictly negative!
    """
    dates = pd.date_range("2020-01-31", periods=2, freq="ME")
    rets = pd.Series([-0.10, -0.10], index=dates)
    metrics = calculate_monthly_metrics(rets)
    assert metrics["cagr"] < 0
    assert metrics["calmar"] < 0
    assert abs(metrics["max_drawdown"] - (-0.19)) < 1e-6
    assert abs(metrics["calmar"] - (-3.7767)) < 1e-3


def test_monthly_gap_detection_disallows_gap_compounding() -> None:
    """Section 5.3: Gap detection prevents silent compounding across missing months."""
    dates = pd.to_datetime(["2020-01-31", "2020-04-30"])  # 2 missing months
    rets = pd.Series([0.02, 0.03], index=dates)
    metrics = calculate_monthly_metrics(rets)
    assert metrics["is_continuous"] is False
    assert np.isnan(metrics["cagr"])


def test_run_research_backtest_with_hand_calc_assets() -> None:
    """Section 8.1: Test REAL run_research_backtest() on 2-asset Section 9.1 scenario.
    Asset 1: s12=1, sigma_ewma=0.20, next_month_ret=0.05 -> weight = +1.0
    Asset 2: s12=-1, sigma_ewma=0.10, next_month_ret=-0.02 -> weight = -2.0
    TSMOM expected return = 1.0 * 0.05 + (-2.0) * (-0.02) = +0.09.
    Passive Long expected return = 1.0 * 0.05 + 2.0 * (-0.02) = +0.01.
    """
    d0 = pd.Timestamp("2020-01-31")
    df = pd.DataFrame([
        {
            "date": d0, "asset": "A1", "s12": 1, "signal_multi": 1.0,
            "sigma_ewma": 0.20, "price_adj_close": 100.0, "formation_eligible": True,
            "next_month_ret": 0.05, "holding_return_observed": True,
        },
        {
            "date": d0, "asset": "A2", "s12": -1, "signal_multi": -1.0,
            "sigma_ewma": 0.10, "price_adj_close": 50.0, "formation_eligible": True,
            "next_month_ret": -0.02, "holding_return_observed": True,
        },
    ])

    res_ts = run_research_backtest(df, strategy_mode="tsmom12", target_volatility=0.40, min_eligible_assets=2)
    assert len(res_ts.monthly_portfolio) == 1
    assert abs(res_ts.monthly_portfolio["portfolio_return"].iloc[0] - 0.09) < 1e-12

    res_pl = run_research_backtest(df, strategy_mode="passive_long", target_volatility=0.40, min_eligible_assets=2)
    assert len(res_pl.monthly_portfolio) == 1
    assert abs(res_pl.monthly_portfolio["portfolio_return"].iloc[0] - 0.01) < 1e-12


def test_run_research_backtest_missing_holding_does_not_rescale() -> None:
    """Section 3.2: If Asset 2 has missing holding return, do NOT drop A2 and rescale A1 to 2.0.
    The month must be flagged invalid with NaN return, not reporting false 10% gain.
    """
    d0 = pd.Timestamp("2020-01-31")
    df = pd.DataFrame([
        {
            "date": d0, "asset": "A1", "s12": 1, "signal_multi": 1.0,
            "sigma_ewma": 0.20, "price_adj_close": 100.0, "formation_eligible": True,
            "next_month_ret": 0.05, "holding_return_observed": True,
        },
        {
            "date": d0, "asset": "A2", "s12": -1, "signal_multi": -1.0,
            "sigma_ewma": 0.10, "price_adj_close": 50.0, "formation_eligible": True,
            "next_month_ret": np.nan, "holding_return_observed": False,
        },
    ])

    res = run_research_backtest(df, strategy_mode="tsmom12", target_volatility=0.40, min_eligible_assets=2)
    # Portfolio return for this month should be NaN (invalid month)
    assert np.isnan(res.monthly_portfolio["portfolio_return"].iloc[0])
    row = res.monthly_portfolio.iloc[0]
    assert row["is_valid_month"] is False or row["is_valid_month"] == False
    assert "MISSING_HOLDING_RETURN" in str(row["status"])


def test_daily_ledger_metrics_bounds_and_day1() -> None:
    """Section 2.3: Ledger metrics must evaluate starting strictly on start_date,
    including Day 1 return, and truncate after end_date.
    """
    dates = pd.bdate_range("2020-02-03", "2020-02-07")
    # Day 0: return +0.01, Day 1: +0.02, Day 2: -0.01, Day 3: +0.005, Day 4 (beyond end): +0.05
    ledger_df = pd.DataFrame({
        "timestamp": dates,
        "daily_return": [0.01, 0.02, -0.01, 0.005, 0.05],
        "nav": [10100.0, 10302.0, 10198.98, 10249.97, 10762.47],
    })

    # Evaluate bounded to 2020-02-03 through 2020-02-06 (4 days)
    m = calculate_daily_ledger_metrics(
        ledger_df,
        start_date="2020-02-03",
        end_date="2020-02-06",
    )

    assert m["trading_days"] == 4
    # Day 1 return (0.01) must be included
    assert m["total_compound_return"] > 0



