from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantcf.backtest import (  # noqa: E402
    BacktestConfig,
    rerun_without_fees,
    run_backtest,
)
from quantcf.portfolio import (  # noqa: E402
    PortfolioConfig,
    generate_target_weights,
)


def panel(
    dates: pd.DatetimeIndex,
    assets: tuple[str, ...] = ("A", "B"),
    *,
    open_value: float = 10.0,
    close_value: float = 10.0,
    amount: float = 1_000_000.0,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": date,
                "asset": asset,
                "open_adj": open_value,
                "close_adj": close_value,
                "amount": amount,
            }
            for date in dates
            for asset in assets
        ]
    )


def target(
    signal: pd.Timestamp,
    execution: pd.Timestamp,
    weights: dict[str, float],
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "signal_date": signal,
                "execution_date": execution,
                "asset": asset,
                "target_weight": weight,
            }
            for asset, weight in weights.items()
        ]
    )


def cfg(**kwargs: object) -> BacktestConfig:
    values: dict[str, object] = {
        "initial_cash": 1_000.0,
        "buy_fee": 0.0,
        "sell_fee": 0.0,
        "capacity_limited": False,
    }
    values.update(kwargs)
    return BacktestConfig(**values)


def test_portfolio_is_close_t_next_open_and_ties_are_deterministic() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    scores = pd.DataFrame(
        [[1.0, 1.0], [2.0, 3.0], [100.0, -100.0], [0.0, 0.0]],
        index=dates,
        columns=["B", "A"],
    )
    targets = generate_target_weights(
        scores,
        config=PortfolioConfig(top_n=1, invest_fraction=1.0, frequency="daily"),
    )
    first = targets[targets.execution_date == dates[1]].iloc[0]
    assert first.signal_date == dates[0]
    assert first.asset == "A"  # same score, stable asset-name tie break

    changed = scores.copy()
    changed.loc[dates[2]:, :] *= -999.0
    changed_targets = generate_target_weights(
        changed,
        config=PortfolioConfig(top_n=1, invest_fraction=1.0, frequency="daily"),
    )
    pd.testing.assert_frame_equal(
        targets[targets.execution_date <= dates[2]].reset_index(drop=True),
        changed_targets[changed_targets.execution_date <= dates[2]].reset_index(drop=True),
    )


@pytest.mark.parametrize("bad_execution", [0, 2])
def test_broker_rejects_same_day_and_skipped_session_execution(bad_execution: int) -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    bad = target(dates[0], dates[bad_execution], {"A": 1.0})
    with pytest.raises(ValueError, match="timing"):
        run_backtest(panel(dates), bad, cfg())


def test_cash_account_fees_and_initial_drawdown_are_exact() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    result = run_backtest(
        panel(dates, assets=("A",)),
        target(dates[0], dates[1], {"A": 1.0}),
        cfg(buy_fee=0.01),
    )
    day = result.ledger.iloc[1]
    expected_buy = 1_000.0 / 1.01
    assert day.buy_notional == pytest.approx(expected_buy)
    assert day.transaction_cost == pytest.approx(expected_buy * 0.01)
    assert day.cash == pytest.approx(0.0, abs=1e-10)
    assert day.equity == pytest.approx(expected_buy)
    assert day.daily_return == pytest.approx(expected_buy / 1_000.0 - 1.0)
    assert result.audit["passed"] is True


def test_sales_are_processed_before_buys_and_cash_identity_holds() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    targets = pd.concat(
        [
            target(dates[0], dates[1], {"A": 1.0}),
            target(dates[1], dates[2], {"B": 1.0}),
        ],
        ignore_index=True,
    )
    result = run_backtest(
        panel(dates),
        targets,
        cfg(buy_fee=0.01, sell_fee=0.02),
    )
    final = result.ledger.iloc[-1]
    assert final.sell_notional > 0
    assert final.buy_notional > 0
    assert final.cash >= -1e-10
    expected_cash = 1_000 + result.ledger.sell_notional.sum() - result.ledger.buy_notional.sum() - result.ledger.transaction_cost.sum()
    assert final.cash == pytest.approx(expected_cash)
    assert result.audit["checks"]["cash_ledger"] is True
    assert result.audit["checks"]["position_ledger"] is True


def test_missing_open_rejects_order_without_fee() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = panel(dates, assets=("A",))
    prices.loc[prices.date == dates[1], "open_adj"] = np.nan
    result = run_backtest(
        prices,
        target(dates[0], dates[1], {"A": 1.0}),
        cfg(buy_fee=0.1),
    )
    order = result.orders.iloc[0]
    assert order.status == "rejected"
    assert order.reason == "missing_open"
    assert order.filled_units == 0
    assert order.fee == 0
    assert result.ledger.iloc[-1].equity == 1_000
    assert result.audit["passed"] is True


