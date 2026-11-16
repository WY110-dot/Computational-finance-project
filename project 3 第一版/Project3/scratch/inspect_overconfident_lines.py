import os

files = [
    r"README.md",
    r"docs\AI_ASSISTANCE.md",
    r"docs\CONTRIBUTIONS.md",
    r"docs\DEVIATIONS.md",
    r"docs\HYPOTHESIS_CARD.md",
    r"docs\PROTOCOL.md",
    r"BUGFIX_CHANGELOG.md"
]

for f in files:
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
        for i, l in enumerate(lines):
            if any(k in l for k in ["证伪", "否定", "主假说被"]):
                print(f"{f}:{i+1} -> {l.strip()}")
