from pypdf import PdfReader
reader = PdfReader("outputs/report/Project3_Report.pdf")
print("Total pages in PDF:", len(reader.pages))
for i, page in enumerate(reader.pages):
    print(f"Page {i+1} character count:", len(page.extract_text()))
