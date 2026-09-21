import pandas as pd
import numpy as np

df = pd.read_csv('data/processed/510050_backtest_results.csv')

print("="*60)
print("回测结果深度分析")
print("="*60)

# 1. 收益分解
print("\n1. 收益分解:")
total_gross_return = df['strategy_return_gross'].sum()
total_net_return = df['strategy_return'].sum()
total_cost = df['transaction_cost'].sum()

print(f"   毛收益累计: {total_gross_return*100:.2f}%")
print(f"   交易成本累计: {total_cost*100:.2f}%")
print(f"   净收益累计: {total_net_return*100:.2f}%")
print(f"   成本占毛收益比: {abs(total_cost/total_gross_return)*100:.1f}%")

# 2. 持仓期间表现
hold_data = df[df['position'] == 1]
empty_data = df[df['position'] == 0]

print(f"\n2. 持仓期间表现:")
print(f"   持仓天数: {len(hold_data)}")
print(f"   持仓期间平均日收益: {hold_data['market_return'].mean()*100:.4f}%")
print(f"   持仓期间累计收益: {(hold_data['market_return'].sum())*100:.2f}%")

print(f"\n3. 空仓期间市场表现:")
print(f"   空仓天数: {len(empty_data)}")
print(f"   空仓期间平均日收益: {empty_data['market_return'].mean()*100:.4f}%")
print(f"   空仓期间累计收益: {(empty_data['market_return'].sum())*100:.2f}%")
print(f"   空仓期间错过收益: {(empty_data['market_return'].sum())*100:.2f}%")

# 4. 分年度表现
print(f"\n4. 分年度表现:")
df['year'] = df['trade_date'].astype(str).str[:4]
yearly_stats = df.groupby('year').agg({
    'strategy_return': 'sum',
    'market_return': 'sum',
    'trade': lambda x: (x != 0).sum()
})
yearly_stats['strategy_return_%'] = yearly_stats['strategy_return'] * 100
yearly_stats['market_return_%'] = yearly_stats['market_return'] * 100

print(yearly_stats[['strategy_return_%', 'market_return_%', 'trade']])

# 5. 最大连续亏损
print(f"\n5. 连续亏损分析:")
losses = df[df['strategy_return'] < 0]
print(f"   亏损天数: {len(losses)}")
print(f"   亏损天数占比: {len(losses)/len(df)*100:.1f}%")
print(f"   最大单日亏损: {df['strategy_return'].min()*100:.2f}%")
print(f"   最大单日收益: {df['strategy_return'].max()*100:.2f}%")

# 6. 交易效率
trades = df[df['trade'] != 0]
print(f"\n6. 交易点分析:")
print(f"   平均交易价格(买入): {df[df['trade']==1]['close'].mean():.3f}")
print(f"   平均交易价格(卖出): {df[df['trade']==-1]['close'].mean():.3f}")

print("\n" + "="*60)
