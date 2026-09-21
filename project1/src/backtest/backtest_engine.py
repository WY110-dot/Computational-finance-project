"""
Backtest Engine Module
回测引擎：计算策略净值、收益和交易成本
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple


class BacktestEngine:
    """
    回测引擎
    模拟历史交易，计算策略表现
    """
    
    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_rate: float = 0.0003
    ):
        """
        初始化回测引擎
        
        Args:
            initial_capital (float): 初始资金，默认 100万
            commission_rate (float): 交易佣金率（单边），默认 0.03%
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        
        print(f"\n[回测引擎] 初始化")
        print(f"  初始资金: {initial_capital:,.0f} RMB")
        print(f"  交易成本: {commission_rate*100:.3f}% (单边)")
        print(f"  实际成本: {commission_rate*2*100:.3f}% (买入+卖出)")
    
    def calculate_returns(
        self,
        df: pd.DataFrame,
        price_col: str = 'close'
    ) -> pd.DataFrame:
        """
        计算每日收益率 (集成 ReturnsCalculator)
        
        Args:
            df (pd.DataFrame): 包含价格数据的DataFrame
            price_col (str): 价格列名
            
        Returns:
            pd.DataFrame: 添加了收益率列的DataFrame
        """
        print("\n[计算收益] 计算每日收益率...")
        
        from src.metrics.returns import ReturnsCalculator
        
        # 计算市场/基准收益率（不考虑持仓）
        df = ReturnsCalculator.calculate_benchmark_returns(df, price_col=price_col)
        df['market_return'] = df['benchmark_return']  # 保持向后兼容
        
        print(f"  市场收益率计算完成")
        print(f"  平均日收益率: {df['market_return'].mean()*100:.4f}%")
        print(f"  收益率标准差: {df['market_return'].std()*100:.4f}%")
        
        return df
    
    def calculate_strategy_returns(
        self,
        df: pd.DataFrame,
        price_col: str = 'close'
    ) -> pd.DataFrame:
        """
        计算策略收益（考虑持仓和交易成本）
        
        Args:
            df (pd.DataFrame): 包含position和market_return的DataFrame
            price_col (str): 价格列名
            
        Returns:
            pd.DataFrame: 添加了策略收益列的DataFrame
        """
        print("\n[策略收益] 计算策略收益（含交易成本）...")
        
        from src.metrics.returns import ReturnsCalculator
        
        # 严格通过 ReturnsCalculator 计算策略毛收益，避免前视偏差
        df = ReturnsCalculator.calculate_strategy_returns(df, price_col=price_col)
        # 保持向后兼容：如果以前依赖 strategy_return_gross，ReturnsCalculator 已经生成了

        # 计算交易动作
        if 'trade' not in df.columns:
            df['position_change'] = df['position'].diff().fillna(0.0)
            df['trade'] = 0
            df.loc[df['position_change'] == 1, 'trade'] = 1   # 买入
            df.loc[df['position_change'] == -1, 'trade'] = -1  # 卖出

        from src.metrics.costs import CostCalculator
        # 计算扣减真实成本费率后的净收益率
        df = CostCalculator.calculate_costs_and_net_returns(
            df,
            buy_fee_rate=self.commission_rate,
            sell_fee_rate=self.commission_rate
        )
        
        # 向后兼容旧字段 (用于之前可能的画图逻辑)
        df['transaction_cost'] = df['strategy_return_gross'] - df['strategy_return']
        
        # 统计
        total_trades = (df['trade'] != 0).sum()
        total_cost_rate_equivalent = df['transaction_cost'].sum()
        avg_return = df['strategy_return'].mean()
        
        print(f"  总交易次数: {total_trades}")
        print(f"  总等效成本率(非金额): {total_cost_rate_equivalent*100:.4f}%")
        print(f"  平均日净收益: {avg_return*100:.4f}%")
        
        return df
    
    def calculate_equity_curve(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        计算净值曲线
        
        Args:
            df (pd.DataFrame): 包含收益率的DataFrame
            
        Returns:
            pd.DataFrame: 添加了净值列的DataFrame
        """
        print("\n[净值曲线] 计算策略和基准净值...")
        
        # 策略净值曲线 (此时 strategy_return 已严格包含手续费摩擦扣减)
        df['strategy_equity'] = self.initial_capital * (1 + df['strategy_return']).cumprod()
        
        # Buy & Hold 基准净值曲线
        df['benchmark_equity'] = self.initial_capital * (1 + df['market_return']).cumprod()
        
        from src.metrics.costs import CostCalculator
        # 补全 Phase C3 要求的绝对金额和名义本金统计
        df = CostCalculator.compute_daily_cost_metrics(
            df, 
            initial_capital=self.initial_capital,
            buy_fee_rate=self.commission_rate,
            sell_fee_rate=self.commission_rate
        )
        
        # 统计
        final_strategy = df['strategy_equity'].iloc[-1]
        final_benchmark = df['benchmark_equity'].iloc[-1]
        
        strategy_return = (final_strategy / self.initial_capital - 1) * 100
        benchmark_return = (final_benchmark / self.initial_capital - 1) * 100
        
        print(f"  策略最终净值: {final_strategy:,.2f} RMB")
        print(f"  基准最终净值: {final_benchmark:,.2f} RMB")
        print(f"  策略总收益: {strategy_return:.2f}%")
        print(f"  基准总收益: {benchmark_return:.2f}%")
        print(f"  超额收益: {strategy_return - benchmark_return:.2f}%")
        
        return df
    
    def run_backtest(
        self,
        df: pd.DataFrame,
        price_col: str = 'close'
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        运行完整回测
        
        Args:
            df (pd.DataFrame): 包含策略数据的DataFrame
            price_col (str): 价格列名
            
        Returns:
            Tuple[pd.DataFrame, Dict]: (回测结果DataFrame, 统计指标字典)
        """
        print("\n" + "="*60)
        print("开始回测")
        print("="*60)
        
        # 确保数据按日期排序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 1. 计算收益率
        df = self.calculate_returns(df, price_col=price_col)
        
        # 2 & 3. 运行完整的逐日账户账本模拟 (Phase C4)
        from src.backtest.ledger import AccountLedger
        ledger = AccountLedger(
            initial_capital=self.initial_capital,
            buy_fee_rate=self.commission_rate,
            sell_fee_rate=self.commission_rate
        )
        print("\n[账本模拟] 开始逐日推演资金曲线与持仓 (Phase C4)...")
        df = ledger.run_ledger_simulation(df, price_col=price_col, position_col='position')
        
        # 补全 benchmark 曲线
        print("\n[净值曲线] 计算基准净值...")
        df['benchmark_equity'] = self.initial_capital * (1 + df['market_return']).cumprod()
        
        # 4. 生成统计指标
        stats = self.calculate_statistics(df)
        
        print("\n" + "="*60)
        print("回测完成")
        print("="*60)
        
        return df, stats
    
    def calculate_statistics(self, df: pd.DataFrame) -> Dict:
        """
        计算回测统计指标
        
        Args:
            df (pd.DataFrame): 回测结果DataFrame
            
        Returns:
            Dict: 统计指标字典
        """
        stats = {}
        
        # 基本信息
        stats['initial_capital'] = self.initial_capital
        stats['commission_rate'] = self.commission_rate
        stats['trading_days'] = len(df)
        
        # 策略指标
        stats['final_equity_strategy'] = df['strategy_equity'].iloc[-1]
        stats['total_return_strategy'] = (df['strategy_equity'].iloc[-1] / self.initial_capital - 1) * 100
        
        # 基准指标
        stats['final_equity_benchmark'] = df['benchmark_equity'].iloc[-1]
        stats['total_return_benchmark'] = (df['benchmark_equity'].iloc[-1] / self.initial_capital - 1) * 100
        
        # 超额收益
        stats['excess_return'] = stats['total_return_strategy'] - stats['total_return_benchmark']
        
        # 交易统计
        stats['total_trades'] = (df['trade'] != 0).sum()
        stats['buy_trades'] = (df['trade'] == 1).sum()
        stats['sell_trades'] = (df['trade'] == -1).sum()
        
        # 成本统计
        stats['total_cost_amount'] = df['total_cost'].sum()
        stats['buy_cost_amount'] = df['buy_cost'].sum()
        stats['sell_cost_amount'] = df['sell_cost'].sum()
        stats['total_turnover'] = df['turnover'].sum()
        
        # 持仓统计
        stats['hold_days'] = (df['position'] == 1).sum()
        stats['empty_days'] = (df['position'] == 0).sum()
        stats['hold_pct'] = stats['hold_days'] / stats['trading_days'] * 100
        
        return stats
    
    def print_summary(self, stats: Dict):
        """
        打印回测摘要
        
        Args:
            stats (Dict): 统计指标字典
        """
        print("\n" + "="*60)
        print("回测统计摘要")
        print("="*60)
        
        print(f"\n基本信息:")
        print(f"  初始资金: {stats['initial_capital']:,.0f} RMB")
        print(f"  交易天数: {stats['trading_days']}")
        print(f"  交易成本费率: {stats['commission_rate']*100:.3f}% (单边)")
        
        print(f"\n策略表现:")
        print(f"  最终净值: {stats['final_equity_strategy']:,.2f} RMB")
        print(f"  总收益率: {stats['total_return_strategy']:.2f}%")
        
        print(f"\nBuy & Hold 基准:")
        print(f"  最终净值: {stats['final_equity_benchmark']:,.2f} RMB")
        print(f"  总收益率: {stats['total_return_benchmark']:.2f}%")
        
        print(f"\n对比:")
        print(f"  超额收益: {stats['excess_return']:.2f}%")
        if stats['excess_return'] > 0:
            print(f"  结论: 策略跑赢 Buy & Hold")
        else:
            print(f"  结论: 策略跑输 Buy & Hold")
        
        print(f"\n交易与成本统计:")
        print(f"  总交易次数: {stats['total_trades']} (买入: {stats['buy_trades']}, 卖出: {stats['sell_trades']})")
        print(f"  总成交额 (Turnover): {stats['total_turnover']:,.2f} RMB")
        print(f"  总交易成本金额: {stats['total_cost_amount']:,.2f} RMB")
        print(f"    - 买入成本: {stats['buy_cost_amount']:,.2f} RMB")
        print(f"    - 卖出成本: {stats['sell_cost_amount']:,.2f} RMB")
        
        print(f"\n持仓统计:")
        print(f"  持仓天数: {stats['hold_days']} ({stats['hold_pct']:.1f}%)")
        print(f"  空仓天数: {stats['empty_days']} ({100-stats['hold_pct']:.1f}%)")
        
        print("="*60 + "\n")


def main():
    """测试回测引擎"""
    print("\n" + "="*60)
    print("回测引擎测试")
    print("="*60)
    
    # 创建简单测试数据
    test_data = pd.DataFrame({
        'trade_date': [f'2024010{i}' for i in range(1, 6)],
        'close': [100, 102, 101, 103, 105],
        'position': [0, 1, 1, 1, 0],
        'trade': [0, 1, 0, 0, -1]
    })
    
    print("\n测试数据:")
    print(test_data)
    
    # 运行回测
    engine = BacktestEngine(initial_capital=1000000, commission_rate=0.0003)
    result_df, stats = engine.run_backtest(test_data)
    
    print("\n回测结果:")
    print(result_df[['trade_date', 'close', 'position', 'market_return', 
                     'strategy_return', 'strategy_equity', 'benchmark_equity']])
    
    engine.print_summary(stats)
    
    print("="*60)
    print("[OK] 测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
