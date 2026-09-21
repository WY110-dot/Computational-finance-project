import tushare as ts
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
token = os.getenv('TUSHARE_TOKEN')
ts.set_token(token)
pro = ts.pro_api()

print("测试不同日期获取数据：\n")

# 测试1: 使用今天日期
print("1. 尝试获取到今天 (2024-09-17):")
df1 = pro.fund_daily(ts_code='510050.SH', start_date='20240910', end_date='20240917')
print(f"   结果: {len(df1)} 条记录")
if len(df1) > 0:
    print(f"   最新日期: {df1['trade_date'].max()}")

# 测试2: 使用未来日期
print("\n2. 尝试获取到未来 (2026-09-17):")
df2 = pro.fund_daily(ts_code='510050.SH', start_date='20240910', end_date='20260917')
print(f"   结果: {len(df2)} 条记录")
if len(df2) > 0:
    print(f"   最新日期: {df2['trade_date'].max()}")

# 测试3: 不指定结束日期
print("\n3. 不指定结束日期（获取所有可用数据）:")
df3 = pro.fund_daily(ts_code='510050.SH', start_date='20240910', end_date='')
print(f"   结果: {len(df3)} 条记录")
if len(df3) > 0:
    print(f"   最新日期: {df3['trade_date'].max()}")

print("\n结论:")
print(f"Tushare 当前可提供的最新交易日: {df3['trade_date'].max() if len(df3) > 0 else '无数据'}")
