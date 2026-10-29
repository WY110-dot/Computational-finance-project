"""Cross-sectional factor diagnostics with explicit information timing.

The implementation deliberately mirrors the useful *ideas* in Alphalens while
remaining small enough to audit for a course project.  In particular:

* a signal observed after close on date ``t`` is labelled from open ``t+1``;
* quantile membership is fixed before a forward return is inspected;
* daily IC values are retained as missing when a cross-section is too small or
  constant instead of silently dropping the difficult dates; and
* tie breaking for quantile groups is deterministic and depends only on the
  factor value and asset identifier.

All public functions accept ordinary pandas objects.  Factors may be supplied
as ``{name: wide_frame}`` or as a long frame with ``date``, ``asset``,
``factor`` and one of ``value``/``score``/``raw_value``.  Price matrices use
dates on the index and assets in columns; long price frames are also accepted.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


DEFAULT_HORIZONS: tuple[int, ...] = (1, 5)
_VALUE_COLUMNS = ("value", "score", "raw_value", "factor_value")
_OPEN_COLUMNS = ("open_adj", "open", "adj_open", "open_price")


def _normalise_horizons(horizons: Iterable[int]) -> tuple[int, ...]:
    result = tuple(sorted({int(horizon) for horizon in horizons}))
    if not result or any(horizon <= 0 for horizon in result):
        raise ValueError("horizons must contain positive integers")
    return result


def _normalise_date(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def _choose_column(frame: pd.DataFrame, candidates: Sequence[str], what: str) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise ValueError(f"could not find a {what} column; tried {list(candidates)}")


def _as_wide(
    frame: pd.DataFrame,
    *,
    value_candidates: Sequence[str],
    what: str,
) -> pd.DataFrame:
    """Return a finite numeric date-by-asset matrix without filling gaps."""

    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{what} must be a pandas DataFrame")
    work = frame.copy()
    if {"date", "asset"}.issubset(work.columns):
        value_column = _choose_column(work, value_candidates, what)
        if work.duplicated(["date", "asset"]).any():
            examples = work.loc[work.duplicated(["date", "asset"], keep=False), ["date", "asset"]].head()
            raise ValueError(f"duplicate date/asset rows in {what}: {examples.to_dict('records')}")
        work["date"] = pd.to_datetime(work["date"], errors="raise")
        work["asset"] = work["asset"].astype(str)
        work = work.pivot(index="date", columns="asset", values=value_column)
    else:
        if isinstance(work.index, pd.MultiIndex):
            raise ValueError(f"{what} must not have a MultiIndex")
        work.index = pd.DatetimeIndex([_normalise_date(value) for value in work.index], name="date")
        work.columns = pd.Index([str(value) for value in work.columns], name="asset")

    if work.index.has_duplicates:
        raise ValueError(f"duplicate dates in {what}")
    if work.columns.has_duplicates:
        raise ValueError(f"duplicate assets in {what}")
    work = work.apply(pd.to_numeric, errors="coerce").astype(float)
    work = work.replace([np.inf, -np.inf], np.nan)
    work = work.sort_index().reindex(columns=sorted(work.columns, key=str))
    work.index.name = "date"
    work.columns.name = "asset"
    return work


def _normalise_factors(factors: Mapping[str, pd.DataFrame] | pd.DataFrame) -> dict[str, pd.DataFrame]:
    if isinstance(factors, Mapping):
        if not factors:
            raise ValueError("at least one factor is required")
        return {
            str(name): _as_wide(frame, value_candidates=_VALUE_COLUMNS, what=f"factor {name!r}")
            for name, frame in sorted(factors.items(), key=lambda item: str(item[0]))
        }

    if not isinstance(factors, pd.DataFrame):
        raise TypeError("factors must be a mapping of wide frames or a long DataFrame")
    if "factor" not in factors.columns:
        return {"factor": _as_wide(factors, value_candidates=_VALUE_COLUMNS, what="factor")}
    required = {"date", "asset", "factor"}
    if not required.issubset(factors.columns):
        raise ValueError(f"long factor data must contain {sorted(required)}")
    value_column = _choose_column(factors, _VALUE_COLUMNS, "factor value")
    work = factors.copy()
    if "is_valid" in work.columns:
        work.loc[~work["is_valid"].fillna(False).astype(bool), value_column] = np.nan
    if work.duplicated(["date", "asset", "factor"]).any():
        raise ValueError("duplicate date/asset/factor rows in factor data")
    result: dict[str, pd.DataFrame] = {}
    for name, group in work.groupby("factor", sort=True, dropna=False):
        if pd.isna(name):
            raise ValueError("factor names must not be missing")
        result[str(name)] = _as_wide(
            group[["date", "asset", value_column]],
            value_candidates=(value_column,),
            what=f"factor {name!r}",
        )
    if not result:
        raise ValueError("at least one factor is required")
    return result


def compute_forward_returns(
    open_prices: pd.DataFrame,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
) -> dict[int, pd.DataFrame]:
    """Compute executable open-to-open labels for close-formed signals.

    For a horizon ``h``, the label attached to formation date ``t`` is
    ``open[t + 1 + h] / open[t + 1] - 1``.  The function never forward-fills
    prices, so a missing entry or exit open produces a missing label.
    """

    horizon_values = _normalise_horizons(horizons)
    prices = _as_wide(open_prices, value_candidates=_OPEN_COLUMNS, what="open price")
    labels: dict[int, pd.DataFrame] = {}
    for horizon in horizon_values:
        entry = prices.shift(-1)
        exit_price = prices.shift(-(horizon + 1))
        result = exit_price.divide(entry).subtract(1.0)
        result = result.replace([np.inf, -np.inf], np.nan)
        labels[horizon] = result
    return labels


def _normalise_labels(
    labels: Mapping[int, pd.DataFrame] | pd.DataFrame,
    horizons: tuple[int, ...],
) -> dict[int, pd.DataFrame]:
    if isinstance(labels, Mapping):
        missing = set(horizons) - {int(key) for key in labels}
        if missing:
            raise ValueError(f"labels are missing horizons: {sorted(missing)}")
        keyed = {int(key): value for key, value in labels.items()}
        return {
            horizon: _as_wide(
                keyed[horizon],
                value_candidates=("forward_return", "return", "label", "value"),
                what=f"{horizon}-day label",
            )
            for horizon in horizons
        }

    if not isinstance(labels, pd.DataFrame):
        raise TypeError("labels must be a mapping or DataFrame")
    if {"date", "asset", "horizon"}.issubset(labels.columns):
        value_column = _choose_column(labels, ("forward_return", "return", "label", "value"), "label")
        result: dict[int, pd.DataFrame] = {}
        for horizon in horizons:
            subset = labels.loc[pd.to_numeric(labels["horizon"], errors="coerce") == horizon]
            result[horizon] = _as_wide(
                subset[["date", "asset", value_column]],
                value_candidates=(value_column,),
                what=f"{horizon}-day label",
            )
        return result
    if len(horizons) != 1:
        raise ValueError("a single label matrix can only be used with one horizon")
    return {
        horizons[0]: _as_wide(
            labels,
            value_candidates=("forward_return", "return", "label", "value"),
            what=f"{horizons[0]}-day label",
        )
    }


def assign_quantile_groups(
    scores: pd.Series,
    n_groups: int = 5,
    min_assets: int = 2,
) -> pd.Series:
    """Assign stable formation-time groups from low (1) to high (``n_groups``).

    Equal values are ordered by the string representation of the asset id.
    This deliberately permits a tie to straddle adjacent groups: every valid
    cross-section produces balanced, reproducible groups without consulting a
    future return.  IC ranks, by contrast, use average ranks for ties.
    """

    if n_groups < 2:
        raise ValueError("n_groups must be at least 2")
    if min_assets < 2:
        raise ValueError("min_assets must be at least 2")
    numeric = pd.to_numeric(scores, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(numeric) < max(n_groups, min_assets) or numeric.nunique(dropna=True) < 2:
        return pd.Series(index=pd.Index([], dtype=object), dtype="Int64", name="group")
    ordered_assets = sorted(numeric.index, key=lambda asset: (float(numeric.loc[asset]), str(asset)))
    membership = {
        asset: 1 + min(n_groups - 1, int(position * n_groups / len(ordered_assets)))
        for position, asset in enumerate(ordered_assets)
    }
    result = pd.Series(membership, dtype="Int64", name="group")
    result.index.name = scores.index.name or "asset"
    return result


def _safe_correlation(left: pd.Series, right: pd.Series, method: str, min_assets: int) -> float:
    valid = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if len(valid) < min_assets or valid["left"].nunique() < 2 or valid["right"].nunique() < 2:
        return np.nan
    if method == "spearman":
        left_values = valid["left"].rank(method="average")
        right_values = valid["right"].rank(method="average")
        value = left_values.corr(right_values, method="pearson")
    else:
        value = valid["left"].corr(valid["right"], method="pearson")
    return float(value) if pd.notna(value) and np.isfinite(value) else np.nan


def _mean_std_ir(series: pd.Series) -> tuple[float, float, float, int]:
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return np.nan, np.nan, np.nan, 0
    mean = float(clean.mean())
    std = float(clean.std(ddof=1)) if len(clean) >= 2 else np.nan
    information_ratio = mean / std if pd.notna(std) and std > 0 else np.nan
    return mean, std, information_ratio, int(len(clean))


def _monotonicity(group_means: pd.Series) -> tuple[str, float]:
    values = group_means.dropna().sort_index()
    if len(values) < 2:
        return "insufficient", np.nan
    differences = np.diff(values.to_numpy(dtype=float))
    if np.all(differences > 0):
        label = "strict_increasing"
    elif np.all(differences >= 0) and np.any(differences > 0):
        label = "non_decreasing"
    elif np.all(differences < 0):
        label = "strict_decreasing"
    elif np.all(differences <= 0) and np.any(differences < 0):
        label = "non_increasing"
    else:
        label = "mixed"
    if values.nunique(dropna=True) < 2:
        correlation = np.nan
    else:
        correlation = pd.Series(values.index.astype(float)).corr(
            pd.Series(values.to_numpy(dtype=float)).rank(method="average"), method="pearson"
        )
    return label, float(correlation) if pd.notna(correlation) else np.nan


@dataclass
class DiagnosticResult:
    """All diagnostic tables; every field is safe to write independently."""

    coverage: pd.DataFrame
    distribution: pd.DataFrame
    ic_timeseries: pd.DataFrame
    ic_summary: pd.DataFrame
    group_returns: pd.DataFrame
    group_summary: pd.DataFrame
    spread_timeseries: pd.DataFrame
    spread_summary: pd.DataFrame
    rank_dynamics: pd.DataFrame
    quantile_turnover: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    def save(self, directory: str | Path) -> dict[str, Path]:
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        for name, table in self.tables().items():
            path = destination / f"{name}.csv"
            table.to_csv(path, index=False, encoding="utf-8-sig")
            paths[name] = path
        return paths


def analyze_factors(
    factors: Mapping[str, pd.DataFrame] | pd.DataFrame,
    open_prices: pd.DataFrame | None = None,
    *,
    labels: Mapping[int, pd.DataFrame] | pd.DataFrame | None = None,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
    n_groups: int = 5,
    min_assets: int = 6,
    start: Any | None = None,
    end: Any | None = None,
) -> DiagnosticResult:
    """Run coverage, IC, quantile-return and turnover diagnostics.

    Exactly one source of labels is needed: either ``open_prices`` (preferred,
    because the timing formula is then explicit) or precomputed ``labels``.
    """

    horizon_values = _normalise_horizons(horizons)
    if n_groups < 2:
        raise ValueError("n_groups must be at least 2")
    if min_assets < 2:
        raise ValueError("min_assets must be at least 2")
    if labels is None:
        if open_prices is None:
            raise ValueError("open_prices or labels is required")
        label_frames = compute_forward_returns(open_prices, horizon_values)
    else:
        label_frames = _normalise_labels(labels, horizon_values)
    factor_frames = _normalise_factors(factors)

    start_date = _normalise_date(start) if start is not None else None
    end_date = _normalise_date(end) if end is not None else None
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start must not be after end")

    coverage_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    ic_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    spread_rows: list[dict[str, Any]] = []
    rank_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []

    for factor_name, original_frame in factor_frames.items():
        frame = original_frame
        if start_date is not None:
            frame = frame.loc[frame.index >= start_date]
        if end_date is not None:
            frame = frame.loc[frame.index <= end_date]
        if frame.empty:
            continue

        valid_counts = frame.notna().sum(axis=1)
        for date, count in valid_counts.items():
            coverage_rows.append(
                {
                    "date": date,
                    "factor": factor_name,
                    "valid_assets": int(count),
                    "total_assets": int(frame.shape[1]),
                    "coverage": float(count / frame.shape[1]) if frame.shape[1] else np.nan,
                }
            )
        flat = frame.to_numpy(dtype=float).ravel()
        flat = flat[np.isfinite(flat)]
        total_slots = int(frame.size)
        values = pd.Series(flat, dtype=float)
        distribution_rows.append(
            {
                "factor": factor_name,
                "observations": int(len(values)),
                "total_slots": total_slots,
                "coverage": float(len(values) / total_slots) if total_slots else np.nan,
                "dates": int(len(frame)),
                "mean_assets": float(valid_counts.mean()) if len(valid_counts) else np.nan,
                "min_assets": int(valid_counts.min()) if len(valid_counts) else 0,
                "max_assets": int(valid_counts.max()) if len(valid_counts) else 0,
                "mean": float(values.mean()) if len(values) else np.nan,
                "std": float(values.std(ddof=1)) if len(values) >= 2 else np.nan,
                "min": float(values.min()) if len(values) else np.nan,
                "p01": float(values.quantile(0.01)) if len(values) else np.nan,
                "p25": float(values.quantile(0.25)) if len(values) else np.nan,
                "p50": float(values.quantile(0.50)) if len(values) else np.nan,
                "p75": float(values.quantile(0.75)) if len(values) else np.nan,
                "p99": float(values.quantile(0.99)) if len(values) else np.nan,
                "max": float(values.max()) if len(values) else np.nan,
                "skew": float(values.skew()) if len(values) >= 3 else np.nan,
                "kurtosis": float(values.kurt()) if len(values) >= 4 else np.nan,
            }
        )

        # Membership is computed exactly once per formation date and reused by
        # every horizon.  Missing labels can therefore never move an asset.
        membership_by_date: dict[pd.Timestamp, pd.Series] = {
            date: assign_quantile_groups(scores, n_groups=n_groups, min_assets=min_assets)
            for date, scores in frame.iterrows()
        }

        previous_scores: pd.Series | None = None
        previous_membership: pd.Series | None = None
        for date, scores in frame.iterrows():
            current_scores = scores.dropna()
            current_membership = membership_by_date[date]
            autocorrelation = np.nan
            rank_turnover = np.nan
            n_common = 0
            if previous_scores is not None:
                common = previous_scores.dropna().index.intersection(current_scores.index)
                n_common = int(len(common))
                if n_common >= min_assets:
                    previous_rank = previous_scores.loc[common].rank(method="average", pct=True)
                    current_rank = current_scores.loc[common].rank(method="average", pct=True)
                    if previous_rank.nunique() > 1 and current_rank.nunique() > 1:
                        autocorrelation = float(previous_rank.corr(current_rank))
                    rank_turnover = float((current_rank - previous_rank).abs().mean())
            rank_rows.append(
                {
                    "date": date,
                    "factor": factor_name,
                    "n_common": n_common,
                    "rank_autocorrelation": autocorrelation,
                    "rank_turnover": rank_turnover,
                }
            )
            for group_number in range(1, n_groups + 1):
                current_assets = set(current_membership[current_membership == group_number].index)
                previous_assets = (
                    set(previous_membership[previous_membership == group_number].index)
                    if previous_membership is not None
                    else set()
                )
                retained = len(current_assets & previous_assets)
                turnover = 1.0 - retained / len(previous_assets) if previous_assets else np.nan
                turnover_rows.append(
                    {
                        "date": date,
                        "factor": factor_name,
                        "group": group_number,
                        "n_previous": len(previous_assets),
                        "n_current": len(current_assets),
                        "n_retained": retained,
                        "turnover": turnover,
                    }
                )
            previous_scores = current_scores
            previous_membership = current_membership

        for horizon in horizon_values:
            label = label_frames[horizon].reindex(index=frame.index, columns=frame.columns)
            for date, scores in frame.iterrows():
                future_return = label.loc[date]
                common_mask = scores.notna() & future_return.notna()
                usable_scores = scores[common_mask]
                usable_returns = future_return[common_mask]
                ic_rows.append(
                    {
                        "date": date,
                        "factor": factor_name,
                        "horizon": horizon,
                        "n_factor": int(scores.notna().sum()),
                        "n_label": int(common_mask.sum()),
                        "ic": _safe_correlation(usable_scores, usable_returns, "pearson", min_assets),
                        "rank_ic": _safe_correlation(usable_scores, usable_returns, "spearman", min_assets),
                    }
                )

                membership = membership_by_date[date]
                daily_returns: dict[int, float] = {}
                for group_number in range(1, n_groups + 1):
                    formed_assets = membership[membership == group_number].index
                    valid_returns = future_return.reindex(formed_assets).dropna()
                    mean_return = float(valid_returns.mean()) if len(valid_returns) else np.nan
                    daily_returns[group_number] = mean_return
                    group_rows.append(
                        {
                            "date": date,
                            "factor": factor_name,
                            "horizon": horizon,
                            "group": group_number,
                            "n_formed": int(len(formed_assets)),
                            "n_valid": int(len(valid_returns)),
                            "mean_return": mean_return,
                        }
                    )
                low_return = daily_returns.get(1, np.nan)
                high_return = daily_returns.get(n_groups, np.nan)
                spread_rows.append(
                    {
                        "date": date,
                        "factor": factor_name,
                        "horizon": horizon,
                        "low_return": low_return,
                        "high_return": high_return,
                        "high_low_spread": (
                            high_return - low_return
                            if np.isfinite(high_return) and np.isfinite(low_return)
                            else np.nan
                        ),
                    }
                )

    coverage = pd.DataFrame(
        coverage_rows,
        columns=["date", "factor", "valid_assets", "total_assets", "coverage"],
    )
    distribution = pd.DataFrame(distribution_rows)
    ic_timeseries = pd.DataFrame(
        ic_rows,
        columns=["date", "factor", "horizon", "n_factor", "n_label", "ic", "rank_ic"],
    )
    group_returns = pd.DataFrame(
        group_rows,
        columns=["date", "factor", "horizon", "group", "n_formed", "n_valid", "mean_return"],
    )
    spread_timeseries = pd.DataFrame(
        spread_rows,
        columns=["date", "factor", "horizon", "low_return", "high_return", "high_low_spread"],
    )
    rank_dynamics = pd.DataFrame(
        rank_rows,
        columns=["date", "factor", "n_common", "rank_autocorrelation", "rank_turnover"],
    )
    quantile_turnover = pd.DataFrame(
        turnover_rows,
        columns=["date", "factor", "group", "n_previous", "n_current", "n_retained", "turnover"],
    )

    ic_summary_rows: list[dict[str, Any]] = []
    if not ic_timeseries.empty:
        for (factor_name, horizon), group in ic_timeseries.groupby(["factor", "horizon"], sort=True):
            mean_ic, std_ic, ic_ir, ic_days = _mean_std_ir(group["ic"])
            mean_rank_ic, std_rank_ic, rank_ic_ir, rank_ic_days = _mean_std_ir(group["rank_ic"])
            ic_summary_rows.append(
                {
                    "factor": factor_name,
                    "horizon": int(horizon),
                    "mean_ic": mean_ic,
                    "std_ic": std_ic,
                    "ic_ir": ic_ir,
                    "mean_rank_ic": mean_rank_ic,
                    "std_rank_ic": std_rank_ic,
                    "rank_ic_ir": rank_ic_ir,
                    "ic_days": ic_days,
                    "rank_ic_days": rank_ic_days,
                    "total_dates": int(len(group)),
                    "mean_factor_assets": float(group["n_factor"].mean()),
                    "mean_effective_assets": float(group["n_label"].mean()),
                }
            )
    ic_summary = pd.DataFrame(ic_summary_rows)

    group_summary_rows: list[dict[str, Any]] = []
    if not group_returns.empty:
        for (factor_name, horizon, group_number), group in group_returns.groupby(
            ["factor", "horizon", "group"], sort=True
        ):
            returns = group["mean_return"].dropna()
            group_summary_rows.append(
                {
                    "factor": factor_name,
                    "horizon": int(horizon),
                    "group": int(group_number),
                    "mean_return": float(returns.mean()) if len(returns) else np.nan,
                    "std_return": float(returns.std(ddof=1)) if len(returns) >= 2 else np.nan,
                    "valid_days": int(len(returns)),
                    "n_formed_total": int(group["n_formed"].sum()),
                    "n_valid_total": int(group["n_valid"].sum()),
                }
            )
    group_summary = pd.DataFrame(group_summary_rows)

    spread_summary_rows: list[dict[str, Any]] = []
    if not spread_timeseries.empty:
        grouped = spread_timeseries.groupby(["factor", "horizon"], sort=True)
        for (factor_name, horizon), spread_group in grouped:
            spread_values = spread_group["high_low_spread"].dropna()
            means = (
                group_summary.loc[
                    (group_summary["factor"] == factor_name) & (group_summary["horizon"] == horizon)
                ]
                .set_index("group")["mean_return"]
                .sort_index()
            )
            monotonicity, monotonicity_score = _monotonicity(means)
            spread_summary_rows.append(
                {
                    "factor": factor_name,
                    "horizon": int(horizon),
                    "low_group_mean": float(means.get(1, np.nan)),
                    "high_group_mean": float(means.get(n_groups, np.nan)),
                    "mean_high_low_spread": float(spread_values.mean()) if len(spread_values) else np.nan,
                    "std_high_low_spread": (
                        float(spread_values.std(ddof=1)) if len(spread_values) >= 2 else np.nan
                    ),
                    "spread_days": int(len(spread_values)),
                    "monotonicity": monotonicity,
                    "monotonicity_score": monotonicity_score,
                }
            )
    spread_summary = pd.DataFrame(spread_summary_rows)

    return DiagnosticResult(
        coverage=coverage,
        distribution=distribution,
        ic_timeseries=ic_timeseries,
        ic_summary=ic_summary,
        group_returns=group_returns,
        group_summary=group_summary,
        spread_timeseries=spread_timeseries,
        spread_summary=spread_summary,
        rank_dynamics=rank_dynamics,
        quantile_turnover=quantile_turnover,
    )


class FactorDiagnostics:
    """Small stateful wrapper retained for convenient pipeline integration."""

    def __init__(
        self,
        factor_data: Mapping[str, pd.DataFrame] | pd.DataFrame,
        open_prices: pd.DataFrame | None = None,
        *,
        labels: Mapping[int, pd.DataFrame] | pd.DataFrame | None = None,
        forward_periods: Iterable[int] = DEFAULT_HORIZONS,
        num_groups: int = 5,
        min_assets: int = 6,
        start: Any | None = None,
        end: Any | None = None,
    ) -> None:
        self._arguments = dict(
            factors=factor_data,
            open_prices=open_prices,
            labels=labels,
            horizons=forward_periods,
            n_groups=num_groups,
            min_assets=min_assets,
            start=start,
            end=end,
        )
        self._result: DiagnosticResult | None = None

    def run(self) -> DiagnosticResult:
        if self._result is None:
            self._result = analyze_factors(**self._arguments)
        return self._result

    def calculate_ic(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        result = self.run()
        return result.ic_summary.copy(), result.ic_timeseries.copy()

    def calculate_group_returns(self) -> pd.DataFrame:
        return self.run().group_returns.copy()


# A concise alias makes the intent clear at call sites.
diagnose_factors = analyze_factors


__all__ = [
    "DEFAULT_HORIZONS",
    "DiagnosticResult",
    "FactorDiagnostics",
    "analyze_factors",
    "assign_quantile_groups",
    "compute_forward_returns",
    "diagnose_factors",
]
