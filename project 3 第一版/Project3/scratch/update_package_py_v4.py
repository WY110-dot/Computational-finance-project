with open("package_project3.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('default="Project3_Review_Bundle_v3.zip"', 'default="Project3_Review_Bundle_v4.zip"')
text = text.replace("Packaging Review Candidate (v3)", "Packaging Review Candidate (v4)")
text = text.replace("v3 review bundle", "v4 review bundle")
text = text.replace("v2 review bundle", "v4 review bundle")

# Exclude scratch directory from FILE_MANIFEST and ZIP
text = text.replace(
    'part in [".venv", "__pycache__", ".git", ".pytest_cache"]',
    'part in [".venv", "__pycache__", ".git", ".pytest_cache", "scratch"]'
)

text = text.replace(
    'exclude_dirs = {".venv", "__pycache__", ".git", ".pytest_cache"}',
    'exclude_dirs = {".venv", "__pycache__", ".git", ".pytest_cache", "scratch"}'
)

with open("package_project3.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated package_project3.py successfully!")
