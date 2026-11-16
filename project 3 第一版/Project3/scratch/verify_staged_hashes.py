import hashlib
from pathlib import Path
import zipfile

ws = Path("..").resolve()
zip_path = ws / "Project3_Review_Bundle_v4.zip"

def get_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

files_to_check = [
    "Project3_Report.pdf",
    "VSCODE_REPORT.md",
    "verification.json",
    "acceptance_matrix.csv",
    "BUGFIX_CHANGELOG.md"
]

in_zip_map = {
    "Project3_Report.pdf": "Project3/outputs/report/Project3_Report.pdf",
    "VSCODE_REPORT.md": "Project3/VSCODE_REPORT.md",
    "verification.json": "Project3/outputs/verification.json",
    "acceptance_matrix.csv": "Project3/outputs/acceptance_matrix.csv",
    "BUGFIX_CHANGELOG.md": "Project3/BUGFIX_CHANGELOG.md"
}

with zipfile.ZipFile(zip_path, "r") as zf:
    for fname in files_to_check:
        ext_path = ws / fname
        ext_bytes = ext_path.read_bytes()
        ext_hash = get_hash(ext_bytes)

        zip_arcname = in_zip_map[fname]
        zip_bytes = zf.read(zip_arcname)
        zip_hash = get_hash(zip_bytes)

        match = (ext_hash == zip_hash)
        print(f"{fname}: {'MATCH' if match else 'MISMATCH'} (SHA256: {ext_hash[:16]}...)")
        if not match:
            print(f"  External size: {len(ext_bytes)}, in-zip size: {len(zip_bytes)}")
