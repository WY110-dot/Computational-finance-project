with open("src/quantcf/project3_report.py", "rb") as f:
    data = f.read()

idx = data.find(b"ER_L(t) = ")
print(data[idx:idx+80])
