"""
Phase C1 Execution & Validation Script
Performs ETF adjustment processing on 510050.SH, validates dividend dates,
and asserts total return consistency against Tushare pct_chg.
"""

import sys
from pathlib import Path
import json
import pandas as pd

# Add src to sys.path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from data.data_downloader import DataDownloader
from data.adjustment import ETFAdjuster


def run_phase_c1():
    print("=" * 80)
    print("PHASE C1: ETF ADJUSTMENT CORRECTNESS EXECUTION & VALIDATION")
    print("=" * 80)

    downloader = DataDownloader()
    ts_code = "510050.SH"
    start_date = "20200101"

    print(f"\n[Step 1] Downloading & processing price and adjustment factors for {ts_code}...")
    adjusted_df, diagnostics = downloader.download_and_adjust_etf_data(
        ts_code=ts_code,
        start_date=start_date,
        end_date=None,  # Up to latest
        save_processed=True
    )

    print(f"\n[Step 2] Validating full sample ({len(adjusted_df)} days)...")
    print(f"  Reference Date (tau): {adjusted_df['adjustment_reference_date'].iloc[0]}")
    print(f"  Diagnostics: {json.dumps(diagnostics, indent=2)}")

    print("\n[Step 3] Checking Ex-Dividend Event (2025-12-17)...")
    sub = adjusted_df[(adjusted_df['trade_date'] >= '20251215') & (adjusted_df['trade_date'] <= '20251218')].copy()
    
    # Calculate raw pct change for inspection
    sub['raw_pct_change'] = sub['close_raw'].pct_change() * 100.0
    sub['ret_total_pct'] = sub['ret_total'] * 100.0

    print(sub[['trade_date', 'close_raw', 'adj_factor', 'close_adj', 'raw_pct_change', 'ret_total_pct', 'pct_chg']])

    ex_row = adjusted_df[adjusted_df['trade_date'] == '20251217'].iloc[0]
    raw_loss = (ex_row['close_raw'] - 3.103) / 3.103 * 100.0
    total_gain = ex_row['ret_total'] * 100.0

    print(f"\nEx-Dividend Inspection for 2025-12-17:")
    print(f"  Raw close drop: {raw_loss:.4f}% (False drop due to dividend)")
    print(f"  Corrected ret_total: +{total_gain:.4f}%")
    print(f"  Official Tushare pct_chg: +{ex_row['pct_chg']:.4f}%")

    assert total_gain > 0, "Corrected return on ex-dividend date must be positive!"
    assert abs(total_gain - ex_row['pct_chg']) < 0.01, "Discrepancy with official pct_chg must be < 0.01%"

    # Save diagnostic summary
    report_path = Path(__file__).parent / "data" / "processed" / "c1_adjustment_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, indent=2)
    print(f"\n[OK] Diagnostic report saved to: {report_path}")

    # Generate documentation report
    doc_path = Path(__file__).parent / "docs" / "phase_c1_completion_report.md"
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("# Phase C1 Completion Report: ETF Adjustment Correctness\n\n")
        f.write(f"- **Asset**: {ts_code}\n")
        f.write(f"- **Total Records**: {len(adjusted_df)}\n")
        f.write(f"- **Date Range**: {adjusted_df['trade_date'].min()} - {adjusted_df['trade_date'].max()}\n")
        f.write(f"- **Reference Date (tau)**: {adjusted_df['adjustment_reference_date'].iloc[0]}\n")
        f.write(f"- **Ex-Dividend (2025-12-17) Raw Return**: {raw_loss:.4f}%\n")
        f.write(f"- **Ex-Dividend (2025-12-17) Corrected Return**: +{total_gain:.4f}%\n")
        f.write(f"- **Official pct_chg**: +{ex_row['pct_chg']:.4f}%\n")
        f.write(f"- **Maximum Absolute Difference (All Days)**: {diagnostics['max_abs_diff_pct']:.6f}%\n")
        f.write(f"- **Mean Absolute Difference (All Days)**: {diagnostics['mean_abs_diff_pct']:.6f}%\n")
        f.write(f"- **Status**: PASS\n")
    print(f"[OK] Completion report saved to: {doc_path}")

    print("\n" + "=" * 80)
    print("PHASE C1 GATE STATUS: PASS")
    print("=" * 80)


if __name__ == "__main__":
    run_phase_c1()

