"""Pure, registered factors and next-open research labels.

The registry follows Qlib's component separation: formulas know nothing about
portfolio construction or execution.  Outputs follow an Alphalens-like long
contract and every built-in factor is oriented so a larger score means a more
desirable asset.  All rolling operations are backward-looking only.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


FactorFunction = Callable[[pd.Series | pd.DataFrame, int], pd.Series | pd.DataFrame]


def _check_window(window: int) -> int:
    if isinstance(window, bool) or int(window) != window or int(window) < 1:
        raise ValueError("Factor window must be a positive integer.")
    return int(window)


def momentum(close: pd.Series | pd.DataFrame, window: int) -> pd.Series | pd.DataFrame:
    """Trailing price momentum: ``close[t] / close[t-window] - 1``."""

    window = _check_window(window)
    return close / close.shift(window) - 1.0


def reversal(close: pd.Series | pd.DataFrame, window: int) -> pd.Series | pd.DataFrame:
    """Trailing reversal, already aligned so larger means better."""

    return -momentum(close, window)


def low_volatility(
    close: pd.Series | pd.DataFrame, window: int
) -> pd.Series | pd.DataFrame:
    """Negative sample volatility of the latest ``window`` close returns."""

    window = _check_window(window)
    returns = close.pct_change(fill_method=None)
    return -returns.rolling(window=window, min_periods=window).std(ddof=1)


@dataclass(frozen=True)
class FactorDefinition:
    name: str
    function: FactorFunction
    default_window: int
    description: str
    aliases: tuple[str, ...] = ()

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "default_window": self.default_window,
            "description": self.description,
            "aliases": list(self.aliases),
            "direction": "higher_is_better",
        }


class FactorRegistry:
    """Deterministic registry for pure factor functions."""

    _definitions: "OrderedDict[str, FactorDefinition]" = OrderedDict()
    _aliases: dict[str, str] = {}

    @classmethod
    def register(
        cls,
        name: str,
        *,
        default_window: int,
        description: str = "",
        aliases: Iterable[str] = (),
    ):
        """Register a function accepting ``(close_matrix, window)``."""

        canonical = str(name).strip().lower()
        if not canonical:
            raise ValueError("Factor name cannot be empty.")
        checked_window = _check_window(default_window)
        clean_aliases = tuple(str(alias).strip() for alias in aliases)

        def decorator(function: FactorFunction) -> FactorFunction:
            if canonical in cls._definitions or canonical in cls._aliases:
                raise KeyError(f"Factor is already registered: {canonical}")
            alias_keys = {alias.lower() for alias in clean_aliases}
            alias_keys.add(canonical)
            collisions = sorted(alias_keys.intersection(cls._aliases))
            if collisions:
                raise KeyError(f"Factor alias is already registered: {collisions}")
            definition = FactorDefinition(
                name=canonical,
                function=function,
                default_window=checked_window,
                description=description,
                aliases=clean_aliases,
            )
            cls._definitions[canonical] = definition
            for alias in alias_keys:
                cls._aliases[alias] = canonical
            return function

        return decorator

    @classmethod
    def canonical_name(cls, name: str) -> str:
        key = str(name).strip().lower()
        try:
            return cls._aliases[key]
        except KeyError as exc:
            raise KeyError(
                f"Unknown factor '{name}'. Available: {list(cls._definitions)}"
            ) from exc

    @classmethod
    def get(cls, name: str) -> FactorDefinition:
        return cls._definitions[cls.canonical_name(name)]

    @classmethod
    def list_factors(cls) -> list[dict[str, Any]]:
        return [definition.metadata() for definition in cls._definitions.values()]

    @classmethod
    def calculate_all(
        cls,
        panel: pd.DataFrame,
        *,
        windows: Mapping[str, int] | None = None,
        factor_names: Iterable[str] | None = None,
        close_column: str = "close_adj",
    ) -> pd.DataFrame:
        return calculate_factors(
            panel,
            windows=windows,
            factor_names=factor_names,
            close_column=close_column,
            registry=cls,
        )


FactorRegistry.register(
    "momentum",
    default_window=20,
    description="Trailing 20-session adjusted-price momentum.",
    aliases=("MOM20",),
)(momentum)
FactorRegistry.register(
    "reversal",
    default_window=5,
    description="Negative trailing 5-session adjusted-price return.",
    aliases=("REV5",),
)(reversal)
FactorRegistry.register(
    "low_volatility",
    default_window=20,
    description="Negative sample volatility of 20 adjusted-price returns.",
    aliases=("LOWVOL20", "low_vol"),
)(low_volatility)

# A concise public view is convenient for notebooks and mirrors project2.
REGISTRY = FactorRegistry._definitions


def _validate_panel(panel: pd.DataFrame, value_column: str) -> pd.DataFrame:
    required = {"date", "asset", value_column}
    missing = sorted(required.difference(panel.columns))
    if missing:
        raise KeyError(f"Panel is missing columns: {missing}")
    if panel.empty:
        raise ValueError("Panel is empty.")
    result = panel[["date", "asset", value_column]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise").dt.normalize()
    result["asset"] = result["asset"].astype("string")
    if result.duplicated(["date", "asset"]).any():
        raise ValueError("Panel contains duplicate date x asset keys.")
    result[value_column] = pd.to_numeric(result[value_column], errors="raise")
    finite_or_missing = np.isfinite(result[value_column]) | result[value_column].isna()
    if not finite_or_missing.all():
        raise ValueError(f"{value_column} contains infinite values.")
    observed = result[value_column].dropna()
    if (observed <= 0).any():
        raise ValueError(f"{value_column} must be positive when observed.")
    return result.sort_values(["date", "asset"], kind="mergesort").reset_index(drop=True)


def _wide(panel: pd.DataFrame, value_column: str) -> pd.DataFrame:
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()), name="date")
    assets = sorted(panel["asset"].astype(str).unique())
    return (
        panel.pivot(index="date", columns="asset", values=value_column)
        .reindex(index=dates, columns=assets)
        .rename_axis(index="date", columns="asset")
    )


def calculate(
    close: pd.DataFrame,
    windows: Mapping[str, int] | None = None,
    factor_names: Iterable[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Calculate registered factor matrices from a date x asset close matrix."""

    if close.index.has_duplicates or close.columns.has_duplicates:
        raise ValueError("Close matrix axes must be unique.")
    matrix = close.sort_index().reindex(sorted(close.columns), axis=1)
    requested = list(factor_names) if factor_names is not None else list(REGISTRY)
    result: dict[str, pd.DataFrame] = {}
    window_map = dict(windows or {})
    for requested_name in requested:
        definition = FactorRegistry.get(requested_name)
        name = definition.name
        if name in result:
            continue
        configured = window_map.get(requested_name, window_map.get(name, definition.default_window))
        window = _check_window(configured)
        values = definition.function(matrix, window)
        result[name] = values.replace([np.inf, -np.inf], np.nan)
    return result


