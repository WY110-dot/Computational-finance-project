"""Portfolio construction, deliberately separated from execution.

The functions in this module only turn information available at a signal close
into target weights for the *next* trading day's open.  They do not inspect an
execution price, estimate transaction costs, or mutate an account.  This is the
same strategy/broker boundary used by event-driven engines such as Backtrader
and makes look-ahead mistakes much easier to detect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


_FREQUENCY_ALIASES = {
    "d": "daily",
    "daily": "daily",
    "w": "weekly",
    "weekly": "weekly",
    "m": "monthly",
    "monthly": "monthly",
}


@dataclass(frozen=True)
class PortfolioConfig:
    """Rules used to translate a cross-sectional score into target weights."""

    top_n: int = 5
    invest_fraction: float = 0.99
    min_assets: int = 1
    frequency: str = "monthly"

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n must be at least one")
        if self.min_assets < 1:
            raise ValueError("min_assets must be at least one")
        if not 0.0 <= self.invest_fraction <= 1.0:
            raise ValueError("invest_fraction must be between zero and one")
        if str(self.frequency).lower() not in _FREQUENCY_ALIASES:
            raise ValueError(f"unsupported rebalance frequency: {self.frequency}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "PortfolioConfig":
        """Build from either a flat mapping or the project's nested config."""

        if value is None:
            return cls()
        raw: Mapping[str, object] = value
        strategy = raw.get("strategy")
        factors = raw.get("factors")
        if isinstance(strategy, Mapping):
            raw = {**raw, **strategy}
        min_assets = raw.get("min_assets")
        if min_assets is None and isinstance(factors, Mapping):
            min_assets = factors.get("min_assets")
        return cls(
            top_n=int(raw.get("top_n", 5)),
            invest_fraction=float(raw.get("invest_fraction", 0.99)),
            min_assets=int(1 if min_assets is None else min_assets),
            frequency=str(
                raw.get(
                    "frequency",
                    raw.get("rebalance_frequency", raw.get("baseline_frequency", "monthly")),
                )
            ),
        )


def _calendar_index(calendar: Iterable[object] | pd.Index) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(list(calendar))).normalize()
    if index.hasnans:
        raise ValueError("calendar contains an invalid date")
    if index.has_duplicates:
        raise ValueError("calendar dates must be unique")
    return index.sort_values()


def _score_matrix(scores: pd.DataFrame) -> pd.DataFrame:
    """Accept a wide score matrix or a conventional long score table."""

    if not isinstance(scores, pd.DataFrame):
        raise TypeError("scores must be a pandas DataFrame")
    if {"date", "asset"}.issubset(scores.columns):
        value_column = next(
            (name for name in ("score", "value", "raw_value", "factor_value") if name in scores),
            None,
        )
        if value_column is None:
            raise ValueError("long scores need a score/value column")
        long = scores[["date", "asset", value_column]].copy()
        long["date"] = pd.to_datetime(long["date"]).dt.normalize()
        if long.duplicated(["date", "asset"]).any():
            raise ValueError("scores contain duplicate date/asset rows")
        matrix = long.pivot(index="date", columns="asset", values=value_column)
    else:
        matrix = scores.copy()
        matrix.index = pd.DatetimeIndex(pd.to_datetime(matrix.index)).normalize()
        if matrix.index.has_duplicates:
            raise ValueError("score dates must be unique")
    matrix.columns = matrix.columns.astype(str)
    if matrix.columns.duplicated().any():
        raise ValueError("score assets must be unique")
    return matrix.sort_index().sort_index(axis=1).apply(pd.to_numeric, errors="coerce")


