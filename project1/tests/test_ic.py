"""
Unit Tests for Section 22: IC and Rank IC Diagnostics
"""
import pytest
import pandas as pd
import numpy as np
from src.analysis.factor_diagnostics import FactorDiagnostics

def test_ic_and_rank_ic_perfect_linear():
    """测试完全线性相关下的 IC 与 Rank IC 必须等于 1.0"""
    # 4 assets, 2 dates
    dates = ['2024-01-01', '2024-01-02']
    assets = ['A', 'B', 'C', 'D']
    
    price_records = []
    factor_records = []
    
    for d_idx, d in enumerate(dates):
        for i, a in enumerate(assets):
            # Price starts at 10.0, next day return is proportional to (i + 1)
            ret = float(i + 1) * 0.01
            # T=0 price
            price_records.append({
                'date': d,
                'asset': a,
                'close_adj': 10.0 if d_idx == 0 else 10.0 * (1 + ret),
                'ret_total': 0.01
            })
            # Factor value at T=0 is exactly proportional to future return
            factor_records.append({
                'date': d,
                'asset': a,
                'factor': 'TEST_MOM',
                'raw_value': float(i + 1),
                'value': float(i + 1),
                'is_valid': True,
                'preprocessing_version': 'v1.0'
            })
            
    # Add a 3rd date so T=1 has forward return too
    for i, a in enumerate(assets):
        price_records.append({
            'date': '2024-01-03',
            'asset': a,
            'close_adj': 15.0,
            'ret_total': 0.01
        })
        
    price_df = pd.DataFrame(price_records)
    factor_df = pd.DataFrame(factor_records)
    
    diag = FactorDiagnostics(factor_df, price_df, forward_periods=[1])
    summary_df, timeseries_df = diag.calculate_ic()
    
    assert not summary_df.empty
    assert not timeseries_df.empty
    assert 'IC' in timeseries_df.columns
    assert 'Rank_IC' in timeseries_df.columns
    assert 'valid_assets' in timeseries_df.columns
    
    # In day 1 ('2024-01-01'), factor is [1, 2, 3, 4] and forward return is [0.01, 0.02, 0.03, 0.04]
    day1_ic = timeseries_df[timeseries_df['date'] == '2024-01-01']['IC'].iloc[0]
    day1_rank_ic = timeseries_df[timeseries_df['date'] == '2024-01-01']['Rank_IC'].iloc[0]
    
    assert np.isclose(day1_ic, 1.0)
    assert np.isclose(day1_rank_ic, 1.0)

def test_rank_ic_vs_pearson_ic_monotonic_nonlinear():
    """测试非线性单调时 Spearman Rank IC = 1.0, 但 Pearson IC < 1.0"""
    # y = exp(x)
    dates = ['2024-01-01', '2024-01-02']
    assets = ['A', 'B', 'C', 'D']
    
    price_records = []
    factor_records = []
    
    # T=0 price = 100.0, T=1 price = 100 * (1 + [0.01, 0.02, 0.09, 0.50])
    # x = [1, 2, 3, 4]
    returns = [0.01, 0.02, 0.09, 0.50]
    
    for i, a in enumerate(assets):
        price_records.append({'date': '2024-01-01', 'asset': a, 'close_adj': 100.0, 'ret_total': 0.0})
        price_records.append({'date': '2024-01-02', 'asset': a, 'close_adj': 100.0 * (1.0 + returns[i]), 'ret_total': returns[i]})
        factor_records.append({
            'date': '2024-01-01',
            'asset': a,
            'factor': 'TEST_EXP',
            'raw_value': float(i + 1),
            'value': float(i + 1),
            'is_valid': True,
            'preprocessing_version': 'v1.0'
        })
        
    price_df = pd.DataFrame(price_records)
    factor_df = pd.DataFrame(factor_records)
    
    diag = FactorDiagnostics(factor_df, price_df, forward_periods=[1])
    summary_df, timeseries_df = diag.calculate_ic()
    
    day1_ic = timeseries_df['IC'].iloc[0]
    day1_rank_ic = timeseries_df['Rank_IC'].iloc[0]
    
    # Rank IC should be strictly 1.0
    assert np.isclose(day1_rank_ic, 1.0)
    # Pearson IC should be strictly less than 1.0 due to nonlinearity
    assert day1_ic < 0.99
    assert day1_ic > 0.0

def test_ic_invalid_assets_handling():
    """测试当有效资产少于2个时自动跳过避免报错"""
    price_df = pd.DataFrame([
        {'date': '2024-01-01', 'asset': 'A', 'close_adj': 10.0, 'ret_total': 0.0},
        {'date': '2024-01-02', 'asset': 'A', 'close_adj': 11.0, 'ret_total': 0.1}
    ])
    factor_df = pd.DataFrame([
        {'date': '2024-01-01', 'asset': 'A', 'factor': 'TEST_SOLO', 'raw_value': 1.0, 'value': 1.0, 'is_valid': True, 'preprocessing_version': 'v1.0'}
    ])
    diag = FactorDiagnostics(factor_df, price_df, forward_periods=[1])
    summary_df, timeseries_df = diag.calculate_ic()
    
    # Single asset cannot compute cross-sectional correlation
    assert timeseries_df.empty or np.isnan(timeseries_df['IC'].iloc[0])

