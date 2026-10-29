"""Performance analyzers for the audited account ledger."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, BacktestResult


def _ledger(value: pd.DataFrame | BacktestResult) -> pd.DataFrame:
    return value.ledger if isinstance(value, BacktestResult) else value


def _configuration(
    ledger: pd.DataFrame,
    config: BacktestConfig | Mapping[str, object] | None,
) -> tuple[float, int, float]:
    if isinstance(config, BacktestConfig):
        return config.initial_cash, config.annualization, config.daily_risk_free
    if isinstance(config, Mapping):
        cfg = BacktestConfig.from_mapping(config)
        return cfg.initial_cash, cfg.annualization, cfg.daily_risk_free
    initial = float(ledger.attrs.get("initial_cash", np.nan))
    if not np.isfinite(initial):
        if "nav" in ledger and len(ledger) and ledger["nav"].iloc[-1] != 0:
            initial = float(ledger["equity"].iloc[-1] / ledger["nav"].iloc[-1])
        elif len(ledger):
            first_return = float(ledger["daily_return"].iloc[0])
            initial = float(ledger["equity"].iloc[0] / (1.0 + first_return))
        else:
            raise ValueError("cannot infer initial capital from an empty ledger")
    annualization = int(ledger.attrs.get("annualization", 252))
    daily_rf = float(ledger.attrs.get("daily_risk_free", 0.0))
    return initial, annualization, daily_rf


def drawdown_series(
    ledger: pd.DataFrame | BacktestResult,
    initial_cash: float | None = None,
) -> pd.Series:
    """Return drawdown including initial capital as the first high-water mark."""

    frame = _ledger(ledger)
    if frame.empty:
        return pd.Series(dtype=float, name="drawdown")
    initial, _, _ = _configuration(frame, None)
    if initial_cash is not None:
        initial = float(initial_cash)
    wealth = np.r_[initial, frame["equity"].to_numpy(float)]
    underwater = wealth / np.maximum.accumulate(wealth) - 1.0
    return pd.Series(underwater[1:], index=pd.DatetimeIndex(frame["date"]), name="drawdown")


def calculate_metrics(
    ledger: pd.DataFrame | BacktestResult,
    config: BacktestConfig | Mapping[str, object] | None = None,
    *,
    fills: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Calculate return, risk, trading, capacity, and concentration metrics."""

    result = ledger if isinstance(ledger, BacktestResult) else None
    frame = _ledger(ledger).copy()
    if frame.empty:
        raise ValueError("cannot calculate metrics for an empty ledger")
    if fills is None and result is not None:
        fills = result.fills
    initial_cash, annualization, daily_rf = _configuration(
        frame, result.config if config is None and result is not None else config
    )
    returns = frame["daily_return"].to_numpy(float)
    equity = frame["equity"].to_numpy(float)
    days = len(frame)
    terminal = float(equity[-1])
    cumulative_return = terminal / initial_cash - 1.0
    annualized_return = (terminal / initial_cash) ** (annualization / days) - 1.0
    annualized_volatility = (
        float(np.std(returns, ddof=1) * np.sqrt(annualization)) if days > 1 else 0.0
    )
    excess = returns - daily_rf
    excess_std = float(np.std(excess, ddof=1)) if days > 1 else 0.0
    sharpe = (
        float(np.sqrt(annualization) * np.mean(excess) / excess_std)
        if excess_std > np.finfo(float).eps
        else None
    )
    downside = np.minimum(excess, 0.0)
    downside_deviation = float(np.sqrt(np.mean(downside**2)) * np.sqrt(annualization))
    sortino = (
        float(np.mean(excess) * annualization / downside_deviation)
        if downside_deviation > np.finfo(float).eps
        else None
    )

    wealth_with_initial = np.r_[initial_cash, equity]
    peaks = np.maximum.accumulate(wealth_with_initial)
    drawdowns = wealth_with_initial / peaks - 1.0
    trough_position = int(np.argmin(drawdowns))
    maximum_drawdown = float(-drawdowns[trough_position])
    peak_position = int(np.argmax(wealth_with_initial[: trough_position + 1]))
    recovery_candidates = np.flatnonzero(
        wealth_with_initial[trough_position:] >= peaks[trough_position] - 1e-12
    )
    recovery_position = (
        trough_position + int(recovery_candidates[0]) if len(recovery_candidates) else None
    )
    dates = pd.DatetimeIndex(frame["date"])

    def _position_date(position: int | None) -> str | None:
        if position is None or position == 0:
            return None
        return dates[position - 1].date().isoformat()

    calmar = (
        float(annualized_return / maximum_drawdown)
        if maximum_drawdown > np.finfo(float).eps
        else None
    )
    turnover = frame["turnover"].to_numpy(float)
    total_turnover = float(np.sum(turnover))
    annualized_turnover = total_turnover * annualization / days
    total_cost = float(frame["transaction_cost"].sum())
    total_slippage = float(frame["slippage_cost"].sum())
    requested = float(frame["requested_notional"].sum())
    filled_reference = float(frame["filled_reference_notional"].sum())
    aggregate_fill_ratio = filled_reference / requested if requested > 0 else 1.0
    total_trade_count = (
        int(len(fills)) if fills is not None else int(frame["trade_count"].sum())
    )
    turnover_notional = float(frame["turnover_notional"].sum())
    fee_bps_on_traded_notional = (
        total_cost / turnover_notional * 10_000 if turnover_notional > 0 else 0.0
    )
    exposures = 1.0 - frame["cash"].to_numpy(float) / equity

    return {
        "trading_days": days,
        "initial_cash": float(initial_cash),
        "terminal_equity": terminal,
        "cumulative_return": float(cumulative_return),
        "annualized_return": float(annualized_return),
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "annualized_downside_deviation": downside_deviation,
        "sortino_ratio": sortino,
        "maximum_drawdown": maximum_drawdown,
        "max_drawdown": maximum_drawdown,
        "drawdown_peak_date": _position_date(peak_position),
        "drawdown_trough_date": _position_date(trough_position),
        "drawdown_recovery_date": _position_date(recovery_position),
        "calmar_ratio": calmar,
        "daily_win_rate": float(np.mean(returns > 0)),
        "best_day": float(np.max(returns)),
        "worst_day": float(np.min(returns)),
        "total_turnover": total_turnover,
        "annualized_turnover": float(annualized_turnover),
        "turnover_notional": turnover_notional,
        "total_transaction_cost": total_cost,
        "total_cost": total_cost,
        "total_slippage_cost": total_slippage,
        "cost_as_initial_capital": total_cost / initial_cash,
        "fee_bps_on_traded_notional": float(fee_bps_on_traded_notional),
        "requested_notional": requested,
        "filled_reference_notional": filled_reference,
        "aggregate_fill_ratio": float(aggregate_fill_ratio),
        "total_trade_count": total_trade_count,
        "average_holdings": float(frame["holding_count"].mean()),
        "maximum_holdings": int(frame["holding_count"].max()),
        "maximum_single_asset_weight": float(frame["max_single_asset_weight"].max()),
        "average_invested_fraction": float(np.mean(exposures)),
        "maximum_stale_positions": int(frame["stale_positions"].max()),
    }


