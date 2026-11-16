from __future__ import annotations

import pandas as pd
import pytest

from quantcf.data import (
    DataValidationError,
    ManifestError,
    build_adjusted_panel,
    create_source_manifest,
    make_shareable_sample,
    validate_tushare_prices,
    verify_source_manifest,
)


def _snapshots() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = ["20240102", "20240103", "20240104", "20240105"]
    rows = []
    factors = []
    values = {
        "AAA.SH": ([10.0, 9.2, 9.9, 9.6], [1.0, 1.1, 1.1, 1.2]),
        "BBB.SH": ([20.0, 20.4, 20.0, 20.8], [2.0, 2.0, 2.0, 2.0]),
    }
    for asset, (closes, adjustment) in values.items():
        for index, (date, close, factor) in enumerate(zip(dates, closes, adjustment)):
            volume_lots = 1_000.0 + index
            rows.append(
                {
                    "ts_code": asset,
                    "trade_date": date,
                    "pre_close": closes[max(index - 1, 0)],
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "change": close - closes[max(index - 1, 0)],
                    "pct_chg": 0.0,
                    "vol": volume_lots,
                    # thousand CNY = price * (hands * 100) / 1,000
                    "amount": close * volume_lots / 10.0,
                }
            )
            factors.append(
                {"ts_code": asset, "trade_date": date, "adj_factor": factor}
            )
    return pd.DataFrame(rows), pd.DataFrame(factors)


def test_fixed_reference_adjustment_preserves_raw_values_and_units():
    prices, adjustments = _snapshots()
    panel, audit = build_adjusted_panel(
        prices,
        adjustments,
        reference_date="20240105",
        min_active_coverage=1.0,
    )

    reference = panel[panel["date"].eq(pd.Timestamp("2024-01-05"))]
    pd.testing.assert_series_equal(
        reference["close_adj"].reset_index(drop=True),
        reference["close_raw"].reset_index(drop=True),
        check_names=False,
    )
    first_a = panel[(panel["asset"] == "AAA.SH")].iloc[0]
    assert first_a["close_adj"] == pytest.approx(10.0 * 1.0 / 1.2)
    assert first_a["close_raw"] == 10.0
    assert first_a["vol_raw"] == 1_000.0
    assert first_a["volume"] == 100_000.0
    assert first_a["amount_raw"] == 1_000.0
    assert first_a["amount"] == 1_000_000.0
    assert audit["coverage_by_asset"] == {"AAA.SH": 1.0, "BBB.SH": 1.0}
    assert "hands" in audit["units"]["vol_raw"]


def test_total_return_hand_calculation_and_reference_invariance():
    prices, adjustments = _snapshots()
    at_day_three, _ = build_adjusted_panel(
        prices, adjustments, reference_date="20240104"
    )
    at_day_four, _ = build_adjusted_panel(
        prices, adjustments, reference_date="20240105"
    )
    return_three = at_day_three.set_index(["date", "asset"])["ret_total"]
    return_four = at_day_four.set_index(["date", "asset"])["ret_total"]
    pd.testing.assert_series_equal(return_three, return_four)

    # AAA day two: (9.2 * 1.1) / (10.0 * 1.0) - 1 = 1.2%.
    observed = return_four.loc[(pd.Timestamp("2024-01-03"), "AAA.SH")]
    assert observed == pytest.approx(0.012)


def test_duplicate_corrupt_ohlc_and_missing_adjustment_are_rejected():
    prices, adjustments = _snapshots()
    duplicate = pd.concat([prices, prices.iloc[[0]]], ignore_index=True)
    with pytest.raises(DataValidationError, match="Duplicate"):
        validate_tushare_prices(duplicate)

    corrupt = prices.copy()
    corrupt.loc[0, "high"] = corrupt.loc[0, "low"] - 1.0
    with pytest.raises(DataValidationError, match="OHLC"):
        validate_tushare_prices(corrupt)

    missing_factor = adjustments.drop(index=0)
    with pytest.raises(DataValidationError, match="Missing same-day adjustment"):
        build_adjusted_panel(prices, missing_factor, reference_date="20240105")


def test_coverage_and_expected_asset_checks_fail_loudly():
    prices, _ = _snapshots()
    with pytest.raises(DataValidationError, match="absent"):
        validate_tushare_prices(prices, expected_assets=["AAA.SH", "MISSING.SH"])

    sparse = prices.drop(
        prices[(prices["ts_code"] == "BBB.SH") & (prices["trade_date"] == "20240103")].index
    )
    with pytest.raises(DataValidationError, match="coverage"):
        validate_tushare_prices(sparse, min_active_coverage=0.9)


def test_manifest_detects_corruption_and_refuses_refresh(tmp_path):
    snapshot = tmp_path / "raw.csv"
    snapshot.write_text("date,value\n20240102,1\n", encoding="utf-8")
    manifest = tmp_path / "source_manifest.json"
    original = create_source_manifest({"prices": snapshot}, manifest)
    assert verify_source_manifest(manifest) == original

    snapshot.write_text("date,value\n20240102,999\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="mismatch"):
        verify_source_manifest(manifest)
    with pytest.raises(ManifestError, match="Refusing to overwrite"):
        create_source_manifest({"prices": snapshot}, manifest)


def test_shareable_sample_is_small_and_deterministic():
    prices, adjustments = _snapshots()
    panel, _ = build_adjusted_panel(prices, adjustments, reference_date="20240105")
    one = make_shareable_sample(panel, max_assets=1, max_dates=3)
    two = make_shareable_sample(panel.sample(frac=1.0, random_state=9), max_assets=1, max_dates=3)
    pd.testing.assert_frame_equal(one, two)
    assert one["asset"].unique().tolist() == ["AAA.SH"]
    assert len(one) == 3

