with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

import re

# Fix broken f-string endings where |\n" was written instead of |\\n"
text = re.sub(r'\|\n"', r'|\\n"', text)

with open("src/quantcf/project3_report.py", "w", encoding="utf-8") as f:
    f.write(text)

import py_compile
try:
    py_compile.compile("src/quantcf/project3_report.py", doraise=True)
    print("Compilation SUCCESS!")
except Exception as e:
    print("Compilation error:", e)
