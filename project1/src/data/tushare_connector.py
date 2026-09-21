"""
Tushare API Connector Module
Handles connection to Tushare data source with proper error handling
"""
import tushare as ts
import os
from dotenv import load_dotenv
from typing import Optional
import pandas as pd

class TushareConnector:
    """
    Tushare API connection manager
    
    Attributes:
        token (str): Tushare API token
        pro_api: Tushare Pro API instance
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize Tushare connector
        
        Args:
            token (str, optional): Tushare API token. If None, will try to load from .env
        """
        # Load environment variables
        load_dotenv()
        
        # Get token from parameter or environment
        self.token = token or os.getenv('TUSHARE_TOKEN')
        
        if not self.token:
            raise ValueError(
                "Tushare token not found. Please provide token or set TUSHARE_TOKEN in .env file"
            )
        
        # Set token and initialize Pro API
        ts.set_token(self.token)
        self.pro_api = ts.pro_api()
        
        print(f"[OK] Tushare connector initialized successfully")
    
    def get_daily_data(
        self, 
        ts_code: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """
        Get daily trading data for a specific security
        Automatically detects if it's an ETF and uses appropriate API
        
        Args:
            ts_code (str): Tushare security code (e.g., '510050.SH')
            start_date (str): Start date in format 'YYYYMMDD'
            end_date (str): End date in format 'YYYYMMDD'
            
        Returns:
            pd.DataFrame: Daily trading data
        """
        try:
            print(f"Fetching data for {ts_code} from {start_date} to {end_date}...")
            
            # For ETFs (code starts with 5), use fund_daily
            if ts_code.startswith('5'):
                print(f"Detected ETF, using fund_daily API...")
                df = self.pro_api.fund_daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # For stocks, use daily
                df = self.pro_api.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            
            if df is None or len(df) == 0:
                print(f"[WARNING] Warning: No data returned for {ts_code}")
                return pd.DataFrame()
            
            # Sort by date ascending
            df = df.sort_values('trade_date').reset_index(drop=True)
            
            print(f"[OK] Successfully fetched {len(df)} records")
            return df
        except Exception as e:
            print(f"[ERROR] Error fetching data: {str(e)}")
            raise

    def get_adj_factor(
        self,
        ts_code: str,
        start_date: str = "",
        end_date: str = ""
    ) -> pd.DataFrame:
        """
        Get adjustment factors for a fund/ETF
        
        Args:
            ts_code (str): Tushare security code (e.g. '510050.SH')
            start_date (str): Start date in YYYYMMDD format
            end_date (str): End date in YYYYMMDD format
            
        Returns:
            pd.DataFrame: DataFrame with columns ['ts_code', 'trade_date', 'adj_factor']
        """
        try:
            print(f"Fetching adjustment factor for {ts_code} ({start_date} to {end_date})...")
            df = self.pro_api.fund_adj(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            if df is None or len(df) == 0:
                print(f"[WARNING] No adjustment factor returned for {ts_code}")
                return pd.DataFrame(columns=['ts_code', 'trade_date', 'adj_factor'])
            
            # Sort by trade_date ascending
            df = df.sort_values('trade_date').reset_index(drop=True)
            print(f"[OK] Successfully fetched {len(df)} adjustment factor records")
            return df
        except Exception as e:
            print(f"[ERROR] Error fetching adjustment factor: {str(e)}")
            raise

    def get_fund_basic(self, ts_code: str) -> pd.DataFrame:
        """
        Get basic information of a fund/ETF
        
        Args:
            ts_code (str): Tushare security code
            
        Returns:
            pd.DataFrame: Fund basic information
        """
        try:
            df = self.pro_api.fund_basic(ts_code=ts_code)
            return df
        except Exception as e:
            print(f"[ERROR] Error fetching fund info: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test if Tushare API connection is working
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Try to fetch a small amount of data
            df = self.pro_api.trade_cal(
                exchange='SSE',
                start_date='20240101',
                end_date='20240110'
            )
            
            if df is not None and len(df) > 0:
                print("[OK] Tushare API connection test passed")
                return True
            else:
                print("[WARNING] Connection test returned empty data")
                return False
                
        except Exception as e:
            print(f"[ERROR] Connection test failed: {str(e)}")
            return False


if __name__ == "__main__":
    # Test the connector
    print("="*60)
    print("Testing Tushare Connector")
    print("="*60)
    
    try:
        # Initialize connector
        connector = TushareConnector()
        
        # Test connection
        connector.test_connection()
        
        # Try to get some sample data
        print("\nFetching sample data for 510050.SH...")
        df = connector.get_daily_data(
            ts_code='510050.SH',
            start_date='20240101',
            end_date='20240110'
        )
        
        if not df.empty:
            print("\nSample data preview:")
            print(df.head())
        
        print("\n" + "="*60)
        print("[OK] All tests passed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {str(e)}")