def compare_results(
    net: pd.DataFrame | BacktestResult,
    gross: pd.DataFrame | BacktestResult,
    benchmark: pd.DataFrame | BacktestResult | None = None,
) -> dict[str, object]:
    """Compare independently simulated net, zero-fee, and benchmark ledgers."""

    net_metrics = calculate_metrics(net)
    gross_metrics = calculate_metrics(gross)
    output: dict[str, object] = {
        "net": net_metrics,
        "gross_zero_fee": gross_metrics,
        "fee_return_drag": float(
            gross_metrics["cumulative_return"] - net_metrics["cumulative_return"]
        ),
        "terminal_wealth_drag": float(
            gross_metrics["terminal_equity"] - net_metrics["terminal_equity"]
        ),
    }
    if benchmark is not None:
        benchmark_metrics = calculate_metrics(benchmark)
        output["benchmark"] = benchmark_metrics
        output["active_cumulative_return"] = float(
            net_metrics["cumulative_return"] - benchmark_metrics["cumulative_return"]
        )
    return output


@dataclass(frozen=True)
class PerformanceAnalyzer:
    """Backtrader-style analyzer facade for notebook users."""

    annualization: int = 252
    daily_risk_free: float = 0.0

    def analyze(
        self,
        ledger: pd.DataFrame | BacktestResult,
        initial_cash: float | None = None,
    ) -> dict[str, object]:
        frame = _ledger(ledger)
        inferred, _, _ = _configuration(frame, None)
        config = BacktestConfig(
            initial_cash=inferred if initial_cash is None else float(initial_cash),
            annualization=self.annualization,
            daily_risk_free=self.daily_risk_free,
            capacity_limited=False,
        )
        return calculate_metrics(ledger, config)


__all__ = [
    "PerformanceAnalyzer",
    "calculate_metrics",
    "compare_results",
    "drawdown_series",
]
