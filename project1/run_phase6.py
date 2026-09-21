"""
Phase 6 执行脚本
绩效与风险分析
"""
import sys
from pathlib import Path
import pandas as pd

# 添加src目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from src.metrics.performance_metrics import PerformanceMetrics

print("\n" + "="*80)
print(" "*23 + "PHASE 6: 绩效与风险分析")
print("="*80)

# 步骤1: 加载回测数据
print("\n[步骤 1/3] 加载回测数据...")
print("-"*80)

try:
    # 加载Phase 5生成的回测结果
    data_file = Path(__file__).parent / "data" / "processed" / "510050_backtest_results.csv"
    
    if not data_file.exists():
        print("[ERROR] 回测数据文件不存在，请先运行 Phase 5")
        sys.exit(1)
    
    df = pd.read_csv(data_file)
    print(f"[OK] 成功加载 {len(df)} 条记录")
    print(f"日期范围: {df['trade_date'].min()} - {df['trade_date'].max()}")
    
    # 检查必要的列
    required_cols = ['strategy_return', 'market_return', 'strategy_equity', 'benchmark_equity', 'trade']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        print(f"[ERROR] 缺少必要列: {missing_cols}")
        sys.exit(1)
    
    print(f"[OK] 数据验证通过\n")
    
except Exception as e:
    print(f"[ERROR] 加载数据失败: {str(e)}")
    sys.exit(1)

# 步骤2: 计算绩效指标
print("\n[步骤 2/3] 计算绩效指标...")
print("-"*80)

try:
    # 初始化绩效计算器
    # 无风险利率设为0（保守假设）
    calculator = PerformanceMetrics(risk_free_rate=0.0)
    
    # 计算所有指标
    metrics = calculator.calculate_all_metrics(df, initial_capital=1000000.0)
    
    print("\n[OK] 指标计算完成\n")
    
except Exception as e:
    print(f"[ERROR] 指标计算失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤3: 保存结果
print("\n[步骤 3/3] 保存分析结果...")
print("-"*80)

try:
    # 保存指标到文件
    metrics_file = Path(__file__).parent / "data" / "processed" / "performance_metrics.txt"
    
    with open(metrics_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("绩效与风险指标\n")
        f.write("="*70 + "\n\n")
        
        f.write("策略指标:\n")
        f.write("-"*70 + "\n")
        f.write(f"总收益率: {metrics['total_return_strategy']:.2f}%\n")
        f.write(f"年化收益率: {metrics['annualized_return_strategy']:.2f}%\n")
        f.write(f"年化波动率: {metrics['volatility_strategy']:.2f}%\n")
        f.write(f"夏普比率: {metrics['sharpe_ratio_strategy']:.4f}\n")
        f.write(f"最大回撤: {metrics['max_drawdown_strategy']:.2f}%\n")
        f.write(f"卡玛比率: {metrics['calmar_ratio_strategy']:.4f}\n")
        
        f.write("\n基准指标:\n")
        f.write("-"*70 + "\n")
        f.write(f"总收益率: {metrics['total_return_benchmark']:.2f}%\n")
        f.write(f"年化收益率: {metrics['annualized_return_benchmark']:.2f}%\n")
        f.write(f"年化波动率: {metrics['volatility_benchmark']:.2f}%\n")
        f.write(f"夏普比率: {metrics['sharpe_ratio_benchmark']:.4f}\n")
        f.write(f"最大回撤: {metrics['max_drawdown_benchmark']:.2f}%\n")
        f.write(f"卡玛比率: {metrics['calmar_ratio_benchmark']:.4f}\n")
        
        f.write("\n对比:\n")
        f.write("-"*70 + "\n")
        f.write(f"超额收益: {metrics['excess_return']:.2f}%\n")
        f.write(f"年化超额: {metrics['excess_annualized']:.2f}%\n")
    
    print(f"[OK] 指标已保存: {metrics_file}")
    
    # 保存回撤序列
    drawdown_file = Path(__file__).parent / "data" / "processed" / "drawdown_data.csv"
    drawdown_df = pd.DataFrame({
        'trade_date': df['trade_date'],
        'strategy_drawdown': metrics['drawdown_series_strategy'],
        'benchmark_drawdown': metrics['drawdown_series_benchmark']
    })
    drawdown_df.to_csv(drawdown_file, index=False, encoding='utf-8-sig')
    print(f"[OK] 回撤数据已保存: {drawdown_file}\n")
    
except Exception as e:
    print(f"[ERROR] 保存结果失败: {str(e)}")
    sys.exit(1)

# Phase 6 完成总结
print("\n" + "="*80)
print(" "*30 + "PHASE 6 完成！")
print("="*80)

# 打印对比表
calculator.print_summary_table(metrics)

# 关键发现
print("\n关键发现:")
print("-"*80)
print(f"1. 策略夏普比率: {metrics['sharpe_ratio_strategy']:.4f}")
if metrics['sharpe_ratio_strategy'] < 0:
    print("   → 风险调整后收益为负，策略不佳")
elif metrics['sharpe_ratio_strategy'] < 1:
    print("   → 风险调整后收益较低")
elif metrics['sharpe_ratio_strategy'] < 2:
    print("   → 风险调整后收益尚可")
else:
    print("   → 风险调整后收益优秀")

print(f"\n2. 策略最大回撤: {metrics['max_drawdown_strategy']:.2f}%")
print(f"   基准最大回撤: {metrics['max_drawdown_benchmark']:.2f}%")
if abs(metrics['max_drawdown_strategy']) > abs(metrics['max_drawdown_benchmark']):
    print("   → 策略回撤更大，风险更高")
else:
    print("   → 策略回撤更小，风险控制较好")

print(f"\n3. 波动率对比:")
print(f"   策略: {metrics['volatility_strategy']:.2f}%")
print(f"   基准: {metrics['volatility_benchmark']:.2f}%")
if metrics['volatility_strategy'] > metrics['volatility_benchmark']:
    print("   → 策略波动更大")
else:
    print("   → 策略波动更小")

print("\n" + "="*80)
print("下一步:")
print("  - 生成可视化图表")
print("  - Phase 7: 策略验证")
print("  - Phase 8: Dashboard 开发")
print("="*80 + "\n")

sys.exit(0)
