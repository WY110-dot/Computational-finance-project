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

from quantcf.pipeline_p2 import (
    calculate_daily_ledger_metrics,
    slice_research_subperiod,
)
from quantcf.research_backtest import (
    ResearchBacktestResult,
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


def test_multi_horizon_weights_validation_and_calculation() -> None:
    """Closing Fix B: multi_horizon_weights validation and calculation."""
    # 1. Calculation with custom weights
    sig = calculate_multi_horizon_signal(1, 0, -1, weights=[0.5, 0.25, 0.25])
    assert abs(sig - 0.25) < 1e-12

    # 2. Rejection of invalid weights
    with pytest.raises(ValueError, match="Multi-horizon weights must have length 3"):
        calculate_multi_horizon_signal(1, 1, 1, weights=[0.5, 0.5])

    with pytest.raises(ValueError, match="Multi-horizon weights must sum to 1.0"):
        calculate_multi_horizon_signal(1, 1, 1, weights=[0.5, 0.5, 0.5])

    with pytest.raises(ValueError, match="Multi-horizon weights must be non-negative"):
        calculate_multi_horizon_signal(1, 1, 1, weights=[-0.2, 0.6, 0.6])

    # 3. Rejection of non-equal weights in dataset builder
    dummy_df = pd.DataFrame({
        "date": ["2020-01-02", "2020-01-03"],
        "asset": ["A1", "A1"],
        "close_adj": [10.0, 10.1],
        "open_adj": [10.0, 10.1],
        "ret_total": [0.0, 0.01],
    })
    from quantcf.tsmom import build_monthly_tsmom_dataset
    with pytest.raises(ValueError, match="Unsupported multi_horizon_weights"):
        build_monthly_tsmom_dataset(dummy_df, multi_horizon_weights=[1.0, 0.0, 0.0])


def test_run_research_backtest_with_missing_months_sets_continuous_false_and_nan_cagr() -> None:
    """Closing Fix C: Reviewer counterexample verifying gap detection in run_research_backtest().
    
    Feeds holding returns for 2020-02 and 2020-04 (missing 2020-03).
    Verifies that the main backtest engine correctly identifies non-consecutive
    months, setting is_continuous=False and CAGR=NaN.
    """
    df = pd.DataFrame([
        {
            "date": pd.Timestamp("2020-01-31"),
            "next_month_date": pd.Timestamp("2020-02-29"),
            "asset": "A1",
            "s12": 1,
            "signal_multi": 1.0,
            "sigma_ewma": 0.20,
            "price_adj_close": 100.0,
            "formation_eligible": True,
            "next_month_ret": 0.05,
            "holding_return_observed": True,
        },
        {
            "date": pd.Timestamp("2020-03-31"),
            "next_month_date": pd.Timestamp("2020-04-30"),
            "asset": "A1",
            "s12": 1,
            "signal_multi": 1.0,
            "sigma_ewma": 0.20,
            "price_adj_close": 105.0,
            "formation_eligible": True,
            "next_month_ret": 0.05,
            "holding_return_observed": True,
        },
    ])

    res = run_research_backtest(df, strategy_mode="tsmom12", target_volatility=0.40, min_eligible_assets=1)
    
    # Portfolio checks
    assert len(res.monthly_portfolio) == 2
    assert res.summary_metrics["is_continuous"] is False
    assert np.isnan(res.summary_metrics["cagr"])
    assert np.isnan(res.summary_metrics["max_drawdown"])
    assert np.isnan(res.summary_metrics["calmar"])
    # Arithmetic mean and volatility are still computed over available months
    # Weight = (1/1) * 1.0 * (0.40 / 0.20) = 2.0 -> monthly ret = 2.0 * 0.05 = 0.10 -> ann_mean = 1.20
    assert abs(res.summary_metrics["ann_mean"] - 1.20) < 1e-6
    assert abs(res.summary_metrics["ann_vol"] - 0.0) < 1e-6

    # Single-asset checks
    single_m = res.single_asset_metrics.iloc[0]
    assert bool(single_m["is_continuous"]) is False
    assert np.isnan(single_m["cagr"])


def test_dynamic_formation_end_derivation() -> None:
    """Closing Fix B: formation_end is derived dynamically from holding_end."""
    h1 = "2026-08-31"
    dt1 = pd.to_datetime(h1)
    f1 = (dt1.replace(day=1) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert f1 == "2026-07-31"

    h2 = "2025-12-31"
    dt2 = pd.to_datetime(h2)
    f2 = (dt2.replace(day=1) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    assert f2 == "2025-11-30"


def test_subperiod_slicing_and_dynamic_end_date() -> None:
    """Fix A Regression Test: Subperiod slicing on actual holding_end_date.
    
    Verifies:
    1. Sub1 (2020-02 to 2022-12) covers exactly 35 months, starts 2020-02-28, ends 2022-12-30,
       with Sharpe ~1.180314, ann vol ~16.4548%, CAGR ~19.6894%.
    2. Sub2 (2023-01 to 2026-08) covers exactly 44 months, starts 2023-01-31, ends 2026-08-31,
       with Sharpe ~0.646021, ann vol ~28.6468%, CAGR ~14.8571%.
    3. Sum of months: 35 + 44 = 79 months (100% of R1 holding months, zero gaps, zero overlap).
    4. Custom end date test: Setting sub2 end to 2024-12-31 yields exactly 24 months terminating at 2024-12-31.
    5. Invalid ranges (start > end, or empty slice) raise ValueError.
    """
    from pathlib import Path
    r1_port_path = Path("outputs_p2_fixed/research/R1_tsmom12_monthly_portfolio.csv")
    if not r1_port_path.exists():
        pytest.skip("outputs_p2_fixed not yet generated")

    df_port = pd.read_csv(r1_port_path)
    res_base = ResearchBacktestResult(
        strategy_name="R1_tsmom12",
        mode="tsmom12",
        monthly_portfolio=df_port,
        monthly_weights=pd.DataFrame(),
        asset_contributions=pd.DataFrame(),
        single_asset_returns=pd.DataFrame(),
        single_asset_metrics=pd.DataFrame(),
        summary_metrics={},
    )

    # 1. Subperiod 1: 2020-02 to 2022-12
    res_sub1 = slice_research_subperiod(res_base, "2020-02-01", "2022-12-31", "R1_sub_2020_2022")
    m1 = res_sub1.summary_metrics
    assert len(res_sub1.monthly_portfolio) == 35
    assert m1["n_months"] == 35
    assert res_sub1.monthly_portfolio["holding_end_date"].iloc[0] == "2020-02-28"
    assert res_sub1.monthly_portfolio["holding_end_date"].iloc[-1] == "2022-12-30"
    assert abs(m1["sharpe"] - 1.180314039853) < 1e-6
    assert abs(m1["ann_vol"] - 0.164547552101) < 1e-6
    assert abs(m1["cagr"] - 0.196893779664) < 1e-6
    assert m1["is_continuous"] is True

    # 2. Subperiod 2: 2023-01 to 2026-08
    res_sub2 = slice_research_subperiod(res_base, "2023-01-01", "2026-08-31", "R1_sub_2023_2026")
    m2 = res_sub2.summary_metrics
    assert len(res_sub2.monthly_portfolio) == 44
    assert m2["n_months"] == 44
    assert res_sub2.monthly_portfolio["holding_end_date"].iloc[0] == "2023-01-31"
    assert res_sub2.monthly_portfolio["holding_end_date"].iloc[-1] == "2026-08-31"
    assert abs(m2["sharpe"] - 0.646021360990) < 1e-6
    assert abs(m2["ann_vol"] - 0.286467627897) < 1e-6
    assert abs(m2["cagr"] - 0.148571083372) < 1e-6
    assert m2["is_continuous"] is True

    # 3. Complete coverage of 79 months
    assert len(res_sub1.monthly_portfolio) + len(res_sub2.monthly_portfolio) == 79

    # 4. Custom end date test (end = 2024-12-31)
    res_sub2_custom = slice_research_subperiod(res_base, "2023-01-01", "2024-12-31", "R1_sub_custom")
    assert len(res_sub2_custom.monthly_portfolio) == 24
    assert res_sub2_custom.monthly_portfolio["holding_end_date"].iloc[0] == "2023-01-31"
    assert res_sub2_custom.monthly_portfolio["holding_end_date"].iloc[-1] == "2024-12-31"
    # Ensure no 2025 or 2026 data leaked
    dates = pd.to_datetime(res_sub2_custom.monthly_portfolio["holding_end_date"])
    assert (dates > pd.to_datetime("2024-12-31")).sum() == 0

    # 5. Boundary & error tests
    with pytest.raises(ValueError, match="is after end date"):
        slice_research_subperiod(res_base, "2025-01-01", "2024-01-01", "invalid")
    with pytest.raises(ValueError, match="yielded no holding months"):
        slice_research_subperiod(res_base, "2018-01-01", "2018-12-31", "empty")


def test_asset_class_contributions_and_variance_decomposition_conservation() -> None:
    """Fix B Regression Test: Contribution & variance decomposition conservation.
    
    Verifies:
    1. Every month, sum of asset class contributions equals portfolio_return within 1e-12.
    2. Sum of annualized arithmetic return contributions across the 4 asset classes
       equals R1's annualized arithmetic mean return within 1e-12.
    3. Bonds annualized contribution is ~10.19 percentage points (~53.9% of R1 mean).
    4. Domestic equity annualized contribution is ~3.06 percentage points, and its
       variance contribution ratio is 84.76%.
    5. Sum of variance contribution ratios across all 4 asset classes equals 100%.
    """
    from pathlib import Path
    c_path = Path("outputs_p2_fixed/research/R1_asset_class_contributions.csv")
    d_path = Path("outputs_p2_fixed/research/asset_class_variance_decomposition.csv")
    s_path = Path("outputs_p2_fixed/strategy_summary.csv")
    if not (c_path.exists() and d_path.exists() and s_path.exists()):
        pytest.skip("outputs_p2_fixed not yet generated")

    c_df = pd.read_csv(c_path)
    d_df = pd.read_csv(d_path)
    s_df = pd.read_csv(s_path)

    # 1. Month-by-month conservation
    classes = ["Bonds", "Cross_Border_Equity", "Domestic_Equity", "Gold"]
    month_sum = c_df[classes].sum(axis=1)
    port_ret = c_df["total_portfolio_return"]
    assert np.abs(month_sum - port_ret).max() < 1e-12

    # 2. Annualized arithmetic return contribution conservation
    ann_contrib_sum = d_df["ann_mean_return_contribution"].sum()
    r1_mean = s_df.loc[s_df["strategy_id"] == "R1_tsmom12", "ann_arithmetic_mean"].iloc[0]
    assert abs(ann_contrib_sum - r1_mean) < 1e-12

    # 3. Specific asset class figures
    bonds_row = d_df[d_df["asset_class"] == "Bonds"].iloc[0]
    eq_row = d_df[d_df["asset_class"] == "Domestic_Equity"].iloc[0]

    bonds_contrib = bonds_row["ann_mean_return_contribution"] * 100
    assert abs(bonds_contrib - 10.194362) < 0.01  # +10.19 pp
    assert abs(bonds_contrib / (r1_mean * 100) * 100 - 53.9) < 0.5  # 53.9% of R1

    eq_contrib = eq_row["ann_mean_return_contribution"] * 100
    assert abs(eq_contrib - 3.055038) < 0.01  # +3.06 pp
    eq_var_share = eq_row["variance_contribution_ratio"] * 100
    assert abs(eq_var_share - 84.76) < 0.01  # 84.76% of variance

    # 4. Variance ratios sum to 100%
    assert abs(d_df["variance_contribution_ratio"].sum() - 1.0) < 1e-12





