with open("outputs/report/Project3_Report.md", "rb") as f:
    data = f.read()

idx = data.find(b"ER_L(t)")
print("Bytes:", data[idx:idx+120])
