"""
Phase 2 Execution Script
Execute data download and quality check
"""
import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

print("\n" + "="*80)
print(" "*20 + "PHASE 2: DATA COLLECTION & QUALITY CHECK")
print("="*80)

# Step 1: Test Tushare connection
print("\n[Step 1/3] Testing Tushare Connection...")
print("-"*80)

try:
    from src.data.tushare_connector import TushareConnector
    
    connector = TushareConnector()
    if connector.test_connection():
        print("[OK] Tushare connection successful\n")
    else:
        print("[ERROR] Tushare connection failed\n")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] Error: {str(e)}\n")
    print("Please ensure you have set TUSHARE_TOKEN in .env file")
    sys.exit(1)

# Step 2: Download data
print("\n[Step 2/3] Downloading 510050.SH Data...")
print("-"*80)

try:
    from src.data.data_downloader import DataDownloader
    
    downloader = DataDownloader()
    # Use fixed end date to avoid future date issue
    df = downloader.download_etf_data(
        ts_code="510050.SH",
        start_date="20200101",
        end_date="20240917",  # Fixed date
        save_csv=True
    )
    
    if df.empty:
        print("[ERROR] No data downloaded\n")
        sys.exit(1)
    
    print(f"\n[OK] Downloaded {len(df)} records\n")
    
except Exception as e:
    print(f"[ERROR] Download error: {str(e)}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Quality check
print("\n[Step 3/3] Running Data Quality Checks...")
print("-"*80)

try:
    from src.data.data_quality import DataQualityChecker
    
    checker = DataQualityChecker()
    results = checker.check_all(df, ts_code="510050.SH")
    
    # Save report
    report_dir = Path(__file__).parent / "data" / "processed"
    checker.save_report(results, report_dir)
    
    print("[OK] Quality check completed\n")
    
except Exception as e:
    print(f"[ERROR] Quality check error: {str(e)}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Phase 2 Complete
print("\n" + "="*80)
print(" "*30 + "PHASE 2 COMPLETE!")
print("="*80)
print("\nSummary:")
print(f"  - Data source: Tushare")
print(f"  - Security: 510050.SH (SSE 50 ETF)")
print(f"  - Records downloaded: {len(df)}")
print(f"  - Date range: {df['trade_date'].min()} to {df['trade_date'].max()}")
print(f"  - Quality status: {results['status']}")
print(f"  - Errors: {results['total_errors']}")
print(f"  - Warnings: {results['total_warnings']}")
print("\nNext steps:")
print("  - Review quality report in data/processed/")
print("  - Proceed to Phase 3: Factor Engineering (MA5, MA20)")
print("="*80 + "\n")

sys.exit(0 if results['status'] != 'FAIL' else 1)
