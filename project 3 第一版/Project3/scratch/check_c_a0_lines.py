with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

for line in text.splitlines():
    if "A0" in line and ("低于" in line or "高于" in line or "比较" in line or "表现" in line):
        print("MD:", line)

with open("VSCODE_REPORT.md", "r", encoding="utf-8") as f:
    text2 = f.read()

for line in text2.splitlines():
    if "A0" in line and ("低于" in line or "高于" in line or "比较" in line or "表现" in line):
        print("VSCODE:", line)
