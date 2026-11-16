with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    md_text = f.read()

import re
matches = [m.start() for m in re.finditer(r'A0', md_text)]
print("Total A0 occurrences in Project3_Report.md:", len(matches))
for idx in matches[:10]:
    start = max(0, idx - 80)
    end = min(len(md_text), idx + 120)
    print("--- MD SNIPPET ---")
    print(repr(md_text[start:end]))
