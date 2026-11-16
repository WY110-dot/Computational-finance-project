from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# SimHei is registered
style = ParagraphStyle(name="test", fontName="SimHei", fontSize=8.5, leading=10.5)
p = Paragraph("新因子构造：F<sub>1</sub>(i, t) = m<sub>12</sub>(i, t) &times; ER<sub>63</sub>(i, t)", style)
print("Paragraph created successfully!")
