from pathlib import Path

content = Path("package_project3.py").read_text(encoding="utf-8")
content = content.replace('default="Project3_Review_Bundle_v2.zip"', 'default="Project3_Review_Bundle_v3.zip"')
content = content.replace('Packaging Review Candidate (v2)', 'Packaging Review Candidate (v3)')
content = content.replace('(v2 review bundle)', '(v3 review bundle)')
Path("package_project3.py").write_text(content, encoding="utf-8")
print("Updated package_project3.py to v3!")
