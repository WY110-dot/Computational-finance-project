"""A deterministic next-open broker, cash ledger, and accounting audit.

The strategy supplies target weights; this module alone decides whether an
order can trade and what it costs.  Prices used to form a close-t signal are
therefore structurally separated from prices used to fill it at open t+1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Mapping

import numpy as np
import pandas as pd

from .portfolio import (
    PortfolioConfig,
    generate_equal_weight_targets,
    generate_target_weights,
)


@dataclass(frozen=True)
class BacktestConfig:
    """Broker, account, and valuation assumptions."""

    initial_cash: float = 1_000_000.0
    buy_fee: float = 0.0003
    sell_fee: float = 0.0003
    slippage_bps: float = 0.0
    adv_window: int = 20
    participation_rate: float = 0.001
    capacity_limited: bool = True
    max_stale_days: int = 5
    allow_fractional_units: bool = True
    lot_size: float = 1.0
    min_trade_notional: float = 0.0
    start: object | None = None
    end: object | None = None
    annualization: int = 252
    daily_risk_free: float = 0.0
    audit_tolerance: float = 1e-6

    def __post_init__(self) -> None:
        if not np.isfinite(self.initial_cash) or self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive and finite")
        for name, rate in (("buy_fee", self.buy_fee), ("sell_fee", self.sell_fee)):
            if not np.isfinite(rate) or not 0 <= rate < 1:
                raise ValueError(f"{name} must be in [0, 1)")
        if not np.isfinite(self.slippage_bps) or not 0 <= self.slippage_bps < 10_000:
            raise ValueError("slippage_bps must be in [0, 10000)")
        if self.adv_window < 1:
            raise ValueError("adv_window must be positive")
        if not np.isfinite(self.participation_rate) or self.participation_rate < 0:
            raise ValueError("participation_rate must be non-negative")
        if self.max_stale_days < 0:
            raise ValueError("max_stale_days must be non-negative")
        if not np.isfinite(self.lot_size) or self.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        if self.min_trade_notional < 0:
            raise ValueError("min_trade_notional must be non-negative")
        if self.annualization < 1:
            raise ValueError("annualization must be positive")
        if self.audit_tolerance <= 0:
            raise ValueError("audit_tolerance must be positive")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "BacktestConfig":
        """Build from a flat dict or ``config/default.json`` style mapping."""

        if value is None:
            return cls()
        execution = value.get("execution")
        data = value.get("data")
        metrics = value.get("metrics")
        merged: dict[str, object] = dict(value)
        if isinstance(data, Mapping):
            merged.update(data)
        if isinstance(metrics, Mapping):
            merged.update(metrics)
        if isinstance(execution, Mapping):
            merged.update(execution)
        return cls(
            initial_cash=float(merged.get("initial_cash", 1_000_000.0)),
            buy_fee=float(merged.get("buy_fee", merged.get("buy_fee_rate", 0.0003))),
            sell_fee=float(merged.get("sell_fee", merged.get("sell_fee_rate", 0.0003))),
            slippage_bps=float(merged.get("slippage_bps", 0.0)),
            adv_window=int(merged.get("adv_window", 20)),
            participation_rate=float(
                merged.get("participation_rate", merged.get("participation", 0.001))
            ),
            capacity_limited=bool(merged.get("capacity_limited", True)),
            max_stale_days=int(merged.get("max_stale_days", 5)),
            allow_fractional_units=bool(merged.get("allow_fractional_units", True)),
            lot_size=float(merged.get("lot_size", 1.0)),
            min_trade_notional=float(merged.get("min_trade_notional", 0.0)),
            start=merged.get("start"),
            end=merged.get("end"),
            annualization=int(merged.get("annualization", 252)),
            daily_risk_free=float(merged.get("daily_risk_free", 0.0)),
            audit_tolerance=float(merged.get("audit_tolerance", 1e-6)),
        )

    def zero_fee(self) -> "BacktestConfig":
        """Return assumptions for an independent gross-performance rerun."""

        return replace(self, buy_fee=0.0, sell_fee=0.0)


@dataclass
class BacktestResult:
    """Tables emitted by the broker plus the audit performed on them."""

    ledger: pd.DataFrame
    orders: pd.DataFrame
    fills: pd.DataFrame
    holdings: pd.DataFrame
    audit: dict[str, object]
    config: BacktestConfig

    @property
    def trades(self) -> pd.DataFrame:
        """Alias used by some research notebooks."""

        return self.fills

    def summary(self) -> dict[str, object]:
        return {
            "config": asdict(self.config),
            "ledger_rows": len(self.ledger),
            "order_rows": len(self.orders),
            "fill_rows": len(self.fills),
            "holding_rows": len(self.holdings),
            "audit": self.audit,
        }


_LEDGER_COLUMNS = [
    "date",
    "pretrade_equity",
    "posttrade_equity_at_open",
    "cash",
    "holdings_value",
    "equity",
    "wealth",
    "nav",
    "daily_return",
    "buy_notional",
    "sell_notional",
    "buy",
    "sell",
    "transaction_cost",
    "cost",
    "slippage_cost",
    "turnover_notional",
    "turnover",
    "requested_notional",
    "filled_reference_notional",
    "unfilled_notional",
    "fill_ratio",
    "order_count",
    "trade_count",
    "holding_count",
    "holdings",
    "max_single_asset_weight",
    "max_weight",
    "stale_positions",
    "max_position_stale_days",
    "rebalance",
]

_ORDER_COLUMNS = [
    "order_id",
    "date",
    "signal_date",
    "asset",
    "side",
    "target_weight",
    "pretrade_units",
    "pretrade_value",
    "target_value",
    "reference_price",
    "requested_units",
    "requested_notional",
    "filled_units",
    "signed_filled_units",
    "fill_price",
    "filled_reference_notional",
    "filled_notional",
    "fee",
    "slippage_cost",
    "adv_notional",
    "capacity_notional",
    "unfilled_units",
    "unfilled_notional",
    "status",
    "reason",
]

_HOLDING_COLUMNS = [
    "date",
    "asset",
    "units",
    "adjusted_units",
    "mark_price",
    "mark",
    "market_value",
    "value",
    "weight",
    "close_available",
    "price_is_stale",
    "stale_days",
]


def _coerce_config(config: BacktestConfig | Mapping[str, object] | None) -> BacktestConfig:
    return config if isinstance(config, BacktestConfig) else BacktestConfig.from_mapping(config)


def _first_existing(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    return next((name for name in names if name in frame.columns), None)


def _normalise_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise ValueError("prices must be a non-empty DataFrame")
    date_col = _first_existing(prices, ("date", "trade_date"))
    asset_col = _first_existing(prices, ("asset", "ts_code", "symbol"))
    open_col = _first_existing(prices, ("open_adj", "adj_open", "open"))
    close_col = _first_existing(prices, ("close_adj", "adj_close", "close"))
    amount_col = _first_existing(prices, ("amount", "turnover_amount"))
    if None in (date_col, asset_col, open_col, close_col):
        raise ValueError("prices need date, asset, open_adj, and close_adj columns")
    selected = [date_col, asset_col, open_col, close_col]
    if amount_col is not None:
        selected.append(amount_col)
    frame = prices[selected].copy()
    rename = {date_col: "date", asset_col: "asset", open_col: "open_adj", close_col: "close_adj"}
    if amount_col is not None:
        rename[amount_col] = "amount"
    frame = frame.rename(columns=rename)
    if "amount" not in frame:
        # Deliberately do not infer RMB turnover from adjusted price * raw volume:
        # those series need not have compatible units after corporate actions.
        frame["amount"] = np.nan
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame["asset"] = frame["asset"].astype(str)
    if frame.duplicated(["date", "asset"]).any():
        duplicate = frame.loc[frame.duplicated(["date", "asset"], keep=False), ["date", "asset"]].head()
        raise ValueError(f"duplicate price rows: {duplicate.to_dict('records')}")
    for column in ("open_adj", "close_adj", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("open_adj", "close_adj"):
        frame.loc[~np.isfinite(frame[column]) | (frame[column] <= 0), column] = np.nan
    frame.loc[~np.isfinite(frame["amount"]) | (frame["amount"] < 0), "amount"] = np.nan
    return frame.sort_values(["date", "asset"], kind="mergesort").reset_index(drop=True)


def _normalise_targets(
    targets: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    assets: list[str],
    tolerance: float,
) -> pd.DataFrame:
    if targets is None or len(targets) == 0:
        return pd.DataFrame(columns=["signal_date", "execution_date", "asset", "target_weight"])
    if not isinstance(targets, pd.DataFrame):
        raise TypeError("targets must be a pandas DataFrame")
    execution_col = _first_existing(targets, ("execution_date", "effective_date"))
    required = {"signal_date", "asset", "target_weight"}
    if execution_col is None or not required.issubset(targets.columns):
        raise ValueError("targets need signal_date, execution_date, asset, and target_weight")
    frame = targets.copy().rename(columns={execution_col: "execution_date"})
    frame = frame[["signal_date", "execution_date", "asset", "target_weight"]]
    frame["signal_date"] = pd.to_datetime(frame["signal_date"], errors="raise").dt.normalize()
    frame["execution_date"] = pd.to_datetime(frame["execution_date"], errors="raise").dt.normalize()
    frame["asset"] = frame["asset"].astype(str)
    frame["target_weight"] = pd.to_numeric(frame["target_weight"], errors="raise")
    if frame.duplicated(["execution_date", "asset"]).any():
        raise ValueError("duplicate target for an asset on one execution date")
    if (~np.isfinite(frame["target_weight"]) | (frame["target_weight"] < -tolerance)).any():
        raise ValueError("target weights must be finite and non-negative")
    frame.loc[frame["target_weight"].abs() <= tolerance, "target_weight"] = 0.0
    unknown = sorted(set(frame["asset"]) - set(assets))
    if unknown:
        raise ValueError(f"targets contain assets absent from prices: {unknown}")
    date_position = {date: position for position, date in enumerate(calendar)}
    violations: list[dict[str, object]] = []
    for pair in frame[["signal_date", "execution_date"]].drop_duplicates().itertuples(index=False):
        signal = pair.signal_date
        execution = pair.execution_date
        if signal not in date_position or execution not in date_position:
            violations.append({"signal_date": signal, "execution_date": execution, "reason": "not_in_calendar"})
        elif execution <= signal:
            violations.append({"signal_date": signal, "execution_date": execution, "reason": "not_after_signal"})
        elif date_position[execution] != date_position[signal] + 1:
            violations.append({"signal_date": signal, "execution_date": execution, "reason": "not_next_session"})
    if violations:
        raise ValueError(f"targets violate close-t/next-open timing: {violations[:3]}")
    signal_counts = frame.groupby("execution_date")["signal_date"].nunique()
    if (signal_counts != 1).any():
        raise ValueError("an execution date cannot contain multiple signal dates")
    weight_sums = frame.groupby("execution_date")["target_weight"].sum()
    if (weight_sums > 1.0 + tolerance).any():
        raise ValueError("target weights exceed 100%")
    return frame.sort_values(["execution_date", "asset"], kind="mergesort").reset_index(drop=True)


def _round_units(units: np.ndarray, cfg: BacktestConfig) -> np.ndarray:
    units = np.maximum(np.asarray(units, dtype=float), 0.0)
    if cfg.allow_fractional_units:
        return units
    return np.floor((units + 1e-12) / cfg.lot_size) * cfg.lot_size


def run_backtest(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    config: BacktestConfig | Mapping[str, object] | None = None,
    *,
    capacity_limited: bool | None = None,
    run_audit: bool = True,
) -> BacktestResult:
    """Execute target weights using a self-financing, long-only cash account.

    Sales are filled before buys.  Fees apply only to actual fills; orders with
    a missing opening price remain unfilled and free of charge.  Capacity uses
    the mean RMB amount over completed sessions only (``rolling(...).shift(1)``).
    Unfilled quantities are day orders and are not silently carried forward.
    """

    cfg = _coerce_config(config)
    limited = cfg.capacity_limited if capacity_limited is None else bool(capacity_limited)
    frame = _normalise_prices(prices)
    calendar = pd.DatetimeIndex(frame["date"].drop_duplicates().sort_values())
    assets = sorted(frame["asset"].unique())
    target_frame = _normalise_targets(targets, calendar, assets, cfg.audit_tolerance)

    open_price = frame.pivot(index="date", columns="asset", values="open_adj").reindex(
        index=calendar, columns=assets
    )
    close_price = frame.pivot(index="date", columns="asset", values="close_adj").reindex(
        index=calendar, columns=assets
    )
    amount = frame.pivot(index="date", columns="asset", values="amount").reindex(
        index=calendar, columns=assets
    )
    if limited and amount.notna().sum().sum() == 0:
        raise ValueError("capacity-limited execution requires RMB amount data")
    # The shift is essential: execution-day liquidity is not known at its open.
    adv = amount.rolling(cfg.adv_window, min_periods=cfg.adv_window).mean().shift(1)

    start = calendar[0] if cfg.start is None else pd.Timestamp(cfg.start).normalize()
    end = calendar[-1] if cfg.end is None else pd.Timestamp(cfg.end).normalize()
    run_dates = calendar[(calendar >= start) & (calendar <= end)]
    if len(run_dates) == 0:
        raise ValueError("configured backtest range contains no price dates")

    targets_by_date = {
        date: group.set_index("asset").sort_index()
        for date, group in target_frame.groupby("execution_date", sort=True)
        if start <= date <= end
    }
    date_position = {date: position for position, date in enumerate(calendar)}
    first_position = date_position[run_dates[0]]

    number_assets = len(assets)
    units = np.zeros(number_assets, dtype=float)
    cash = float(cfg.initial_cash)
    last_close = np.full(number_assets, np.nan)
    last_close_position = np.full(number_assets, -1, dtype=int)
    if first_position:
        historical = close_price.iloc[:first_position]
        for asset_position in range(number_assets):
            valid_positions = np.flatnonzero(np.isfinite(historical.iloc[:, asset_position].to_numpy(float)))
            if len(valid_positions):
                position = int(valid_positions[-1])
                last_close[asset_position] = float(historical.iloc[position, asset_position])
                last_close_position[asset_position] = position

    ledger_rows: list[dict[str, object]] = []
    order_rows: list[dict[str, object]] = []
    holding_rows: list[dict[str, object]] = []
    previous_equity = float(cfg.initial_cash)
    slip = cfg.slippage_bps / 10_000.0
    tiny = max(cfg.audit_tolerance * 1e-3, 1e-10)

    for date in run_dates:
        position = date_position[date]
        openings = open_price.loc[date].to_numpy(float)
        closes = close_price.loc[date].to_numpy(float)
        opening_valid = np.isfinite(openings) & (openings > 0)
        opening_marks = np.where(opening_valid, openings, last_close)
        if np.any((units > tiny) & ~np.isfinite(opening_marks)):
            bad = [assets[i] for i in np.flatnonzero((units > tiny) & ~np.isfinite(opening_marks))]
            raise ValueError(f"unmarkable holdings at open {date.date()}: {bad}")
        pretrade_values = units * np.nan_to_num(opening_marks, nan=0.0)
        pretrade_units_snapshot = units.copy()
        pretrade_equity = float(cash + pretrade_values.sum())
        if pretrade_equity <= 0:
            raise AssertionError("account equity must remain positive")

        day_buy = day_sell = day_fee = day_slippage = 0.0
        requested_total = filled_reference_total = 0.0
        rebalance = date in targets_by_date
        day_orders: list[dict[str, object]] = []

        if rebalance:
            target_group = targets_by_date[date]
            signal_date = pd.Timestamp(target_group["signal_date"].iloc[0]).normalize()
            target_weight = np.zeros(number_assets, dtype=float)
            asset_location = {asset: i for i, asset in enumerate(assets)}
            for asset, row in target_group.iterrows():
                target_weight[asset_location[asset]] = float(row["target_weight"])
            target_values = target_weight * pretrade_equity
            demand_value = target_values - pretrade_values
            requested_units_signed = np.divide(
                target_values,
                openings,
                out=np.full(number_assets, np.nan),
                where=opening_valid,
            ) - units
            requested_notional = np.where(
                opening_valid,
                np.abs(requested_units_signed) * openings,
                np.abs(demand_value),
            )
            order_mask = requested_notional > tiny

            adv_today = adv.loc[date].to_numpy(float)
            if limited:
                capacity = np.nan_to_num(adv_today, nan=0.0, posinf=0.0, neginf=0.0)
                capacity = np.maximum(capacity * cfg.participation_rate, 0.0)
            else:
                capacity = np.full(number_assets, np.inf)
            capacity = np.where(opening_valid, capacity, 0.0)

            sell_request = np.where(
                opening_valid & (requested_units_signed < -tiny), -requested_units_signed, 0.0
            )
            sell_cap_units = np.divide(
                capacity,
                openings,
                out=np.zeros(number_assets),
                where=opening_valid,
            )
            sell_units = np.minimum.reduce([sell_request, sell_cap_units, units])
            sell_units = _round_units(sell_units, cfg)
            if cfg.min_trade_notional > 0:
                sell_units = np.where(
                    sell_units * np.nan_to_num(openings) >= cfg.min_trade_notional,
                    sell_units,
                    0.0,
                )
            sell_fill_price = np.where(opening_valid, openings * (1.0 - slip), np.nan)
            sell_notional = sell_units * np.nan_to_num(sell_fill_price)
            sell_fees = sell_notional * cfg.sell_fee
            cash += float((sell_notional - sell_fees).sum())
            units -= sell_units

            buy_request = np.where(
                opening_valid & (requested_units_signed > tiny), requested_units_signed, 0.0
            )
            buy_cap_units = np.divide(
                capacity,
                openings,
                out=np.zeros(number_assets),
                where=opening_valid,
            )
            buy_units_before_cash = _round_units(np.minimum(buy_request, buy_cap_units), cfg)
            if cfg.min_trade_notional > 0:
                buy_units_before_cash = np.where(
                    buy_units_before_cash * np.nan_to_num(openings) >= cfg.min_trade_notional,
                    buy_units_before_cash,
                    0.0,
                )
            buy_fill_price = np.where(opening_valid, openings * (1.0 + slip), np.nan)
            required_cash = float(
                (buy_units_before_cash * np.nan_to_num(buy_fill_price) * (1.0 + cfg.buy_fee)).sum()
            )
            cash_scale = 1.0 if required_cash <= cash + tiny else max(cash, 0.0) / required_cash
            buy_units = _round_units(buy_units_before_cash * cash_scale, cfg)
            if cfg.min_trade_notional > 0:
                buy_units = np.where(
                    buy_units * np.nan_to_num(openings) >= cfg.min_trade_notional,
                    buy_units,
                    0.0,
                )
            buy_notional = buy_units * np.nan_to_num(buy_fill_price)
            buy_fees = buy_notional * cfg.buy_fee
            cash -= float((buy_notional + buy_fees).sum())
            if cash < -cfg.audit_tolerance:
                raise AssertionError(f"cash account borrowed {cash}")
            if cash < 0:
                cash = 0.0
            units += buy_units
            units[np.abs(units) < tiny] = 0.0
            if (units < -cfg.audit_tolerance).any():
                raise AssertionError("short position created")

            day_buy = float(buy_notional.sum())
            day_sell = float(sell_notional.sum())
            day_fee = float(buy_fees.sum() + sell_fees.sum())
            buy_reference = buy_units * np.nan_to_num(openings)
            sell_reference = sell_units * np.nan_to_num(openings)
            day_slippage = float(
                np.sum(buy_units * np.nan_to_num(buy_fill_price - openings))
                + np.sum(sell_units * np.nan_to_num(openings - sell_fill_price))
            )
            requested_total = float(requested_notional[order_mask].sum())
            filled_reference_total = float((buy_reference + sell_reference).sum())

            for i in np.flatnonzero(order_mask):
                side = "buy" if demand_value[i] > 0 else "sell"
                filled_units = float(buy_units[i] if side == "buy" else sell_units[i])
                signed_filled_units = filled_units if side == "buy" else -filled_units
                fill_price = float(buy_fill_price[i] if side == "buy" else sell_fill_price[i])
                filled_notional = float(
                    buy_notional[i] if side == "buy" else sell_notional[i]
                )
                filled_reference = float(filled_units * openings[i]) if opening_valid[i] else 0.0
                requested_units = (
                    float(abs(requested_units_signed[i])) if opening_valid[i] else np.nan
                )
                unfilled_units = (
                    max(requested_units - filled_units, 0.0)
                    if np.isfinite(requested_units)
                    else np.nan
                )
                unfilled_notional = max(float(requested_notional[i]) - filled_reference, 0.0)
                fee = float(buy_fees[i] if side == "buy" else sell_fees[i])
                slip_cost = (
                    float(filled_units * abs(fill_price - openings[i]))
                    if opening_valid[i]
                    else 0.0
                )
                if filled_reference >= requested_notional[i] - cfg.audit_tolerance:
                    status, reason = "filled", "filled"
                elif filled_units > tiny:
                    status = "partial"
                    capacity_bound = limited and capacity[i] < requested_notional[i] - cfg.audit_tolerance
                    cash_bound = side == "buy" and buy_units[i] < buy_units_before_cash[i] - tiny
                    reason = (
                        "capacity_and_cash"
                        if capacity_bound and cash_bound
                        else "capacity"
                        if capacity_bound
                        else "insufficient_cash"
                        if cash_bound
                        else "lot_rounding"
                    )
                else:
                    status = "rejected"
                    if not opening_valid[i]:
                        reason = "missing_open"
                    elif cfg.min_trade_notional > 0 and requested_notional[i] < cfg.min_trade_notional:
                        reason = "below_min_notional"
                    elif limited and capacity[i] <= tiny:
                        reason = "no_lagged_capacity"
                    elif side == "buy" and cash_scale <= tiny:
                        reason = "insufficient_cash"
                    else:
                        reason = "lot_rounding"
                day_orders.append(
                    {
                        "order_id": f"{date:%Y%m%d}-{assets[i]}-{side}",
                        "date": date,
                        "signal_date": signal_date,
                        "asset": assets[i],
                        "side": side,
                        "target_weight": float(target_weight[i]),
                        "pretrade_units": float(units[i] - signed_filled_units),
                        "pretrade_value": float(pretrade_values[i]),
                        "target_value": float(target_values[i]),
                        "reference_price": float(openings[i]) if opening_valid[i] else np.nan,
                        "requested_units": requested_units,
                        "requested_notional": float(requested_notional[i]),
                        "filled_units": filled_units,
                        "signed_filled_units": signed_filled_units,
                        "fill_price": fill_price if filled_units > tiny else np.nan,
                        "filled_reference_notional": filled_reference,
                        "filled_notional": filled_notional,
                        "fee": fee,
                        "slippage_cost": slip_cost,
                        "adv_notional": float(adv_today[i]) if np.isfinite(adv_today[i]) else np.nan,
                        "capacity_notional": float(capacity[i]) if limited else np.nan,
                        "unfilled_units": unfilled_units,
                        "unfilled_notional": unfilled_notional,
                        "status": status,
                        "reason": reason,
                    }
                )
            order_rows.extend(day_orders)

        posttrade_open_values = units * np.nan_to_num(opening_marks, nan=0.0)
        posttrade_equity_at_open = float(cash + posttrade_open_values.sum())
        close_valid = np.isfinite(closes) & (closes > 0)
        last_close = np.where(close_valid, closes, last_close)
        last_close_position = np.where(close_valid, position, last_close_position)
        # A newly acquired asset can have a valid auction/open but no published
        # close.  Its fill/open is then the only defensible observable mark; do
        # not turn that holding into zero or reach into a future close.
        newly_opened = (pretrade_units_snapshot <= tiny) & (units > tiny)
        open_fallback = newly_opened & ~close_valid & opening_valid
        last_close = np.where(open_fallback, openings, last_close)
        last_close_position = np.where(open_fallback, position, last_close_position)
        if np.any((units > tiny) & ~np.isfinite(last_close)):
            bad = [assets[i] for i in np.flatnonzero((units > tiny) & ~np.isfinite(last_close))]
            raise ValueError(f"unmarkable holdings at close {date.date()}: {bad}")
        stale_days = np.where(close_valid, 0, position - last_close_position)
        held = units > tiny
        stale_violation = held & (stale_days > cfg.max_stale_days)
        if stale_violation.any():
            bad = {assets[i]: int(stale_days[i]) for i in np.flatnonzero(stale_violation)}
            raise ValueError(f"holding exceeds stale-close limit at {date.date()}: {bad}")
        end_values = units * np.nan_to_num(last_close, nan=0.0)
        holdings_value = float(end_values.sum())
        equity = float(cash + holdings_value)
        if equity <= 0:
            raise AssertionError("account equity must remain positive")
        daily_return = equity / previous_equity - 1.0
        turnover_notional = day_buy + day_sell
        turnover = turnover_notional / pretrade_equity
        unfilled_total = max(requested_total - filled_reference_total, 0.0)
        fill_ratio = filled_reference_total / requested_total if requested_total > tiny else 1.0
        max_weight = float(end_values.max() / equity) if number_assets else 0.0
        trades_today = sum(row["filled_units"] > tiny for row in day_orders)

        ledger_rows.append(
            {
                "date": date,
                "pretrade_equity": pretrade_equity,
                "posttrade_equity_at_open": posttrade_equity_at_open,
                "cash": float(cash),
                "holdings_value": holdings_value,
                "equity": equity,
                "wealth": equity,
                "nav": equity / cfg.initial_cash,
                "daily_return": daily_return,
                "buy_notional": day_buy,
                "sell_notional": day_sell,
                "buy": day_buy,
                "sell": day_sell,
                "transaction_cost": day_fee,
                "cost": day_fee,
                "slippage_cost": day_slippage,
                "turnover_notional": turnover_notional,
                "turnover": turnover,
                "requested_notional": requested_total,
                "filled_reference_notional": filled_reference_total,
                "unfilled_notional": unfilled_total,
                "fill_ratio": fill_ratio,
                "order_count": len(day_orders),
                "trade_count": trades_today,
                "holding_count": int(held.sum()),
                "holdings": int(held.sum()),
                "max_single_asset_weight": max_weight,
                "max_weight": max_weight,
                "stale_positions": int((held & ~close_valid).sum()),
                "max_position_stale_days": int(stale_days[held].max()) if held.any() else 0,
                "rebalance": rebalance,
            }
        )
        for i, asset in enumerate(assets):
            weight = float(end_values[i] / equity)
            holding_rows.append(
                {
                    "date": date,
                    "asset": asset,
                    "units": float(units[i]),
                    "adjusted_units": float(units[i]),
                    "mark_price": float(last_close[i]) if np.isfinite(last_close[i]) else np.nan,
                    "mark": float(last_close[i]) if np.isfinite(last_close[i]) else np.nan,
                    "market_value": float(end_values[i]),
                    "value": float(end_values[i]),
                    "weight": weight,
                    "close_available": bool(close_valid[i]),
                    "price_is_stale": bool(held[i] and not close_valid[i]),
                    "stale_days": int(stale_days[i]) if last_close_position[i] >= 0 else np.nan,
                }
            )
        previous_equity = equity

    ledger = pd.DataFrame(ledger_rows, columns=_LEDGER_COLUMNS)
    orders = pd.DataFrame(order_rows, columns=_ORDER_COLUMNS)
    holdings = pd.DataFrame(holding_rows, columns=_HOLDING_COLUMNS)
    fills = orders.loc[orders["filled_units"] > tiny].reset_index(drop=True).copy()
    ledger.attrs["initial_cash"] = cfg.initial_cash
    ledger.attrs["annualization"] = cfg.annualization
    ledger.attrs["daily_risk_free"] = cfg.daily_risk_free
    audit = (
        audit_backtest(ledger, orders, fills, holdings, cfg, calendar=calendar)
        if run_audit
        else {"passed": None, "checks": {}, "max_errors": {}}
    )
    return BacktestResult(ledger, orders, fills, holdings, audit, cfg)


def audit_backtest(
    ledger: pd.DataFrame,
    orders: pd.DataFrame,
    fills: pd.DataFrame,
    holdings: pd.DataFrame,
    config: BacktestConfig | Mapping[str, object] | None = None,
    *,
    calendar: pd.DatetimeIndex | None = None,
    raise_on_error: bool = True,
) -> dict[str, object]:
    """Reconcile returns, compounding, valuation, cash, positions, and fills."""

    cfg = _coerce_config(config)
    tolerance = cfg.audit_tolerance
    if ledger.empty:
        raise ValueError("cannot audit an empty ledger")

    wealth = ledger["equity"].to_numpy(float)
    previous = np.r_[cfg.initial_cash, wealth[:-1]]
    return_error = float(np.max(np.abs(wealth / previous - 1.0 - ledger["daily_return"].to_numpy(float))))
    compound_error = float(abs(np.prod(1.0 + ledger["daily_return"].to_numpy(float)) - wealth[-1] / cfg.initial_cash))

    holding_value = (
        holdings.groupby("date", sort=True)["market_value"]
        .sum()
        .reindex(pd.DatetimeIndex(ledger["date"]))
        .to_numpy(float)
    )
    valuation_error = float(np.max(np.abs(holding_value + ledger["cash"].to_numpy(float) - wealth)))

    expected_cash = cfg.initial_cash + np.cumsum(
        ledger["sell_notional"].to_numpy(float)
        - ledger["buy_notional"].to_numpy(float)
        - ledger["transaction_cost"].to_numpy(float)
    )
    cash_error = float(np.max(np.abs(expected_cash - ledger["cash"].to_numpy(float))))

    daily_fill_fee = (
        fills.groupby("date")["fee"]
        .sum()
        .reindex(pd.DatetimeIndex(ledger["date"]), fill_value=0.0)
        .to_numpy(float)
        if not fills.empty
        else np.zeros(len(ledger))
    )
    fee_reconciliation_error = float(
        np.max(np.abs(daily_fill_fee - ledger["transaction_cost"].to_numpy(float)))
    )
    if fills.empty:
        fee_formula_error = 0.0
    else:
        expected_fee = fills["filled_notional"].to_numpy(float) * np.where(
            fills["side"].to_numpy() == "buy", cfg.buy_fee, cfg.sell_fee
        )
        fee_formula_error = float(np.max(np.abs(expected_fee - fills["fee"].to_numpy(float))))

    holding_units = holdings.pivot(index="date", columns="asset", values="units").sort_index()
    signed_fills = (
        fills.pivot_table(
            index="date", columns="asset", values="signed_filled_units", aggfunc="sum"
        )
        .reindex(index=holding_units.index, columns=holding_units.columns, fill_value=0.0)
        .fillna(0.0)
        if not fills.empty
        else pd.DataFrame(0.0, index=holding_units.index, columns=holding_units.columns)
    )
    position_error = float(np.max(np.abs(holding_units.to_numpy(float) - signed_fills.cumsum().to_numpy(float))))
    audit_units = holdings["units"].to_numpy(float)
    audit_marks = holdings["mark_price"].to_numpy(float)
    expected_position_value = np.where(
        np.abs(audit_units) <= tolerance,
        0.0,
        audit_units * audit_marks,
    )
    position_valuation_error = float(
        np.max(np.abs(holdings["market_value"].to_numpy(float) - expected_position_value))
    )

    execution_conservation_error = float(
        np.max(
            np.abs(
                ledger["pretrade_equity"].to_numpy(float)
                - ledger["posttrade_equity_at_open"].to_numpy(float)
                - ledger["transaction_cost"].to_numpy(float)
                - ledger["slippage_cost"].to_numpy(float)
            )
        )
    )
    no_borrow = bool((ledger["cash"] >= -tolerance).all())
    no_short = bool((holdings["units"] >= -tolerance).all())
    stale_limit = bool(
        (ledger["max_position_stale_days"] <= cfg.max_stale_days).all()
    )

    timing_violations = 0
    if not orders.empty:
        timing_violations += int((orders["signal_date"] >= orders["date"]).sum())
        if calendar is not None:
            positions = {date: i for i, date in enumerate(pd.DatetimeIndex(calendar))}
            timing_violations += sum(
                positions.get(pd.Timestamp(row.date), -2)
                != positions.get(pd.Timestamp(row.signal_date), -1) + 1
                for row in orders[["date", "signal_date"]].drop_duplicates().itertuples(index=False)
            )
    missing_open_fill_violations = int(
        ((orders["reference_price"].isna()) & (orders["filled_units"] > tolerance)).sum()
    ) if not orders.empty else 0
    rejected_fee_violations = int(
        ((orders["filled_units"] <= tolerance) & (orders["fee"].abs() > tolerance)).sum()
    ) if not orders.empty else 0
    if fills.empty:
        capacity_violations = 0
    else:
        capacity_rows = fills["capacity_notional"].notna()
        capacity_violations = int(
            (
                fills.loc[capacity_rows, "filled_reference_notional"]
                > fills.loc[capacity_rows, "capacity_notional"] + tolerance
            ).sum()
        )

    max_errors = {
        "return": return_error,
        "compound": compound_error,
        "valuation": valuation_error,
        "cash": cash_error,
        "fee_reconciliation": fee_reconciliation_error,
        "fee_formula": fee_formula_error,
        "position": position_error,
        "position_valuation": position_valuation_error,
        "execution_conservation": execution_conservation_error,
    }
    checks = {
        "returns": return_error <= tolerance,
        "compound": compound_error <= tolerance,
        "valuation": valuation_error <= tolerance,
        "cash_ledger": cash_error <= tolerance,
        "cost": max(fee_reconciliation_error, fee_formula_error) <= tolerance,
        "position_ledger": max(position_error, position_valuation_error) <= tolerance,
        "execution_conservation": execution_conservation_error <= tolerance,
        "no_borrowing": no_borrow,
        "no_shorting": no_short,
        "timing": timing_violations == 0,
        "capacity": capacity_violations == 0,
        "missing_open": missing_open_fill_violations == 0,
        "rejected_orders_are_free": rejected_fee_violations == 0,
        "stale_limit": stale_limit,
    }
    violations = {
        "timing": int(timing_violations),
        "capacity": capacity_violations,
        "missing_open": missing_open_fill_violations,
        "rejected_order_fee": rejected_fee_violations,
    }
    passed = bool(all(checks.values()))
    report: dict[str, object] = {
        "passed": passed,
        "tolerance": tolerance,
        "checks": checks,
        "max_errors": max_errors,
        "violations": violations,
    }
    if raise_on_error and not passed:
        raise AssertionError(report)
    return report


def run_factor_backtest(
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    portfolio_config: PortfolioConfig | Mapping[str, object] | None = None,
    backtest_config: BacktestConfig | Mapping[str, object] | None = None,
    *,
    capacity_limited: bool | None = None,
) -> BacktestResult:
    """Convenience composition of the independent strategy and broker layers."""

    bt = _coerce_config(backtest_config)
    normalised = _normalise_prices(prices)
    calendar = pd.DatetimeIndex(normalised["date"].drop_duplicates().sort_values())
    targets = generate_target_weights(
        scores,
        calendar=calendar,
        config=portfolio_config,
        start=bt.start,
        end=bt.end,
    )
    return run_backtest(
        normalised,
        targets,
        bt,
        capacity_limited=capacity_limited,
    )


def run_equal_weight_benchmark(
    prices: pd.DataFrame,
    portfolio_config: PortfolioConfig | Mapping[str, object] | None = None,
    backtest_config: BacktestConfig | Mapping[str, object] | None = None,
    *,
    capacity_limited: bool | None = None,
) -> BacktestResult:
    """Run an equal-weight eligible-universe benchmark through the same broker."""

    bt = _coerce_config(backtest_config)
    normalised = _normalise_prices(prices)
    calendar = pd.DatetimeIndex(normalised["date"].drop_duplicates().sort_values())
    eligibility = normalised.pivot(index="date", columns="asset", values="close_adj")
    eligibility = eligibility.where(eligibility.notna(), np.nan)
    targets = generate_equal_weight_targets(
        eligibility,
        calendar=calendar,
        config=portfolio_config,
        start=bt.start,
        end=bt.end,
    )
    return run_backtest(
        normalised,
        targets,
        bt,
        capacity_limited=capacity_limited,
    )


def rerun_without_fees(
    prices: pd.DataFrame,
    targets: pd.DataFrame,
    config: BacktestConfig | Mapping[str, object] | None = None,
    *,
    capacity_limited: bool | None = None,
) -> BacktestResult:
    """Compute gross results by an independent zero-commission simulation."""

    cfg = _coerce_config(config).zero_fee()
    return run_backtest(prices, targets, cfg, capacity_limited=capacity_limited)


__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "audit_backtest",
    "rerun_without_fees",
    "run_backtest",
    "run_equal_weight_benchmark",
    "run_factor_backtest",
]
