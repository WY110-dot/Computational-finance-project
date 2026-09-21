import tushare as ts
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv('TUSHARE_TOKEN')
print(f"Token: {token[:20]}...")

ts.set_token(token)
pro = ts.pro_api()

# Test 1: Get fund basic info
print("\nTest 1: Fund basic info")
try:
    df = pro.fund_basic(ts_code='510050.SH')
    print(f"Success: {len(df)} records")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")

# Test 2: Try different date range
print("\n\nTest 2: Recent data (2024)")
try:
    df = pro.daily(ts_code='510050.SH', start_date='20240101', end_date='20240630')
    print(f"Success: {len(df)} records")
    if len(df) > 0:
        print(df.head())
except Exception as e:
    print(f"Error: {e}")

# Test 3: Try older date range
print("\n\nTest 3: Older data (2023)")
try:
    df = pro.daily(ts_code='510050.SH', start_date='20230101', end_date='20230630')
    print(f"Success: {len(df)} records")
    if len(df) > 0:
        print(df.head())
except Exception as e:
    print(f"Error: {e}")

# Test 4: Try fund_daily instead
print("\n\nTest 4: Using fund_daily API")
try:
    df = pro.fund_daily(ts_code='510050.SH', start_date='20230101', end_date='20230630')
    print(f"Success: {len(df)} records")
    if len(df) > 0:
        print(df.head())
except Exception as e:
    print(f"Error: {e}")
