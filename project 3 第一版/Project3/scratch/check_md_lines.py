with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

lines = text.splitlines()
for i, l in enumerate(lines[:35]):
    print(f"{i+1}: {repr(l)}")
