"""Unicode-path-safe CLI runner for rebuilding Project 2 reports."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.report_p2 import generate_all_reports  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild Project 2 research reports and PDFs")
    parser.add_argument("--out", default="outputs", help="Outputs directory containing artifacts")
    args = parser.parse_args()

    out_path = ROOT / args.out
    print(f"Rebuilding Project 2 reports from {out_path}...")
    generate_all_reports(out_dir=out_path)
    print("Report build finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


