"""Tests for TSMOM Long/Cash execution target generator."""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from quantcf.portfolio import generate_tsmom_long_cash_targets


def test_tsmom_long_cash_targets_basic() -> None:
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    
    signals_data = [
        # month end 1
        {"date": dates[0], "asset": "A", "s12": 1, "signal_multi": 0.33, "sigma_ewma": 0.20, "is_eligible": True},
        {"date": dates[0], "asset": "B", "s12": -1, "signal_multi": -0.33, "sigma_ewma": 0.10, "is_eligible": True},
        {"date": dates[0], "asset": "C", "s12": 1, "signal_multi": 1.0, "sigma_ewma": 0.20, "is_eligible": True},
    ]
    signals_df = pd.DataFrame(signals_data)
    
    # Require at least 2 assets
    targets = generate_tsmom_long_cash_targets(
        signals_df,
        calendar=dates,
        strategy_mode="tsmom12",
        invest_fraction=0.99,
        min_eligible_assets=2,
    )
    
    assert not targets.empty
    assert (targets["target_weight"] >= 0.0).all()
    assert targets.groupby("execution_date")["target_weight"].sum().max() <= 0.99 + 1e-6
    
    # Asset B had negative s12 -> target_weight must be 0
    b_weight = targets.loc[targets["asset"] == "B", "target_weight"].iloc[0]
    assert b_weight == 0.0


def test_tsmom_long_cash_targets_insufficient_assets_emits_zero() -> None:
    dates = pd.date_range("2020-01-01", periods=5, freq="B")
    signals_data = [
        {"date": dates[0], "asset": "A", "s12": 1, "signal_multi": 1.0, "sigma_ewma": 0.20, "is_eligible": True},
    ]
    signals_df = pd.DataFrame(signals_data)
    
    # Require 6 assets, but only 1 eligible
    targets = generate_tsmom_long_cash_targets(
        signals_df,
        calendar=dates,
        strategy_mode="tsmom12",
        invest_fraction=0.99,
        min_eligible_assets=6,
        universe_assets=["A", "B", "C"],
    )
    
    # All emitted weights should be 0.0
    assert not targets.empty
    assert (targets["target_weight"] == 0.0).all()


def test_future_holding_deletion_does_not_affect_formation_targets() -> None:
    """Independent reviewer check for Section 3:
    Formation-time execution target generation must NOT depend on whether next_month_ret
    is observed or missing.
    """
    dates = pd.date_range("2020-01-31", periods=10, freq="B")
    
    # Baseline: both assets have formation info; whether next_month_ret is present or missing
    # in signals_df must not alter the generated execution targets.
    signals_base = pd.DataFrame([
        {
            "date": dates[0], "asset": "A", "s12": 1, "signal_multi": 1.0,
            "sigma_ewma": 0.20, "formation_eligible": True, "next_month_ret": 0.05,
            "holding_return_observed": True,
        },
        {
            "date": dates[0], "asset": "B", "s12": 1, "signal_multi": 1.0,
            "sigma_ewma": 0.10, "formation_eligible": True, "next_month_ret": -0.02,
            "holding_return_observed": True,
        },
    ])
    
    signals_with_missing_future = signals_base.copy()
    # Delete B's future return completely:
    signals_with_missing_future.loc[1, "next_month_ret"] = np.nan
    signals_with_missing_future.loc[1, "holding_return_observed"] = False
    
    targets_base = generate_tsmom_long_cash_targets(
        signals_base,
        calendar=dates,
        strategy_mode="tsmom12",
        invest_fraction=0.99,
        min_eligible_assets=2,
    )
    
    targets_missing_future = generate_tsmom_long_cash_targets(
        signals_with_missing_future,
        calendar=dates,
        strategy_mode="tsmom12",
        invest_fraction=0.99,
        min_eligible_assets=2,
    )
    
    # Both targets should be IDENTICAL at formation time
    pd.testing.assert_frame_equal(targets_base, targets_missing_future)
    assert not targets_base.empty
    assert (targets_base["target_weight"] > 0).all()


