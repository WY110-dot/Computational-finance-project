import pandas as pd
import numpy as np

class FactorDiagnostics:
    """
    因子诊断模块 (Phase A1)
    """
    
    def __init__(self, factor_df: pd.DataFrame, price_df: pd.DataFrame, forward_periods: list = [1, 5]):
        """
        Args:
            factor_df: Long table containing factors (date, asset, factor, value, is_valid)
            price_df: Long table containing prices (date, asset, close_adj, ret_total)
            forward_periods: List of horizons (e.g. 1 day, 5 days) to calculate forward return
        """
        self.factor_df = factor_df[factor_df['is_valid']].copy()
        self.price_df = price_df.copy()
        self.forward_periods = forward_periods
        
        # Merge factor values with forward returns
        self.merged_df = self._prepare_data()
        
    def _prepare_data(self) -> pd.DataFrame:
        """
        Calculates forward returns and merges with factors
        """
        p_df = self.price_df.sort_values(['asset', 'date']).reset_index(drop=True)
        
        for h in self.forward_periods:
            col_name = f'ret_forward_{h}'
            # Shift(-h) brings future price to current date
            p_df[col_name] = p_df.groupby('asset')['close_adj'].transform(lambda x: x.shift(-h) / x - 1.0)
            
        # Merge on date and asset
        merged = pd.merge(self.factor_df, p_df[['date', 'asset'] + [f'ret_forward_{h}' for h in self.forward_periods]], 
                          on=['date', 'asset'], how='inner')
        return merged
        
    def calculate_ic(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        计算 IC 和 Rank IC (Section 22 要求)
        
        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - summary_df: 汇总统计 (mean_IC, std_IC, IC_IR, mean_Rank_IC, std_Rank_IC, Rank_IC_IR, coverage, mean_valid_assets)
                - timeseries_df: 时间序列明细 (date, factor, horizon, IC, Rank_IC, valid_assets)
        """
        results = []
        all_ts_results = []
        for factor_name, group in self.merged_df.groupby('factor'):
            for h in self.forward_periods:
                ret_col = f'ret_forward_{h}'
                
                # Drop NA
                valid_data = group.dropna(subset=['value', ret_col])
                if valid_data.empty:
                    continue
                    
                # Calculate daily IC
                def _calc_daily_ic(g):
                    if len(g) < 2:
                        return pd.Series({'IC': np.nan, 'Rank_IC': np.nan, 'valid_assets': float(len(g))})
                    
                    # Using pandas corr (Pearson and Spearman)
                    ic = g['value'].corr(g[ret_col], method='pearson')
                    rank_ic = g['value'].corr(g[ret_col], method='spearman')
                    return pd.Series({'IC': ic, 'Rank_IC': rank_ic, 'valid_assets': float(len(g))})
                    
                daily_ic = valid_data.groupby('date', group_keys=False).apply(_calc_daily_ic)
                daily_ic = daily_ic.dropna(subset=['IC', 'Rank_IC'])
                
                if daily_ic.empty:
                    continue
                
                daily_ts = daily_ic.reset_index()
                # If index was named date or index
                if 'date' not in daily_ts.columns and 'index' in daily_ts.columns:
                    daily_ts = daily_ts.rename(columns={'index': 'date'})
                daily_ts['factor'] = factor_name
                daily_ts['horizon'] = h
                all_ts_results.append(daily_ts[['date', 'factor', 'horizon', 'IC', 'Rank_IC', 'valid_assets']])
                    
                mean_ic = daily_ic['IC'].mean()
                std_ic = daily_ic['IC'].std()
                ic_ir = mean_ic / std_ic if std_ic != 0 and not np.isnan(std_ic) else np.nan
                
                mean_rank_ic = daily_ic['Rank_IC'].mean()
                std_rank_ic = daily_ic['Rank_IC'].std()
                rank_ic_ir = mean_rank_ic / std_rank_ic if std_rank_ic != 0 and not np.isnan(std_rank_ic) else np.nan
                
                coverage = len(valid_data) / (len(group['date'].unique()) * len(group['asset'].unique())) if len(group['asset'].unique()) > 0 else 0.0
                mean_valid_assets = daily_ic['valid_assets'].mean()
                
                results.append({
                    'factor': factor_name,
                    'horizon': h,
                    'mean_IC': mean_ic,
                    'std_IC': std_ic,
                    'IC_IR': ic_ir,
                    'mean_Rank_IC': mean_rank_ic,
                    'std_Rank_IC': std_rank_ic,
                    'Rank_IC_IR': rank_ic_ir,
                    'coverage': coverage,
                    'mean_valid_assets': mean_valid_assets
                })
                
        summary_df = pd.DataFrame(results)
        timeseries_df = pd.concat(all_ts_results, ignore_index=True) if all_ts_results else pd.DataFrame(
            columns=['date', 'factor', 'horizon', 'IC', 'Rank_IC', 'valid_assets']
        )
        return summary_df, timeseries_df

    def calculate_group_returns(self, num_groups: int = 5) -> pd.DataFrame:
        """
        分组收益 (Group Return & High-Low Spread).

        ``Group_i_original_count`` is the number of assets assigned to group i
        after formation-date grouping, regardless of future-return availability.
        ``Group_i_effective_count`` is the number of those assets with a valid
        return at the requested horizon and therefore included in the mean.
        """
        results = []
        for factor_name, group in self.merged_df.groupby('factor'):
            for h in self.forward_periods:
                ret_col = f'ret_forward_{h}'
                # 分组时绝不能丢弃缺失标签的数据，否则形成日分组不客观
                formation_data = group.dropna(subset=['value']).copy()
                if formation_data.empty:
                    continue
                    
                def _assign_group(g):
                    try:
                        return pd.qcut(g['value'], q=num_groups, labels=False, duplicates='drop') + 1
                    except:
                        return pd.Series(np.nan, index=g.index)
                        
                formation_data['group'] = formation_data.groupby('date', group_keys=False).apply(_assign_group)
                formation_data = formation_data.dropna(subset=['group'])
                
                # 分组完成后再匹配未来收益
                valid_data = formation_data.dropna(subset=[ret_col])
                if valid_data.empty:
                    continue
                    
                # Calculate mean return per group per date
                daily_group_ret = valid_data.groupby(['date', 'group'])[ret_col].mean().unstack()
                
                # Calculate original count and effective count
                original_counts = formation_data.groupby('group')['asset'].count()
                effective_counts = valid_data.groupby('group')['asset'].count()

                
                # Mean over time
                mean_group_ret = daily_group_ret.mean()
                
                # High - Low spread (Group K - Group 1)
                high_val = mean_group_ret.get(num_groups, np.nan)
                low_val = mean_group_ret.get(1, np.nan)
                spread = (high_val - low_val) if not np.isnan(high_val) and not np.isnan(low_val) else np.nan
                
                # Monotonicity check
                # A simple check: is G5 > G4 > G3 > G2 > G1 ?
                diffs = mean_group_ret.diff().dropna()
                monotonicity = "Strict" if (not diffs.empty and (diffs > 0).all()) else "Partial"
                
                row = {
                    'factor': factor_name,
                    'horizon': h,
                    'spread': spread,
                    'monotonicity': monotonicity
                }
                for i in range(1, num_groups + 1):
                    row[f'Group_{i}'] = mean_group_ret.get(i, np.nan)
                    row[f'Group_{i}_original_count'] = int(original_counts.get(i, 0))
                    row[f'Group_{i}_effective_count'] = int(effective_counts.get(i, 0))
                    
                results.append(row)
                
        return pd.DataFrame(results)
