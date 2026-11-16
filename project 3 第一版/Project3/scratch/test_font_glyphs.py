from reportlab.platypus import Paragraph, SimpleDocTemplate
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

pdfmetrics.registerFont(TTFont("SimHei", "C:/Windows/Fonts/simhei.ttf"))
style = ParagraphStyle(name="test", fontName="SimHei", fontSize=8.5, leading=10.5)
doc = SimpleDocTemplate("scratch/test_glyphs.pdf")
story = [
    Paragraph("F_1(i, t) = m_12(i, t) × ER_63(i, t)", style),
    Paragraph("ER_L(t) = |ln(P_t / P_{t-L})| / &Sigma;_{k=1}^L |ln(P_k / P_{k-1})|", style),
    Paragraph("ER_L = |ln(P_t / P_{t-L})| / Σ|ln(P_k / P_{k-1})|", style),
]
doc.build(story)
print("Build test_glyphs.pdf SUCCESS!")

import pypdf
r = pypdf.PdfReader("scratch/test_glyphs.pdf")
print("Extracted:", repr(r.pages[0].extract_text()))
