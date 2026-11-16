for filename in ["outputs/report/Project3_Report.md", "VSCODE_REPORT.md"]:
    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()
    if "已计入滑点" in text:
        print(f"FOUND '已计入滑点' in {filename}")
    if "滑点" in text:
        for line in text.splitlines():
            if "滑点" in line:
                print(f"{filename}: {line.strip()}")

import pypdf
reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
pdf_text = "".join([p.extract_text() for p in reader.pages])
if "已计入滑点" in pdf_text:
    print("FOUND '已计入滑点' in PDF")
for line in pdf_text.splitlines():
    if "滑点" in line:
        print("PDF:", line.strip())
