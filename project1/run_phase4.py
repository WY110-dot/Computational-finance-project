"""
Phase 4 执行脚本
策略设计：MA5/MA20 移动平均线策略
"""
import sys
from pathlib import Path
import pandas as pd

# 添加src目录到路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from src.strategy.factor_calculator import FactorCalculator
from src.strategy.signal_generator import SignalGenerator

print("\n" + "="*80)
print(" "*25 + "PHASE 4: 策略设计 (MA5/MA20)")
print("="*80)

# 步骤1: 加载数据
print("\n[步骤 1/5] 加载原始数据...")
print("-"*80)

try:
    # 找到最新的数据文件
    data_dir = Path(__file__).parent / "data" / "raw"
    csv_files = list(data_dir.glob("510050_SH_*.csv"))
    
    if not csv_files:
        print("[ERROR] 未找到数据文件，请先运行 Phase 2")
        sys.exit(1)
    
    # 使用最新文件
    latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"读取文件: {latest_file.name}")
    
    df = pd.read_csv(latest_file)
    print(f"[OK] 成功加载 {len(df)} 条记录")
    print(f"日期范围: {df['trade_date'].min()} - {df['trade_date'].max()}\n")
    
except Exception as e:
    print(f"[ERROR] 加载数据失败: {str(e)}")
    sys.exit(1)

# 步骤2: 计算因子
print("\n[步骤 2/5] 计算技术因子 (MA5, MA20)...")
print("-"*80)

try:
    calculator = FactorCalculator()
    df = calculator.calculate_ma5_ma20(df, price_col='close')
    
    # 验证计算
    if not calculator.validate_ma_calculation(df):
        print("[ERROR] MA 计算验证失败")
        sys.exit(1)
    
except Exception as e:
    print(f"[ERROR] 因子计算失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤3: 生成信号
print("\n[步骤 3/5] 生成交易信号...")
print("-"*80)

try:
    generator = SignalGenerator()
    df = generator.generate_ma_cross_signal(df, fast_ma='ma5', slow_ma='ma20')
    
except Exception as e:
    print(f"[ERROR] 信号生成失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤4: 生成持仓（避免前视偏差）
print("\n[步骤 4/5] 生成持仓（延迟信号1天）...")
print("-"*80)

try:
    df = generator.generate_position(df, signal_col='signal')
    df = generator.identify_trades(df)
    
    # 验证无前视偏差
    if not generator.validate_no_lookahead_bias(df):
        print("[ERROR] 前视偏差验证失败")
        sys.exit(1)
    
except Exception as e:
    print(f"[ERROR] 持仓生成失败: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤5: 保存处理后数据
print("\n[步骤 5/5] 保存策略数据...")
print("-"*80)

try:
    # 保存到processed目录
    processed_dir = Path(__file__).parent / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = processed_dir / "510050_strategy_data.csv"
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"[OK] 策略数据已保存: {output_file}")
    print(f"文件大小: {output_file.stat().st_size / 1024:.2f} KB\n")
    
except Exception as e:
    print(f"[ERROR] 保存数据失败: {str(e)}")
    sys.exit(1)

# Phase 4 完成总结
print("\n" + "="*80)
print(" "*30 + "PHASE 4 完成！")
print("="*80)

# 生成统计摘要
valid_signals = df['signal'].notna().sum()
buy_signals = (df['signal'] == 1).sum()
sell_signals = (df['signal'] == 0).sum()
total_trades = (df['trade'] != 0).sum()

print("\n策略统计摘要:")
print("-"*80)
print(f"数据总量: {len(df)} 个交易日")
print(f"有效信号数: {valid_signals}")
print(f"  - 看多信号 (MA5>MA20): {buy_signals} ({buy_signals/valid_signals*100:.1f}%)")
print(f"  - 看空信号 (MA5<=MA20): {sell_signals} ({sell_signals/valid_signals*100:.1f}%)")
print(f"交易次数: {total_trades}")

# 显示最近的信号和持仓
print("\n最近10个交易日的策略状态:")
print("-"*80)
recent = df.tail(10)[['trade_date', 'close', 'ma5', 'ma20', 'signal', 'position', 'trade']]
print(recent.to_string(index=False))

print("\n" + "="*80)
print("下一步:")
print("  - Phase 5: 回测引擎（计算策略收益）")
print("  - Phase 6: 绩效与风险分析（Sharpe, Drawdown等）")
print("="*80 + "\n")

sys.exit(0)
