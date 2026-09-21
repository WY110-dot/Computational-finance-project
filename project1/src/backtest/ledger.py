import pandas as pd
import numpy as np

class AccountLedger:
    """
    账户账本 (Phase C4)
    使用逐日迭代计算，严格跟踪资金、持仓、名义本金和实际手续费扣除。
    完全遵守恒等式：equity = cash + holdings market value
    """
    
    def __init__(self, initial_capital: float = 1000000.0, buy_fee_rate: float = 0.0003, sell_fee_rate: float = 0.0003):
        self.initial_capital = initial_capital
        self.buy_fee_rate = buy_fee_rate
        self.sell_fee_rate = sell_fee_rate

    def run_ledger_simulation(self, df: pd.DataFrame, price_col: str = 'close_adj', position_col: str = 'position') -> pd.DataFrame:
        """
        运行账本模拟
        
        Args:
            df: 必须包含 price_col 和 position_col(0或1目标持仓)
        """
        df = df.copy()
        
        # 结果列表
        records = []
        
        current_cash = self.initial_capital
        current_shares = 0.0
        prev_equity_after_trade = self.initial_capital
        
        for idx, row in df.iterrows():
            date = row.get('trade_date', idx)
            price = row[price_col]
            target_pos = row[position_col]
            
            # 1. 盘前/交易前状态评估
            holdings_value = current_shares * price
            equity_before_trade = current_cash + holdings_value
            
            buy_notional = 0.0
            sell_notional = 0.0
            cost = 0.0
            trade_action = 0
            
            # 2. 交易决策执行
            # 假设全仓买入/清仓卖出
            if target_pos == 1.0 and current_shares == 0.0:
                # 全仓买入：扣除手续费后能够买入的市值
                # cash = notional + notional * fee_rate
                # notional = cash / (1 + fee_rate)
                buy_notional = current_cash / (1 + self.buy_fee_rate)
                cost = buy_notional * self.buy_fee_rate
                shares_bought = buy_notional / price
                
                current_cash = current_cash - buy_notional - cost # 理论上=0
                current_shares = shares_bought
                trade_action = 1
                
            elif target_pos == 0.0 and current_shares > 0.0:
                # 全部卖出
                sell_notional = current_shares * price
                cost = sell_notional * self.sell_fee_rate
                
                current_cash = current_cash + sell_notional - cost
                current_shares = 0.0
                trade_action = -1
                
            # 3. 交易后状态更新
            holdings_value_after = current_shares * price
            equity_after_trade = current_cash + holdings_value_after
            
            # 4. 计算当日收益
            daily_return = equity_after_trade / prev_equity_after_trade - 1.0
            prev_equity_after_trade = equity_after_trade
            
            # 5. 记录
            records.append({
                'trade_date': date,
                'price': price,
                'cash': current_cash,
                'shares': current_shares,
                'holdings_value': holdings_value_after,
                'equity_before_trade': equity_before_trade,
                'trade': trade_action,
                'buy_notional': buy_notional,
                'sell_notional': sell_notional,
                'buy_cost': cost if trade_action == 1 else 0.0,
                'sell_cost': cost if trade_action == -1 else 0.0,
                'cost': cost,
                'turnover': buy_notional + sell_notional,
                'equity_after_trade': equity_after_trade,
                'daily_return': daily_return
            })
            
        ledger_df = pd.DataFrame(records)
        
        # 将原始 df 的其他信息合并过来
        for col in df.columns:
            if col not in ledger_df.columns:
                ledger_df[col] = df[col].values
                
        # 兼容旧引擎字段
        ledger_df['strategy_equity'] = ledger_df['equity_after_trade']
        ledger_df['strategy_return'] = ledger_df['daily_return']
        ledger_df['total_cost'] = ledger_df['cost']
        
        return ledger_df
