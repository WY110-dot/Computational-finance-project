import pytest
import pandas as pd
import numpy as np
import os
import sys

# 添加 src 到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.metrics.performance_metrics import PerformanceMetrics

def test_annualized_return():
    pm = PerformanceMetrics()
    # 252 days, 10% total return
    ann_ret = pm.calculate_annualized_return(10.0, 252)
    assert np.isclose(ann_ret, 10.0)
    
    # 504 days (2 years), 21% total return -> (1.21^(1/2) - 1) = 10%
    ann_ret = pm.calculate_annualized_return(21.0, 504)
    assert np.isclose(ann_ret, 10.0)

def test_volatility():
    pm = PerformanceMetrics()
    returns = pd.Series([0.01, -0.01, 0.01, -0.01])
    # sample std of returns = 0.011547
    # annual vol = 0.011547 * sqrt(252) * 100
    expected_vol = returns.std() * np.sqrt(252) * 100
    vol = pm.calculate_volatility(returns)
    assert np.isclose(vol, expected_vol)

def test_sharpe_ratio():
    pm = PerformanceMetrics(risk_free_rate=0.0)
    returns = pd.Series([0.01, 0.02, -0.01, 0.01, 0.02])
    # mean = 0.01, std = 0.012247
    # daily_sharpe = 0.01 / 0.012247 = 0.816496
    # annual_sharpe = 0.816496 * sqrt(252) = 12.96
    mean_ret = returns.mean()
    std_ret = returns.std()
    expected_sharpe = (mean_ret / std_ret) * np.sqrt(252)
    
    sharpe = pm.calculate_sharpe_ratio(returns)
    assert np.isclose(sharpe, expected_sharpe)

def test_max_drawdown():
    pm = PerformanceMetrics()
    # equity curve: 100 -> 120 -> 90 -> 110 -> 80 -> 150
    equity = pd.Series([100, 120, 90, 110, 80, 150])
    # drawdowns:
    # t=0: max_so_far=100, dd=0
    # t=1: max=120, dd=0
    # t=2: max=120, dd=(120-90)/120 = 25%
    # t=3: max=120, dd=(120-110)/120 = 8.33%
    # t=4: max=120, dd=(120-80)/120 = 33.33%
    # t=5: max=150, dd=0
    # max_drawdown = -33.33%
    expected_mdd = -33.33333333333333
    
    mdd, _ = pm.calculate_max_drawdown(equity)
    assert np.isclose(mdd, expected_mdd)
