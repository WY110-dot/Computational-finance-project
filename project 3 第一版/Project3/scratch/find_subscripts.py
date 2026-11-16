with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
subscripts = re.findall(r'[\u2080-\u2089]', text)
print("Subscript characters count:", len(subscripts), set(subscripts))

for i, line in enumerate(text.splitlines()):
    if re.search(r'[\u2080-\u2089]', line):
        print(f"Line {i+1}: {line}")
