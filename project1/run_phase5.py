"""
Phase 5 执行脚本
回测引擎：计算策略净值和收益
"""
import sys
from pathlib import Path
import pandas as pd

# 添加src目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from src.backtest.backtest_engine import BacktestEngine

print("\n" + "="*80)
print(" "*28 + "PHASE 5: 回测引擎")
print("="*80)

# 步骤1: 加载策略数据
print("\n[步骤 1/3] 加载策略数据...")
print("-"*80)

try:
    # 加载Phase 4生成的策略数据
    data_file = Path(__file__).parent / "data" / "processed" / "510050_strategy_data.csv"
    
    if not data_file.exists():
        print("[ERROR] 策略数据文件不存在，请先运行 Phase 4")
        sys.exit(1)
    
    df = pd.read_csv(data_file)
    print(f"[OK] 成功加载 {len(df)} 条记录")
    print(f"日期范围: {df['trade_date'].min()} - {df['trade_date'].max()}")
    
    # 检查必要的列
    required_cols = ['close', 'position', 'trade']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        print(f"[ERROR] 缺少必要列: {missing_cols}")
        sys.exit(1)
    
    print(f"[OK] 数据验证通过\n")
    
except Exception as e:
    print(f"[ERROR] 加载数据失败: {str(e)}")
    sys.exit(1)

# 步骤2: 运行回测
print("\n[步骤 2/3] 运行回测引擎...")
print("-"*80)

try:
    # 初始化回测引擎
    # 初始资金: 100万
    # 交易成本: 0.03% (单边)
    engine = BacktestEngine(
        initial_capital=1000000.0,
        commission_rate=0.0003
    )
    
    # 运行回测
    result_df, stats = engine.run_backtest(df, price_col='close')
    
    print("[OK] 回测计算完成\n")
    
except Exception as e:
    print(f"[ERROR] 回测失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤3: 保存结果
print("\n[步骤 3/3] 保存回测结果...")
print("-"*80)

try:
    # 保存完整回测数据
    output_file = Path(__file__).parent / "data" / "processed" / "510050_backtest_results.csv"
    result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"[OK] 回测数据已保存: {output_file}")
    
    # 保存统计指标
    stats_file = Path(__file__).parent / "data" / "processed" / "backtest_statistics.txt"
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("回测统计指标\n")
        f.write("="*60 + "\n\n")
        
        for key, value in stats.items():
            if isinstance(value, float):
                f.write(f"{key}: {value:.4f}\n")
            else:
                f.write(f"{key}: {value}\n")
    
    print(f"[OK] 统计指标已保存: {stats_file}\n")
    
except Exception as e:
    print(f"[ERROR] 保存结果失败: {str(e)}")
    sys.exit(1)

# Phase 5 完成总结
print("\n" + "="*80)
print(" "*30 + "PHASE 5 完成！")
print("="*80)

# 打印详细摘要
engine.print_summary(stats)

# 显示关键数据
print("最近10个交易日的净值变化:")
print("-"*80)
recent = result_df.tail(10)[['trade_date', 'close', 'position', 'strategy_equity', 'benchmark_equity']].copy()
recent['strategy_equity'] = recent['strategy_equity'].apply(lambda x: f"{x:,.2f}")
recent['benchmark_equity'] = recent['benchmark_equity'].apply(lambda x: f"{x:,.2f}")
print(recent.to_string(index=False))

print("\n" + "="*80)
print("下一步:")
print("  - Phase 6: 绩效与风险分析（Sharpe Ratio, Max Drawdown等）")
print("  - 生成可视化图表")
print("="*80 + "\n")

sys.exit(0)
