import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.backtest.backtest_engine import BacktestEngine
from src.strategy.signal_generator import SignalGenerator
from src.metrics.returns import ReturnsCalculator

def run_c3():
    print("="*60)
    print("Phase C3: Costs Calculation Validation")
    print("="*60)
    
    # 模拟数据
    data = pd.DataFrame({
        'trade_date': pd.date_range(start='2024-01-01', periods=10, freq='B'),
        'close_adj': [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0]
    })
    
    # 使用 SignalGenerator 产生信号和仓位
    data['ma5'] = data['close_adj'].rolling(window=2, min_periods=1).mean()
    data['ma20'] = data['close_adj'].rolling(window=5, min_periods=1).mean()
    
    sg = SignalGenerator()
    data = sg.generate_ma_cross_signal(data, fast_ma='ma5', slow_ma='ma20')
    data = sg.generate_position(data)
    
    # 运行 BacktestEngine
    print("\n1. 运行 BacktestEngine (内部集成了 ReturnsCalculator 和 CostCalculator):")
    engine = BacktestEngine(initial_capital=1000000, commission_rate=0.003) # 故意设大费率观察成本
    result, stats = engine.run_backtest(data, price_col='close_adj')
    
    print("\n2. 回测核心成本数据结果 (Phase C3 Requirements):")
    # 按照 Phase C3 要求打印每日必须记录的指标
    metrics_cols = ['trade_date', 'trade', 'strategy_return', 'strategy_equity', 'buy_notional', 'sell_notional', 'buy_cost', 'sell_cost', 'total_cost', 'turnover']
    print(result[metrics_cols].head(8))
    
    engine.print_summary(stats)
    
    print("\nPhase C3 验证完成！")
    print("="*60)

if __name__ == "__main__":
    run_c3()

