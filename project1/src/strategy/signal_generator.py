"""
Signal Generator Module
生成交易信号，严格避免前视偏差
"""
import pandas as pd
import numpy as np
from typing import Tuple


class SignalGenerator:
    """
    交易信号生成器
    基于技术指标生成买卖信号
    """
    
    def __init__(self):
        """初始化信号生成器"""
        pass
    
    @staticmethod
    def generate_ma_cross_signal(
        df: pd.DataFrame,
        fast_ma: str = 'ma5',
        slow_ma: str = 'ma20'
    ) -> pd.DataFrame:
        """
        生成移动平均线交叉信号
        
        策略规则:
        - 当 MA5 > MA20 时，Signal = 1 (看多，希望持有)
        - 当 MA5 <= MA20 时，Signal = 0 (看空，希望空仓)
        
        Args:
            df (pd.DataFrame): 包含MA数据的DataFrame
            fast_ma (str): 快速MA列名
            slow_ma (str): 慢速MA列名
            
        Returns:
            pd.DataFrame: 添加了signal列的DataFrame
        """
        print("\n[生成信号] 开始生成交易信号...")
        
        # 确保数据按日期排序
        if 'trade_date' in df.columns:
            df = df.sort_values('trade_date').reset_index(drop=True)
        
        # 生成信号
        # Signal = 1 当 MA5 > MA20 (看多)
        # Signal = 0 当 MA5 <= MA20 (看空)
        df['signal'] = 0
        df.loc[df[fast_ma] > df[slow_ma], 'signal'] = 1
        
        # 统计信号
        total_signals = df['signal'].notna().sum()
        buy_signals = (df['signal'] == 1).sum()
        sell_signals = (df['signal'] == 0).sum()
        
        print(f"  总信号数: {total_signals}")
        print(f"  看多信号 (Signal=1): {buy_signals} ({buy_signals/total_signals*100:.1f}%)")
        print(f"  看空信号 (Signal=0): {sell_signals} ({sell_signals/total_signals*100:.1f}%)")
        print("[OK] 信号生成完成\n")
        
        return df
    
    @staticmethod
    def generate_position(
        df: pd.DataFrame,
        signal_col: str = 'signal'
    ) -> pd.DataFrame:
        """
        根据信号生成持仓
        
        关键点：避免前视偏差
        - 今天的信号在明天才能执行
        - Position(t) = Signal(t-1)
        - 即：今天的持仓是基于昨天收盘后生成的信号
        
        Args:
            df (pd.DataFrame): 包含signal的DataFrame
            signal_col (str): 信号列名
            
        Returns:
            pd.DataFrame: 添加了position列的DataFrame
        """
        print("\n[生成持仓] 根据信号生成持仓（避免前视偏差）...")
        
        # 关键：信号延迟一天执行
        # shift(1) 表示将信号向下移动一行
        # 即：今天的持仓 = 昨天的信号
        df['position'] = df[signal_col].shift(1)
        
        # 第一天没有前一天的信号，设为0（空仓）
        df['position'] = df['position'].fillna(0)
        
        # 统计持仓
        total_days = len(df)
        hold_days = (df['position'] == 1).sum()
        empty_days = (df['position'] == 0).sum()
        
        print(f"  总交易日: {total_days}")
        print(f"  持仓天数: {hold_days} ({hold_days/total_days*100:.1f}%)")
        print(f"  空仓天数: {empty_days} ({empty_days/total_days*100:.1f}%)")
        print(f"  [重要] 持仓信号已延迟1天，避免前视偏差")
        print("[OK] 持仓生成完成\n")
        
        return df
    
    @staticmethod
    def identify_trades(df: pd.DataFrame) -> pd.DataFrame:
        """
        识别交易点（买入/卖出）
        
        Args:
            df (pd.DataFrame): 包含position的DataFrame
            
        Returns:
            pd.DataFrame: 添加了trade列的DataFrame
        """
        print("\n[识别交易] 识别买入卖出点...")
        
        # 计算持仓变化
        df['position_change'] = df['position'].diff()
        
        # 标记交易类型
        # 1: 买入 (从0变1)
        # -1: 卖出 (从1变0)
        # 0: 无交易
        df['trade'] = 0
        df.loc[df['position_change'] == 1, 'trade'] = 1   # 买入
        df.loc[df['position_change'] == -1, 'trade'] = -1  # 卖出
        
        # 统计交易次数
        buy_trades = (df['trade'] == 1).sum()
        sell_trades = (df['trade'] == -1).sum()
        total_trades = buy_trades + sell_trades
        
        print(f"  买入次数: {buy_trades}")
        print(f"  卖出次数: {sell_trades}")
        print(f"  总交易次数: {total_trades}")
        
        if buy_trades > 0:
            # 显示前几次交易
            trade_dates = df[df['trade'] != 0][['trade_date', 'close', 'trade']].head(10)
            print(f"\n  前几次交易:")
            for idx, row in trade_dates.iterrows():
                trade_type = "买入" if row['trade'] == 1 else "卖出"
                print(f"    {row['trade_date']}: {trade_type} @ {row['close']:.3f}")
        
        print("[OK] 交易识别完成\n")
        
        return df
    
    @staticmethod
    def validate_no_lookahead_bias(df: pd.DataFrame) -> bool:
        """
        验证是否存在前视偏差
        
        检查：
        1. Position 应该是 Signal 的延迟版本
        2. 第一天的 Position 应该是 0
        
        Args:
            df (pd.DataFrame): 包含signal和position的DataFrame
            
        Returns:
            bool: 验证是否通过
        """
        print("\n[验证] 检查是否存在前视偏差...")
        
        passed = True
        
        # 检查1: 第一天持仓应该是0
        if df['position'].iloc[0] != 0:
            print("  [ERROR] 第一天持仓不为0，可能存在前视偏差")
            passed = False
        else:
            print("  [OK] 第一天持仓为0")
        
        # 检查2: Position(t) 应该等于 Signal(t-1)
        # 验证前10个有信号的交易日
        check_rows = min(10, len(df) - 1)
        mismatches = 0
        
        for i in range(1, check_rows):
            if pd.notna(df['signal'].iloc[i-1]) and pd.notna(df['position'].iloc[i]):
                if df['position'].iloc[i] != df['signal'].iloc[i-1]:
                    mismatches += 1
        
        if mismatches == 0:
            print(f"  [OK] Position 正确延迟了 Signal（验证了前 {check_rows} 行）")
        else:
            print(f"  [ERROR] 发现 {mismatches} 处 Position 与延迟的 Signal 不匹配")
            passed = False
        
        # 检查3: 统计信号与持仓的分布差异
        signal_1_pct = (df['signal'] == 1).sum() / len(df) * 100
        position_1_pct = (df['position'] == 1).sum() / len(df) * 100
        
        print(f"  信号分布: {signal_1_pct:.1f}% 看多")
        print(f"  持仓分布: {position_1_pct:.1f}% 持有")
        print(f"  差异: {abs(signal_1_pct - position_1_pct):.2f}% (应该很小)")
        
        if passed:
            print("[OK] 无前视偏差验证通过\n")
        else:
            print("[ERROR] 前视偏差验证失败\n")
        
        return passed


