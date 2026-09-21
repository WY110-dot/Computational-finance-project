"""
Target Portfolio Generator (Phase P1, Section 25)
负责根据因子得分、调仓周期与持仓上限，生成严格无前视偏差的目标资产权重。
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

class TargetPortfolioGenerator:
    """
    目标组合生成器：
    实现 Top N 等权配置与调仓日识别。
    """
    
    def __init__(
        self,
        holding_count: int = 5,
        rebalance_frequency: str = "M",
        missing_policy: str = "hold"
    ):
        """
        Args:
            holding_count: 持仓数量 N，默认 5
            rebalance_frequency: 调仓频率 'M' (月度) 或 'W' (周度)
            missing_policy: 资产缺失或停牌策略，默认 'hold'
        """
        self.holding_count = holding_count
        self.rebalance_frequency = rebalance_frequency.upper()
        self.missing_policy = missing_policy

    def identify_rebalance_dates(self, dates: List[str]) -> List[str]:
        """
        识别所有调仓信号生成日 (按自然周期月末/周末对应的最后一个交易日)
        
        Args:
            dates: 升序排列的交易日列表 (YYYYMMDD 格式字符串)
            
        Returns:
            List[str]: 属于调仓信号生成日的日期列表
        """
        if not dates:
            return []
            
        dt_series = pd.to_datetime(pd.Series(dates, name='trade_date'))
        df_dates = pd.DataFrame({'date_str': dates, 'dt': dt_series})
        
        if self.rebalance_frequency == 'M':
            # 按年-月分组，取每组最后一个交易日
            df_dates['period'] = df_dates['dt'].dt.to_period('M')
        elif self.rebalance_frequency == 'W':
            # 按年-周分组，取每组最后一个交易日
            df_dates['period'] = df_dates['dt'].dt.to_period('W')
        else:
            raise ValueError(f"Unsupported rebalance frequency: {self.rebalance_frequency}")
            
        # 每一个周期的最后一个交易日即为信号形成日
        rebal_dates = df_dates.groupby('period')['date_str'].last().tolist()
        return rebal_dates

    def generate_target_weights(
        self,
        factor_df: pd.DataFrame,
        factor_name: str = "MOM20",
        universe_dates: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        在调仓形成日筛选 Top N 标的并分配等权权重。
        严格防止前视偏差：
        在信号日 t 形成的权重，必须标记在 t 日；
        回测执行引擎在 t+1 日开盘/收盘以此目标权重调仓。
        
        Args:
            factor_df: 包含 ['date', 'asset', 'factor', 'value', 'is_valid'] 的长表
            factor_name: 使用的因子名称
            universe_dates: 完整交易日列表 (若为None则从 factor_df 提取)
            
        Returns:
            pd.DataFrame: 包含 ['signal_date', 'effective_date', 'asset', 'target_weight']
        """
        df_f = factor_df[factor_df['factor'] == factor_name].copy()
        df_f['date'] = df_f['date'].astype(str)
        
        if universe_dates is None:
            all_dates = sorted(df_f['date'].unique().tolist())
        else:
            all_dates = sorted([str(d) for d in universe_dates])
            
        rebal_signal_dates = set(self.identify_rebalance_dates(all_dates))
        
        # 建立日期映射：date_t -> date_{t+1} (生效日)
        next_date_map = {}
        for i in range(len(all_dates) - 1):
            next_date_map[all_dates[i]] = all_dates[i + 1]
            
        target_weight_records = []
        
        for sig_date in sorted(list(rebal_signal_dates)):
            if sig_date not in next_date_map:
                # 最后一个日期无法在历史期内执行调仓
                continue
            effective_date = next_date_map[sig_date]
            
            sub = df_f[df_f['date'] == sig_date]
            valid_sub = sub[sub['is_valid'] & sub['value'].notna()].copy()
            
            if valid_sub.empty:
                # 无可用资产，目标全现金 (无权重记录)
                continue
                
            # 按因子得分从高到低排序 (在 F1 中已统一处理为越高越好)
            ranked = valid_sub.sort_values('value', ascending=False)
            
            # 选择 Top N
            top_assets = ranked.head(self.holding_count)['asset'].tolist()
            k = len(top_assets)
            
            if k > 0:
                weight = 1.0 / float(k)
                for asset in top_assets:
                    target_weight_records.append({
                        'signal_date': sig_date,
                        'effective_date': effective_date,
                        'asset': asset,
                        'target_weight': weight
                    })
                    
        weights_df = pd.DataFrame(target_weight_records)
        return weights_df

