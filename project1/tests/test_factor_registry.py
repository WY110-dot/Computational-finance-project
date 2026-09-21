"""
Unit Test for Section 34: Factor Registry & Batch Diagnostics Extension
"""
import pytest
import pandas as pd
import numpy as np
from src.factors.base_factor import BaseFactor
from src.factors.registry import FactorRegistry
from src.analysis.batch_diagnostics import BatchFactorDiagnostics

def test_custom_factor_registration_and_batch_diagnostics():
    """测试动态注册自定义因子，自动进入批处理与IC/分组收益诊断而无需修改回测核心"""
    
    # 动态定义一个新因子: 3日反转因子
    @FactorRegistry.register(name="TEST_REV3", direction=1, description="3日反转扩展测试因子")
    class TestREV3Factor(BaseFactor):
        def __init__(self):
            super().__init__(name="TEST_REV3", direction=1)
        def calculate_raw(self, df: pd.DataFrame) -> pd.Series:
            return df.groupby('asset', group_keys=False).apply(
                lambda g: -(g['close_adj'] / g['close_adj'].shift(3) - 1.0)
            )
            
    # 验证注册成功
    registered_names = [f['name'] for f in FactorRegistry.list_factors()]
    assert "TEST_REV3" in registered_names
    
    # 构造简易多资产数据 (10只标的)
    dates = [f"202401{i:02d}" for i in range(1, 15)]
    assets = [f'ETF{i}' for i in range(1, 11)]
    records = []
    for d_idx, d in enumerate(dates):
        for a_idx, a in enumerate(assets):
            records.append({
                'date': d,
                'asset': a,
                'close_adj': 10.0 + (a_idx + 1) * 0.5 + d_idx * 0.1,
                'ret_total': 0.005 * (a_idx + 1)
            })
    df_prices = pd.DataFrame(records)
    
    # 运行批量诊断套件
    suite = BatchFactorDiagnostics(df_prices, forward_periods=[1])
    res = suite.run_all_diagnostics(factor_names=["TEST_REV3"])
    
    assert not res['factors_long'].empty
    assert "TEST_REV3" in res['factors_long']['factor'].unique()
    assert 'distribution' in res
    assert 'ic_summary' in res
