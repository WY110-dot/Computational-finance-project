with open("VSCODE_REPORT.md", "r", encoding="utf-8") as f:
    text = f.read()

print("Length of VSCODE_REPORT.md:", len(text))
idx = text.find("相关系数")
if idx != -1:
    print(text[idx-50:idx+250])
else:
    print("相关系数 not found in VSCODE_REPORT.md")