def signal_execution_pairs(
    calendar: Iterable[object] | pd.Index,
    frequency: str,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return close-signal/next-open pairs for a rebalance schedule.

    Weekly and monthly signals are formed on the final observed trading day of
    each period and are executed on the immediately following trading day.  A
    daily schedule pairs every date except the last with its successor.
    """

    dates = _calendar_index(calendar)
    if len(dates) < 2:
        return []
    canonical = _FREQUENCY_ALIASES.get(str(frequency).lower())
    if canonical is None:
        raise ValueError(f"unsupported rebalance frequency: {frequency}")
    if canonical == "daily":
        signal_positions = np.arange(len(dates) - 1)
    else:
        periods = dates.to_period("W-FRI" if canonical == "weekly" else "M")
        # A signal is actionable only if its next trading date exists.
        period_ends = np.r_[periods[:-1] != periods[1:], True]
        signal_positions = np.flatnonzero(period_ends)
        signal_positions = signal_positions[signal_positions < len(dates) - 1]
    return [(dates[i], dates[i + 1]) for i in signal_positions]


def generate_target_weights(
    scores: pd.DataFrame,
    calendar: Iterable[object] | pd.Index | None = None,
    config: PortfolioConfig | Mapping[str, object] | None = None,
    *,
    frequency: str | None = None,
    top_n: int | None = None,
    invest_fraction: float | None = None,
    min_assets: int | None = None,
    equal_weight_universe: bool = False,
    start: object | None = None,
    end: object | None = None,
) -> pd.DataFrame:
    """Create deterministic long-only target weights.

    Ties are resolved by the asset identifier in ascending order.  When fewer
    than ``min_assets`` scores are available, that rebalance is skipped (the
    broker therefore keeps the existing account rather than silently trading
    to cash).  Only the score at ``signal_date`` is consulted.
    """

    matrix = _score_matrix(scores)
    base = config if isinstance(config, PortfolioConfig) else PortfolioConfig.from_mapping(config)
    cfg = PortfolioConfig(
        top_n=base.top_n if top_n is None else int(top_n),
        invest_fraction=base.invest_fraction if invest_fraction is None else float(invest_fraction),
        min_assets=base.min_assets if min_assets is None else int(min_assets),
        frequency=base.frequency if frequency is None else str(frequency),
    )
    dates = _calendar_index(matrix.index if calendar is None else calendar)
    start_date = None if start is None else pd.Timestamp(start).normalize()
    end_date = None if end is None else pd.Timestamp(end).normalize()
    rows: list[dict[str, object]] = []

    for signal_date, execution_date in signal_execution_pairs(dates, cfg.frequency):
        if start_date is not None and execution_date < start_date:
            continue
        if end_date is not None and execution_date > end_date:
            continue
        if signal_date not in matrix.index:
            continue
        signal = matrix.loc[signal_date].replace([np.inf, -np.inf], np.nan).dropna()
        if len(signal) < cfg.min_assets:
            continue
        ranked = pd.DataFrame({"asset": signal.index.astype(str), "score": signal.to_numpy(float)})
        ranked = ranked.sort_values(["score", "asset"], ascending=[False, True], kind="mergesort")
        selected = ranked if equal_weight_universe else ranked.head(cfg.top_n)
        if selected.empty:
            continue
        weight = cfg.invest_fraction / len(selected)
        for rank, record in enumerate(selected.itertuples(index=False), start=1):
            rows.append(
                {
                    "signal_date": signal_date,
                    "execution_date": execution_date,
                    "asset": record.asset,
                    "target_weight": weight,
                    "rank": rank,
                    "score": float(record.score),
                }
            )

    columns = ["signal_date", "execution_date", "asset", "target_weight", "rank", "score"]
    result = pd.DataFrame(rows, columns=columns)
    if not result.empty:
        result = result.sort_values(["execution_date", "asset"], kind="mergesort").reset_index(drop=True)
    return result


def generate_equal_weight_targets(
    eligibility: pd.DataFrame,
    calendar: Iterable[object] | pd.Index | None = None,
    config: PortfolioConfig | Mapping[str, object] | None = None,
    **kwargs: object,
) -> pd.DataFrame:
    """Generate an equal-weight benchmark over every eligible asset.

    ``eligibility`` may be a boolean matrix or any matrix where finite values
    denote membership.  It is evaluated at the signal close, never at the
    execution open.
    """

    matrix = eligibility.copy()
    if matrix.dtypes.apply(lambda value: value == bool).all():
        matrix = matrix.astype(float).where(matrix)
    return generate_target_weights(
        matrix,
        calendar=calendar,
        config=config,
        equal_weight_universe=True,
        **kwargs,
    )


class TargetPortfolioGenerator:
    """Small compatibility wrapper around :func:`generate_target_weights`."""

    def __init__(
        self,
        holding_count: int = 5,
        rebalance_frequency: str = "monthly",
        invest_fraction: float = 0.99,
        min_assets: int = 1,
    ) -> None:
        self.config = PortfolioConfig(
            top_n=holding_count,
            frequency=rebalance_frequency,
            invest_fraction=invest_fraction,
            min_assets=min_assets,
        )

    def identify_rebalance_dates(self, dates: Iterable[object]) -> list[pd.Timestamp]:
        return [signal for signal, _ in signal_execution_pairs(dates, self.config.frequency)]

    def generate_target_weights(
        self,
        scores: pd.DataFrame,
        calendar: Iterable[object] | pd.Index | None = None,
    ) -> pd.DataFrame:
        return generate_target_weights(scores, calendar=calendar, config=self.config)


__all__ = [
    "PortfolioConfig",
    "TargetPortfolioGenerator",
    "generate_equal_weight_targets",
    "generate_target_weights",
    "signal_execution_pairs",
]
