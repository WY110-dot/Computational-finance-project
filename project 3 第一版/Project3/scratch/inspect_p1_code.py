with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find("新因子构造")
print(text[idx:idx+400])
