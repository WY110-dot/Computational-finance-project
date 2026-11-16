"""Unit tests for Project 3 pipeline, broker ledger, tie-handling, split filtering and bootstrap."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantcf.project3_pipeline import (
    assign_tercile_memberships,
    get_holding_periods,
    compute_holding_labels,
    execute_broker_simulation,
)
from quantcf.project3_diagnostics import (
    compute_cross_sectional_residual_factor,
    circular_block_bootstrap_pairwise,
)


def test_fractional_membership_all_ties():
    """When all assets have identical scores, memberships are exactly 1/3 in all groups."""
    scores = pd.Series([1.5, 1.5, 1.5, 1.5, 1.5, 1.5], index=[f"A{i}" for i in range(6)])
    memberships = assign_tercile_memberships(scores)
    assert len(memberships) == 6
    for a in memberships:
        m1, m2, m3 = memberships[a]
        assert np.isclose(m1, 1.0 / 3.0, atol=1e-12)
        assert np.isclose(m2, 1.0 / 3.0, atol=1e-12)
        assert np.isclose(m3, 1.0 / 3.0, atol=1e-12)
    # Total top tercile mass is N/3 = 2.0
    tot_t3 = sum(m[2] for m in memberships.values())
    assert np.isclose(tot_t3, 2.0, atol=1e-12)


def test_fractional_membership_strict_and_boundary_ties():
    """Verify fractional memberships when ties occur across boundary."""
    # 6 assets: ranks [0, 6]. Terciles are [0, 2], [2, 4], [4, 6]
    # Assets A0, A1 have score 1.0 (ranks 0, 2 -> completely in T1)
    # Assets A2, A3, A4 have score 2.0 (ranks 2 to 5 -> straddles T2 and T3: covers [2, 4] and [4, 5])
    # Asset A5 has score 3.0 (ranks 5 to 6 -> completely in T3)
    scores = pd.Series({"A0": 1.0, "A1": 1.0, "A2": 2.0, "A3": 2.0, "A4": 2.0, "A5": 3.0})
    m = assign_tercile_memberships(scores)
    
    # A0, A1 should be 100% in T1
    assert np.isclose(m["A0"][0], 1.0) and np.isclose(m["A1"][0], 1.0)
    assert np.isclose(m["A0"][2], 0.0) and np.isclose(m["A1"][2], 0.0)
    
    # A5 should be 100% in T3
    assert np.isclose(m["A5"][2], 1.0)
    
    # A2, A3, A4 share interval [2, 5], overlapping T2 [2, 4] (mass 2) and T3 [4, 5] (mass 1)
    # Each gets 2/3 in T2, and 1/3 in T3
    for a in ["A2", "A3", "A4"]:
        assert np.isclose(m[a][1], 2.0 / 3.0)
        assert np.isclose(m[a][2], 1.0 / 3.0)
        
    # Sum of T3 mass must be exactly 6/3 = 2.0
    assert np.isclose(sum(v[2] for v in m.values()), 2.0)


def test_holding_period_filtering_and_p5_isolation():
    """Holding periods that cross the split end date must be strictly rejected."""
    month_ends = pd.to_datetime(["2024-09-30", "2024-10-31", "2024-11-29", "2024-12-31"])
    cal_dates = pd.to_datetime([
        "2024-09-30", "2024-10-08", "2024-10-31", "2024-11-01", 
        "2024-11-29", "2024-12-02", "2024-12-31", "2025-01-02", "2025-02-05"
    ])
    
    # Filter for split 2024-01-01 to 2024-12-31
    periods = get_holding_periods(cal_dates, month_ends, "2024-01-01", "2024-12-31")
    
    # Period formed on 2024-10-31 enters 2024-11-01 and exits 2024-12-02 (valid, <= 2024-12-31)
    # Period formed on 2024-11-29 enters 2024-12-02 and exits 2025-01-02 (> 2024-12-31, MUST BE REJECTED)
    exit_dates = [p["exit_date"] for p in periods]
    for ex in exit_dates:
        assert ex <= pd.Timestamp("2024-12-31")
    assert pd.Timestamp("2025-01-02") not in exit_dates


def test_broker_ledger_accounting_and_cost_sensitivity():
    """Verify cash non-negativity, equity balance, and cost monotonicity (10 bps < 0 bps)."""
    dates = pd.date_range("2024-01-01", "2024-03-31", freq="B")
    assets = ["ETF0", "ETF1", "ETF2", "ETF3", "ETF4", "ETF5"]
    
    rows = []
    for d in dates:
        for a in assets:
            rows.append({"date": d, "asset": a, "open_adj": 100.0, "close_adj": 100.0, "ret_total": 0.0})
    panel = pd.DataFrame(rows)
    
    # Introduce price rise in ETF0 and drop in ETF1
    mask_0 = (panel["asset"] == "ETF0") & (panel["date"] >= "2024-02-01")
    panel.loc[mask_0, ["open_adj", "close_adj"]] = 120.0
    
    m_ends = [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29")]
    periods = [
        {"formation_date": pd.Timestamp("2024-01-31"), "entry_date": pd.Timestamp("2024-02-01"), "exit_date": pd.Timestamp("2024-03-01")},
    ]
    
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2024-01-31"), "execution_date": pd.Timestamp("2024-02-01"), "asset": "ETF0", "target_weight": 0.495},
        {"signal_date": pd.Timestamp("2024-01-31"), "execution_date": pd.Timestamp("2024-02-01"), "asset": "ETF1", "target_weight": 0.495},
    ])
    
    # Run with 0 bps
    res_0 = execute_broker_simulation(panel, targets, periods, list(dates), cost_bps=0.0)
    assert res_0["audit"]["passed"]
    assert res_0["audit"]["checks"]["no_borrowing"]
    assert res_0["audit"]["checks"]["no_shorting"]
    assert res_0["audit"]["checks"]["valuation"]
    assert res_0["audit"]["checks"]["execution_conservation"]
    
    # Run with 10 bps
    res_10 = execute_broker_simulation(panel, targets, periods, list(dates), cost_bps=10.0)
    assert res_10["audit"]["passed"]
    assert res_10["audit"]["checks"]["no_borrowing"]
    
    # Higher fees MUST result in strictly lower final equity
    eq_0 = res_0["summary"]["w_end_open"]
    eq_10 = res_10["summary"]["w_end_open"]
    assert eq_0 > eq_10
    assert np.isclose(res_0["summary"]["total_fees"], 0.0)
    assert res_10["summary"]["total_fees"] > 0.0


def test_residual_factor_orthogonality():
    """Verify that cross-sectional residual factor epsilon has zero mean and zero correlation with A."""
    np.random.seed(42)
    assets = [f"A{i}" for i in range(10)]
    A = np.random.randn(10)
    A = (A - np.mean(A)) / np.std(A)
    # B = 0.5 * A + noise
    B = 0.5 * A + 0.3 * np.random.randn(10)
    B = (B - np.mean(B)) / np.std(B)
    
    df_fac = pd.DataFrame({
        "formation_date": pd.Timestamp("2024-01-31"),
        "asset": assets,
        "A": A,
        "B": B,
    })
    df_lab = pd.DataFrame({
        "formation_date": pd.Timestamp("2024-01-31"),
        "asset": assets,
        "holding_return": np.random.randn(10) * 0.05,
    })
    
    df_res, summary = compute_cross_sectional_residual_factor(df_fac, df_lab, min_assets=6)
    assert summary["n_dates"] == 1
    assert not df_res.empty
    
    # Exact orthogonality assertions
    assert summary["orthogonality_verified"]
    assert df_res["ortho_mean_abs"].iloc[0] < 1e-10
    assert df_res["ortho_cov_abs"].iloc[0] < 1e-10
    assert np.isclose(df_res["ortho_mean_abs"].iloc[0], 0.0, atol=1e-10)
    assert np.isclose(df_res["ortho_cov_abs"].iloc[0], 0.0, atol=1e-10)
    
    # Test degeneracy handling: when all A are identical, should not raise, gracefully handles
    df_fac_degen = df_fac.copy()
    df_fac_degen["A"] = 1.0
    df_res_degen, summary_degen = compute_cross_sectional_residual_factor(df_fac_degen, df_lab, min_assets=6)
    # Regression with rank deficiency handles without crashing


def test_block_bootstrap_identity():
    """When C == A, bootstrap delta return and delta Sharpe are strictly zero."""
    dates = pd.date_range("2023-01-01", periods=12, freq="MS")
    rets = np.array([0.02, -0.01, 0.03, 0.01, -0.02, 0.04, 0.00, 0.01, -0.01, 0.02, 0.03, -0.01])
    df_c = pd.DataFrame({"formation_date": dates, "net_return": rets})
    df_a = pd.DataFrame({"formation_date": dates, "net_return": rets})
    
    res = circular_block_bootstrap_pairwise(df_c, df_a, block_size=3, n_reps=100, seed=42)
    assert np.isclose(res["delta_ann_mean"], 0.0, atol=1e-12)
    assert np.isclose(res["delta_sharpe_mean"], 0.0, atol=1e-12)
    assert np.isclose(res["delta_ann_ci_95"][0], 0.0, atol=1e-12)
    assert np.isclose(res["delta_ann_ci_95"][1], 0.0, atol=1e-12)