def main():
    """测试信号生成器"""
    print("\n" + "="*60)
    print("信号生成器测试")
    print("="*60)
    
    # 创建测试数据
    test_data = pd.DataFrame({
        'trade_date': [f'2024010{i}' for i in range(1, 9)],
        'close': [10, 11, 12, 11, 10, 11, 12, 13],
        'ma5': [np.nan, np.nan, np.nan, np.nan, 10.8, 11.0, 11.2, 11.4],
        'ma20': [np.nan] * 8  # 简化测试，假设MA20为某固定值
    })
    test_data['ma20'] = 11.0  # 固定MA20为11
    
    print("\n测试数据:")
    print(test_data[['trade_date', 'close', 'ma5', 'ma20']])
    
    # 生成信号
    generator = SignalGenerator()
    test_data = generator.generate_ma_cross_signal(test_data)
    
    print("\n生成信号后:")
    print(test_data[['trade_date', 'close', 'ma5', 'ma20', 'signal']])
    
    # 生成持仓
    test_data = generator.generate_position(test_data)
    
    print("\n生成持仓后:")
    print(test_data[['trade_date', 'signal', 'position']])
    
    # 验证无前视偏差
    generator.validate_no_lookahead_bias(test_data)
    
    print("\n" + "="*60)
    print("[OK] 测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
