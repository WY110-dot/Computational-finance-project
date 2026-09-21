"""
Portfolio Performance Metrics Module (Phase M1, Section 28)
负责计算多资产投资组合的收益、风险、交易摩擦及持仓行为指标，严格区分毛收益 (Gross) 与净收益 (Net)。
"""
import pandas as pd
import numpy as np
from typing import Dict, Any

class PortfolioPerformanceMetrics:
    """
    组合绩效评估器
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Args:
            risk_free_rate: 年化无风险利率，默认 2% (0.02)
        """
        self.risk_free_rate = risk_free_rate
        self.daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0

    def calculate_metrics(self, daily_ledger: pd.DataFrame) -> Dict[str, Any]:
        """
        根据逐日账本计算全套绩效指标。
        
        Args:
            daily_ledger: DataFrame 包含 ['daily_return', 'daily_return_gross', 'equity', 
                          'turnover', 'daily_cost', 'trade_count', 'holding_count', 
                          'max_single_asset_weight', 'benchmark_equity']
        """
        df = daily_ledger.copy()
        n_days = len(df)
        if n_days == 0:
            return {}
            
        initial_equity = df['equity'].iloc[0] / (1.0 + df['daily_return'].iloc[0]) if df['daily_return'].iloc[0] != -1 else 1000000.0
        final_equity = df['equity'].iloc[-1]
        
        # 1. 收益指标 (Net vs Gross)
        net_cum_return = (final_equity / initial_equity) - 1.0
        ann_factor = 252.0 / float(n_days)
        net_ann_return = (1.0 + net_cum_return) ** ann_factor - 1.0
        
        # Gross Return
        gross_returns = df['daily_return_gross'].fillna(0.0)
        gross_cum_return = np.prod(1.0 + gross_returns) - 1.0
        gross_ann_return = (1.0 + gross_cum_return) ** ann_factor - 1.0
        
        # Benchmark Return
        bench_initial = df['benchmark_equity'].iloc[0]
        bench_final = df['benchmark_equity'].iloc[-1]
        bench_cum_return = (bench_final / bench_initial) - 1.0
        bench_ann_return = (1.0 + bench_cum_return) ** ann_factor - 1.0
        
        # 2. 风险指标 (基于净收益)
        net_returns = df['daily_return'].fillna(0.0)
        ann_volatility = net_returns.std(ddof=1) * np.sqrt(252.0)
        
        excess_returns = net_returns - self.daily_rf
        excess_std = excess_returns.std(ddof=1)
        sharpe_ratio = (excess_returns.mean() / excess_std * np.sqrt(252.0)) if excess_std > 0 else 0.0
        
        # 最大回撤
        cummax = df['equity'].cummax()
        drawdown = (df['equity'] - cummax) / cummax
        max_drawdown = drawdown.min()
        
        # 3. 交易指标
        total_turnover = df['turnover'].sum()
        ann_turnover = (total_turnover / df['equity'].mean()) * ann_factor if df['equity'].mean() > 0 else 0.0
        total_cost = df['daily_cost'].sum()
        total_trades = int(df['trade_count'].sum())
        avg_holdings = df['holding_count'].mean()
        max_weight = df['max_single_asset_weight'].max()
        
        return {
            'Trading Days': n_days,
            'Net Cumulative Return (%)': net_cum_return * 100.0,
            'Net Annualized Return (%)': net_ann_return * 100.0,
            'Gross Cumulative Return (%)': gross_cum_return * 100.0,
            'Gross Annualized Return (%)': gross_ann_return * 100.0,
            'Benchmark Cumulative Return (%)': bench_cum_return * 100.0,
            'Benchmark Annualized Return (%)': bench_ann_return * 100.0,
            'Annualized Volatility (%)': ann_volatility * 100.0,
            'Sharpe Ratio': sharpe_ratio,
            'Maximum Drawdown (%)': max_drawdown * 100.0,
            'Total Turnover (RMB)': total_turnover,
            'Annualized Turnover (x)': ann_turnover,
            'Total Cost (RMB)': total_cost,
            'Total Trade Count': total_trades,
            'Average Holdings Count': avg_holdings,
            'Max Single Asset Weight (%)': max_weight * 100.0
        }

