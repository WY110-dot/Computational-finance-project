with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("## 9.")
if idx != -1:
    print(text[idx:])
else:
    print("## 9. not found")
