"""
Data Quality Checker Module
Validates data integrity and generates quality report
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple


class DataQualityChecker:
    """
    Perform comprehensive data quality checks on downloaded market data
    """
    
    def __init__(self):
        """Initialize data quality checker"""
        self.report = []
        self.errors = []
        self.warnings = []
    
    def check_all(self, df: pd.DataFrame, ts_code: str = "510050.SH") -> Dict:
        """
        Run all quality checks on the dataframe
        
        Args:
            df (pd.DataFrame): Data to check
            ts_code (str): Security code for reporting
            
        Returns:
            Dict: Quality check results
        """
        print(f"\n{'='*60}")
        print(f"Data Quality Check for {ts_code}")
        print(f"{'='*60}\n")
        
        results = {
            'ts_code': ts_code,
            'check_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_records': len(df),
            'checks': []
        }
        
        # Run individual checks
        self._check_basic_info(df, results)
        self._check_missing_values(df, results)
        self._check_duplicates(df, results)
        self._check_date_continuity(df, results)
        self._check_price_validity(df, results)
        self._check_volume_validity(df, results)
        self._check_price_relationships(df, results)
        self._check_outliers(df, results)
        
        # Summary
        results['total_errors'] = len(self.errors)
        results['total_warnings'] = len(self.warnings)
        results['errors'] = self.errors
        results['warnings'] = self.warnings
        
        # Overall status
        if len(self.errors) == 0:
            results['status'] = 'PASS' if len(self.warnings) == 0 else 'PASS_WITH_WARNINGS'
        else:
            results['status'] = 'FAIL'
        
        self._print_summary(results)
        
        return results
    
    def _check_basic_info(self, df: pd.DataFrame, results: Dict):
        """Check basic dataframe information"""
        print("1. Basic Information Check")
        print(f"   Total records: {len(df)}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Memory usage: {df.memory_usage(deep=True).sum() / 1024:.2f} KB")
        print("   [OK] PASS\n")
        
        results['checks'].append({
            'name': 'Basic Info',
            'status': 'PASS',
            'details': f"{len(df)} records, {len(df.columns)} columns"
        })
    
    def _check_missing_values(self, df: pd.DataFrame, results: Dict):
        """Check for missing values"""
        print("2. Missing Values Check")
        
        missing = df.isnull().sum()
        missing_pct = (missing / len(df) * 100).round(2)
        
        has_missing = False
        for col, count in missing.items():
            if count > 0:
                has_missing = True
                msg = f"   [WARNING] Column '{col}' has {count} missing values ({missing_pct[col]}%)"
                print(msg)
                self.warnings.append(msg)
        
        if not has_missing:
            print("   [OK] No missing values found")
            status = 'PASS'
        else:
            status = 'WARNING'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Missing Values',
            'status': status,
            'details': missing[missing > 0].to_dict() if has_missing else 'No missing values'
        })
    
    def _check_duplicates(self, df: pd.DataFrame, results: Dict):
        """Check for duplicate dates"""
        print("3. Duplicate Dates Check")
        
        duplicates = df[df.duplicated(subset=['trade_date'], keep=False)]
        
        if len(duplicates) > 0:
            msg = f"   [ERROR] Found {len(duplicates)} duplicate date records"
            print(msg)
            self.errors.append(msg)
            status = 'FAIL'
        else:
            print("   [OK] No duplicate dates found")
            status = 'PASS'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Duplicate Dates',
            'status': status,
            'details': f"{len(duplicates)} duplicates found" if len(duplicates) > 0 else 'No duplicates'
        })
    
    def _check_date_continuity(self, df: pd.DataFrame, results: Dict):
        """Check date sequence and gaps"""
        print("4. Date Continuity Check")
        
        # Convert to datetime for checking
        df_sorted = df.sort_values('trade_date').copy()
        df_sorted['date'] = pd.to_datetime(df_sorted['trade_date'], format='%Y%m%d')
        
        # Check if sorted
        is_sorted = df_sorted['trade_date'].is_monotonic_increasing
        print(f"   Date order: {'[OK] Ascending' if is_sorted else '[WARNING] Not sorted'}")
        
        # Check date range
        date_min = df_sorted['trade_date'].min()
        date_max = df_sorted['trade_date'].max()
        print(f"   Date range: {date_min} to {date_max}")
        
        # Check for large gaps (more than 10 days)
        df_sorted['date_diff'] = df_sorted['date'].diff().dt.days
        large_gaps = df_sorted[df_sorted['date_diff'] > 10]
        
        if len(large_gaps) > 0:
            msg = f"   [WARNING] Found {len(large_gaps)} gaps larger than 10 days"
            print(msg)
            self.warnings.append(msg)
            status = 'WARNING'
        else:
            print("   [OK] No large gaps found")
            status = 'PASS'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Date Continuity',
            'status': status,
            'details': f"Range: {date_min} to {date_max}, {len(large_gaps)} large gaps"
        })
    
    def _check_price_validity(self, df: pd.DataFrame, results: Dict):
        """Check if prices are valid (positive, reasonable)"""
        print("5. Price Validity Check")
        
        price_cols = ['open', 'high', 'low', 'close', 'pre_close']
        issues = []
        
        for col in price_cols:
            if col in df.columns:
                # Check for non-positive prices
                non_positive = df[df[col] <= 0]
                if len(non_positive) > 0:
                    msg = f"   [ERROR] Column '{col}' has {len(non_positive)} non-positive values"
                    print(msg)
                    self.errors.append(msg)
                    issues.append(msg)
        
        if len(issues) == 0:
            print("   [OK] All prices are positive")
            status = 'PASS'
        else:
            status = 'FAIL'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Price Validity',
            'status': status,
            'details': issues if issues else 'All prices positive'
        })
    
    def _check_volume_validity(self, df: pd.DataFrame, results: Dict):
        """Check if volume and amount are valid"""
        print("6. Volume Validity Check")
        
        issues = []
        
        # Check for negative volume
        if 'vol' in df.columns:
            neg_vol = df[df['vol'] < 0]
            if len(neg_vol) > 0:
                msg = f"   [ERROR] Found {len(neg_vol)} negative volume records"
                print(msg)
                self.errors.append(msg)
                issues.append(msg)
        
        # Check for zero volume days (might be data issue or genuine)
        if 'vol' in df.columns:
            zero_vol = df[df['vol'] == 0]
            if len(zero_vol) > 0:
                msg = f"   [WARNING] Found {len(zero_vol)} zero volume records"
                print(msg)
                self.warnings.append(msg)
        
        if len(issues) == 0:
            print("   [OK] Volume data looks valid")
            status = 'PASS'
        else:
            status = 'FAIL'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Volume Validity',
            'status': status,
            'details': issues if issues else 'Volume data valid'
        })
    
    def _check_price_relationships(self, df: pd.DataFrame, results: Dict):
        """Check if high >= low, high >= close, etc."""
        print("7. Price Relationship Check")
        
        issues = []
        
        # Check high >= low
        invalid_hl = df[df['high'] < df['low']]
        if len(invalid_hl) > 0:
            msg = f"   [ERROR] Found {len(invalid_hl)} records where high < low"
            print(msg)
            self.errors.append(msg)
            issues.append(msg)
        
        # Check high >= close
        invalid_hc = df[df['high'] < df['close']]
        if len(invalid_hc) > 0:
            msg = f"   [ERROR] Found {len(invalid_hc)} records where high < close"
            print(msg)
            self.errors.append(msg)
            issues.append(msg)
        
        # Check low <= close
        invalid_lc = df[df['low'] > df['close']]
        if len(invalid_lc) > 0:
            msg = f"   [ERROR] Found {len(invalid_lc)} records where low > close"
            print(msg)
            self.errors.append(msg)
            issues.append(msg)
        
        if len(issues) == 0:
            print("   [OK] All price relationships are valid")
            status = 'PASS'
        else:
            status = 'FAIL'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Price Relationships',
            'status': status,
            'details': issues if issues else 'All relationships valid'
        })
    
    def _check_outliers(self, df: pd.DataFrame, results: Dict):
        """Check for potential outliers in price changes"""
        print("8. Outlier Detection")
        
        if 'pct_chg' in df.columns:
            # Check for extreme daily changes (e.g., > 10% which is unusual for ETF)
            extreme_changes = df[abs(df['pct_chg']) > 10]
            
            if len(extreme_changes) > 0:
                msg = f"   [WARNING] Found {len(extreme_changes)} days with >10% price change"
                print(msg)
                print(f"   Max change: {df['pct_chg'].max():.2f}%")
                print(f"   Min change: {df['pct_chg'].min():.2f}%")
                self.warnings.append(msg)
                status = 'WARNING'
            else:
                print("   [OK] No extreme price changes detected")
                status = 'PASS'
        else:
            print("   [WARNING] No pct_chg column to check")
            status = 'WARNING'
        
        print(f"   {status}\n")
        
        results['checks'].append({
            'name': 'Outlier Detection',
            'status': status,
            'details': f"{len(extreme_changes)} extreme changes" if 'pct_chg' in df.columns else 'No pct_chg column'
        })
    
    def _print_summary(self, results: Dict):
        """Print summary of quality check"""
        print("="*60)
        print("Quality Check Summary")
        print("="*60)
        print(f"Status: {results['status']}")
        print(f"Total Errors: {results['total_errors']}")
        print(f"Total Warnings: {results['total_warnings']}")
        print("="*60)
        
        if results['status'] == 'PASS':
            print("[OK] All quality checks passed!")
        elif results['status'] == 'PASS_WITH_WARNINGS':
            print("[OK] Quality checks passed with warnings")
        else:
            print("[ERROR] Quality checks failed - please review errors")
        
        print("="*60 + "\n")
    
    def save_report(self, results: Dict, output_dir: Path):
        """Save quality check report to file"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"quality_report_{results['ts_code'].replace('.', '_')}_{timestamp}.txt"
        filepath = output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write(f"Data Quality Report\n")
            f.write("="*60 + "\n")
            f.write(f"Security: {results['ts_code']}\n")
            f.write(f"Check Time: {results['check_time']}\n")
            f.write(f"Total Records: {results['total_records']}\n")
            f.write(f"Status: {results['status']}\n")
            f.write(f"Total Errors: {results['total_errors']}\n")
            f.write(f"Total Warnings: {results['total_warnings']}\n")
            f.write("="*60 + "\n\n")
            
            f.write("Detailed Checks:\n")
            f.write("-"*60 + "\n")
            for check in results['checks']:
                f.write(f"\n{check['name']}: {check['status']}\n")
                f.write(f"  Details: {check['details']}\n")
            
            if results['errors']:
                f.write("\n" + "="*60 + "\n")
                f.write("Errors:\n")
                f.write("-"*60 + "\n")
                for error in results['errors']:
                    f.write(f"  {error}\n")
            
            if results['warnings']:
                f.write("\n" + "="*60 + "\n")
                f.write("Warnings:\n")
                f.write("-"*60 + "\n")
                for warning in results['warnings']:
                    f.write(f"  {warning}\n")
        
        print(f"[OK] Quality report saved to: {filepath}\n")
        return filepath


def main():
    """Test quality checker on downloaded data"""
    print("\n" + "="*60)
    print("Data Quality Checker Test")
    print("="*60)
    
    # Find the most recent data file
    data_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    csv_files = list(data_dir.glob("510050_SH_*.csv"))
    
    if not csv_files:
        print("[ERROR] No data files found. Please run data_downloader.py first.")
        return 1
    
    # Use the most recent file
    latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
    print(f"\nChecking file: {latest_file.name}\n")
    
    # Load data
    df = pd.read_csv(latest_file)
    
    # Run quality checks
    checker = DataQualityChecker()
    results = checker.check_all(df, ts_code="510050.SH")
    
    # Save report
    report_dir = Path(__file__).parent.parent.parent / "data" / "processed"
    checker.save_report(results, report_dir)
    
    return 0 if results['status'] != 'FAIL' else 1


if __name__ == "__main__":
    exit(main())

