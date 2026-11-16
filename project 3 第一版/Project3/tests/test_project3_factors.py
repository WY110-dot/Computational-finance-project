"""Unit tests for Project 3 factor calculation, ER math, hand calculations and lookahead checks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantcf.project3_factors import (
    calculate_er,
    winsorize_and_zscore,
    compute_monthly_factors_for_panel,
)


def test_er_monotonic_path():
    """Verify ER=1.0 on strictly monotonic path."""
    prices = [100.0, 110.0, 121.0]
    er, is_flat = calculate_er(prices, window=2)
    assert not is_flat
    assert np.isclose(er, 1.0, atol=1e-12)


def test_er_roundtrip_path():
    """Verify ER=0.0 on symmetric round-trip path."""
    prices = [100.0, 110.0, 100.0]
    er, is_flat = calculate_er(prices, window=2)
    assert not is_flat
    assert np.isclose(er, 0.0, atol=1e-12)


def test_er_flat_path():
    """Verify ER=0.0 and is_flat=True on completely constant prices."""
    prices = [100.0, 100.0, 100.0]
    er, is_flat = calculate_er(prices, window=2)
    assert is_flat
    assert np.isclose(er, 0.0, atol=1e-12)


def test_er_bounds_error():
    """Verify calculate_er raises or clips gracefully for numerical float precision."""
    # When prices are strictly positive, ER is mathematically in [0, 1]
    prices = [50.0, 52.0, 48.0, 55.0]
    er, _ = calculate_er(prices, window=3)
    assert 0.0 <= er <= 1.0


def test_hand_calculation_example():
    """Verify the exact synthetic hand-calculation example from docs/FACTOR_CARDS.md."""
    # S1: P=[100, 110, 121] -> ER=1.0, b1=0.20 -> F1_1 = 0.20
    # S2: P=[100, 110, 100] -> ER=0.0, b2=0.10 -> F1_2 = 0.00
    # S3: P=[100, 100, 100] -> ER=0.0, b3=-0.05 -> F1_3 = 0.00
    b = pd.Series({"S1": 0.20, "S2": 0.10, "S3": -0.05})
    f1 = pd.Series({"S1": 0.20, "S2": 0.00, "S3": 0.00})
    
    # 1. Check A = z_cs(winsor(b))
    mu_b = (0.20 + 0.10 - 0.05) / 3.0
    sigma_b = np.sqrt(((0.20 - mu_b)**2 + (0.10 - mu_b)**2 + (-0.05 - mu_b)**2) / 3.0)
    expected_A_S1 = (0.20 - mu_b) / sigma_b
    expected_A_S2 = (0.10 - mu_b) / sigma_b
    expected_A_S3 = (-0.05 - mu_b) / sigma_b
    
    A = winsorize_and_zscore(b)
    assert np.isclose(A["S1"], expected_A_S1, atol=1e-7)
    assert np.isclose(A["S2"], expected_A_S2, atol=1e-7)
    assert np.isclose(A["S3"], expected_A_S3, atol=1e-7)
    assert np.isclose(A.mean(), 0.0, atol=1e-12)
    assert np.isclose(A.std(ddof=0), 1.0, atol=1e-12)
    
    # 2. Check B = z_cs(winsor(f1))
    mu_f1 = 0.20 / 3.0
    sigma_f1 = np.sqrt(((0.20 - mu_f1)**2 + 2.0 * (0.0 - mu_f1)**2) / 3.0)
    expected_B_S1 = (0.20 - mu_f1) / sigma_f1
    expected_B_S2 = (0.00 - mu_f1) / sigma_f1
    expected_B_S3 = (0.00 - mu_f1) / sigma_f1
    
    B = winsorize_and_zscore(f1)
    assert np.isclose(B["S1"], expected_B_S1, atol=1e-7)
    assert np.isclose(B["S2"], expected_B_S2, atol=1e-7)
    assert np.isclose(B["S3"], expected_B_S3, atol=1e-7)
    assert np.isclose(B["S1"], np.sqrt(2.0), atol=1e-7)
    assert np.isclose(B["S2"], -1.0 / np.sqrt(2.0), atol=1e-7)
    assert np.isclose(B.mean(), 0.0, atol=1e-12)
    assert np.isclose(B.std(ddof=0), 1.0, atol=1e-12)
    
    # 3. Check C = z_cs(0.5 * A + 0.5 * B)
    c_raw = 0.5 * A + 0.5 * B
    C = winsorize_and_zscore(c_raw)
    assert np.isclose(C.mean(), 0.0, atol=1e-12)
    assert np.isclose(C.std(ddof=0), 1.0, atol=1e-12)
    # Check ordering preserved: S1 > S2 > S3
    assert C["S1"] > C["S2"] > C["S3"]


def test_future_perturbation_invariance():
    """Verify that perturbing future prices at t+1 does not alter factor scores at t."""
    dates = pd.date_range("2020-01-01", "2021-06-30", freq="B")
    assets = [f"ETF{i}" for i in range(8)]
    np.random.seed(42)
    
    # Generate random walk prices
    rows = []
    for d in dates:
        for a in assets:
            rows.append({"date": d, "asset": a, "close_adj": 100.0, "open_adj": 100.0})
    df_base = pd.DataFrame(rows)
    for a in assets:
        mask = df_base["asset"] == a
        p = 100.0 + np.cumsum(np.random.randn(len(dates)) * 0.5)
        df_base.loc[mask, "close_adj"] = np.maximum(p, 10.0)
        df_base.loc[mask, "open_adj"] = np.maximum(p, 10.0)
        
    month_ends = df_base.groupby(df_base["date"].dt.to_period("M"))["date"].max().tolist()
    cal_dates = sorted(df_base["date"].unique())
    
    res1 = compute_monthly_factors_for_panel(
        df_base, month_ends, cal_dates, min_vol_days=65, min_lookback_months=13, min_qualified_assets=6
    )
    
    if not res1["factors"].empty:
        t_target = res1["factors"]["formation_date"].iloc[0]
        # Create perturbed dataset where prices after t_target are doubled
        df_perturbed = df_base.copy()
        post_mask = df_perturbed["date"] > t_target
        df_perturbed.loc[post_mask, "close_adj"] *= 2.5
        df_perturbed.loc[post_mask, "open_adj"] *= 2.5
        
        res2 = compute_monthly_factors_for_panel(
            df_perturbed, month_ends, cal_dates, min_vol_days=65, min_lookback_months=13, min_qualified_assets=6
        )
        
        # Compare factor values at t_target
        f1 = res1["factors"][res1["factors"]["formation_date"] == t_target].sort_values("asset")
        f2 = res2["factors"][res2["factors"]["formation_date"] == t_target].sort_values("asset")
        
        for col in ["A", "B", "C", "F2", "F3", "A0"]:
            assert np.allclose(f1[col].values, f2[col].values, equal_nan=True, atol=1e-12)
