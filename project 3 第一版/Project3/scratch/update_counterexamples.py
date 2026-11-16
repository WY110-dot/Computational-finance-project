from pathlib import Path

content = Path("tests/test_project3_counterexamples.py").read_text(encoding="utf-8")

# Update imports
content = content.replace(
    "from quantcf.project3_pipeline import execute_broker_simulation",
    "from quantcf.project3_pipeline import execute_broker_simulation, generate_portfolio_target_weights"
)

extra_tests = '''

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
        for a in assets:
            panel_rows.append({
                "date": d,
                "asset": a,
                "open_adj": 100.0,
                "close_adj": 100.0,
                "ret_total": 0.001,
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
    dd_a = res_a["metrics"]["max_drawdown_daily"]
    dd_b = res_b["metrics"]["max_drawdown_daily"]
    assert np.isclose(dd_a, 0.0, atol=1e-6)
    assert np.isclose(dd_b, 0.0, atol=1e-6)
'''

content += extra_tests
Path("tests/test_project3_counterexamples.py").write_text(content, encoding="utf-8")
print("Successfully updated tests/test_project3_counterexamples.py!")
