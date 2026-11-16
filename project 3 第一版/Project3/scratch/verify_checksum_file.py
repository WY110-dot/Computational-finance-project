import hashlib
from pathlib import Path

ws = Path("..").resolve()
zip_path = ws / "Project3_Review_Bundle_v4.zip"
sha_path = ws / "Project3_Review_Bundle_v4.zip.sha256.txt"

actual_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
file_content = sha_path.read_text(encoding="utf-8").strip()

print("Actual SHA-256: ", actual_sha)
print("File content:   ", file_content)
assert actual_sha in file_content, "SHA256 mismatch!"
print("SHA256 Checksum file verified 100% OK!")
