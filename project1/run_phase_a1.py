import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.analysis.factor_diagnostics import FactorDiagnostics

def run_phase_a1():
    print("="*60)
    print("Phase A1: Factor Diagnostics")
    print("="*60)
    
    # 1. Load Data
    price_path = 'data/processed/prices_daily.parquet'
    factor_path = 'data/processed/factors/core_factors_long.parquet'
    
    if not os.path.exists(price_path) or not os.path.exists(factor_path):
        print("Error: Required data not found. Run D1 and F1 first.")
        return
        
    print("1. Loading processed prices and factors...")
    price_df = pd.read_parquet(price_path)
    factor_df = pd.read_parquet(factor_path)
    
    # 2. Run Diagnostics
    print("2. Running Diagnostics (IC, Rank IC, Group Returns)...")
    diag = FactorDiagnostics(factor_df, price_df, forward_periods=[1, 5])
    
    ic_summary_df, ic_timeseries_df = diag.calculate_ic()
    group_df = diag.calculate_group_returns(num_groups=5)
    
    # Calculate Factor Distribution
    dist_list = []
    for f, group in factor_df[factor_df['is_valid']].groupby('factor'):
        dist_list.append({
            'factor': f,
            'count': group['value'].count(),
            'mean': group['value'].mean(),
            'std': group['value'].std(),
            'min': group['value'].min(),
            '25%': group['value'].quantile(0.25),
            '50%': group['value'].median(),
            '75%': group['value'].quantile(0.75),
            'max': group['value'].max(),
            'skew': group['value'].skew()
        })
    dist_df = pd.DataFrame(dist_list)
    
    # 3. Print Results
    print("\n--- IC & Rank IC Summary (Section 22) ---")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    print(ic_summary_df.round(4))
    
    print("\n--- IC Time Series Sample (First 5 Rows) ---")
    print(ic_timeseries_df.head())
    
    print("\n--- Group Returns (K=5) ---")
    print(group_df.round(4))
    
    print("\n--- Factor Distribution ---")
    print(dist_df.round(4))
    
    # 4. Save Results
    print("\n3. Saving reports...")
    os.makedirs('outputs/analysis', exist_ok=True)
    ic_summary_df.to_csv('outputs/analysis/ic_report.csv', index=False)
    ic_timeseries_df.to_csv('outputs/analysis/ic_timeseries.csv', index=False)
    group_df.to_csv('outputs/analysis/group_return_report.csv', index=False)
    dist_df.to_csv('outputs/analysis/factor_distribution_report.csv', index=False)
    
    print("\nPhase A1 验证完成！")
    print("="*60)

if __name__ == "__main__":
    run_phase_a1()
