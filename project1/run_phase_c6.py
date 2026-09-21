import os
import sys
import pandas as pd
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.backtest.backtest_engine import BacktestEngine
from src.strategy.signal_generator import SignalGenerator
from src.metrics.performance_metrics import PerformanceMetrics

def run_c6():
    print("="*60)
    print("Phase C6: Regenerate Official Baseline (After Correctness Fixes)")
    print("="*60)
    
    # 1. 载入 C1 处理好的复权数据
    data_path = 'data/processed/510050_SH_adjusted.csv'
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found. Please run run_phase_c1.py first.")
        return
        
    print(f"1. Loading verified data from {data_path}...")
    data = pd.read_csv(data_path)
    data['trade_date'] = pd.to_datetime(data['trade_date'].astype(str))
    data = data.sort_values('trade_date').reset_index(drop=True)
    
    # 2. 信号生成 (MA 双均线作为 baseline)
    print("2. Generating MA Cross Signals (Fast=5, Slow=20)...")
    sg = SignalGenerator()
    data['ma5'] = data['close_adj'].rolling(window=5, min_periods=1).mean()
    data['ma20'] = data['close_adj'].rolling(window=20, min_periods=1).mean()
    data = sg.generate_ma_cross_signal(data, fast_ma='ma5', slow_ma='ma20')
    data = sg.generate_position(data)
    
    # 3. 运行含分类账和手续费扣减的正确回测引擎
    print("3. Running BacktestEngine (Ledger, Exact Cost, No Look-ahead)...")
    engine = BacktestEngine(initial_capital=1000000.0, commission_rate=0.0003)
    result, stats = engine.run_backtest(data, price_col='close_adj')
    
    # 4. 计算官方 Metrics
    print("4. Calculating Official Performance Metrics...")
    pm = PerformanceMetrics()
    
    # 需要基于 strategy_return_net 来算，或者直接基于 equity 曲线反推
    returns = result['strategy_return'].fillna(0.0)
    ann_ret = pm.calculate_annualized_return(stats['total_return_strategy'], stats['trading_days'])
    vol = pm.calculate_volatility(returns)
    sharpe = pm.calculate_sharpe_ratio(returns)
    max_dd, dd_series = pm.calculate_max_drawdown(result['strategy_equity'])
    
    print("\n[Official Metrics]")
    print(f"  Annualized Return: {ann_ret:.2f}%")
    print(f"  Volatility:        {vol:.2f}%")
    print(f"  Sharpe Ratio:      {sharpe:.4f}")
    print(f"  Max Drawdown:      {max_dd:.2f}%\n")
    
    # 5. 保存图表
    print("5. Generating and Saving Plots...")
    os.makedirs('outputs/figures', exist_ok=True)
    
    plt.figure(figsize=(12, 6))
    plt.plot(result['trade_date'], result['strategy_equity'], label='Strategy (MA 5/20)', color='red')
    plt.plot(result['trade_date'], result['benchmark_equity'], label='Benchmark (B&H)', color='blue')
    plt.title('Official Strategy vs Benchmark Equity Curve (Post-Correction)')
    plt.xlabel('Date')
    plt.ylabel('Equity (RMB)')
    plt.legend()
    plt.grid(True)
    
    plot_path = 'outputs/figures/official_equity_curve_post_correction.png'
    plt.savefig(plot_path)
    print(f"  Saved plot to {plot_path}")
    
    # 6. 保存数据
    os.makedirs('outputs/tables', exist_ok=True)
    csv_path = 'outputs/tables/official_backtest_ledger_post_correction.csv'
    result.to_csv(csv_path, index=False)
    print(f"  Saved ledger data to {csv_path}")
    
    print("\nPhase C6 验证完成！")
    print("="*60)

if __name__ == "__main__":
    run_c6()

