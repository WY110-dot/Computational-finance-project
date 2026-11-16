with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

lines = text.splitlines()
for i in range(35, min(len(lines), 70)):
    print(f"{i+1}: {repr(lines[i])}")
