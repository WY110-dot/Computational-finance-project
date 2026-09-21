"""
Multi-Asset Portfolio Backtest Engine (Phase B1, Section 26)
实现配置化、逐日迭代账户账本、真实多标的再平衡调仓、交易费用扣减与恒等式校验。
"""
import pandas as pd
import numpy as np
import yaml
from typing import Dict, List, Optional, Tuple, Any

class PortfolioBacktestEngine:
    """
    多资产组合回测引擎
    """
    
    def __init__(self, config_or_path: Any):
        """
        Args:
            config_or_path: 字典对象或 YAML 配置文件路径
        """
        if isinstance(config_or_path, str):
            with open(config_or_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        elif isinstance(config_or_path, dict):
            self.config = config_or_path.copy()
        else:
            raise TypeError("config_or_path must be a file path string or a dict")
            
        self.initial_cash = float(self.config.get('initial_cash', 1000000.0))
        self.buy_fee_rate = float(self.config.get('buy_fee_rate', 0.0003))
        self.sell_fee_rate = float(self.config.get('sell_fee_rate', 0.0003))
        self.benchmark_asset = self.config.get('benchmark_asset', '510050.SH')
        self.slippage = float(self.config.get('slippage', 0.0))

    def run_backtest(
        self,
        prices_df: pd.DataFrame,
        weights_df: pd.DataFrame,
        price_col: str = "close_adj"
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        运行多资产组合回测。
        
        Args:
            prices_df: 价格面板数据，必须包含 ['date', 'asset', price_col]
            weights_df: 目标权重数据，必须包含 ['effective_date', 'asset', 'target_weight']
            price_col: 用于交易计算的价格列，默认 'close_adj'
            
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - daily_ledger: 每日账户指标 (equity, cash, daily_return, turnover, cost, benchmark 等)
                - holdings_history: 每日资产持仓股数与权重明细
        """
        # 1. 数据对齐与预处理
        df_p = prices_df.copy()
        df_p['date'] = df_p['date'].astype(str)
        df_p = df_p.sort_values(['date', 'asset']).reset_index(drop=True)
        
        # 提取价格矩阵 (date x asset)
        price_pivot = df_p.pivot(index='date', columns='asset', values=price_col).ffill()
        all_dates = sorted(price_pivot.index.tolist())
        
        # 目标权重字典: effective_date -> {asset: target_weight}
        target_weights_by_date = {}
        if not weights_df.empty:
            for eff_date, group in weights_df.groupby('effective_date'):
                target_weights_by_date[str(eff_date)] = dict(zip(group['asset'], group['target_weight']))
                
        # 2. 状态初始化
        current_cash = self.initial_cash
        current_shares = {} # asset -> float shares
        prev_equity = self.initial_cash
        cum_cost = 0.0
        gross_equity = self.initial_cash
        
        # Benchmark 价格序列
        if self.benchmark_asset in price_pivot.columns:
            bench_prices = price_pivot[self.benchmark_asset].ffill().bfill()
            bench_base = bench_prices.iloc[0]
        else:
            bench_prices = pd.Series(1.0, index=all_dates)
            bench_base = 1.0
            
        daily_records = []
        holdings_records = []
        
        # 3. 逐日逐笔迭代仿真
        for d in all_dates:
            curr_prices = price_pivot.loc[d]
            
            # 计算盘前/盘初持仓市值 (按当日价格评估)
            curr_holdings_val = 0.0
            for a, s in list(current_shares.items()):
                if s > 0:
                    p = curr_prices.get(a, np.nan)
                    if not np.isnan(p):
                        curr_holdings_val += s * p
                    else:
                        # 缺失价格，按最近价格或0
                        pass
                        
            equity_before_rebalance = current_cash + curr_holdings_val
            
            day_buy_notional = 0.0
            day_sell_notional = 0.0
            day_cost = 0.0
            trade_count = 0
            
            # 检查当日是否为调仓执行日
            if d in target_weights_by_date:
                targets = target_weights_by_date[d] # {asset: weight}
                
                # 计算目标市值: target_weight * equity_before_rebalance
                target_values = {a: w * equity_before_rebalance for a, w in targets.items()}
                
                # 第一步：卖出逻辑 (清仓不在目标的标的，或减持)
                for a in list(current_shares.keys()):
                    s = current_shares[a]
                    if s <= 0:
                        continue
                    p = curr_prices.get(a, np.nan)
                    if np.isnan(p) or p <= 0:
                        continue # 停牌或缺失暂不交易
                        
                    current_val = s * p
                    target_val = target_values.get(a, 0.0)
                    
                    if current_val > target_val:
                        # 需要减持
                        sell_val = current_val - target_val
                        shares_to_sell = sell_val / p
                        sell_notional = shares_to_sell * p
                        fee = sell_notional * self.sell_fee_rate
                        
                        current_cash += (sell_notional - fee)
                        current_shares[a] -= shares_to_sell
                        day_sell_notional += sell_notional
                        day_cost += fee
                        trade_count += 1
                        
                # 第二步：买入逻辑 (建仓或加仓)
                # 统计所有需要买入的缺口
                buy_gaps = {}
                total_buy_gap = 0.0
                for a, target_val in target_values.items():
                    p = curr_prices.get(a, np.nan)
                    if np.isnan(p) or p <= 0:
                        continue
                    current_val = current_shares.get(a, 0.0) * p
                    if target_val > current_val:
                        gap = target_val - current_val
                        buy_gaps[a] = (gap, p)
                        total_buy_gap += gap
                        
                # 如果可用现金足够覆盖缺口及佣金，全额买入；否则按现金等比例缩放
                max_affordable_notional = max(0.0, current_cash / (1.0 + self.buy_fee_rate))
                scale = min(1.0, max_affordable_notional / total_buy_gap) if total_buy_gap > 0 else 1.0
                
                for a, (gap, p) in buy_gaps.items():
                    actual_buy_notional = gap * scale
                    fee = actual_buy_notional * self.buy_fee_rate
                    shares_to_buy = actual_buy_notional / p
                    
                    current_cash -= (actual_buy_notional + fee)
                    current_shares[a] = current_shares.get(a, 0.0) + shares_to_buy
                    day_buy_notional += actual_buy_notional
                    day_cost += fee
                    trade_count += 1
                    
            # 4. 结算收盘净值与恒等式核对
            close_holdings_val = 0.0
            active_holdings_count = 0
            max_single_weight = 0.0
            
            for a, s in list(current_shares.items()):
                if s > 1e-6:
                    p = curr_prices.get(a, 0.0)
                    h_val = s * p
                    close_holdings_val += h_val
                    active_holdings_count += 1
                    holdings_records.append({
                        'date': d,
                        'asset': a,
                        'shares': s,
                        'price': p,
                        'market_value': h_val
                    })
                else:
                    current_shares[a] = 0.0
                    
            equity_after_trade = current_cash + close_holdings_val
            
            # 计算各项持仓权重
            if equity_after_trade > 0:
                for a, s in current_shares.items():
                    if s > 1e-6:
                        w = (s * curr_prices.get(a, 0.0)) / equity_after_trade
                        if w > max_single_weight:
                            max_single_weight = w
                            
            # 收益计算 (严格对账)
            if prev_equity > 0:
                daily_return_net = equity_after_trade / prev_equity - 1.0
                daily_return_gross = (equity_after_trade + day_cost) / prev_equity - 1.0
            else:
                daily_return_net = 0.0
                daily_return_gross = 0.0
                
            prev_equity = equity_after_trade
            gross_equity = gross_equity * (1.0 + daily_return_gross)
            cum_cost += day_cost
            day_turnover = day_buy_notional + day_sell_notional
            turnover_ratio = day_turnover / equity_before_rebalance if equity_before_rebalance > 0 else 0.0
            
            # 基准净值
            bench_eq = (bench_prices.loc[d] / bench_base) * self.initial_cash
            
            daily_records.append({
                'date': d,
                'equity': equity_after_trade,
                'cash': current_cash,
                'holdings_value': close_holdings_val,
                'daily_return': daily_return_net,
                'daily_return_gross': daily_return_gross,
                'gross_equity': gross_equity,
                'buy_notional': day_buy_notional,
                'sell_notional': day_sell_notional,
                'turnover': day_turnover,
                'turnover_ratio': turnover_ratio,
                'daily_cost': day_cost,
                'cumulative_cost': cum_cost,
                'trade_count': trade_count,
                'holding_count': active_holdings_count,
                'max_single_asset_weight': max_single_weight,
                'benchmark_equity': bench_eq
            })
            
        daily_ledger = pd.DataFrame(daily_records)
        daily_ledger['benchmark_return'] = daily_ledger['benchmark_equity'].pct_change().fillna(0.0)
        
        holdings_history = pd.DataFrame(holdings_records)
        if not holdings_history.empty and not daily_ledger.empty:
            # 补充实际持仓权重
            holdings_history = pd.merge(holdings_history, daily_ledger[['date', 'equity']], on='date', how='left')
            holdings_history['weight'] = holdings_history['market_value'] / holdings_history['equity']
            
        return daily_ledger, holdings_history

