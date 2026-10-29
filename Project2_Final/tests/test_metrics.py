from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantcf.backtest import BacktestConfig, rerun_without_fees, run_backtest  # noqa: E402
from quantcf.metrics import calculate_metrics, compare_results, drawdown_series  # noqa: E402


def synthetic_ledger(returns: list[float], initial: float = 1_000.0) -> pd.DataFrame:
    r = np.asarray(returns, dtype=float)
    equity = initial * np.cumprod(1.0 + r)
    dates = pd.bdate_range("2024-01-02", periods=len(r))
    frame = pd.DataFrame(
        {
            "date": dates,
            "equity": equity,
            "daily_return": r,
            "cash": np.zeros(len(r)),
            "transaction_cost": np.zeros(len(r)),
            "slippage_cost": np.zeros(len(r)),
            "turnover": np.zeros(len(r)),
            "turnover_notional": np.zeros(len(r)),
            "requested_notional": np.zeros(len(r)),
            "filled_reference_notional": np.zeros(len(r)),
            "trade_count": np.zeros(len(r)),
            "holding_count": np.ones(len(r)),
            "max_single_asset_weight": np.ones(len(r)),
            "stale_positions": np.zeros(len(r)),
        }
    )
    frame.attrs["initial_cash"] = initial
    frame.attrs["annualization"] = 252
    frame.attrs["daily_risk_free"] = 0.0
    return frame


def test_metrics_include_first_day_drawdown_from_initial_capital() -> None:
    ledger = synthetic_ledger([-0.10, 0.0, 0.05])
    metrics = calculate_metrics(ledger)
    assert metrics["maximum_drawdown"] == pytest.approx(0.10)
    assert drawdown_series(ledger).iloc[0] == pytest.approx(-0.10)
    assert metrics["cumulative_return"] == pytest.approx(0.9 * 1.05 - 1.0)
    assert metrics["drawdown_peak_date"] is None


def test_compounding_annualization_volatility_and_sharpe() -> None:
    ledger = synthetic_ledger([0.01, -0.01, 0.02, 0.00])
    metrics = calculate_metrics(ledger)
    expected_total = np.prod([1.01, 0.99, 1.02, 1.0]) - 1
    expected_annual = (1 + expected_total) ** (252 / 4) - 1
    expected_vol = np.std([0.01, -0.01, 0.02, 0.0], ddof=1) * np.sqrt(252)
    expected_sharpe = (
        np.mean([0.01, -0.01, 0.02, 0.0])
        / np.std([0.01, -0.01, 0.02, 0.0], ddof=1)
        * np.sqrt(252)
    )
    assert metrics["cumulative_return"] == pytest.approx(expected_total)
    assert metrics["annualized_return"] == pytest.approx(expected_annual)
    assert metrics["annualized_volatility"] == pytest.approx(expected_vol)
    assert metrics["sharpe_ratio"] == pytest.approx(expected_sharpe)


def test_constant_returns_have_undefined_sharpe_not_fake_zero() -> None:
    metrics = calculate_metrics(synthetic_ledger([0.0, 0.0, 0.0]))
    assert metrics["sharpe_ratio"] is None
    assert metrics["maximum_drawdown"] == 0.0


def test_trade_cost_fill_and_concentration_metrics_from_real_ledger() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = pd.DataFrame(
        {
            "date": dates,
            "asset": ["A", "A"],
            "open_adj": [10.0, 10.0],
            "close_adj": [10.0, 10.0],
            "amount": [1_000_000.0, 1_000_000.0],
        }
    )
    targets = pd.DataFrame(
        {
            "signal_date": [dates[0]],
            "execution_date": [dates[1]],
            "asset": ["A"],
            "target_weight": [1.0],
        }
    )
    config = BacktestConfig(
        initial_cash=1_000.0,
        buy_fee=0.01,
        sell_fee=0.0,
        capacity_limited=False,
    )
    result = run_backtest(prices, targets, config)
    metrics = calculate_metrics(result)
    assert metrics["total_transaction_cost"] == pytest.approx(result.ledger.transaction_cost.sum())
    assert metrics["aggregate_fill_ratio"] < 1.0  # cash reserved for the fee
    assert metrics["total_trade_count"] == 1
    assert metrics["maximum_single_asset_weight"] == pytest.approx(1.0)
    assert metrics["maximum_drawdown"] > 0

    gross = rerun_without_fees(prices, targets, config)
    comparison = compare_results(result, gross)
    assert comparison["fee_return_drag"] > 0
    assert comparison["terminal_wealth_drag"] > 0

