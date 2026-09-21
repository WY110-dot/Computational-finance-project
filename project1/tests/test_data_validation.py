import pytest
import pandas as pd
import numpy as np

def validate_data_quality(df: pd.DataFrame):
    """验证数据质量的核心检查（Phase C5 要求的集合）"""
    errors = []
    
    # 1. 日期排序
    if not df['trade_date'].is_monotonic_increasing:
        # 如果是多资产，需要按 asset 排序后再看日期
        if 'asset' in df.columns:
            for asset, group in df.groupby('asset'):
                if not group['trade_date'].is_monotonic_increasing:
                    errors.append(f"Data for {asset} is not sorted by date.")
        else:
            errors.append("Data is not sorted by date.")
            
    # 2. date × asset 唯一
    if 'asset' in df.columns:
        if df.duplicated(subset=['trade_date', 'asset']).any():
            errors.append("Duplicate (date, asset) keys found.")
    else:
        if df.duplicated(subset=['trade_date']).any():
            errors.append("Duplicate date keys found.")
            
    # 3. 缺失
    if df.isnull().any().any():
        errors.append("Missing values found in the dataset.")
        
    # 4. 非法价格
    price_cols = [c for c in df.columns if 'price' in c or 'close' in c or 'open' in c or 'high' in c or 'low' in c]
    for col in price_cols:
        if (df[col] <= 0).any():
            errors.append(f"Invalid negative or zero price in {col}.")
            
    # 5. 非法成交量
    vol_cols = [c for c in df.columns if 'volume' in c or 'amount' in c]
    for col in vol_cols:
        if (df[col] < 0).any():
            errors.append(f"Invalid negative volume/amount in {col}.")
            
    # 6. 复权因子 > 0
    if 'adj_factor' in df.columns:
        if (df['adj_factor'] <= 0).any():
            errors.append("Adjustment factor must be > 0.")
            
    return errors

def test_data_validation_passes_good_data():
    df = pd.DataFrame({
        'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'asset': ['510050.SH', '510050.SH', '510050.SH'],
        'close': [10.0, 10.5, 11.0],
        'volume': [1000, 2000, 1500],
        'adj_factor': [1.0, 1.0, 1.05]
    })
    errors = validate_data_quality(df)
    assert len(errors) == 0, f"Expected 0 errors, got: {errors}"

def test_data_validation_catches_bad_data():
    df = pd.DataFrame({
        'trade_date': ['2024-01-02', '2024-01-01', '2024-01-02'], # Unsorted and Duplicate
        'asset': ['510050.SH', '510050.SH', '510050.SH'],
        'close': [10.0, -5.0, np.nan], # Negative price and missing
        'volume': [-100, 2000, 1500],  # Negative volume
        'adj_factor': [1.0, 0.0, 1.05] # Zero adj_factor
    })
    errors = validate_data_quality(df)
    
    assert any("not sorted" in e for e in errors)
    assert any("Duplicate" in e for e in errors)
    assert any("Missing values" in e for e in errors)
    assert any("negative or zero price" in e for e in errors)
    assert any("negative volume" in e for e in errors)
    assert any("Adjustment factor" in e for e in errors)

