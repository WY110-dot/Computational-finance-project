"""
Returns Calculation Module (Phase C2)
收益计算模块：负责独立、正确地计算资产收益、策略收益、基准收益和超额收益，严格防止前视偏差。
"""
import pandas as pd
import numpy as np


class ReturnsCalculator:
    """
    收益计算器：
    分离因子收益（Factor Return）和实际交易收益（Strategy Return）。
    """

    @staticmethod
    def calculate_forward_returns(df: pd.DataFrame, price_col: str = 'close_adj', periods: int = 1) -> pd.DataFrame:
        """
        计算因子研究所需的未来N日收益 (Forward Return)
        用于 IC, Rank IC, Group Return 计算。
        注意：前向收益包含了未来数据，只能作为因子的标签(label)，绝对不能用于回测。
        
        Args:
            df: 包含价格的 DataFrame
            price_col: 价格列，默认 'close_adj'
            periods: 向前的天数
        """
        df = df.copy()
        
        if price_col not in df.columns:
            if 'close' in df.columns:
                price_col = 'close'
            else:
                raise ValueError(f"Price column {price_col} not found.")

        # ret_forward_N = close_{t+N} / close_t - 1
        col_name = f'ret_forward_{periods}'
        
        if 'asset' in df.columns:
            def _calc(g):
                g = g.copy()
                g[col_name] = g[price_col].pct_change(periods).shift(-periods)
                return g
            df = df.groupby('asset', group_keys=False).apply(_calc)
        else:
            df[col_name] = df[price_col].pct_change(periods).shift(-periods)
        
        return df

    @staticmethod
    def calculate_strategy_returns(df: pd.DataFrame, signal_col: str = 'signal', price_col: str = 'close_adj') -> pd.DataFrame:
        """
        计算策略的实际交易收益。
        严格避免前视偏差：
        Factor(t) -> Signal(t) -> Position(t+1) -> Return(t+1)
        即 t 日产生的信号，只能决定 t+1 日的仓位，从而获得 t+1 日的收益。
        
        Args:
            df: DataFrame containing signal and price
            signal_col: 信号列名
            price_col: 用于计算收益的复权价格列
            
        Returns:
            DataFrame 包含 position, ret_total, strategy_return_gross
        """
        df = df.copy()
        
        if price_col not in df.columns and 'close' in df.columns:
            price_col = 'close'
            
        # 1. 资产本身的当日总收益 return_t = close_t / close_{t-1} - 1
        # 如果 df 已经包含 ret_total，则不重新计算，以保持数据一致性
        if 'ret_total' not in df.columns:
            df['ret_total'] = df[price_col].pct_change().fillna(0.0)
        
        # 2. 从信号推导持仓，必须 shift(1) 避免前视偏差
        # 如果 df 中已经有正确生成的 position，我们信任它。否则我们根据 signal 生成它。
        if 'position' not in df.columns:
            if signal_col in df.columns:
                df['position'] = df[signal_col].shift(1).fillna(0.0)
            else:
                raise ValueError(f"DataFrame must contain either '{signal_col}' or 'position' column.")
            
        # 3. 策略毛收益 = 实际持仓 * 当日资产收益
        # (此时的 position(t) 已经是基于 signal(t-1) 的，所以没有前视偏差)
        df['strategy_return_gross'] = df['position'] * df['ret_total']
        
        return df

    @staticmethod
    def calculate_benchmark_returns(df: pd.DataFrame, price_col: str = 'close_adj') -> pd.DataFrame:
        """
        计算基准收益（通常为 Buy & Hold 标的资产）
        """
        df = df.copy()
        if price_col not in df.columns and 'close' in df.columns:
            price_col = 'close'
            
        df['benchmark_return'] = df[price_col].pct_change().fillna(0.0)
        return df

    @staticmethod
    def calculate_excess_returns(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算策略相对于基准的超额收益
        """
        df = df.copy()
        if 'strategy_return_gross' in df.columns and 'benchmark_return' in df.columns:
            df['excess_return'] = df['strategy_return_gross'] - df['benchmark_return']
        return df

