import re

for filename in ["outputs/report/Project3_Report.md", "VSCODE_REPORT.md"]:
    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()
    nan_matches = re.findall(r'(?i)\b\w*nan\w*\b', text)
    print(f"{filename} nan matches:", set(nan_matches))

import pypdf
reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
pdf_text = "".join([p.extract_text() for p in reader.pages])
pdf_nan = re.findall(r'(?i)\b\w*nan\w*\b', pdf_text)
print("PDF nan matches:", set(pdf_nan))
