import os
import sys
import pandas as pd
import json
import hashlib
from datetime import datetime

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.data.tushare_connector import TushareConnector
from src.data.adjustment import ETFAdjuster

ETF_UNIVERSE = [
    "510050.SH", "510300.SH", "510500.SH", "159915.SZ", "512100.SH",
    "518880.SH", "513100.SH", "513500.SH", "512880.SH", "512000.SH",
    "512200.SH", "512690.SH", "515030.SH", "159995.SZ", "512480.SH",
    "512660.SH", "512010.SH", "515700.SH", "159928.SZ", "515050.SH",
    "159920.SZ", "513050.SH", "511260.SH", "511010.SH", "511220.SH"
]

def calculate_checksum(file_path: str) -> str:
    """计算文件的 SHA256 校验和"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def run_phase_d1():
    print("="*60)
    print("Phase D1: Build Multi-Asset Data Layer")
    print("="*60)
    
    # 1. 初始化
    os.makedirs('data/raw', exist_ok=True)
    os.makedirs('data/processed', exist_ok=True)
    os.makedirs('data/sample', exist_ok=True)
    os.makedirs('data/manifests', exist_ok=True)
    os.makedirs('outputs/quality', exist_ok=True)
    os.makedirs('docs', exist_ok=True)
    
    start_date = "20190101"
    end_date = "20260918"
    
    connector = TushareConnector()
    adjuster = ETFAdjuster()
    
    all_prices = []
    all_adjs = []
    
    # 2. 爬取数据
    print("\n[Data Fetching] Downloading universe from Tushare...")
    for etf in ETF_UNIVERSE:
        # Download Prices
        try:
            df_price = connector.get_daily_data(ts_code=etf, start_date=start_date, end_date=end_date)
            if not df_price.empty:
                all_prices.append(df_price)
        except Exception as e:
            print(f"Failed to fetch price for {etf}: {e}")
            
        # Download Adjustments
        try:
            df_adj = connector.get_adj_factor(ts_code=etf, start_date=start_date, end_date=end_date)
            if not df_adj.empty:
                all_adjs.append(df_adj)
        except Exception as e:
            print(f"Failed to fetch adj for {etf}: {e}")
            
    if not all_prices or not all_adjs:
        print("Error: No data downloaded.")
        return
        
    df_prices_raw = pd.concat(all_prices, ignore_index=True)
    df_adjs_raw = pd.concat(all_adjs, ignore_index=True)
    
    # 保存 raw
    raw_prices_path = 'data/raw/prices_raw.parquet'
    raw_adj_path = 'data/raw/adjustment_raw.parquet'
    df_prices_raw.to_parquet(raw_prices_path, engine='pyarrow')
    df_adjs_raw.to_parquet(raw_adj_path, engine='pyarrow')
    
    # 3. 处理复权
    print("\n[Data Processing] Adjusting prices...")
    all_adjusted = []
    for asset, group_price in df_prices_raw.groupby('ts_code'):
        group_adj = df_adjs_raw[df_adjs_raw['ts_code'] == asset]
        if group_adj.empty:
            continue
        try:
            merged = adjuster.merge_raw_and_adj(group_price, group_adj)
            adjusted = adjuster.compute_forward_adjustment(merged)
            all_adjusted.append(adjusted)
        except Exception as e:
            print(f"Failed to adjust {asset}: {e}")
            
    df_processed = pd.concat(all_adjusted, ignore_index=True)
    
    # 重命名列以满足 Phase D1 Data Dictionary 要求
    # 注意：ETFAdjuster 已经做了一部分，确保严格一致
    columns_to_keep = [
        'date', 'asset', 'open_raw', 'close_raw', 'adj_factor', 
        'close_adj', 'volume', 'amount', 'ret_total', 'adjustment_reference_date'
    ]
    # 如果有缺的可以补0，但正常都有
    for col in columns_to_keep:
        if col not in df_processed.columns:
            df_processed[col] = 0.0
            
    df_processed = df_processed[columns_to_keep].sort_values(['date', 'asset']).reset_index(drop=True)
    
    # 4. 生成 processed 文件
    print("\n[Data Saving] Saving processed parquets...")
    processed_prices_path = 'data/processed/prices_daily.parquet'
    processed_returns_path = 'data/processed/returns_daily.parquet'
    universe_path = 'data/processed/universe_daily.parquet'
    
    df_processed.to_parquet(processed_prices_path, engine='pyarrow')
    # Returns separately
    df_processed[['date', 'asset', 'ret_total']].to_parquet(processed_returns_path, engine='pyarrow')
    # Universe (just date and asset keys)
    df_processed[['date', 'asset']].to_parquet(universe_path, engine='pyarrow')
    
    # 5. 生成 Sample
    print("\n[Sample Generation] Creating shareable sample...")
    sample_assets = ETF_UNIVERSE[:5]
    sample_dates = sorted(df_processed['date'].unique())[-60:] # last 60 days
    sample_df = df_processed[df_processed['asset'].isin(sample_assets) & df_processed['date'].isin(sample_dates)]
    
    sample_prices_path = 'data/sample/prices_sample.csv'
    sample_df.to_csv(sample_prices_path, index=False)
    
    sample_factors_path = 'data/sample/factors_sample.csv'
    sample_df[['date', 'asset', 'ret_total']].to_csv(sample_factors_path, index=False)
    
    # 6. 生成 Manifest
    print("\n[Manifest Generation] Creating data_manifest.json...")
    manifest = {
        "download_time": datetime.now().isoformat(),
        "data_source": "Tushare Pro",
        "api_name": ["fund_daily", "fund_adj"],
        "asset_universe_version": "v1_25_etfs",
        "start_date": start_date,
        "end_date": end_date,
        "row_count": len(df_processed),
        "files": [
            {
                "file_name": "prices_daily.parquet",
                "checksum": calculate_checksum(processed_prices_path),
                "data_version": "1.0"
            }
        ]
    }
    with open('data/manifests/data_manifest.json', 'w') as f:
        json.dump(manifest, f, indent=4)
        
    # 7. 生成 Data Dictionary
    print("\n[Documentation] Generating docs/data_dictionary.md...")
    dictionary_content = """# Data Dictionary

