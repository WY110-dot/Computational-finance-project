import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.backtest.backtest_engine import BacktestEngine
from src.strategy.signal_generator import SignalGenerator

def run_c4():
    print("="*60)
    print("Phase C4: Account Ledger Validation")
    print("="*60)
    
    # 模拟数据
    data = pd.DataFrame({
        'trade_date': pd.date_range(start='2024-01-01', periods=10, freq='B'),
        'close_adj': [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 107.0, 110.0]
    })
    
    sg = SignalGenerator()
    data['ma5'] = data['close_adj'].rolling(window=2, min_periods=1).mean()
    data['ma20'] = data['close_adj'].rolling(window=5, min_periods=1).mean()
    data = sg.generate_ma_cross_signal(data, fast_ma='ma5', slow_ma='ma20')
    data = sg.generate_position(data)
    
    # 运行 BacktestEngine (现已集成 AccountLedger)
    print("\n1. 运行 BacktestEngine (集成 AccountLedger):")
    engine = BacktestEngine(initial_capital=1000000, commission_rate=0.003)
    result, stats = engine.run_backtest(data, price_col='close_adj')
    
    print("\n2. 回测核心账本数据结果 (Phase C4 Requirements):")
    metrics_cols = [
        'trade_date', 'price', 'trade', 'cash', 'shares', 
        'holdings_value', 'equity_before_trade', 'buy_cost', 'sell_cost', 'equity_after_trade'
    ]
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(result[metrics_cols].head(10))
    
    # 恒等式验证
    print("\n3. 验证恒等式 (equity = cash + holdings_value):")
    identity_check = (result['cash'] + result['holdings_value'] - result['equity_after_trade']).abs() < 1e-5
    if identity_check.all():
        print("  [OK] 所有交易日的账户恒等式均严格成立！")
    else:
        print("  [ERROR] 存在恒等式不成立的记录！")
        
    engine.print_summary(stats)
    
    print("\nPhase C4 验证完成！")
    print("="*60)

if __name__ == "__main__":
    run_c4()

