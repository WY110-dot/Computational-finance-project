from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantcf.factors import (
    FactorRegistry,
    calculate_factors,
    low_volatility,
    momentum,
    next_open_forward_labels,
    reversal,
)


def test_pure_factor_formulas_match_hand_calculations():
    close = pd.Series([100.0, 110.0, 99.0])
    observed_momentum = momentum(close, 1)
    observed_reversal = reversal(close, 1)
    assert observed_momentum.iloc[1] == pytest.approx(0.10)
    assert observed_momentum.iloc[2] == pytest.approx(-0.10)
    assert observed_reversal.iloc[2] == pytest.approx(0.10)

    observed_low_vol = low_volatility(close, 2)
    expected_sample_std = np.std([0.10, -0.10], ddof=1)
    assert observed_low_vol.iloc[2] == pytest.approx(-expected_sample_std)


def _factor_panel(periods: int = 10) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=periods)
    rows = []
    for index, date in enumerate(dates):
        rows.extend(
            [
                {"date": date, "asset": "AAA", "close_adj": 100.0 * 1.02**index},
                {"date": date, "asset": "BBB", "close_adj": 100.0 * 1.01**index},
                {"date": date, "asset": "CCC", "close_adj": 100.0 * 0.99**index},
            ]
        )
    return pd.DataFrame(rows)


def test_standard_long_output_rank_direction_and_warmup():
    panel = _factor_panel(6)
    result = calculate_factors(
        panel,
        windows={"momentum": 2, "reversal": 2, "low_volatility": 2},
    )
    assert list(result.columns) == [
        "date",
        "asset",
        "factor",
        "raw_value",
        "score",
        "value",
        "is_valid",
        "window",
        "preprocessing",
    ]
    first_date = result["date"].min()
    assert not result[result["date"] == first_date]["is_valid"].any()

    last = result[result["date"] == result["date"].max()]
    mom = last[last["factor"] == "momentum"].set_index("asset")
    rev = last[last["factor"] == "reversal"].set_index("asset")
    assert mom.loc["AAA", "score"] == 1.0
    assert mom.loc["CCC", "score"] == pytest.approx(1 / 3)
    assert rev.loc["CCC", "score"] == 1.0
    assert rev.loc["AAA", "score"] == pytest.approx(1 / 3)
    assert (last.loc[last["is_valid"], "score"] == last.loc[last["is_valid"], "value"]).all()


def test_factor_aliases_are_registry_metadata_not_separate_formulas():
    assert FactorRegistry.get("MOM20").name == "momentum"
    assert FactorRegistry.get("REV5").name == "reversal"
    assert FactorRegistry.get("LOWVOL20").name == "low_volatility"
    assert all(item["direction"] == "higher_is_better" for item in FactorRegistry.list_factors())


def test_next_open_labels_have_correct_timing_and_no_fill():
    dates = pd.bdate_range("2024-01-02", periods=7)
    opens = [10.0, 11.0, 12.0, 15.0, 18.0, 20.0, 22.0]
    panel = pd.DataFrame(
        {"date": dates, "asset": "AAA", "open_adj": opens}
    )
    labels = next_open_forward_labels(panel, horizons=(1, 5))
    first = labels[labels["date"] == dates[0]].set_index("horizon")
    assert first.loc[1, "entry_date"] == dates[1]
    assert first.loc[1, "exit_date"] == dates[2]
    assert first.loc[1, "forward_return"] == pytest.approx(12.0 / 11.0 - 1.0)
    assert first.loc[5, "forward_return"] == pytest.approx(22.0 / 11.0 - 1.0)

    missing = panel.copy()
    missing.loc[1, "open_adj"] = np.nan
    missing_labels = next_open_forward_labels(missing, horizons=(1,))
    first_missing = missing_labels[missing_labels["date"] == dates[0]].iloc[0]
    assert not first_missing["is_valid"]
    assert pd.isna(first_missing["forward_return"])


def test_appending_future_rows_does_not_change_historical_factors():
    prefix = _factor_panel(10)
    future_dates = pd.bdate_range(prefix["date"].max() + pd.Timedelta(days=1), periods=4)
    future_rows = []
    for offset, date in enumerate(future_dates):
        for asset, multiplier in (("AAA", 50.0), ("BBB", 0.01), ("CCC", 7.0)):
            future_rows.append(
                {
                    "date": date,
                    "asset": asset,
                    "close_adj": (offset + 1) * multiplier,
                }
            )
    full = pd.concat([prefix, pd.DataFrame(future_rows)], ignore_index=True)
    kwargs = {"windows": {"momentum": 3, "reversal": 3, "low_volatility": 3}}
    prefix_result = calculate_factors(prefix, **kwargs)
    full_result = calculate_factors(full, **kwargs)
    historical = full_result[full_result["date"] <= prefix["date"].max()].reset_index(drop=True)
    pd.testing.assert_frame_equal(prefix_result, historical)


def test_shuffled_input_produces_identical_factor_output():
    panel = _factor_panel(8)
    ordered = calculate_factors(panel, windows={"momentum": 3})
    shuffled = calculate_factors(
        panel.sample(frac=1.0, random_state=42), windows={"momentum": 3}
    )
    pd.testing.assert_frame_equal(ordered, shuffled)

