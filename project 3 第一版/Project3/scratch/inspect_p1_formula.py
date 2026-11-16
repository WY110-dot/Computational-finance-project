import pypdf

reader = pypdf.PdfReader("outputs/report/Project3_Report.pdf")
page1 = reader.pages[0].extract_text()
idx = page1.find("一、研究问题")
print(page1[idx:idx+1000])
