"""
Unit Tests for ETF Price Adjustment (Phase C1)
Fast, deterministic, offline pytest tests using synthetic fixtures.
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add src directory to sys.path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from data.adjustment import ETFAdjuster


@pytest.fixture
def synthetic_dividend_data():
    """
    Synthetic 3-day data representing an ETF dividend event.
    Day 1: Pre-dividend, raw close = 3.103, adj_factor = 1.35
    Day 2: Ex-dividend day. Raw close drops to 3.058 (raw change -1.4502%).
           Due to dividend adjustment, adj_factor rises to 1.385848.
           Official total return pct_chg is +1.1578%.
    Day 3: Post-dividend normal day. Raw close rises to 3.064, adj_factor = 1.385848.
           pct_chg = +0.1962%.
    """
    df_price = pd.DataFrame({
        "trade_date": ["20251216", "20251217", "20251218"],
        "ts_code": ["510050.SH", "510050.SH", "510050.SH"],
        "open": [3.133, 3.023, 3.058],
        "high": [3.140, 3.065, 3.070],
        "low": [3.098, 3.020, 3.050],
        "close": [3.103, 3.058, 3.064],
        "vol": [100000.0, 120000.0, 110000.0],
        "amount": [310000.0, 360000.0, 330000.0],
        "pct_chg": [-0.9575, 1.1578, 0.1962]
    })

    df_adj = pd.DataFrame({
        "trade_date": ["20251216", "20251217", "20251218"],
        "ts_code": ["510050.SH", "510050.SH", "510050.SH"],
        "adj_factor": [1.4104, 1.4478, 1.4478]
    })

    return df_price, df_adj


def test_adjustment_factor_positive(synthetic_dividend_data):
    """Test that non-positive adjustment factors are rejected with ValueError."""
    df_price, df_adj = synthetic_dividend_data
    
    # Inject an invalid non-positive factor
    df_adj_invalid = df_adj.copy()
    df_adj_invalid.loc[1, "adj_factor"] = -1.0

    adjuster = ETFAdjuster()
    with pytest.raises(ValueError, match="non-positive adjustment factor"):
        adjuster.merge_raw_and_adj(df_price, df_adj_invalid)


def test_raw_price_is_preserved(synthetic_dividend_data):
    """Test that raw OHLC prices are preserved unchanged in standard columns."""
    df_price, df_adj = synthetic_dividend_data
    adjuster = ETFAdjuster()
    adjusted, _ = adjuster.process_and_standardize(df_price, df_adj)

    # Raw prices must match original input values exactly
    np.testing.assert_array_equal(adjusted["open_raw"].values, df_price["open"].values)
    np.testing.assert_array_equal(adjusted["high_raw"].values, df_price["high"].values)
    np.testing.assert_array_equal(adjusted["low_raw"].values, df_price["low"].values)
    np.testing.assert_array_equal(adjusted["close_raw"].values, df_price["close"].values)


def test_reference_date_is_fixed(synthetic_dividend_data):
    """Test that on reference date tau, adjusted price strictly equals raw price."""
    df_price, df_adj = synthetic_dividend_data
    ref_date = "20251218"
    adjuster = ETFAdjuster(reference_date=ref_date)
    adjusted, _ = adjuster.process_and_standardize(df_price, df_adj, reference_date=ref_date)

    ref_row = adjusted[adjusted["trade_date"] == ref_date].iloc[0]
    assert ref_row["adjustment_reference_date"] == ref_date
    assert pytest.approx(ref_row["close_adj"], rel=1e-7) == ref_row["close_raw"]
    assert pytest.approx(ref_row["open_adj"], rel=1e-7) == ref_row["open_raw"]


def test_dividend_event_does_not_create_false_loss(synthetic_dividend_data):
    """
    Critical correctness test:
    On dividend ex-date (2025-12-17), raw close.pct_change() is negative (-1.4502%),
    while actual economic return (ret_total) is positive (+1.16%).
    """
    df_price, df_adj = synthetic_dividend_data
    adjuster = ETFAdjuster()
    adjusted, _ = adjuster.process_and_standardize(df_price, df_adj)

    # Raw pct change between day 0 and day 1
    raw_return = (df_price.loc[1, "close"] - df_price.loc[0, "close"]) / df_price.loc[0, "close"]
    assert raw_return < 0, "Raw return should be negative due to ex-dividend drop"
    assert pytest.approx(raw_return, abs=1e-4) == -0.014502

    # Corrected total return on ex-dividend day
    ret_total_ex_div = adjusted.loc[1, "ret_total"]
    assert ret_total_ex_div > 0, "Corrected total return must be positive, not a false loss"
    # Economic return is around +1.16%, consistent with Tushare's official pct_chg (+1.1578%) within 0.01%
    assert pytest.approx(ret_total_ex_div * 100, abs=0.01) == 1.16


def test_adjusted_return_matches_reference(synthetic_dividend_data):
    """Test that ret_total * 100 matches Tushare's official pct_chg within tolerance."""
    df_price, df_adj = synthetic_dividend_data
    adjuster = ETFAdjuster()
    adjusted, diag = adjuster.process_and_standardize(df_price, df_adj)

    assert diag["status"] == "PASS"
    assert diag["mismatch_count"] == 0
    assert diag["max_abs_diff_pct"] < 0.01  # Less than 0.01%


def test_backward_compatibility_columns(synthetic_dividend_data):
    """Test that standard C1 columns and legacy aliases both exist."""
    df_price, df_adj = synthetic_dividend_data
    adjuster = ETFAdjuster()
    adjusted, _ = adjuster.process_and_standardize(df_price, df_adj)

    # Standard C1 columns
    for col in ETFAdjuster.STANDARD_COLUMNS:
        assert col in adjusted.columns, f"Standard column '{col}' missing"

    # Legacy aliases
    for legacy_col in ["trade_date", "ts_code", "close", "open", "high", "low"]:
        assert legacy_col in adjusted.columns, f"Legacy column '{legacy_col}' missing"
