from __future__ import annotations

import numpy as np
import pandas as pd

from quantcf.diagnostics import (
    FactorDiagnostics,
    analyze_factors,
    assign_quantile_groups,
    compute_forward_returns,
)


def _wide(values: list[list[float]], dates: pd.DatetimeIndex, assets: list[str]) -> pd.DataFrame:
    return pd.DataFrame(values, index=dates, columns=assets, dtype=float)


def test_forward_returns_respect_next_open_timing() -> None:
    dates = pd.bdate_range("2024-01-01", periods=8)
    opens = pd.DataFrame(
        {
            "A": [100, 110, 121, 133.1, 146.41, 161.051, 177.1561, 194.87171],
            "B": [50, 51, 53, 52, 55, 56, 58, 60],
        },
        index=dates,
    )
    labels = compute_forward_returns(opens, horizons=[1, 3])

    assert np.isclose(labels[1].loc[dates[0], "A"], opens.loc[dates[2], "A"] / opens.loc[dates[1], "A"] - 1)
    assert np.isclose(labels[3].loc[dates[0], "B"], opens.loc[dates[4], "B"] / opens.loc[dates[1], "B"] - 1)
    assert labels[1].iloc[-2:].isna().all().all()
    assert labels[3].iloc[-4:].isna().all().all()


def test_daily_ic_rank_ic_multiple_horizons_and_constants() -> None:
    dates = pd.bdate_range("2024-02-01", periods=3)
    assets = list("ABCDE")
    increasing = _wide([[1, 2, 3, 4, 5]] * 3, dates, assets)
    constant = _wide([[7, 7, 7, 7, 7]] * 3, dates, assets)
    one_day = _wide([[0.01, 0.04, 0.09, 0.16, 0.25]] * 3, dates, assets)
    five_day = _wide([[0.5, 0.4, 0.3, 0.2, 0.1]] * 3, dates, assets)

    result = analyze_factors(
        {"signal": increasing, "constant": constant},
        labels={1: one_day, 5: five_day},
        horizons=[1, 5],
        n_groups=5,
        min_assets=5,
    )

    signal_1 = result.ic_timeseries.query("factor == 'signal' and horizon == 1")
    signal_5 = result.ic_timeseries.query("factor == 'signal' and horizon == 5")
    constant_rows = result.ic_timeseries.query("factor == 'constant'")
    assert np.allclose(signal_1["rank_ic"], 1.0)
    assert (signal_1["ic"] < 0.99).all() and (signal_1["ic"] > 0).all()
    assert np.allclose(signal_5["ic"], -1.0)
    assert np.allclose(signal_5["rank_ic"], -1.0)
    assert constant_rows["ic"].isna().all()
    assert constant_rows["rank_ic"].isna().all()


def test_too_few_assets_retains_date_with_nan_ic() -> None:
    dates = pd.bdate_range("2024-03-01", periods=2)
    scores = _wide([[1, 2, np.nan], [2, 3, np.nan]], dates, ["A", "B", "C"])
    labels = _wide([[0.1, 0.2, 0.3], [0.2, 0.3, 0.4]], dates, ["A", "B", "C"])
    result = analyze_factors(
        {"small": scores}, labels={1: labels}, horizons=[1], n_groups=2, min_assets=3
    )
    assert len(result.ic_timeseries) == 2
    assert result.ic_timeseries["n_label"].eq(2).all()
    assert result.ic_timeseries["ic"].isna().all()
    summary = result.ic_summary.iloc[0]
    assert summary["ic_days"] == 0
    assert np.isnan(summary["mean_ic"])


def test_stable_ties_and_missing_labels_do_not_regroup() -> None:
    scores = pd.Series({"B": 1.0, "A": 1.0, "F": 4.0, "D": 3.0, "C": 2.0, "E": 4.0})
    membership = assign_quantile_groups(scores, n_groups=3, min_assets=6)
    assert membership.to_dict() == {"A": 1, "B": 1, "C": 2, "D": 2, "E": 3, "F": 3}

    date = pd.Timestamp("2024-04-01")
    factor = pd.DataFrame([scores], index=[date])
    label = pd.DataFrame(
        [{"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04, "E": np.nan, "F": 0.06}],
        index=[date],
    )
    result = analyze_factors(
        {"tied": factor}, labels={1: label}, horizons=[1], n_groups=3, min_assets=6
    )
    high = result.group_returns.query("group == 3").iloc[0]
    assert high["n_formed"] == 2
    assert high["n_valid"] == 1
    # F remains in the high group; E's missing label cannot promote D.
    assert np.isclose(high["mean_return"], label.loc[date, "F"])


def test_high_low_and_monotonicity_are_based_on_daily_group_returns() -> None:
    dates = pd.bdate_range("2024-05-01", periods=2)
    assets = list("ABCDEF")
    scores = _wide([[1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]], dates, assets)
    labels = _wide([[0.01, 0.02, 0.03, 0.04, 0.05, 0.06]] * 2, dates, assets)
    result = analyze_factors(
        {"ordered": scores}, labels={1: labels}, horizons=[1], n_groups=3, min_assets=6
    )
    summary = result.spread_summary.iloc[0]
    assert summary["monotonicity"] == "strict_increasing"
    assert np.isclose(summary["low_group_mean"], 0.015)
    assert np.isclose(summary["high_group_mean"], 0.055)
    assert np.isclose(summary["mean_high_low_spread"], 0.04)
    assert summary["spread_days"] == 2


def test_rank_autocorrelation_and_quantile_turnover() -> None:
    dates = pd.bdate_range("2024-06-03", periods=2)
    assets = list("ABCD")
    factor = _wide([[1, 2, 3, 4], [4, 3, 2, 1]], dates, assets)
    labels = _wide([[0.1, 0.2, 0.3, 0.4]] * 2, dates, assets)
    result = analyze_factors(
        {"flip": factor}, labels={1: labels}, horizons=[1], n_groups=2, min_assets=4
    )
    second = result.rank_dynamics.iloc[1]
    assert np.isclose(second["rank_autocorrelation"], -1.0)
    assert second["rank_turnover"] > 0
    second_turnover = result.quantile_turnover.query("date == @dates[1]")
    assert np.allclose(second_turnover["turnover"], 1.0)


def test_long_input_coverage_and_wrapper_compatibility() -> None:
    dates = pd.bdate_range("2024-07-01", periods=2)
    long = pd.DataFrame(
        [
            {"date": dates[0], "asset": "A", "factor": "x", "value": 1.0, "is_valid": True},
            {"date": dates[0], "asset": "B", "factor": "x", "value": 2.0, "is_valid": True},
            {"date": dates[1], "asset": "A", "factor": "x", "value": 3.0, "is_valid": False},
            {"date": dates[1], "asset": "B", "factor": "x", "value": 4.0, "is_valid": True},
        ]
    )
    labels = pd.DataFrame([[0.1, 0.2], [0.2, 0.3]], index=dates, columns=["A", "B"])
    diagnostics = FactorDiagnostics(
        long, labels={1: labels}, forward_periods=[1], num_groups=2, min_assets=2
    )
    result = diagnostics.run()
    distribution = result.distribution.iloc[0]
    assert distribution["observations"] == 3
    assert np.isclose(distribution["coverage"], 0.75)
    summary, timeseries = diagnostics.calculate_ic()
    pd.testing.assert_frame_equal(summary, result.ic_summary)
    pd.testing.assert_frame_equal(timeseries, result.ic_timeseries)
