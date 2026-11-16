with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

# Let's inspect where \times, \frac, \ln, etc. appear in text
import re
for m in re.finditer(r'[\t\f\r\n\a\b\v]rac|[\t\f\r\n\a\b\v]imes', text):
    start = max(0, m.start() - 20)
    end = min(len(text), m.end() + 20)
    print(repr(text[start:end]))
