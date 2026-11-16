import pypdf

reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
p4 = reader.pages[3].extract_text()
idx = p4.find("九、")
print(p4[idx:idx+800])