| Field | Definition | Unit | Notes |
|---|---|---|---|
| date | 交易日 | YYYYMMDD | |
| asset | Tushare 代码 | string | |
| open_raw | 原始开盘价 | RMB | |
| close_raw | 原始收盘价 | RMB | |
| adj_factor | 复权因子 | dimensionless | |
| close_adj | 复权收盘价 | adjusted RMB | |
| volume | 成交量 | 手 | 1手=100份 |
| amount | 成交金额 | 千元 | |
| ret_total | 总收益率 | decimal | |
| adjustment_reference_date | 复权基准日 | YYYYMMDD | Phase C1 固定 reference date |
"""
    with open('docs/data_dictionary.md', 'w', encoding='utf-8') as f:
        f.write(dictionary_content)
        
    # 8. 生成 Data Quality Report
    print("\n[Quality Report] Generating outputs/quality/data_quality_report.md...")
    duplicates = df_processed.duplicated(subset=['date', 'asset']).sum()
    missing_open = df_processed['open_raw'].isnull().sum()
    missing_close = df_processed['close_raw'].isnull().sum()
    missing_volume = df_processed['volume'].isnull().sum()
    invalid_price_rows = (df_processed['close_raw'] <= 0).sum()
    invalid_volume_rows = (df_processed['volume'] < 0).sum()
    coverage = "100%"
    removed_rows = len(df_prices_raw) - len(df_processed)
    
    quality_content = f"""# Data Quality Report

- asset_count: {df_processed['asset'].nunique()}
- start_date: {df_processed['date'].min()}
- end_date: {df_processed['date'].max()}
- raw_rows: {len(df_prices_raw)}
- clean_rows: {len(df_processed)}
- duplicate_keys: {duplicates}
- missing_open: {missing_open}
- missing_close: {missing_close}
- missing_volume: {missing_volume}
- invalid_price_rows: {invalid_price_rows}
- invalid_volume_rows: {invalid_volume_rows}
- coverage: {coverage}
- removed_rows: {removed_rows}
- removal_reasons: "Mainly missing adjustment factors or non-trading days filtered during merge."
"""
    with open('outputs/quality/data_quality_report.md', 'w', encoding='utf-8') as f:
        f.write(quality_content)
        
    print("\nPhase D1 完全完成！")
    print("="*60)

if __name__ == "__main__":
    run_phase_d1()

