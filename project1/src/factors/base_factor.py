from abc import ABC, abstractmethod
import pandas as pd
import numpy as np

class BaseFactor(ABC):
    """
    Abstract Base Class for all Alpha Factors.
    Enforces standardized output and evaluation.
    """
    
    def __init__(self, name: str, direction: int = 1):
        """
        Args:
            name: Name of the factor (e.g. MOM20)
            direction: 1 if higher value is better, -1 if lower value is better.
                       (Outputs will be standardized so higher is always better).
        """
        self.name = name
        self.direction = direction
        self.preprocessing_version = "v1.0"
        
    @abstractmethod
    def calculate_raw(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculates the raw factor value. 
        MUST NOT contain look-ahead bias.
        
        Args:
            df: DataFrame indexed/grouped by asset, containing 'close_adj' or 'ret_total'
            
        Returns:
            pd.Series containing the raw factor values
        """
        pass
        
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        End-to-end processing: calculates raw, applies direction, formats output,
        and applies cross-sectional rank preprocessing.
        """
        self.preprocessing_version = "v1.1_cs_rank"
        
        raw_values = self.calculate_raw(df)
        
        # Apply direction so that higher is always better
        aligned_values = raw_values * self.direction
        
        out = pd.DataFrame({
            'date': df['date'],
            'asset': df['asset'],
            'factor': self.name,
            'raw_value': raw_values,
            'aligned_value': aligned_values
        })
        
        # is_valid mask (no NaN filled with 0!)
        out['is_valid'] = out['aligned_value'].notna() & np.isfinite(out['aligned_value'])
        
        # 19. 因子预处理: Cross-sectional Rank
        # Calculate rank (0 to 1) per date for valid rows only
        def _rank(g):
            # pct=True gives values from 0.0 to 1.0
            return g.rank(pct=True, ascending=True)
            
        # Initialize 'value' with NaN
        out['value'] = np.nan
        
        # Apply ranking only on valid data, grouped by date
        valid_mask = out['is_valid']
        if valid_mask.any():
            out.loc[valid_mask, 'value'] = out.loc[valid_mask].groupby('date')['aligned_value'].transform(_rank)
            
        out['preprocessing_version'] = self.preprocessing_version
        
        # Drop temporary column
        out = out.drop(columns=['aligned_value'])
        
        # Ensure final column order matches Section 18
        out = out[['date', 'asset', 'factor', 'raw_value', 'value', 'is_valid', 'preprocessing_version']]
        
        return out

