with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("Bootstrap")
print(text[idx:idx+800])
