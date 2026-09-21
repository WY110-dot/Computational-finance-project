"""
Factor Calculator Module
计算技术指标因子（移动平均线等）
"""
import pandas as pd
import numpy as np
from typing import Optional


class FactorCalculator:
    """
    技术因子计算器
    计算各种技术指标，如移动平均线
    """
    
    def __init__(self):
        """初始化因子计算器"""
        pass
    
    @staticmethod
    def calculate_ma(
        df: pd.DataFrame, 
        price_col: str = 'close', 
        window: int = 5,
        col_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        计算移动平均线
        
        Args:
            df (pd.DataFrame): 包含价格数据的DataFrame
            price_col (str): 价格列名，默认为 'close'
            window (int): 移动平均窗口大小
            col_name (str, optional): 输出列名，默认为 'ma_{window}'
            
        Returns:
            pd.DataFrame: 添加了MA列的DataFrame
        """
        if col_name is None:
            col_name = f'ma_{window}'
        
        # 计算移动平均
        # 使用 rolling 方法，min_periods=window 确保前面不足window的为NaN
        df[col_name] = df[price_col].rolling(window=window, min_periods=window).mean()
        
        return df
    
    @staticmethod
    def calculate_ma5_ma20(df: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame:
        """
        一次性计算 MA5 和 MA20
        
        Args:
            df (pd.DataFrame): 包含价格数据的DataFrame
            price_col (str): 价格列名
            
        Returns:
            pd.DataFrame: 添加了 ma5 和 ma20 列的DataFrame
        """
        print("\n[计算因子] 开始计算 MA5 和 MA20...")
        
        # 确保数据按日期排序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 计算 MA5
        df = FactorCalculator.calculate_ma(df, price_col=price_col, window=5, col_name='ma5')
        
        # 计算 MA20
        df = FactorCalculator.calculate_ma(df, price_col=price_col, window=20, col_name='ma20')
        
        # 统计有效数据
        valid_ma5 = df['ma5'].notna().sum()
        valid_ma20 = df['ma20'].notna().sum()
        
        print(f"  MA5 有效数据点: {valid_ma5}/{len(df)}")
        print(f"  MA20 有效数据点: {valid_ma20}/{len(df)}")
        print(f"  前 {19} 天因数据不足无法计算 MA20（正常现象）")
        print("[OK] 因子计算完成\n")
        
        return df
    
    @staticmethod
    def validate_ma_calculation(df: pd.DataFrame) -> bool:
        """
        验证移动平均线计算的正确性
        
        Args:
            df (pd.DataFrame): 包含MA数据的DataFrame
            
        Returns:
            bool: 验证是否通过
        """
        print("\n[验证] 检查 MA 计算正确性...")
        
        passed = True
        
        # 检查1: MA5 和 MA20 列是否存在
        if 'ma5' not in df.columns or 'ma20' not in df.columns:
            print("  [ERROR] 缺少 ma5 或 ma20 列")
            return False
        
        # 检查2: 手动验证第一个有效的MA5值
        # 第5个交易日（索引4）应该是前5天收盘价的平均
        if len(df) >= 5:
            expected_ma5 = df['close'].iloc[0:5].mean()
            actual_ma5 = df['ma5'].iloc[4]
            
            if pd.notna(actual_ma5):
                diff = abs(expected_ma5 - actual_ma5)
                if diff < 0.0001:  # 允许浮点误差
                    print(f"  [OK] MA5 计算正确（第5天验证通过）")
                else:
                    print(f"  [ERROR] MA5 计算错误：期望 {expected_ma5:.4f}，实际 {actual_ma5:.4f}")
                    passed = False
        
        # 检查3: 手动验证第一个有效的MA20值
        if len(df) >= 20:
            expected_ma20 = df['close'].iloc[0:20].mean()
            actual_ma20 = df['ma20'].iloc[19]
            
            if pd.notna(actual_ma20):
                diff = abs(expected_ma20 - actual_ma20)
                if diff < 0.0001:
                    print(f"  [OK] MA20 计算正确（第20天验证通过）")
                else:
                    print(f"  [ERROR] MA20 计算错误：期望 {expected_ma20:.4f}，实际 {actual_ma20:.4f}")
                    passed = False
        
        # 检查4: MA20 应该比 MA5 更平滑（方差更小）
        valid_data = df[df['ma5'].notna() & df['ma20'].notna()]
        if len(valid_data) > 0:
            ma5_std = valid_data['ma5'].std()
            ma20_std = valid_data['ma20'].std()
            
            if ma20_std <= ma5_std:
                print(f"  [OK] MA20 比 MA5 更平滑（标准差: MA5={ma5_std:.4f}, MA20={ma20_std:.4f}）")
            else:
                print(f"  [WARNING] MA20 波动性大于 MA5（不太常见）")
        
        if passed:
            print("[OK] MA 计算验证通过\n")
        else:
            print("[ERROR] MA 计算验证失败\n")
        
        return passed


def main():
    """测试因子计算器"""
    print("\n" + "="*60)
    print("因子计算器测试")
    print("="*60)
    
    # 创建测试数据
    test_data = pd.DataFrame({
        'trade_date': [f'2024010{i}' for i in range(1, 8)],
        'close': [10, 11, 12, 13, 14, 15, 16]
    })
    
    print("\n测试数据:")
    print(test_data)
    
    # 计算MA5
    calculator = FactorCalculator()
    test_data = calculator.calculate_ma(test_data, price_col='close', window=5)
    
    print("\n计算 MA5 后:")
    print(test_data[['trade_date', 'close', 'ma5']])
    
    # 验证第5天的MA5
    expected = (10 + 11 + 12 + 13 + 14) / 5
    actual = test_data['ma5'].iloc[4]
    print(f"\n第5天 MA5 验证:")
    print(f"  期望值: {expected}")
    print(f"  实际值: {actual}")
    print(f"  {'[OK] 正确' if abs(expected - actual) < 0.0001 else '[ERROR] 错误'}")
    
    print("\n" + "="*60)
    print("[OK] 测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
