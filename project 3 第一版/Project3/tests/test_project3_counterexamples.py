"""Unit tests for Reviewer Counterexamples and Edge Cases in Project 3.

Verifies:
1. Reviewer Counterexample 1: Entry intraday jump & exit jump, open-to-open return == 9.9% (not 99.09%).
2. Reviewer Counterexample 2: Flat price with 3 bps cost, net return == -0.0297% and fee == 297 RMB.
3. Reviewer Counterexample 3: Adjacent monthly fees non-overlapping sum == total ledger fees == total fills fees.
4. Intraday price jump isolation: Entry open-to-close and exit open-to-close jumps correctly scoped.
5. Overnight price gaps correctly captured by open-to-open compounding.
6. Empty signal handling / re-entry: Strategy rebalances to 100% cash when no positive signals exist, never borrows.
7. Exact telescoping compounding: prod(1 + r_k) == W(T_{K+1}^-) / W_0 across all periods.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantcf.backtest import BacktestConfig, run_backtest
from quantcf.project3_pipeline import execute_broker_simulation, generate_portfolio_target_weights


def test_counterexample_1_open_to_open_vs_close_to_close():
    """Independent reviewer counterexample 1:
    Initial cash 1M, 99% invested, 0 fee.
    Day 1 (entry): open 100, close 110.
    Day 2 (exit): open 110, close 220.
    True open-to-open return: (110 / 100 - 1) * 0.99 = 9.9%.
    Old buggy code returned 99.09008189%.
    """
    prices = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 110.0, "amount": 1e9, "ret_total": 0.10},
        {"date": pd.Timestamp("2024-01-03"), "asset": "ETF1", "open_adj": 110.0, "close_adj": 220.0, "amount": 1e9, "ret_total": 1.00},
    ])
    periods = [
        {"formation_date": pd.Timestamp("2023-12-29"), "entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-01-03")}
    ]
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2023-12-29"), "execution_date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "target_weight": 0.99}
    ])
    
    res = execute_broker_simulation(prices, targets, periods, list(prices["date"]), cost_bps=0.0)
    assert res["audit"]["passed"]
    
    m_rets = res["monthly_returns"]
    assert len(m_rets) == 1
    ret = m_rets["net_return"].iloc[0]
    
    # Assert return is exactly 9.9%, NOT 99.09%
    assert np.isclose(ret, 0.099, atol=1e-6)
    assert not np.isclose(ret, 0.9909, atol=1e-2)
    assert np.isclose(m_rets["fees"].iloc[0], 0.0, atol=1e-6)


def test_counterexample_2_flat_price_with_fee():
    """Independent reviewer counterexample 2:
    Flat price (open 100, close 100), 3 bps fee, 99% invested.
    True net return: -0.0297%, fee == 297 RMB.
    Old buggy code returned 0.0% net return and missed the fee.
    """
    prices = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-03"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
    ])
    periods = [
        {"formation_date": pd.Timestamp("2023-12-29"), "entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-01-03")}
    ]
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2023-12-29"), "execution_date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "target_weight": 0.99}
    ])
    
    res = execute_broker_simulation(prices, targets, periods, list(prices["date"]), cost_bps=3.0)
    assert res["audit"]["passed"]
    
    m_rets = res["monthly_returns"]
    ret = m_rets["net_return"].iloc[0]
    fee = m_rets["fees"].iloc[0]
    
    # Assert net return is -0.0297% and fee is 297 RMB
    assert np.isclose(ret, -0.000297, atol=1e-6)
    assert np.isclose(fee, 297.0, atol=1e-1)


def test_counterexample_3_adjacent_months_non_overlapping_fees():
    """Independent reviewer finding 3:
    Adjacent months sharing a rebalance date must NOT double count fees.
    Sum of monthly fees must strictly equal total ledger transaction costs.
    """
    prices = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 105.0, "amount": 1e9, "ret_total": 0.05},
        {"date": pd.Timestamp("2024-01-31"), "asset": "ETF1", "open_adj": 105.0, "close_adj": 105.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-02-01"), "asset": "ETF1", "open_adj": 105.0, "close_adj": 110.0, "amount": 1e9, "ret_total": 0.0476},
        {"date": pd.Timestamp("2024-02-29"), "asset": "ETF1", "open_adj": 110.0, "close_adj": 110.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-03-01"), "asset": "ETF1", "open_adj": 110.0, "close_adj": 110.0, "amount": 1e9, "ret_total": 0.0},
    ])
    periods = [
        {"formation_date": pd.Timestamp("2023-12-29"), "entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-02-01")},
        {"formation_date": pd.Timestamp("2024-01-31"), "entry_date": pd.Timestamp("2024-02-01"), "exit_date": pd.Timestamp("2024-03-01")},
    ]
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2023-12-29"), "execution_date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "target_weight": 0.5},
        {"signal_date": pd.Timestamp("2024-01-31"), "execution_date": pd.Timestamp("2024-02-01"), "asset": "ETF1", "target_weight": 0.8},
    ])
    
    res = execute_broker_simulation(prices, targets, periods, list(prices["date"]), cost_bps=3.0)
    assert res["audit"]["passed"]
    
    m_rets = res["monthly_returns"]
    monthly_fees_sum = m_rets["fees"].sum()
    ledger_fees_sum = res["ledger"]["transaction_cost"].sum()
    fills_fees_sum = res["fills"]["fee"].sum()
    
    # Exact non-overlapping fee conservation
    assert np.isclose(monthly_fees_sum, ledger_fees_sum, atol=1e-5)
    assert np.isclose(monthly_fees_sum, fills_fees_sum, atol=1e-5)
    
    # Exact telescoping compounding
    compounded = np.prod(1.0 + m_rets["net_return"].values)
    w_start = m_rets["w_entry_pretrade"].iloc[0]
    w_end = m_rets["w_exit_pretrade"].iloc[-1]
    nav_ratio = w_end / w_start
    assert np.isclose(compounded, nav_ratio, atol=1e-10)


def test_intraday_jumps_and_overnight_gaps():
    """Verify that open-to-open returns correctly ignore exit-day intraday jumps,
    while capturing entry-day intraday moves and overnight gaps."""
    # Entry date: open 100, close 150 (huge intraday jump of +50%)
    # Overnight gap: close 150 -> next open 180 (huge overnight gap of +20%)
    # Exit date: open 180, close 300 (huge post-exit jump of +66%)
    # Open-to-open return must be 180 / 100 - 1 = +80% (for 100% weight, 0 fee)
    prices = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 150.0, "amount": 1e9, "ret_total": 0.50},
        {"date": pd.Timestamp("2024-01-03"), "asset": "ETF1", "open_adj": 180.0, "close_adj": 300.0, "amount": 1e9, "ret_total": 0.666},
    ])
    periods = [
        {"formation_date": pd.Timestamp("2023-12-29"), "entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-01-03")}
    ]
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2023-12-29"), "execution_date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "target_weight": 0.99}
    ])
    res = execute_broker_simulation(prices, targets, periods, list(prices["date"]), cost_bps=0.0)
    m_rets = res["monthly_returns"]
    ret = m_rets["net_return"].iloc[0]
    
    # 99% invested: expected return = (180 / 100 - 1) * 0.99 = 0.80 * 0.99 = 0.792 (79.2%)
    assert np.isclose(ret, 0.792, atol=1e-6)


def test_empty_signal_rebalance_to_cash_and_reentry():
    """Verify that when a rebalance has 0 targets (e.g. bear market in A0),
    the broker actively sells all holdings to 100% cash, never borrows,
    and cleanly re-enters when positive signals appear."""
    prices = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 105.0, "amount": 1e9, "ret_total": 0.05},
        {"date": pd.Timestamp("2024-01-31"), "asset": "ETF1", "open_adj": 105.0, "close_adj": 90.0, "amount": 1e9, "ret_total": -0.1428},
        {"date": pd.Timestamp("2024-02-01"), "asset": "ETF1", "open_adj": 90.0, "close_adj": 80.0, "amount": 1e9, "ret_total": -0.111},
        {"date": pd.Timestamp("2024-02-29"), "asset": "ETF1", "open_adj": 80.0, "close_adj": 85.0, "amount": 1e9, "ret_total": 0.0625},
        {"date": pd.Timestamp("2024-03-01"), "asset": "ETF1", "open_adj": 85.0, "close_adj": 90.0, "amount": 1e9, "ret_total": 0.0588},
        {"date": pd.Timestamp("2024-03-29"), "asset": "ETF1", "open_adj": 90.0, "close_adj": 90.0, "amount": 1e9, "ret_total": 0.0},
    ])
    periods = [
        {"formation_date": pd.Timestamp("2023-12-29"), "entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-02-01")},
        {"formation_date": pd.Timestamp("2024-01-31"), "entry_date": pd.Timestamp("2024-02-01"), "exit_date": pd.Timestamp("2024-03-01")},
        {"formation_date": pd.Timestamp("2024-02-29"), "entry_date": pd.Timestamp("2024-03-01"), "exit_date": pd.Timestamp("2024-03-29")},
    ]
    # Month 1: Buy 0.5
    # Month 2: Rebalance to 0.0 (all cash)
    # Month 3: Re-enter with 0.8
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2023-12-29"), "execution_date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "target_weight": 0.5},
        {"signal_date": pd.Timestamp("2024-01-31"), "execution_date": pd.Timestamp("2024-02-01"), "asset": "ETF1", "target_weight": 0.0},
        {"signal_date": pd.Timestamp("2024-02-29"), "execution_date": pd.Timestamp("2024-03-01"), "asset": "ETF1", "target_weight": 0.8},
    ])
    res = execute_broker_simulation(prices, targets, periods, list(prices["date"]), cost_bps=3.0)
    assert res["audit"]["passed"]
    
    ledger = res["ledger"]
    # Check that in Month 2 (after 2024-02-01 rebalance to 0), holdings value is 0.0
    m2_ledger = ledger[(ledger["date"] >= "2024-02-01") & (ledger["date"] < "2024-03-01")]
    assert (m2_ledger["holdings_value"] <= 1e-4).all()
    assert (m2_ledger["cash"] > 0).all()


def test_a0_long_cash_six_assets():
    """Verify P2 Long/Cash asset allocation mechanics in A0:
    In a 6-asset universe where 3 assets have positive momentum and 3 have negative momentum,
    with identical volatility and 99% maximum budget:
    - Inverse-vol budget allocates 99% / 6 = 16.5% to each of the 6 qualified assets.
    - Negative momentum assets receive 0% weight and their allocated budget stays in cash.
    - Total target portfolio weight must equal 3 * 16.5% = 49.5%, with remaining 50.5% in cash.
    - The strategy must NOT re-normalize to 99%!
    """
    assets = [f"ETF{i}" for i in range(1, 7)]
    t = pd.Timestamp("2023-12-29")
    entry = pd.Timestamp("2024-01-02")
    
    # 3 positive signs (ETF1, ETF2, ETF3), 3 negative signs (ETF4, ETF5, ETF6)
    factors_data = []
    for i, a in enumerate(assets):
        sign = 1.0 if i < 3 else -1.0
        factors_data.append({
            "formation_date": t,
            "asset": a,
            "a0_raw": sign,
            "A0": sign,
        })
    df_factors = pd.DataFrame(factors_data)
    
    # Create daily panel with 260 days of identical daily returns for all 6 assets so volatilities are equal
    dates = pd.date_range("2023-01-01", "2023-12-29", freq="B")
    panel_rows = []
    for d in dates:
        ret_val = 0.01 if (d.day % 2 == 0) else -0.01
        for a in assets:
            panel_rows.append({
                "date": d,
                "asset": a,
                "open_adj": 100.0,
                "close_adj": 100.0,
                "ret_total": ret_val,
                "amount": 1e8,
            })
    daily_panel = pd.DataFrame(panel_rows)
    
    periods = [{"formation_date": t, "entry_date": entry, "exit_date": pd.Timestamp("2024-02-01")}]
    
    targets = generate_portfolio_target_weights(
        df_factors=df_factors,
        periods=periods,
        daily_panel=daily_panel,
        calendar_dates=list(dates),
        strategy_mode="A0",
        budget=0.99,
        min_assets=6,
        min_vol_days=250,
    )
    
    # Must only contain the 3 positive assets
    assert len(targets) == 3
    assert set(targets["asset"]) == {"ETF1", "ETF2", "ETF3"}
    
    # Each target weight must be 0.99 / 6 = 0.165 (16.5%)
    for w in targets["target_weight"]:
        assert np.isclose(w, 0.165, atol=1e-5)
        
    # Total invested weight must be 49.5%, NOT 99%
    total_invested = targets["target_weight"].sum()
    assert np.isclose(total_invested, 0.495, atol=1e-5)
    assert not np.isclose(total_invested, 0.99, atol=1e-2)


def test_exit_close_price_independence():
    """Verify that daily risk and monthly returns terminate strictly at T_{K+1}^- open equity.
    Altering the exit date close price (e.g. from 100 down to 1.0, a -99% crash after open exit)
    must NOT affect:
    1. Monthly net return (positions were closed at open).
    2. Daily max drawdown (open-to-open holding period does not include post-exit price drops).
    """
    periods = [
        {"formation_date": pd.Timestamp("2023-12-29"), "entry_date": pd.Timestamp("2024-01-02"), "exit_date": pd.Timestamp("2024-01-03")}
    ]
    targets = pd.DataFrame([
        {"signal_date": pd.Timestamp("2023-12-29"), "execution_date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "target_weight": 0.99}
    ])
    
    # Scenario A: Flat exit close
    prices_a = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-03"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
    ])
    res_a = execute_broker_simulation(prices_a, targets, periods, list(prices_a["date"]), cost_bps=0.0)
    
    # Scenario B: Exit close crashes to 1.0 (-99%) after position is closed at open
    prices_b = pd.DataFrame([
        {"date": pd.Timestamp("2023-12-29"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-02"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 100.0, "amount": 1e9, "ret_total": 0.0},
        {"date": pd.Timestamp("2024-01-03"), "asset": "ETF1", "open_adj": 100.0, "close_adj": 1.0, "amount": 1e9, "ret_total": -0.99},
    ])
    res_b = execute_broker_simulation(prices_b, targets, periods, list(prices_b["date"]), cost_bps=0.0)
    
    # Monthly returns must be identical (0.0% return)
    ret_a = res_a["monthly_returns"]["net_return"].iloc[0]
    ret_b = res_b["monthly_returns"]["net_return"].iloc[0]
    assert np.isclose(ret_a, 0.0, atol=1e-7)
    assert np.isclose(ret_b, 0.0, atol=1e-7)
    
    # Daily max drawdown must be identical (0.0% drawdown, NOT -99%)
    dd_a = res_a["summary"]["max_drawdown_daily"]
    dd_b = res_b["summary"]["max_drawdown_daily"]
    assert np.isclose(dd_a, 0.0, atol=1e-6)
    assert np.isclose(dd_b, 0.0, atol=1e-6)
