with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
for m in re.finditer(r'ER_L', text):
    start = max(0, m.start() - 100)
    end = min(len(text), m.end() + 200)
    print("--- MATCH ---")
    print(text[start:end])
