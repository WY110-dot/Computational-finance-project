import os
from pathlib import Path
import hashlib

ws = Path("f:/金融数学/计算金融/Project/project 3 第一版")

req_files = [
    "Project3_Review_Bundle_v4.zip",
    "Project3_Review_Bundle_v4.zip.sha256.txt",
    "Project3_Report.pdf",
    "VSCODE_REPORT.md",
    "verification.json",
    "acceptance_matrix.csv",
    "BUGFIX_CHANGELOG.md"
]

print("=== CHECKING WORKSPACE ROOT DELIVERABLES ===")
for f in req_files:
    p = ws / f
    if p.exists():
        size = p.stat().st_size
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        print(f"[OK] {f} ({size:,} bytes) SHA-256: {sha}")
    else:
        print(f"[MISSING] {f}")