def _matrix_to_long(matrix: pd.DataFrame, value_name: str) -> pd.DataFrame:
    return (
        matrix.rename_axis(index="date", columns="asset")
        .reset_index()
        .melt(id_vars="date", var_name="asset", value_name=value_name)
    )


def calculate_factors(
    panel: pd.DataFrame,
    *,
    windows: Mapping[str, int] | None = None,
    factor_names: Iterable[str] | None = None,
    close_column: str = "close_adj",
    registry: type[FactorRegistry] = FactorRegistry,
) -> pd.DataFrame:
    """Return registered factors in a standard deterministic long format.

    Output columns are ``date, asset, factor, raw_value, score, value,
    is_valid, window, preprocessing``.  ``score`` and its compatibility alias
    ``value`` are same-date cross-sectional percentile ranks.  Missing factor
    values remain missing and are never mapped to zero.
    """

    clean = _validate_panel(panel, close_column)
    close = _wide(clean, close_column)
    requested = list(factor_names) if factor_names is not None else list(registry._definitions)
    window_map = dict(windows or {})
    keys = clean[["date", "asset"]]
    outputs: list[pd.DataFrame] = []
    seen: set[str] = set()
    for requested_name in requested:
        definition = registry.get(requested_name)
        if definition.name in seen:
            continue
        seen.add(definition.name)
        configured = window_map.get(
            requested_name,
            window_map.get(definition.name, definition.default_window),
        )
        window = _check_window(configured)
        raw_matrix = definition.function(close, window).replace([np.inf, -np.inf], np.nan)
        long = keys.merge(
            _matrix_to_long(raw_matrix, "raw_value"),
            on=["date", "asset"],
            how="left",
            validate="one_to_one",
        )
        long["factor"] = definition.name
        long["is_valid"] = long["raw_value"].notna() & np.isfinite(long["raw_value"])
        long["score"] = np.nan
        valid = long["is_valid"]
        long.loc[valid, "score"] = long.loc[valid].groupby("date", sort=False)[
            "raw_value"
        ].rank(method="average", pct=True, ascending=True)
        long["value"] = long["score"]
        long["window"] = window
        long["preprocessing"] = "cross_sectional_percentile_rank_v1"
        outputs.append(
            long[
                [
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
            ]
        )
    if not outputs:
        return pd.DataFrame(
            columns=[
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
        )
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["date", "asset", "factor"], kind="mergesort", ignore_index=True
    )


def as_long(factors: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """Convert precomputed matrices to a simple Alphalens-style long table."""

    rows: list[pd.DataFrame] = []
    for name in sorted(factors):
        frame = _matrix_to_long(factors[name], "raw_value")
        frame["factor"] = FactorRegistry.canonical_name(name)
        rows.append(frame[["date", "asset", "factor", "raw_value"]])
    if not rows:
        return pd.DataFrame(columns=["date", "asset", "factor", "raw_value"])
    return pd.concat(rows, ignore_index=True).sort_values(
        ["date", "asset", "factor"], kind="mergesort", ignore_index=True
    )


def forward_label(open_price: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Next-open label for a signal formed after today's close.

    A horizon of one is the return from open ``t+1`` to open ``t+2``; a horizon
    of five is from open ``t+1`` to open ``t+6``.  No missing open is filled.
    """

    horizon = _check_window(horizon)
    return open_price.shift(-(horizon + 1)) / open_price.shift(-1) - 1.0


def forward_labels_wide(
    open_price: pd.DataFrame, horizons: Iterable[int] = (1, 5)
) -> dict[int, pd.DataFrame]:
    """Calculate deterministic next-open label matrices."""

    if open_price.index.has_duplicates or open_price.columns.has_duplicates:
        raise ValueError("Open matrix axes must be unique.")
    matrix = open_price.sort_index().reindex(sorted(open_price.columns), axis=1)
    return {h: forward_label(matrix, h) for h in sorted({_check_window(x) for x in horizons})}


def next_open_forward_labels(
    panel: pd.DataFrame,
    horizons: Iterable[int] = (1, 5),
    *,
    open_column: str = "open_adj",
) -> pd.DataFrame:
    """Return auditable 1/5-day (or custom) next-open labels in long form."""

    clean = _validate_panel(panel, open_column)
    opens = _wide(clean, open_column)
    keys = clean[["date", "asset"]]
    dates = pd.DatetimeIndex(opens.index)
    outputs: list[pd.DataFrame] = []
    for horizon, labels in forward_labels_wide(opens, horizons).items():
        entry = opens.shift(-1)
        exit_price = opens.shift(-(horizon + 1))
        long = keys.merge(
            _matrix_to_long(labels, "forward_return"),
            on=["date", "asset"],
            how="left",
            validate="one_to_one",
        )
        long = long.merge(
            _matrix_to_long(entry, "entry_open"),
            on=["date", "asset"],
            how="left",
            validate="one_to_one",
        ).merge(
            _matrix_to_long(exit_price, "exit_open"),
            on=["date", "asset"],
            how="left",
            validate="one_to_one",
        )
        position = {date: index for index, date in enumerate(dates)}
        long["entry_date"] = long["date"].map(
            lambda date: dates[position[date] + 1]
            if position[date] + 1 < len(dates)
            else pd.NaT
        )
        long["exit_date"] = long["date"].map(
            lambda date: dates[position[date] + horizon + 1]
            if position[date] + horizon + 1 < len(dates)
            else pd.NaT
        )
        long["horizon"] = horizon
        long["label_name"] = f"next_open_{horizon}d"
        long["label"] = long["forward_return"]
        long["is_valid"] = long["forward_return"].notna() & np.isfinite(
            long["forward_return"]
        )
        outputs.append(
            long[
                [
                    "date",
                    "asset",
                    "horizon",
                    "label_name",
                    "entry_date",
                    "exit_date",
                    "entry_open",
                    "exit_open",
                    "forward_return",
                    "label",
                    "is_valid",
                ]
            ]
        )
    if not outputs:
        raise ValueError("At least one label horizon is required.")
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["date", "asset", "horizon"], kind="mergesort", ignore_index=True
    )


# Friendly aliases used by analysis code.
compute_factors = calculate_factors
make_forward_labels = next_open_forward_labels


__all__ = [
    "FactorDefinition",
    "FactorRegistry",
    "REGISTRY",
    "as_long",
    "calculate",
    "calculate_factors",
    "compute_factors",
    "forward_label",
    "forward_labels_wide",
    "low_volatility",
    "make_forward_labels",
    "momentum",
    "next_open_forward_labels",
    "reversal",
]
