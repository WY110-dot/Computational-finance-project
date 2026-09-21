import pytest
import pandas as pd
import numpy as np
import os
import sys

# 添加 src 到路径，使得能够导入模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.metrics.returns import ReturnsCalculator

def test_forward_returns_no_future_leak():
    """测试前向收益仅用作标签，不能用于当前t日的决策"""
    df = pd.DataFrame({
        'close_adj': [100, 102, 101, 105, 110]
    })
    
    res = ReturnsCalculator.calculate_forward_returns(df, periods=1)
    
    # ret_forward_1 at t=0 should be close_1/close_0 - 1 = 102/100 - 1 = 0.02
    assert np.isclose(res.loc[0, 'ret_forward_1'], 0.02)
    # ret_forward_1 at t=3 should be 110/105 - 1 = 0.047619
    assert np.isclose(res.loc[3, 'ret_forward_1'], 110/105 - 1)
    # last day should be NaN since no future data
    assert np.isnan(res.loc[4, 'ret_forward_1'])

def test_strategy_returns_no_lookahead_bias():
    """验证策略收益严格延迟信号，消除前视偏差"""
    # 模拟数据
    df = pd.DataFrame({
        'close_adj': [10, 10, 11, 11, 12],
        'signal':    [1,  0,  0,  1,  1]
    })
    
    # 手动推导：
    # t=0: close=10, signal=1 -> position(1)=1
    # t=1: close=10, signal=0 -> ret_total = 0, position(1)=1 -> return_gross=0. position(2)=0
    # t=2: close=11, signal=0 -> ret_total = 0.1, position(2)=0 -> return_gross=0. position(3)=0
    # t=3: close=11, signal=1 -> ret_total = 0, position(3)=0 -> return_gross=0. position(4)=1
    # t=4: close=12, signal=1 -> ret_total = 12/11-1, position(4)=1 -> return_gross=12/11-1
    
    res = ReturnsCalculator.calculate_strategy_returns(df, signal_col='signal')
    
    assert 'position' in res.columns
    # 检查 position 是否是 signal.shift(1)
    assert res.loc[0, 'position'] == 0.0
    assert res.loc[1, 'position'] == 1.0
    assert res.loc[2, 'position'] == 0.0
    assert res.loc[3, 'position'] == 0.0
    assert res.loc[4, 'position'] == 1.0
    
    # 检查 strategy return gross
    assert np.isclose(res.loc[0, 'strategy_return_gross'], 0.0)
    assert np.isclose(res.loc[1, 'strategy_return_gross'], 0.0)
    assert np.isclose(res.loc[2, 'strategy_return_gross'], 0.0)
    assert np.isclose(res.loc[3, 'strategy_return_gross'], 0.0)
    assert np.isclose(res.loc[4, 'strategy_return_gross'], 12/11 - 1)

def test_benchmark_returns():
    """测试独立复算基准收益"""
    df = pd.DataFrame({
        'close_adj': [100, 105, 100]
    })
    res = ReturnsCalculator.calculate_benchmark_returns(df)
    assert np.isclose(res.loc[0, 'benchmark_return'], 0.0)
    assert np.isclose(res.loc[1, 'benchmark_return'], 0.05)
    assert np.isclose(res.loc[2, 'benchmark_return'], 100/105 - 1)

def test_future_data_does_not_change_historical_signal():
    """验证追加未来数据不会改变历史 signal"""
    from src.strategy.signal_generator import SignalGenerator
    
    # 历史数据
    df_hist = pd.DataFrame({'close': [10, 11, 10, 12]})
    df_hist['ma5'] = df_hist['close'].rolling(2, min_periods=1).mean()
    df_hist['ma20'] = df_hist['close'].rolling(4, min_periods=1).mean()
    
    sg = SignalGenerator()
    res_hist = sg.generate_ma_cross_signal(df_hist.copy(), 'ma5', 'ma20')
    
    # 追加未来数据
    df_future = pd.DataFrame({'close': [10, 11, 10, 12, 13]})
    df_future['ma5'] = df_future['close'].rolling(2, min_periods=1).mean()
    df_future['ma20'] = df_future['close'].rolling(4, min_periods=1).mean()
    
    res_future = sg.generate_ma_cross_signal(df_future.copy(), 'ma5', 'ma20')
    
    # 对比前4天（即历史区间）信号必须一致
    pd.testing.assert_series_equal(res_hist['signal'], res_future['signal'].iloc[:4])
