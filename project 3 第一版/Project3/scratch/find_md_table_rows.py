with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'md_content \+= f"\|', text)]
for idx in matches:
    end = text.find("\n", idx)
    print(repr(text[idx:end+1]))