def test_missing_open_freezes_existing_position_but_close_marks_it() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = panel(dates, assets=("A",))
    prices.loc[prices.date == dates[2], ["open_adj", "close_adj"]] = [np.nan, 11.0]
    targets = pd.concat(
        [
            target(dates[0], dates[1], {"A": 1.0}),
            target(dates[1], dates[2], {"A": 0.0}),
        ],
        ignore_index=True,
    )
    result = run_backtest(prices, targets, cfg(sell_fee=0.1))
    frozen = result.orders[result.orders.date == dates[2]].iloc[0]
    assert frozen.reason == "missing_open"
    assert frozen.fee == 0
    assert result.holdings.query("date == @dates[2]").iloc[0].units == pytest.approx(100.0)
    assert result.ledger.iloc[-1].equity == pytest.approx(1_100.0)


def test_stale_close_limit_fails_loudly() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    prices = panel(dates, assets=("A",))
    prices.loc[prices.date >= dates[2], "close_adj"] = np.nan
    with pytest.raises(ValueError, match="stale-close limit"):
        run_backtest(
            prices,
            target(dates[0], dates[1], {"A": 1.0}),
            cfg(max_stale_days=1),
        )


def test_new_position_without_same_day_close_uses_observed_open_mark() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = panel(dates, assets=("A",))
    prices.loc[prices.date == dates[1], "close_adj"] = np.nan
    # No earlier A close is available: start on the execution date.
    result = run_backtest(
        prices,
        target(dates[0], dates[1], {"A": 1.0}),
        cfg(start=dates[1], max_stale_days=0),
    )
    holding = result.holdings.iloc[0]
    assert holding.mark_price == pytest.approx(10.0)
    assert holding.market_value == pytest.approx(1_000.0)
    assert result.ledger.iloc[0].equity == pytest.approx(1_000.0)


def test_capacity_is_partial_and_uses_only_lagged_amount() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = panel(dates, assets=("A",), amount=100.0)
    prices.loc[prices.date == dates[1], "amount"] = 1_000_000_000.0
    assumptions = BacktestConfig(
        initial_cash=1_000.0,
        buy_fee=0.0,
        sell_fee=0.0,
        adv_window=1,
        participation_rate=0.1,
        capacity_limited=True,
    )
    result = run_backtest(
        prices,
        target(dates[0], dates[1], {"A": 1.0}),
        assumptions,
    )
    order = result.orders.iloc[0]
    assert order.status == "partial"
    assert order.reason == "capacity"
    assert order.capacity_notional == pytest.approx(10.0)
    assert order.filled_reference_notional == pytest.approx(10.0)
    assert order.unfilled_notional == pytest.approx(990.0)
    assert order.fee == 0.0
    assert result.audit["checks"]["capacity"] is True

    changed = prices.copy()
    changed.loc[changed.date == dates[1], "amount"] *= 1000
    repeated = run_backtest(
        changed,
        target(dates[0], dates[1], {"A": 1.0}),
        assumptions,
    )
    assert repeated.orders.iloc[0].filled_reference_notional == pytest.approx(10.0)


def test_slippage_and_commission_reconcile_at_open() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    result = run_backtest(
        panel(dates, assets=("A",)),
        target(dates[0], dates[1], {"A": 0.5}),
        cfg(buy_fee=0.01, slippage_bps=100),
    )
    day = result.ledger.iloc[-1]
    assert day.pretrade_equity - day.posttrade_equity_at_open == pytest.approx(
        day.transaction_cost + day.slippage_cost
    )
    assert result.audit["checks"]["execution_conservation"] is True


def test_zero_fee_gross_is_an_independent_rerun() -> None:
    dates = pd.bdate_range("2024-01-02", periods=2)
    prices = panel(dates, assets=("A",))
    targets = target(dates[0], dates[1], {"A": 1.0})
    net = run_backtest(prices, targets, cfg(buy_fee=0.01))
    gross = rerun_without_fees(prices, targets, cfg(buy_fee=0.01))
    assert gross.config.buy_fee == 0.0
    assert gross.ledger.iloc[-1].equity == pytest.approx(1_000.0)
    assert gross.ledger.iloc[-1].equity > net.ledger.iloc[-1].equity
    assert gross.audit["passed"] is True
