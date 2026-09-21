import pytest
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtest.backtest_engine import BacktestEngine
from src.strategy.signal_generator import SignalGenerator

def test_engine_reproducibility():
    """测试同一data、code、config重复运行，主要结果完全一致"""
    data = pd.DataFrame({
        'trade_date': pd.date_range(start='2024-01-01', periods=20, freq='B'),
        'close_adj': np.random.RandomState(42).lognormal(mean=0.001, sigma=0.02, size=20).cumprod() * 100
    })
    
    sg = SignalGenerator()
    data['ma5'] = data['close_adj'].rolling(window=2, min_periods=1).mean()
    data['ma20'] = data['close_adj'].rolling(window=5, min_periods=1).mean()
    data = sg.generate_ma_cross_signal(data, fast_ma='ma5', slow_ma='ma20')
    data = sg.generate_position(data)
    
    engine1 = BacktestEngine(initial_capital=1000000, commission_rate=0.001)
    res1, stats1 = engine1.run_backtest(data.copy(), price_col='close_adj')
    
    engine2 = BacktestEngine(initial_capital=1000000, commission_rate=0.001)
    res2, stats2 = engine2.run_backtest(data.copy(), price_col='close_adj')
    
    # 结果 DataFrame 完全一致
    pd.testing.assert_frame_equal(res1, res2)
    
    # 统计字典完全一致
    assert stats1.keys() == stats2.keys()
    for k in stats1:
        assert np.isclose(stats1[k], stats2[k]), f"Mismatch in stat {k}: {stats1[k]} != {stats2[k]}"

