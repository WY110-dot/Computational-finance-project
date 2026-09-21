import pytest
import pandas as pd
import numpy as np
import os
import sys

# 添加 src 到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.metrics.costs import CostCalculator

def test_cost_and_net_returns():
    """测试净收益率计算，验证无成交日成本为0"""
    df = pd.DataFrame({
        'position': [0, 1, 1, 0, 0],
        'trade':    [0, 1, 0, -1, 0],
        'ret_total':[0.0, 0.05, 0.02, 0.0, 0.0]
    })
    
    res = CostCalculator.calculate_costs_and_net_returns(
        df, buy_fee_rate=0.001, sell_fee_rate=0.002
    )
    
    returns = res['strategy_return'].values
    
    # t=0: trade=0, pos=0 -> return = 0
    assert np.isclose(returns[0], 0.0)
    
    # t=1: trade=1, buy. (1 - 0.001)*(1 + 0.05) - 1
    expected_t1 = (1 - 0.001) * 1.05 - 1
    assert np.isclose(returns[1], expected_t1)
    
    # t=2: trade=0, pos=1. return = ret_total = 0.02
    assert np.isclose(returns[2], 0.02)
    
    # t=3: trade=-1, sell. return = -sell_fee_rate = -0.002
    assert np.isclose(returns[3], -0.002)
    
    # t=4: trade=0, pos=0. return = 0
    assert np.isclose(returns[4], 0.0)


def test_daily_cost_metrics():
    """验证买入/卖出成本的手工核对以及金额累计的一致性"""
    df = pd.DataFrame({
        'trade': [0, 1, 0, -1, 0],
        # 手工设定一个简化的 equity 曲线
        # initial = 1000
        # t=0: eq=1000
        # t=1: buy. eq=1000 * (1-0.001)*1.05 = 1048.95
        # t=2: hold. eq=1048.95 * 1.02 = 1069.929
        # t=3: sell. eq=1069.929 * (1-0.002) = 1067.789142
        # t=4: empty. eq=1067.789142
        'strategy_equity': [
            1000.0, 
            1048.95, 
            1069.929, 
            1067.789142, 
            1067.789142
        ]
    })
    
    res = CostCalculator.compute_daily_cost_metrics(
        df, initial_capital=1000.0, buy_fee_rate=0.001, sell_fee_rate=0.002
    )
    
    # t=1 (Buy) 手工核对
    # buy_notional = eq_before = eq_0 = 1000.0
    assert np.isclose(res.loc[1, 'buy_notional'], 1000.0)
    assert np.isclose(res.loc[1, 'buy_cost'], 1000.0 * 0.001)
    assert np.isclose(res.loc[1, 'sell_notional'], 0.0)
    assert np.isclose(res.loc[1, 'sell_cost'], 0.0)
    assert np.isclose(res.loc[1, 'turnover'], 1000.0)
    assert np.isclose(res.loc[1, 'total_cost'], 1.0)
    
    # t=3 (Sell) 手工核对
    # sell_notional = eq_before = eq_2 = 1069.929
    assert np.isclose(res.loc[3, 'sell_notional'], 1069.929)
    assert np.isclose(res.loc[3, 'sell_cost'], 1069.929 * 0.002)
    assert np.isclose(res.loc[3, 'buy_cost'], 0.0)
    assert np.isclose(res.loc[3, 'total_cost'], 1069.929 * 0.002)
    
    # 累计成本核对
    sum_daily_cost = res['total_cost'].sum()
    expected_sum = (1000.0 * 0.001) + (1069.929 * 0.002)
    assert np.isclose(sum_daily_cost, expected_sum)
    
    # 无成交日成本为 0
    assert np.isclose(res.loc[0, 'total_cost'], 0.0)
    assert np.isclose(res.loc[2, 'total_cost'], 0.0)
    assert np.isclose(res.loc[4, 'total_cost'], 0.0)

