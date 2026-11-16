with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'f"""', text)]
print("Count of f\"\"\":", len(matches))
for idx in matches:
    print(repr(text[idx-10:idx+30]))
