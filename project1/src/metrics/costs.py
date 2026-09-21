"""
Costs Calculation Module (Phase C3)
交易成本计算模块：重构成本模型，精准计算名义本金和实际手续费。
"""
import pandas as pd
import numpy as np

class CostCalculator:
    """
    成本计算器：
    实现 Phase C3 要求的严格成本口径：
    Cost_t = buy_fee_rate * buy_notional_t + sell_fee_rate * sell_notional_t
    记录：buy_notional, sell_notional, buy_cost, sell_cost, total_cost, turnover
    """

    @staticmethod
    def calculate_costs_and_net_returns(
        df: pd.DataFrame, 
        buy_fee_rate: float = 0.0003, 
        sell_fee_rate: float = 0.0003
    ) -> pd.DataFrame:
        """
        计算考虑真实交易成本后的净收益。
        
        依赖列:
        - position: 当日持仓 (0或1)
        - ret_total: 当日资产本身的收益率
        - trade: 当日交易动作 (1买入, -1卖出, 0无)
        
        生成列:
        - strategy_return_net: 扣除成本后的真实净收益率
        - 各种 cost 和 notional 统计将在引擎级的 equity 曲线生成后补全，
          因为 notional 依赖于绝对资金量。但收益率可以向量化先算出来。
        """
        df = df.copy()
        
        # 确保必需列存在
        for col in ['position', 'ret_total', 'trade']:
            if col not in df.columns:
                raise ValueError(f"Missing required column for cost calculation: {col}")

        # 计算扣费后的真实策略日收益率 (向量化)
        # 1. trade == 1 (买入): 净收益 = (1 - buy_fee) * (1 + ret_total) - 1
        # 2. trade == -1 (卖出): 净收益 = (1 - sell_fee) - 1 = -sell_fee  (因为不享受当日涨幅)
        # 3. trade == 0 & position == 1: 净收益 = ret_total
        # 4. trade == 0 & position == 0: 净收益 = 0
        
        # 默认等于毛收益
        if 'strategy_return_gross' in df.columns:
            strategy_return = df['strategy_return_gross'].copy()
        else:
            strategy_return = df['position'] * df['ret_total']
            
        # 买入日
        buy_mask = (df['trade'] == 1)
        strategy_return.loc[buy_mask] = (1 - buy_fee_rate) * (1 + df.loc[buy_mask, 'ret_total']) - 1
        
        # 卖出日
        sell_mask = (df['trade'] == -1)
        strategy_return.loc[sell_mask] = -sell_fee_rate
        
        df['strategy_return'] = strategy_return
        
        return df

    @staticmethod
    def compute_daily_cost_metrics(
        df: pd.DataFrame, 
        initial_capital: float,
        buy_fee_rate: float = 0.0003, 
        sell_fee_rate: float = 0.0003
    ) -> pd.DataFrame:
        """
        基于绝对资金曲线（equity），计算每日具体的名义本金和绝对成本金额。
        
        依赖列:
        - trade
        - strategy_equity (由引擎通过 cumprod 算出)
        """
        df = df.copy()
        
        # equity_before_trade 是前一天的 equity
        # 第一天的 equity_before_trade 是 initial_capital
        equity_shifted = df['strategy_equity'].shift(1).fillna(initial_capital)
        df['equity_before_trade'] = equity_shifted
        
        # Notional (名义本金)
        df['buy_notional'] = 0.0
        df['sell_notional'] = 0.0
        
        buy_mask = (df['trade'] == 1)
        sell_mask = (df['trade'] == -1)
        
        df.loc[buy_mask, 'buy_notional'] = df.loc[buy_mask, 'equity_before_trade']
        df.loc[sell_mask, 'sell_notional'] = df.loc[sell_mask, 'equity_before_trade']
        
        # Costs
        df['buy_cost'] = df['buy_notional'] * buy_fee_rate
        df['sell_cost'] = df['sell_notional'] * sell_fee_rate
        df['total_cost'] = df['buy_cost'] + df['sell_cost']
        
        # Turnover
        df['turnover'] = df['buy_notional'] + df['sell_notional']
        
        return df

