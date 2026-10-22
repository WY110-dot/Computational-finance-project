"""Unicode-path-safe launcher for preparing Project 2 reference sources."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.reference_data import fetch_project2_sources  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Project 2 paper and reference sources")
    parser.add_argument("--config", default="config/project2_tsmom.json", help="Path to P2 config")
    parser.add_argument("--force", action="store_true", help="Force redownload even if files exist")
    args = parser.parse_args()

    print(f"Preparing Project 2 sources for {ROOT}...")
    results = fetch_project2_sources(root_dir=ROOT, force_download=args.force)
    for name, info in results.items():
        print(f"[{name}] {info['path']} ({info['size_bytes']} bytes, SHA-256: {info['sha256'][:16]}...)")
    print("All project 2 reference sources are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

