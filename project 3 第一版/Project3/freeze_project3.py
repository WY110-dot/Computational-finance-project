"""Freeze protocol script for CF2026 Project 3.

Computes SHA256 hashes of pre-registered documents, configuration, factor definitions,
pipeline logic, and data sources, locking them in outputs/freeze_manifest.json before
the evaluation phase begins.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantcf.data import sha256_file


FREEZE_TARGET_FILES = [
    "config/project3.json",
    "docs/HYPOTHESIS_CARD.md",
    "docs/FACTOR_CARDS.md",
    "docs/PROTOCOL.md",
    "docs/DATA.md",
    "docs/P2_TO_P3_MAPPING.md",
    "docs/CANDIDATE_REGISTER.csv",
    "run_project3.py",
    "src/quantcf/backtest.py",
    "src/quantcf/project3_factors.py",
    "src/quantcf/project3_pipeline.py",
    "src/quantcf/project3_diagnostics.py",
    "data/manifests/source_manifest.json",
    "data/us_sector/source_manifest.json",
]


def get_git_commit() -> str | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze Project 3 configuration and definitions")
    parser.add_argument("--out", default="outputs", help="Output directory")
    args = parser.parse_args()

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== CF2026 Project 3: Freezing Research Configuration ===")
    
    records = []
    for rel_path in FREEZE_TARGET_FILES:
        fpath = ROOT / rel_path
        if not fpath.exists():
            raise FileNotFoundError(f"Freeze target missing: {rel_path}")
        h = sha256_file(fpath)
        size = fpath.stat().st_size
        records.append({
            "path": rel_path,
            "sha256": h,
            "bytes": size,
        })
        print(f"  [FROZEN] {rel_path} ({size} bytes) -> {h[:12]}...")

    git_commit = get_git_commit()
    now_utc = datetime.now(timezone.utc).isoformat()

    # Archive current v2 manifest if it exists
    curr_manifest_path = out_dir / "freeze_manifest.json"
    if curr_manifest_path.exists():
        v2_archive_path = out_dir / "freeze_manifest_v2.json"
        if not v2_archive_path.exists():
            v2_archive_path.write_bytes(curr_manifest_path.read_bytes())
            print(f"  [ARCHIVED] v2 freeze manifest to {v2_archive_path.name}")

    manifest = {
        "project": "CF2026_Project3",
        "version": "3.0.0-engineering-repair",
        "frozen_at": now_utc,
        "git_commit": git_commit or "NO_GIT_REPO",
        "v1_freeze_manifest": "outputs/freeze_manifest_v1.json",
        "v2_freeze_manifest": "outputs/freeze_manifest_v2.json",
        "repair_note": "v3.0.0 engineering fix: A0 P2 long/cash mapping (negative budget kept in cash), daily risk strictly bounded at exit open, clean rerun freeze manifest parameterization, deep verification asserting raw values in report_trace and recomputing reconciliation from fills/ledger, full P5 chunked scanning, ReportLab LaTeX math formatting clean-up, and dynamic correlation reporting.",
        "files_count": len(records),
        "files": records,
        "research_discipline": {
            "evaluation_split_untuned": True,
            "p5_quarantined": True,
            "candidate_budget_locked": True,
            "zero_leakage_enforced": True,
        },
    }

    manifest_path = out_dir / "freeze_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFreeze manifest written successfully to {manifest_path}")
    print(f"Total frozen entries: {len(records)} files, Git commit: {git_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
