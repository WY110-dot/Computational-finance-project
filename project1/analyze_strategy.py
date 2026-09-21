import pandas as pd

df = pd.read_csv('data/processed/510050_strategy_data.csv')

print("="*60)
print("策略数据详细分析")
print("="*60)

# 基本统计
print(f"\n数据维度: {df.shape}")
print(f"列名: {list(df.columns)}")

# 信号统计
print(f"\n信号分布:")
print(df['signal'].value_counts().sort_index())

# 持仓统计
print(f"\n持仓分布:")
print(df['position'].value_counts().sort_index())

# 交易统计
print(f"\n交易类型分布:")
print(df['trade'].value_counts().sort_index())

# 查看金叉死叉
trades = df[df['trade'] != 0][['trade_date', 'close', 'ma5', 'ma20', 'trade']].copy()
trades['trade_type'] = trades['trade'].map({1: '买入(金叉)', -1: '卖出(死叉)'})

print(f"\n所有交易点 (共 {len(trades)} 次):")
print(trades[['trade_date', 'close', 'ma5', 'ma20', 'trade_type']].head(20).to_string(index=False))

# 计算简单统计
buy_prices = trades[trades['trade'] == 1]['close'].values
sell_prices = trades[trades['trade'] == -1]['close'].values

if len(buy_prices) > 0 and len(sell_prices) > 0:
    print(f"\n交易价格统计:")
    print(f"  平均买入价: {buy_prices.mean():.3f}")
    print(f"  平均卖出价: {sell_prices.mean():.3f}")
    print(f"  买入价格范围: {buy_prices.min():.3f} - {buy_prices.max():.3f}")
    print(f"  卖出价格范围: {sell_prices.min():.3f} - {sell_prices.max():.3f}")

print("\n" + "="*60)
