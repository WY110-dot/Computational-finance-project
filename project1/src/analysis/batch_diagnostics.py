"""
Batch Diagnostics Module (Section 34)
自动连接 FactorRegistry 与 FactorDiagnostics，实现新增因子自动进行全要素诊断批处理。
"""
import pandas as pd
from typing import Dict, Any, List, Optional
from src.factors.registry import FactorRegistry
from src.analysis.factor_diagnostics import FactorDiagnostics

class BatchFactorDiagnostics:
    """
    全自动因子批处理诊断套件
    """
    
    def __init__(self, prices_df: pd.DataFrame, forward_periods: List[int] = [1, 5]):
        self.prices_df = prices_df.copy()
        self.forward_periods = forward_periods

    def run_all_diagnostics(self, factor_names: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        """
        一键执行：因子计算 -> IC/Rank IC 时序与汇总 -> 分组收益 -> 因子分布
        """
        # 1. 批量因子计算
        long_factors_df = FactorRegistry.calculate_all(self.prices_df, factor_names=factor_names)
        
        # 2. 执行诊断
        diag = FactorDiagnostics(long_factors_df, self.prices_df, forward_periods=self.forward_periods)
        ic_summary, ic_timeseries = diag.calculate_ic()
        group_returns = diag.calculate_group_returns(num_groups=5)
        
        # 3. 因子分布统计
        dist_records = []
        for f_name, group in long_factors_df[long_factors_df['is_valid']].groupby('factor'):
            s = group['value']
            dist_records.append({
                'factor': f_name,
                'count': int(s.count()),
                'mean': s.mean(),
                'std': s.std(),
                'min': s.min(),
                '25%': s.quantile(0.25),
                '50%': s.median(),
                '75%': s.quantile(0.75),
                'max': s.max(),
                'skew': s.skew()
            })
        dist_df = pd.DataFrame(dist_records)
        
        return {
            'factors_long': long_factors_df,
            'ic_summary': ic_summary,
            'ic_timeseries': ic_timeseries,
            'group_returns': group_returns,
            'distribution': dist_df
        }

