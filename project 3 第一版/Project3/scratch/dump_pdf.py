import pypdf

reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
print("Total pages:", len(reader.pages))

for idx, page in enumerate(reader.pages):
    print(f"\n{'='*30} PAGE {idx+1} {'='*30}")
    text = page.extract_text()
    print(text[:800])
    if len(text) > 800:
        print("...\n" + text[-400:])
