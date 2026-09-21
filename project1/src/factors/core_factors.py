import pandas as pd
import numpy as np
from src.factors.base_factor import BaseFactor

class MOM20Factor(BaseFactor):
    def __init__(self):
        super().__init__(name="MOM20", direction=1)
        
    def calculate_raw(self, df: pd.DataFrame) -> pd.Series:
        """
        MOM20_t = close_adj_t / close_adj_(t-20) - 1
        Higher is better.
        """
        # Data is already grouped by asset in run_phase_f1.py
        # Or we can do the groupby inside calculate_raw to be safe.
        # But we assume the caller passes data sorted by date for a single asset, 
        # or we do the groupby here. 
        # It's safer to groupby here.
        def _calc(g):
            return g['close_adj'] / g['close_adj'].shift(20) - 1.0
            
        return df.groupby('asset', group_keys=False).apply(_calc)

class REV5Factor(BaseFactor):
    def __init__(self):
        # direction = 1 because the formula in the plan includes the negative sign already.
        # Plan: REV5_t = -(close_adj_t / close_adj_(t-5) - 1)
        # 越高越好
        super().__init__(name="REV5", direction=1)
        
    def calculate_raw(self, df: pd.DataFrame) -> pd.Series:
        def _calc(g):
            return -(g['close_adj'] / g['close_adj'].shift(5) - 1.0)
            
        return df.groupby('asset', group_keys=False).apply(_calc)

class LOWVOL20Factor(BaseFactor):
    def __init__(self):
        # direction = 1 because the formula includes negative sign
        # Plan: LOWVOL20_t = -std(return over past 20 trading days)
        # 越高越好
        super().__init__(name="LOWVOL20", direction=1)
        
    def calculate_raw(self, df: pd.DataFrame) -> pd.Series:
        def _calc(g):
            # standard deviation of ret_total over past 20 days
            # ddof=1 for sample std
            return -g['ret_total'].rolling(window=20, min_periods=20).std(ddof=1)
            
        return df.groupby('asset', group_keys=False).apply(_calc)

