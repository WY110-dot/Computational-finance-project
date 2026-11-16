"""Unicode-path-safe CLI runner for Project 2 research pipeline."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.pipeline_p2 import run_p2_pipeline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Project 2 TSMOM replication and extension pipeline")
    parser.add_argument("--config", default="config/project2_tsmom.json", help="Path to P2 config JSON")
    parser.add_argument("--out", default="outputs_p2", help="Output directory")
    parser.add_argument("--offline", action="store_true", default=True, help="Run offline using local snapshots")
    parser.add_argument("--seed", type=int, default=20261022, help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"Launching Project 2 pipeline with config={args.config}, out={args.out}, offline={args.offline}...")
    run_p2_pipeline(
        config_path=ROOT / args.config,
        out_dir=ROOT / args.out,
        offline=args.offline,
        random_seed=args.seed,
    )
    print("Project 2 pipeline finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

