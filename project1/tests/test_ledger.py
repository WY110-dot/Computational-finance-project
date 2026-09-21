import pytest
import pandas as pd
import numpy as np
import os
import sys

# 添加 src 到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtest.ledger import AccountLedger

def test_ledger_identities():
    """测试账本核心恒等式及逻辑"""
    # 模拟数据
    df = pd.DataFrame({
        'trade_date': ['20240101', '20240102', '20240103', '20240104'],
        'close_adj': [10.0, 11.0, 9.0, 12.0],
        'position': [0, 1, 1, 0] # t=1 买入, t=2 持有, t=3 卖出
    })
    
    ledger = AccountLedger(initial_capital=1000.0, buy_fee_rate=0.01, sell_fee_rate=0.01)
    res = ledger.run_ledger_simulation(df, price_col='close_adj', position_col='position')
    
    # 验证多次运行一致性
    res2 = ledger.run_ledger_simulation(df, price_col='close_adj', position_col='position')
    pd.testing.assert_frame_equal(res, res2)
    
    # t=0: 空仓
    assert np.isclose(res.loc[0, 'cash'], 1000.0)
    assert np.isclose(res.loc[0, 'shares'], 0.0)
    assert np.isclose(res.loc[0, 'equity_after_trade'], 1000.0)
    
    # t=1: 买入 
    # notional = 1000 / 1.01 = 990.099
    # cost = 9.90099
    # shares = 990.099 / 11.0 = 90.009
    # cash = 1000 - 990.099 - 9.90099 = 0.0
    # equity_after_trade = cash + shares * 11 = 0 + 990.099
    assert np.isclose(res.loc[1, 'trade'], 1)
    assert np.isclose(res.loc[1, 'cash'], 0.0, atol=1e-5)
    assert np.isclose(res.loc[1, 'shares'], 990.0990099 / 11.0)
    assert np.isclose(res.loc[1, 'cost'], 9.900990099)
    assert np.isclose(res.loc[1, 'equity_after_trade'], 990.0990099)
    
    # t=2: 持有
    # shares = 90.009 (from t=1)
    # price = 9.0
    # cash = 0.0
    # equity = 0 + 90.009 * 9.0 = 810.081
    assert np.isclose(res.loc[2, 'trade'], 0)
    assert np.isclose(res.loc[2, 'shares'], res.loc[1, 'shares'])
    assert np.isclose(res.loc[2, 'cash'], 0.0)
    assert np.isclose(res.loc[2, 'equity_after_trade'], res.loc[2, 'shares'] * 9.0)
    assert np.isclose(res.loc[2, 'equity_after_trade'], res.loc[2, 'cash'] + res.loc[2, 'holdings_value'])
    
    # t=3: 卖出
    # price = 12.0
    # sell_notional = shares * 12.0 = 90.009 * 12.0 = 1080.108
    # cost = 1080.108 * 0.01 = 10.80108
    # cash = 0 + 1080.108 - 10.80108 = 1069.30692
    assert np.isclose(res.loc[3, 'trade'], -1)
    assert np.isclose(res.loc[3, 'shares'], 0.0)
    assert np.isclose(res.loc[3, 'cost'], res.loc[3, 'sell_notional'] * 0.01)
    assert np.isclose(res.loc[3, 'cash'], res.loc[3, 'sell_notional'] - res.loc[3, 'cost'])
    
    # 核心恒等式循环验证
    for i in range(len(res)):
        eq = res.loc[i, 'cash'] + res.loc[i, 'holdings_value']
        assert np.isclose(eq, res.loc[i, 'equity_after_trade'])

