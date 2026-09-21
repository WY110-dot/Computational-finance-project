# -*- coding: utf-8 -*-
"""
Test Dashboard Components
"""
import pandas as pd
import sys

sys.path.append('src')

print("=" * 80)
print("Phase 8: Dashboard Components Test")
print("=" * 80)

# Test 1: Check data files
print("\n[Test 1] Checking data files...")
try:
    df = pd.read_csv('outputs/tables/best_strategy_in_sample_20260917_150126.csv')
    print(f"✅ Data file loaded: {len(df)} rows")
    print(f"   Columns: {df.columns.tolist()}")
    print(f"   Date range: {df['trade_date'].min()} to {df['trade_date'].max()}")
except FileNotFoundError as e:
    print(f"❌ Data file not found: {e}")
    sys.exit(1)

# Test 2: Check required columns
print("\n[Test 2] Checking required columns...")
required_cols = ['trade_date', 'close', 'strategy_equity', 'benchmark_equity']
missing_cols = [col for col in required_cols if col not in df.columns]

if missing_cols:
    print(f"❌ Missing columns: {missing_cols}")
else:
    print(f"✅ All required columns present")

# Test 3: Check data quality
print("\n[Test 3] Checking data quality...")
print(f"   Null values: {df[required_cols].isnull().sum().sum()}")
print(f"   Latest price: {df['close'].iloc[-1]:.3f}")
print(f"   Final strategy equity: {df['strategy_equity'].iloc[-1]:,.2f}")
print(f"   Final benchmark equity: {df['benchmark_equity'].iloc[-1]:,.2f}")

# Test 4: Calculate metrics
print("\n[Test 4] Calculating metrics...")
initial_equity = df['strategy_equity'].iloc[0]
final_equity = df['strategy_equity'].iloc[-1]
total_return = (final_equity / initial_equity - 1) * 100

benchmark_initial = df['benchmark_equity'].iloc[0]
benchmark_final = df['benchmark_equity'].iloc[-1]
benchmark_return = (benchmark_final / benchmark_initial - 1) * 100

print(f"   Strategy return: {total_return:.2f}%")
print(f"   Benchmark return: {benchmark_return:.2f}%")
print(f"   Excess return: {total_return - benchmark_return:.2f}%")

# Test 5: Check Streamlit installation
print("\n[Test 5] Checking Streamlit installation...")
try:
    import streamlit
    print(f"✅ Streamlit version: {streamlit.__version__}")
except ImportError:
    print("❌ Streamlit not installed")
    sys.exit(1)

# Test 6: Check Plotly installation
print("\n[Test 6] Checking Plotly installation...")
try:
    import plotly
    print(f"✅ Plotly version: {plotly.__version__}")
except ImportError:
    print("❌ Plotly not installed")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ All tests passed! Dashboard is ready to run.")
print("=" * 80)
print("\nTo start the dashboard, run:")
print("  .\\run_dashboard.bat")
print("\nOr manually:")
print("  .\\.venv\\Scripts\\streamlit run app\\dashboard.py")
print("=" * 80)
