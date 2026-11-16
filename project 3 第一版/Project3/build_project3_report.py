"""CLI runner for building Project 3 research reports, figures, trace table, and PDF."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.project3_report import (
    generate_report_figures,
    build_report_trace_table,
    generate_markdown_and_pdf_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Project 3 reports, figures, trace and PDF")
    parser.add_argument("--out", default="outputs", help="Output directory")
    args = parser.parse_args()

    out_dir = ROOT / args.out
    print(f"=== CF2026 Project 3: Building Reports from {out_dir} ===")

    print("1. Generating analytical figures...")
    figures = generate_report_figures(out_dir)
    print(f"   Generated {len(figures)} figures in {out_dir / 'report' / 'figures'}")

    print("2. Compiling report trace table...")
    df_trace = build_report_trace_table(out_dir)
    print(f"   Saved {len(df_trace)} trace entries in {out_dir / 'report' / 'report_trace.csv'}")

    print("3. Generating Markdown and ReportLab PDF...")
    md_path, pdf_path = generate_markdown_and_pdf_report(out_dir, figures)
    print(f"   Markdown report: {md_path}")
    print(f"   PDF report:      {pdf_path}")

    print("\n=== Report build finished successfully! ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
