import pypdf

reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
page5_text = reader.pages[4].extract_text()
print("=== PDF PAGE 5 ===")
idx = page5_text.find("十一、")
if idx != -1:
    print(page5_text[idx:])
else:
    print(page5_text)

print("\n=== MD SECTION ===")
with open("outputs/report/Project3_Report.md", "r", encoding="utf-8") as f:
    text = f.read()

idx_md = text.find("相关性")
if idx_md != -1:
    print(text[idx_md:idx_md+800])
