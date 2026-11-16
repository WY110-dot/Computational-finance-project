with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i in range(600, min(len(lines), 660)):
    print(f"{i+1}: {repr(lines[i])}")
