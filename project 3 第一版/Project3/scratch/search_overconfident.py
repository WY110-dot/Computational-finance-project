import os

keywords = ["证伪", "否定", "主假说被"]
matches = []

for root, dirs, files in os.walk("."):
    if ".git" in root or ".venv" in root or "__pycache__" in root or "scratch" in root:
        continue
    for f in files:
        if f.endswith((".py", ".md", ".json", ".csv", ".txt")):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    for kw in keywords:
                        if kw in content:
                            matches.append((path, kw))
            except Exception:
                pass

for path, kw in matches:
    print(f"{path}: contains '{kw}'")
