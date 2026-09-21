"""
Strategy Optimization Module - Updated to handle metrics naming
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import sys
sys.path.append('src')

from backtest.backtest_engine import BacktestEngine
from metrics.performance_metrics import PerformanceMetrics

def run_backtest(df: pd.DataFrame, initial_capital: float = 1_000_000, 
                 transaction_cost: float = 0.0003) -> pd.DataFrame:
    """Wrapper: run backtest"""
    engine = BacktestEngine(initial_capital=initial_capital, commission_rate=transaction_cost)
    result_df, _ = engine.run_backtest(df, price_col='close')
    return result_df

def calculate_all_metrics(df: pd.DataFrame, initial_capital: float = 1_000_000) -> Dict:
    """Wrapper: calculate all performance metrics and normalize naming"""
    metrics_calc = PerformanceMetrics(risk_free_rate=0.0)
    raw_metrics = metrics_calc.calculate_all_metrics(df, initial_capital)
    
    # Normalize metric names (remove _strategy suffix for easier access)
    normalized = {}
    for key, value in raw_metrics.items():
        if key.endswith('_strategy'):
            new_key = key.replace('_strategy', '')
            normalized[new_key] = value
        elif key.endswith('_benchmark'):
            normalized[key] = value
        else:
            normalized[key] = value
    
    # Also keep original names for compatibility
    normalized.update(raw_metrics)
    
    return normalized

class StrategyOptimizer:
    """Strategy Optimizer"""
    
    def __init__(self, data: pd.DataFrame, initial_capital: float = 1_000_000, 
                 transaction_cost: float = 0.0003):
        self.data = data.copy()
        self.initial_capital = initial_capital
        self.transaction_cost = transaction_cost
        self.results = {}
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: pd.Series, 
                       fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, prices: pd.Series, period: int = 20, 
                                  num_std: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands"""
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        return upper_band, sma, lower_band
    
    def test_ma_strategy(self, short_window: int, long_window: int, 
                        strategy_name: str = None, verbose: bool = False) -> Dict:
        """Test Moving Average strategy"""
        if strategy_name is None:
            strategy_name = f'MA{short_window}_{long_window}'
        
        df = self.data.copy()
        df[f'ma{short_window}'] = df['close'].rolling(window=short_window).mean()
        df[f'ma{long_window}'] = df['close'].rolling(window=long_window).mean()
        
        df['signal'] = 0
        df.loc[df[f'ma{short_window}'] > df[f'ma{long_window}'], 'signal'] = 1
        df['position'] = df['signal'].shift(1).fillna(0)
        df['trade'] = df['position'].diff().fillna(0)
        
        if not verbose:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                df = run_backtest(df, self.initial_capital, self.transaction_cost)
                metrics = calculate_all_metrics(df, self.initial_capital)
        else:
            df = run_backtest(df, self.initial_capital, self.transaction_cost)
            metrics = calculate_all_metrics(df, self.initial_capital)
        
        metrics['strategy_name'] = strategy_name
        metrics['parameters'] = {'short': short_window, 'long': long_window}
        
        self.results[strategy_name] = {'data': df, 'metrics': metrics}
        return metrics
    
    def test_rsi_strategy(self, rsi_period: int = 14, oversold: int = 30, 
                         overbought: int = 70, verbose: bool = False) -> Dict:
        """Test RSI strategy"""
        strategy_name = f'RSI_{rsi_period}_{oversold}_{overbought}'
        df = self.data.copy()
        df['rsi'] = self.calculate_rsi(df['close'], rsi_period)
        
        position = 0
        signals = []
        for i in range(len(df)):
            rsi_val = df['rsi'].iloc[i]
            if pd.notna(rsi_val):
                if rsi_val < oversold:
                    position = 1
                elif rsi_val > overbought:
                    position = 0
            signals.append(position)
        
        df['signal'] = signals
        df['position'] = df['signal'].shift(1).fillna(0)
        df['trade'] = df['position'].diff().fillna(0)
        
        if not verbose:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                df = run_backtest(df, self.initial_capital, self.transaction_cost)
                metrics = calculate_all_metrics(df, self.initial_capital)
        else:
            df = run_backtest(df, self.initial_capital, self.transaction_cost)
            metrics = calculate_all_metrics(df, self.initial_capital)
        
        metrics['strategy_name'] = strategy_name
        metrics['parameters'] = {'rsi_period': rsi_period, 'oversold': oversold, 'overbought': overbought}
        self.results[strategy_name] = {'data': df, 'metrics': metrics}
        return metrics
    
    def test_macd_strategy(self, fast: int = 12, slow: int = 26, signal: int = 9, verbose: bool = False) -> Dict:
        """Test MACD strategy"""
        strategy_name = f'MACD_{fast}_{slow}_{signal}'
        df = self.data.copy()
        
        macd_line, signal_line, histogram = self.calculate_macd(df['close'], fast, slow, signal)
        df['macd'] = macd_line
        df['macd_signal'] = signal_line
        df['macd_hist'] = histogram
        
        df['signal'] = 0
        df.loc[df['macd'] > df['macd_signal'], 'signal'] = 1
        df['position'] = df['signal'].shift(1).fillna(0)
        df['trade'] = df['position'].diff().fillna(0)
        
        if not verbose:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                df = run_backtest(df, self.initial_capital, self.transaction_cost)
                metrics = calculate_all_metrics(df, self.initial_capital)
        else:
            df = run_backtest(df, self.initial_capital, self.transaction_cost)
            metrics = calculate_all_metrics(df, self.initial_capital)
        
        metrics['strategy_name'] = strategy_name
        metrics['parameters'] = {'fast': fast, 'slow': slow, 'signal': signal}
        self.results[strategy_name] = {'data': df, 'metrics': metrics}
        return metrics
    
    def test_ma_rsi_combined(self, ma_short: int = 10, ma_long: int = 30, 
                            rsi_period: int = 14, rsi_threshold: int = 70, verbose: bool = False) -> Dict:
        """Test MA + RSI combined strategy"""
        strategy_name = f'MA{ma_short}_{ma_long}_RSI{rsi_period}'
        df = self.data.copy()
        
        df[f'ma{ma_short}'] = df['close'].rolling(window=ma_short).mean()
        df[f'ma{ma_long}'] = df['close'].rolling(window=ma_long).mean()
        df['rsi'] = self.calculate_rsi(df['close'], rsi_period)
        
        df['ma_signal'] = 0
        df.loc[df[f'ma{ma_short}'] > df[f'ma{ma_long}'], 'ma_signal'] = 1
        df['signal'] = 0
        df.loc[(df['ma_signal'] == 1) & (df['rsi'] < rsi_threshold), 'signal'] = 1
        df['position'] = df['signal'].shift(1).fillna(0)
        df['trade'] = df['position'].diff().fillna(0)
        
        if not verbose:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                df = run_backtest(df, self.initial_capital, self.transaction_cost)
                metrics = calculate_all_metrics(df, self.initial_capital)
        else:
            df = run_backtest(df, self.initial_capital, self.transaction_cost)
            metrics = calculate_all_metrics(df, self.initial_capital)
        
        metrics['strategy_name'] = strategy_name
        metrics['parameters'] = {'ma_short': ma_short, 'ma_long': ma_long, 'rsi_period': rsi_period, 'rsi_threshold': rsi_threshold}
        self.results[strategy_name] = {'data': df, 'metrics': metrics}
        return metrics
    
    def test_bollinger_band_strategy(self, period: int = 20, num_std: float = 2, verbose: bool = False) -> Dict:
        """Test Bollinger Band strategy"""
        strategy_name = f'BB_{period}_{num_std}'
        df = self.data.copy()
        
        upper, middle, lower = self.calculate_bollinger_bands(df['close'], period, num_std)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        
        position = 0
        signals = []
        for i in range(len(df)):
            close = df['close'].iloc[i]
            lower_band = df['bb_lower'].iloc[i]
            upper_band = df['bb_upper'].iloc[i]
            
            if pd.notna(lower_band) and pd.notna(upper_band):
                if close <= lower_band:
                    position = 1
                elif close >= upper_band:
                    position = 0
            signals.append(position)
        
        df['signal'] = signals
        df['position'] = df['signal'].shift(1).fillna(0)
        df['trade'] = df['position'].diff().fillna(0)
        
        if not verbose:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                df = run_backtest(df, self.initial_capital, self.transaction_cost)
                metrics = calculate_all_metrics(df, self.initial_capital)
        else:
            df = run_backtest(df, self.initial_capital, self.transaction_cost)
            metrics = calculate_all_metrics(df, self.initial_capital)
        
        metrics['strategy_name'] = strategy_name
        metrics['parameters'] = {'period': period, 'num_std': num_std}
        self.results[strategy_name] = {'data': df, 'metrics': metrics}
        return metrics
    
    def run_all_strategies(self) -> pd.DataFrame:
        """Run all strategies"""
        all_metrics = []
        
        print("Testing multiple strategies...")
        print("=" * 80)
        
        print("\n1. Testing MA combinations...")
        for short, long in [(5, 20), (10, 30), (20, 60), (10, 50)]:
            print(f"   Testing MA{short}/{long}...", end='')
            metrics = self.test_ma_strategy(short, long, verbose=False)
            all_metrics.append(metrics)
            print(f" Done (Sharpe: {metrics.get('sharpe_ratio', 0):.4f})")
        
        print("\n2. Testing RSI strategy...", end='')
        metrics = self.test_rsi_strategy(14, 30, 70, verbose=False)
        all_metrics.append(metrics)
        print(f" Done (Sharpe: {metrics.get('sharpe_ratio', 0):.4f})")
        
        print("\n3. Testing MACD strategy...", end='')
        metrics = self.test_macd_strategy(12, 26, 9, verbose=False)
        all_metrics.append(metrics)
        print(f" Done (Sharpe: {metrics.get('sharpe_ratio', 0):.4f})")
        
        print("\n4. Testing MA+RSI combined...", end='')
        metrics = self.test_ma_rsi_combined(10, 30, 14, 70, verbose=False)
        all_metrics.append(metrics)
        print(f" Done (Sharpe: {metrics.get('sharpe_ratio', 0):.4f})")
        
        print("\n5. Testing Bollinger Bands...", end='')
        metrics = self.test_bollinger_band_strategy(20, 2, verbose=False)
        all_metrics.append(metrics)
        print(f" Done (Sharpe: {metrics.get('sharpe_ratio', 0):.4f})")
        
        print("\n" + "=" * 80)
        print("All strategies tested!")
        
        results_df = pd.DataFrame(all_metrics)
        results_df = results_df.sort_values('sharpe_ratio', ascending=False)
        return results_df

if __name__ == '__main__':
    print("Strategy optimization module loaded")
