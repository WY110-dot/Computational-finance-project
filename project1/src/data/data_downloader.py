"""
Data Downloader Module
Downloads historical data for 510050.SH and saves to CSV
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional
import sys
import os

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from tushare_connector import TushareConnector
from adjustment import ETFAdjuster


class DataDownloader:
    """
    Download and save market data for quantitative analysis
    """
    
    def __init__(self, data_dir: str = "../../data/raw"):
        """
        Initialize data downloader
        
        Args:
            data_dir (str): Directory to save raw data
        """
        self.data_dir = Path(__file__).parent.parent.parent / "data" / "raw"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Tushare connector
        self.connector = TushareConnector()
    
    def download_etf_data(
        self,
        ts_code: str = "510050.SH",
        start_date: str = "20200101",
        end_date: str = None,
        save_csv: bool = True
    ) -> pd.DataFrame:
        """
        Download ETF daily trading data
        
        Args:
            ts_code (str): ETF code, default is 510050.SH (SSE 50 ETF)
            start_date (str): Start date in YYYYMMDD format
            end_date (str): End date in YYYYMMDD format, default is today
            save_csv (bool): Whether to save data to CSV file
            
        Returns:
            pd.DataFrame: Downloaded data
        """
        # Set end_date to today if not provided
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        
        print(f"\n{'='*60}")
        print(f"Downloading {ts_code} data")
        print(f"Period: {start_date} to {end_date}")
        print(f"{'='*60}\n")
        
        # Download data
        df = self.connector.get_daily_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if df.empty:
            print("[WARNING] No data downloaded!")
            return df
        
        # Add metadata columns
        df['download_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df['data_source'] = 'Tushare'
        
        # Data info
        print(f"\n[OK] Downloaded {len(df)} trading days")
        print(f"  Date range: {df['trade_date'].min()} to {df['trade_date'].max()}")
        print(f"  Columns: {list(df.columns)}")
        
        # Save to CSV if requested
        if save_csv:
            filename = f"{ts_code.replace('.', '_')}_{start_date}_{end_date}.csv"
            filepath = self.data_dir / filename
            
            df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"\n[OK] Data saved to: {filepath}")
            print(f"  File size: {filepath.stat().st_size / 1024:.2f} KB")
        
        return df
    
    def download_multiple_periods(
        self,
        ts_code: str = "510050.SH",
        periods: list = None
    ):
        """
        Download data for multiple time periods
        
        Args:
            ts_code (str): ETF code
            periods (list): List of (start_date, end_date) tuples
        """
        if periods is None:
            # Default periods: recent years
            periods = [
                ("20200101", "20201231"),  # 2020
                ("20210101", "20211231"),  # 2021
                ("20220101", "20221231"),  # 2022
                ("20230101", "20231231"),  # 2023
                ("20240101", "20241231"),  # 2024
            ]
        
        all_data = []
        
        for start_date, end_date in periods:
            df = self.download_etf_data(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                save_csv=False
            )
            
            if not df.empty:
                all_data.append(df)
        
        # Combine all data
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['trade_date']).sort_values('trade_date')
            
            # Save combined data
            filename = f"{ts_code.replace('.', '_')}_combined.csv"
            filepath = self.data_dir / filename
            combined_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            print(f"\n{'='*60}")
            print(f"[OK] Combined data saved: {filepath}")
            print(f"  Total records: {len(combined_df)}")
            print(f"{'='*60}")
            
            return combined_df
        
        return pd.DataFrame()

    def download_adj_factor(
        self,
        ts_code: str = "510050.SH",
        start_date: str = "20200101",
        end_date: str = None,
        save_csv: bool = True
    ) -> pd.DataFrame:
        """
        Download ETF adjustment factor data
        
        Args:
            ts_code (str): ETF code
            start_date (str): Start date in YYYYMMDD format
            end_date (str): End date in YYYYMMDD format
            save_csv (bool): Whether to save data to CSV file
            
        Returns:
            pd.DataFrame: Adjustment factor data
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
            
        print(f"\nDownloading adjustment factor for {ts_code} from {start_date} to {end_date}...")
        df_adj = self.connector.get_adj_factor(ts_code, start_date=start_date, end_date=end_date)
        
        if not df_adj.empty and save_csv:
            filename = f"{ts_code.replace('.', '_')}_adj_factor_{start_date}_{end_date}.csv"
            filepath = self.data_dir / filename
            df_adj.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"[OK] Adjustment factor saved to: {filepath}")
            
        return df_adj

    def download_and_adjust_etf_data(
        self,
        ts_code: str = "510050.SH",
        start_date: str = "20200101",
        end_date: str = None,
        reference_date: str = None,
        save_processed: bool = True
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Download raw prices and adjustment factors, compute forward adjustment,
        and validate consistency.
        
        Args:
            ts_code: ETF code (e.g. '510050.SH')
            start_date: Start date YYYYMMDD
            end_date: End date YYYYMMDD
            reference_date: Reference date tau for forward adjustment
            save_processed: Whether to save processed DataFrame to data/processed
            
        Returns:
            Tuple[pd.DataFrame, Dict]: (Adjusted DataFrame, Diagnostic dict)
        """
        # 1. Download raw prices
        df_price = self.download_etf_data(ts_code=ts_code, start_date=start_date, end_date=end_date, save_csv=True)
        if df_price.empty:
            raise ValueError(f"No price data downloaded for {ts_code}")
            
        # 2. Download adjustment factors
        df_adj = self.download_adj_factor(ts_code=ts_code, start_date=start_date, end_date=end_date, save_csv=True)
        if df_adj.empty:
            raise ValueError(f"No adjustment factor downloaded for {ts_code}")
            
        # 3. Compute forward adjustment
        adjuster = ETFAdjuster(reference_date=reference_date)
        adjusted_df, diagnostics = adjuster.process_and_standardize(
            df_price, df_adj, reference_date=reference_date
        )
        
        # 4. Save processed file if requested
        if save_processed:
            processed_dir = Path(__file__).parent.parent.parent / "data" / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{ts_code.replace('.', '_')}_adjusted.csv"
            filepath = processed_dir / filename
            adjusted_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            print(f"[OK] Standardized adjusted data saved to: {filepath}")
            
        return adjusted_df, diagnostics


def main():
    """
    Main function to download data
    """
    print("\n" + "="*60)
    print("ETF Data Downloader - Phase 2")
    print("="*60)
    
    try:
        # Initialize downloader
        downloader = DataDownloader()
        
        # Download 510050.SH data from 2020 to now
        # This covers sufficient history for backtesting
        df = downloader.download_etf_data(
            ts_code="510050.SH",
            start_date="20200101",
            end_date=None,  # Will use today's date
            save_csv=True
        )
        
        if not df.empty:
            print("\n" + "="*60)
            print("Data Download Summary")
            print("="*60)
            print(f"Total trading days: {len(df)}")
            print(f"Start date: {df['trade_date'].min()}")
            print(f"End date: {df['trade_date'].max()}")
            print(f"\nFirst 5 rows:")
            print(df.head())
            print(f"\nLast 5 rows:")
            print(df.tail())
            print("\n[OK] Phase 2 - Data download completed successfully!")
        else:
            print("\n[WARNING] No data was downloaded")
        
    except Exception as e:
        print(f"\n[ERROR] Error during download: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
