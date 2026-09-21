import pandas as pd

df = pd.read_csv('data/raw/510050_SH_20200101_.csv')

print('='*60)
print('最新完整数据概览')
print('='*60)
print(f'总记录数: {len(df)}')
print(f'日期范围: {df["trade_date"].min()} - {df["trade_date"].max()}')
print(f'时间跨度: 6.7年 (2020-2026)')

print('\n最新10个交易日:')
print(df.tail(10)[['trade_date','open','high','low','close','vol']])

print('\n数据统计摘要:')
print(df[['open','high','low','close']].describe())

print('\n2026年数据:')
df_2026 = df[df['trade_date'] >= 20260101]
print(f'2026年交易日数: {len(df_2026)}')
print(f'2026年日期范围: {df_2026["trade_date"].min()} - {df_2026["trade_date"].max()}')
