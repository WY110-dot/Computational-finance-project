import sys
from pathlib import Path
sys.path.insert(0, str(Path(".").resolve()))
from verify_project3 import check_report_trace, check_reconciliation, check_p5_quarantine, check_freeze_manifest

out_dir = Path("outputs")
root = Path(".")

print("1. check_report_trace:", check_report_trace(out_dir, root))
print("2. check_reconciliation:", check_reconciliation(out_dir))
print("3. check_p5_quarantine:", check_p5_quarantine(out_dir))
print("4. check_freeze_manifest:", check_freeze_manifest(out_dir, root))
