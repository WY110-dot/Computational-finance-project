import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.factors.core_factors import MOM20Factor, REV5Factor, LOWVOL20Factor

def run_phase_f1():
    print("="*60)
    print("Phase F1: Three Core Factors")
    print("="*60)
    
    # 1. Load Data
    data_path = 'data/processed/prices_daily.parquet'
    if not os.path.exists(data_path):
        print(f"Error: {data_path} not found. Please run run_phase_d1.py first.")
        return
        
    print(f"1. Loading processed multi-asset data from {data_path}...")
    df = pd.read_parquet(data_path)
    # Ensure sorted by date
    df = df.sort_values(['asset', 'date']).reset_index(drop=True)
    
    # 2. Initialize Factors
    factors = [MOM20Factor(), REV5Factor(), LOWVOL20Factor()]
    
    # 3. Compute Factors
    print("2. Computing Factors (MOM20, REV5, LOWVOL20)...")
    out_dfs = []
    for f in factors:
        print(f"   -> Processing {f.name}...")
        factor_out = f.process(df)
        out_dfs.append(factor_out)
        
    # 4. Combine into Long Table
    long_table = pd.concat(out_dfs, ignore_index=True)
    
    # 5. Save Output
    os.makedirs('data/processed/factors', exist_ok=True)
    out_path = 'data/processed/factors/core_factors_long.parquet'
    long_table.to_parquet(out_path, engine='pyarrow')
    print(f"\n3. Saved unified long table to {out_path}")
    print(f"   Total rows: {len(long_table)}")
    print(f"   Valid rows: {long_table['is_valid'].sum()}")
    
    # 6. Generate Factor Cards
    print("4. Generating Factor Cards...")
    os.makedirs('docs/factors', exist_ok=True)
    
    mom20_card = """# Factor Card: MOM20

- **factor_name**: MOM20
- **research_hypothesis**: 过去20天涨幅较大的资产，在短期内会继续维持强势（动量效应）。
- **economic_intuition**: 市场对信息的反应可能存在延迟，或者存在趋势跟踪资金推波助澜，导致近期表现好的资产持续上涨。
- **formula**: `close_adj_t / close_adj_(t-20) - 1`
- **input_fields**: close_adj
- **lookback_window**: 20 days
- **direction**: 1 (Higher is better)
- **expected_sign**: Positive
- **missing_value_policy**: Keep as NaN (is_valid=False), do not fill with 0
- **winsorize_policy**: None
- **standardization_policy**: Cross-sectional Rank (0 to 1) per day
- **failure_scenarios**: 均值回归极其强烈的震荡市、或者牛市突然转熊的断头铡刀行情。
- **data_version**: v1.1_cs_rank
"""
    
    rev5_card = """# Factor Card: REV5

- **factor_name**: REV5
- **research_hypothesis**: 过去5天跌幅较大的资产，在接下来的极短期内存在反弹需求（反转效应）。
- **economic_intuition**: 市场情绪在短期内容易过度反应，导致超卖，从而带来修正性的均值回归机会。
- **formula**: `-(close_adj_t / close_adj_(t-5) - 1)`
- **input_fields**: close_adj
- **lookback_window**: 5 days
- **direction**: 1 (Higher is better)
- **expected_sign**: Positive
- **missing_value_policy**: Keep as NaN (is_valid=False), do not fill with 0
- **winsorize_policy**: None
- **standardization_policy**: Cross-sectional Rank (0 to 1) per day
- **failure_scenarios**: 流动性危机导致的连续跌停、或者基本面彻底恶化导致的单边杀跌。
- **data_version**: v1.1_cs_rank
"""
    
    lowvol20_card = """# Factor Card: LOWVOL20

- **factor_name**: LOWVOL20
- **research_hypothesis**: 过去20天波动率较小的资产，其风险调整后收益更高（低波动异象）。
- **economic_intuition**: 投资者往往偏好高波动、具有“彩票特征”的资产，导致高波动资产被高估，低波动资产被低估。
- **formula**: `-std(ret_total_t, window=20, ddof=1)`
- **input_fields**: ret_total
- **lookback_window**: 20 days
- **direction**: 1 (Higher is better)
- **expected_sign**: Positive
- **missing_value_policy**: Keep as NaN (is_valid=False), do not fill with 0
- **winsorize_policy**: None
- **standardization_policy**: Cross-sectional Rank (0 to 1) per day
- **failure_scenarios**: 市场极度追求成长性与高弹性的狂热期。
- **data_version**: v1.1_cs_rank
"""

    with open('docs/factors/MOM20_card.md', 'w', encoding='utf-8') as f:
        f.write(mom20_card)
    with open('docs/factors/REV5_card.md', 'w', encoding='utf-8') as f:
        f.write(rev5_card)
    with open('docs/factors/LOWVOL20_card.md', 'w', encoding='utf-8') as f:
        f.write(lowvol20_card)
        
    print("   Created MOM20_card.md, REV5_card.md, LOWVOL20_card.md in docs/factors/")
    
    # 7. Basic Validation Print
    sample = long_table[(long_table['asset'] == '510050.SH') & (long_table['is_valid'])].groupby('factor').tail(1)
    print("\n5. Hand-calculation Sample check (510050.SH latest):")
    print(sample[['date', 'asset', 'factor', 'value', 'is_valid']])
    
    print("\nPhase F1 完全完成！")
    print("="*60)

if __name__ == "__main__":
    run_phase_f1()

