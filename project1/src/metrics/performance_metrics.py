"""
Performance Metrics Module
绩效与风险指标计算模块
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
from datetime import datetime


class PerformanceMetrics:
    """
    绩效指标计算器
    计算策略的各项风险和收益指标
    """
    
    def __init__(self, risk_free_rate: float = 0.0):
        """
        初始化绩效指标计算器
        
        Args:
            risk_free_rate (float): 无风险利率（年化），默认0
        """
        self.risk_free_rate = risk_free_rate
        
        print(f"\n[绩效指标] 初始化")
        print(f"  无风险利率: {risk_free_rate*100:.2f}%")
    
    def calculate_total_return(
        self,
        initial_value: float,
        final_value: float
    ) -> float:
        """
        计算总收益率
        
        Args:
            initial_value: 初始资金
            final_value: 最终资金
            
        Returns:
            float: 总收益率（百分比）
        """
        return (final_value / initial_value - 1) * 100
    
    def calculate_annualized_return(
        self,
        total_return: float,
        days: int
    ) -> float:
        """
        计算年化收益率
        
        Args:
            total_return: 总收益率（小数形式，如0.1表示10%）
            days: 交易天数
            
        Returns:
            float: 年化收益率（百分比）
        """
        years = days / 252  # 假设每年252个交易日
        if years <= 0:
            return 0.0
        
        annualized = (1 + total_return / 100) ** (1 / years) - 1
        return annualized * 100
    
    def calculate_volatility(
        self,
        returns: pd.Series,
        annualize: bool = True
    ) -> float:
        """
        计算波动率
        
        Args:
            returns: 日收益率序列
            annualize: 是否年化
            
        Returns:
            float: 波动率（百分比）
        """
        vol = returns.std()
        
        if annualize:
            vol = vol * np.sqrt(252)  # 年化
        
        return vol * 100
    
    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: float = None
    ) -> float:
        """
        计算夏普比率
        
        Args:
            returns: 日收益率序列
            risk_free_rate: 无风险利率（年化），如果为None则使用初始化时的值
            
        Returns:
            float: 夏普比率
        """
        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate
        
        # 日无风险利率
        daily_rf = risk_free_rate / 252
        
        # 超额收益
        excess_returns = returns - daily_rf
        
        # 夏普比率
        if excess_returns.std() == 0:
            return 0.0
        
        sharpe = excess_returns.mean() / excess_returns.std()
        
        # 年化
        sharpe_annualized = sharpe * np.sqrt(252)
        
        return sharpe_annualized
    
    def calculate_max_drawdown(
        self,
        equity_curve: pd.Series
    ) -> Tuple[float, pd.Series]:
        """
        计算最大回撤
        
        Args:
            equity_curve: 净值曲线
            
        Returns:
            Tuple[float, pd.Series]: (最大回撤百分比, 回撤序列)
        """
        # 累计最高净值
        cummax = equity_curve.cummax()
        
        # 回撤
        drawdown = (equity_curve - cummax) / cummax * 100
        
        # 最大回撤
        max_dd = drawdown.min()
        
        return max_dd, drawdown
    
    def calculate_calmar_ratio(
        self,
        annualized_return: float,
        max_drawdown: float
    ) -> float:
        """
        计算卡玛比率
        
        Calmar Ratio = 年化收益率 / |最大回撤|
        
        Args:
            annualized_return: 年化收益率
            max_drawdown: 最大回撤（负数）
            
        Returns:
            float: 卡玛比率
        """
        if max_drawdown == 0:
            return 0.0
        
        return annualized_return / abs(max_drawdown)
    
    def calculate_win_rate(
        self,
        trades: pd.DataFrame
    ) -> Dict:
        """
        计算交易胜率
        
        Args:
            trades: 包含交易信息的DataFrame
            
        Returns:
            Dict: 胜率统计
        """
        # 这里需要交易对（买入-卖出）的盈亏
        # 简化处理：计算策略收益为正的天数占比
        
        stats = {
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'win_loss_ratio': 0.0
        }
        
        return stats
    
    def calculate_all_metrics(
        self,
        df: pd.DataFrame,
        initial_capital: float
    ) -> Dict:
        """
        计算所有绩效指标
        
        Args:
            df: 回测结果DataFrame
            initial_capital: 初始资金
            
        Returns:
            Dict: 所有指标
        """
        print("\n" + "="*60)
        print("计算绩效指标")
        print("="*60)
        
        metrics = {}
        
        # 基本信息
        metrics['trading_days'] = len(df)
        metrics['initial_capital'] = initial_capital
        
        # 策略指标
        print("\n[策略指标]")
        
        # 1. 总收益率
        final_equity_strategy = df['strategy_equity'].iloc[-1]
        metrics['final_equity_strategy'] = final_equity_strategy
        metrics['total_return_strategy'] = self.calculate_total_return(
            initial_capital, final_equity_strategy
        )
        print(f"  总收益率: {metrics['total_return_strategy']:.2f}%")
        
        # 2. 年化收益率
        metrics['annualized_return_strategy'] = self.calculate_annualized_return(
            metrics['total_return_strategy'],
            metrics['trading_days']
        )
        print(f"  年化收益率: {metrics['annualized_return_strategy']:.2f}%")
        
        # 3. 波动率
        metrics['volatility_strategy'] = self.calculate_volatility(
            df['strategy_return']
        )
        print(f"  年化波动率: {metrics['volatility_strategy']:.2f}%")
        
        # 4. 夏普比率
        metrics['sharpe_ratio_strategy'] = self.calculate_sharpe_ratio(
            df['strategy_return']
        )
        print(f"  夏普比率: {metrics['sharpe_ratio_strategy']:.4f}")
        
        # 5. 最大回撤
        max_dd_strategy, dd_series_strategy = self.calculate_max_drawdown(
            df['strategy_equity']
        )
        metrics['max_drawdown_strategy'] = max_dd_strategy
        metrics['drawdown_series_strategy'] = dd_series_strategy
        print(f"  最大回撤: {metrics['max_drawdown_strategy']:.2f}%")
        
        # 6. 卡玛比率
        metrics['calmar_ratio_strategy'] = self.calculate_calmar_ratio(
            metrics['annualized_return_strategy'],
            metrics['max_drawdown_strategy']
        )
        print(f"  卡玛比率: {metrics['calmar_ratio_strategy']:.4f}")
        
        # 基准指标
        print("\n[基准指标 (Buy & Hold)]")
        
        final_equity_benchmark = df['benchmark_equity'].iloc[-1]
        metrics['final_equity_benchmark'] = final_equity_benchmark
        metrics['total_return_benchmark'] = self.calculate_total_return(
            initial_capital, final_equity_benchmark
        )
        print(f"  总收益率: {metrics['total_return_benchmark']:.2f}%")
        
        metrics['annualized_return_benchmark'] = self.calculate_annualized_return(
            metrics['total_return_benchmark'],
            metrics['trading_days']
        )
        print(f"  年化收益率: {metrics['annualized_return_benchmark']:.2f}%")
        
        metrics['volatility_benchmark'] = self.calculate_volatility(
            df['market_return']
        )
        print(f"  年化波动率: {metrics['volatility_benchmark']:.2f}%")
        
        metrics['sharpe_ratio_benchmark'] = self.calculate_sharpe_ratio(
            df['market_return']
        )
        print(f"  夏普比率: {metrics['sharpe_ratio_benchmark']:.4f}")
        
        max_dd_benchmark, dd_series_benchmark = self.calculate_max_drawdown(
            df['benchmark_equity']
        )
        metrics['max_drawdown_benchmark'] = max_dd_benchmark
        metrics['drawdown_series_benchmark'] = dd_series_benchmark
        print(f"  最大回撤: {metrics['max_drawdown_benchmark']:.2f}%")
        
        metrics['calmar_ratio_benchmark'] = self.calculate_calmar_ratio(
            metrics['annualized_return_benchmark'],
            metrics['max_drawdown_benchmark']
        )
        print(f"  卡玛比率: {metrics['calmar_ratio_benchmark']:.4f}")
        
        # 对比
        print("\n[策略 vs 基准]")
        metrics['excess_return'] = metrics['total_return_strategy'] - metrics['total_return_benchmark']
        metrics['excess_annualized'] = metrics['annualized_return_strategy'] - metrics['annualized_return_benchmark']
        print(f"  超额收益: {metrics['excess_return']:.2f}%")
        print(f"  年化超额: {metrics['excess_annualized']:.2f}%")
        
        # 交易统计
        print("\n[交易统计]")
        metrics['total_trades'] = (df['trade'] != 0).sum()
        metrics['buy_trades'] = (df['trade'] == 1).sum()
        metrics['sell_trades'] = (df['trade'] == -1).sum()
        print(f"  总交易次数: {metrics['total_trades']}")
        print(f"  买入次数: {metrics['buy_trades']}")
        print(f"  卖出次数: {metrics['sell_trades']}")
        
        print("\n" + "="*60)
        
        return metrics
    
    def print_summary_table(self, metrics: Dict):
        """
        打印指标对比表
        
        Args:
            metrics: 指标字典
        """
        print("\n" + "="*70)
        print(" "*20 + "绩效指标对比表")
        print("="*70)
        
        print(f"\n{'指标':<30} {'策略':>15} {'基准':>15} {'差异':>10}")
        print("-"*70)
        
        # 收益指标
        print(f"{'总收益率 (%)':30} {metrics['total_return_strategy']:>15.2f} "
              f"{metrics['total_return_benchmark']:>15.2f} "
              f"{metrics['excess_return']:>10.2f}")
        
        print(f"{'年化收益率 (%)':30} {metrics['annualized_return_strategy']:>15.2f} "
              f"{metrics['annualized_return_benchmark']:>15.2f} "
              f"{metrics['excess_annualized']:>10.2f}")
        
        # 风险指标
        print(f"{'年化波动率 (%)':30} {metrics['volatility_strategy']:>15.2f} "
              f"{metrics['volatility_benchmark']:>15.2f} "
              f"{metrics['volatility_strategy']-metrics['volatility_benchmark']:>10.2f}")
        
        print(f"{'最大回撤 (%)':30} {metrics['max_drawdown_strategy']:>15.2f} "
              f"{metrics['max_drawdown_benchmark']:>15.2f} "
              f"{metrics['max_drawdown_strategy']-metrics['max_drawdown_benchmark']:>10.2f}")
        
        # 风险调整收益
        print(f"{'夏普比率':30} {metrics['sharpe_ratio_strategy']:>15.4f} "
              f"{metrics['sharpe_ratio_benchmark']:>15.4f} "
              f"{metrics['sharpe_ratio_strategy']-metrics['sharpe_ratio_benchmark']:>10.4f}")
        
        print(f"{'卡玛比率':30} {metrics['calmar_ratio_strategy']:>15.4f} "
              f"{metrics['calmar_ratio_benchmark']:>15.4f} "
              f"{metrics['calmar_ratio_strategy']-metrics['calmar_ratio_benchmark']:>10.4f}")
        
        # 其他
        print(f"{'交易次数':30} {metrics['total_trades']:>15} {'-':>15} {'-':>10}")
        
        print("="*70 + "\n")


def main():
    """测试绩效指标计算"""
    print("\n" + "="*60)
    print("绩效指标计算器测试")
    print("="*60)
    
    # 创建测试数据
    test_data = pd.DataFrame({
        'strategy_return': np.random.normal(0.001, 0.02, 100),
        'market_return': np.random.normal(0.0005, 0.015, 100),
    })
    
    test_data['strategy_equity'] = 1000000 * (1 + test_data['strategy_return']).cumprod()
    test_data['benchmark_equity'] = 1000000 * (1 + test_data['market_return']).cumprod()
    test_data['trade'] = 0
    
    # 计算指标
    calculator = PerformanceMetrics(risk_free_rate=0.03)
    metrics = calculator.calculate_all_metrics(test_data, 1000000)
    
    # 打印对比表
    calculator.print_summary_table(metrics)
    
    print("="*60)
    print("[OK] 测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
