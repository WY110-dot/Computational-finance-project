import os

keywords = ["超额正收益概率", "超额胜率", "主假说被明确否定", "主假说被明确证伪", "主假说被证伪"]
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

if not matches:
    print("ALL CLEAN: None of the forbidden phrases found!")
