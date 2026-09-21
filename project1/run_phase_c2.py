import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.backtest.backtest_engine import BacktestEngine
from src.strategy.signal_generator import SignalGenerator
from src.metrics.returns import ReturnsCalculator

def run_c2():
    print("="*60)
    print("Phase C2: Returns Calculation Validation")
    print("="*60)
    
    # 模拟从 C1 得到的数据（包含 close_adj）
    data = pd.DataFrame({
        'trade_date': pd.date_range(start='2024-01-01', periods=10, freq='B'),
        'close_adj': [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0]
    })
    
    print("\n1. 模拟行情数据:")
    print(data.head())
    
    # 使用 SignalGenerator 产生信号
    data['ma5'] = data['close_adj'].rolling(window=2, min_periods=1).mean()
    data['ma20'] = data['close_adj'].rolling(window=5, min_periods=1).mean()
    
    sg = SignalGenerator()
    data = sg.generate_ma_cross_signal(data, fast_ma='ma5', slow_ma='ma20')
    
    print("\n2. 生成交易信号 (Signal t):")
    print(data[['trade_date', 'close_adj', 'ma5', 'ma20', 'signal']].head())
    
    # 使用 ReturnsCalculator 生成因子收益 (不参与回测，仅用于IC等)
    print("\n3. 计算 Forward Return (Factor return):")
    factor_df = ReturnsCalculator.calculate_forward_returns(data.copy(), periods=1)
    print(factor_df[['trade_date', 'close_adj', 'signal', 'ret_forward_1']].head())
    
    # 使用 BacktestEngine 测试完整的收益逻辑
    print("\n4. 运行 BacktestEngine (内部集成了 ReturnsCalculator):")
    engine = BacktestEngine(initial_capital=1000000, commission_rate=0.0003)
    
    # 根据最新的引擎，计算过程严格执行: Signal(t) -> Position(t+1)
    # 我们在传入 engine 之前不需要提前生成 position，因为 ReturnsCalculator 会处理
    # 但为了兼容可能需要 signal_col
    # wait: ReturnsCalculator需要根据 signal 生成 position。如果 df 里没有 position。
    # 让我们直接通过 backtest_engine 跑
    
    # BacktestEngine 期望有个 position。我们在传入前必须生成 position，
    # 否则 ReturnsCalculator(如果没position有signal)也可以生成。
    # 为了保险，我们保留 SignalGenerator 生成 position
    data = sg.generate_position(data)
    
    result, stats = engine.run_backtest(data, price_col='close_adj')
    
    print("\n5. 回测核心收益数据结果:")
    print(result[['trade_date', 'close_adj', 'signal', 'position', 'ret_total', 'strategy_return_gross', 'strategy_return', 'benchmark_return']].head(8))
    
    print("\nPhase C2 验证完成！")
    print("="*60)

if __name__ == "__main__":
    run_c2()

