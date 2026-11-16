import pypdf
import re

reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
full_text = ""
for idx, page in enumerate(reader.pages):
    txt = page.extract_text()
    full_text += f"\n--- PAGE {idx+1} ---\n" + txt

latex_artifacts = [
    r"\$",
    r"\\frac",
    r"\\times",
    r"\\cdot",
    r"\\sum",
    r"\\ln",
    r"\{\{",
    r"\}\}",
    r"\\alpha",
    r"\\beta",
    r"\\epsilon",
]

found_issues = []
for art in latex_artifacts:
    matches = list(re.finditer(art, full_text))
    if matches:
        found_issues.append((art, len(matches)))
        print(f"FOUND LATEX ARTIFACT: {art} ({len(matches)} times)")

if not found_issues:
    print("SUCCESS: Absolutely NO raw LaTeX artifacts found in PDF!")
