"""Render REPORT.md to a submission PDF.

Chinese text uses reportlab's built-in STSong-Light CID font, so the build is
offline. The Markdown report is the single source of truth: headings, tables,
figures, bullet lists and fenced code blocks are converted in order.

Usage (from project2/):
    python build_report.py
"""
import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame,
                                HRFlowable, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Preformatted, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'REPORT.md'
OUT = ROOT / 'output' / 'pdf' / 'CF2026_Project2_Report.pdf'

FONT = 'STSong-Light'
LATIN = 'Helvetica'
MONO = 'Courier'
INK = colors.HexColor('#1D2733')
MUTED = colors.HexColor('#5B6775')
BLUE = colors.HexColor('#1F4E79')
ACCENT = colors.HexColor('#2A78D6')
RULE = colors.HexColor('#C9D2DE')
HEAD_BG = colors.HexColor('#E9EFF7')
ZEBRA = colors.HexColor('#F7F9FC')
PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
USABLE = PAGE_W - 2 * MARGIN

pdfmetrics.registerFont(UnicodeCIDFont(FONT))
registerFontFamily(FONT, normal=FONT, bold=FONT, italic=FONT, boldItalic=FONT)

BASE = getSampleStyleSheet()
STYLES = {
    'body': ParagraphStyle(
        'Body', parent=BASE['BodyText'], fontName=FONT, fontSize=9.6,
        leading=15.6, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6,
        wordWrap='CJK', splitLongWords=1),
    'h2': ParagraphStyle(
        'H2', parent=BASE['Heading2'], fontName=FONT, fontSize=16,
        leading=22, textColor=BLUE, spaceBefore=18, spaceAfter=10,
        wordWrap='CJK'),
    'h3': ParagraphStyle(
        'H3', parent=BASE['Heading3'], fontName=FONT, fontSize=11.5,
        leading=16, textColor=colors.HexColor('#234E7A'),
        spaceBefore=10, spaceAfter=5, wordWrap='CJK'),
    'bullet': ParagraphStyle(
        'Bullet', parent=BASE['BodyText'], fontName=FONT, fontSize=9.6,
        leading=15.2, textColor=INK, alignment=TA_JUSTIFY,
        leftIndent=16, bulletIndent=3, spaceAfter=3, wordWrap='CJK'),
    'number': ParagraphStyle(
        'Number', parent=BASE['BodyText'], fontName=FONT, fontSize=9.6,
        leading=15.2, textColor=INK, alignment=TA_JUSTIFY,
        leftIndent=17, firstLineIndent=-13, spaceAfter=3, wordWrap='CJK'),
    'quote': ParagraphStyle(
        'Quote', parent=BASE['BodyText'], fontName=FONT, fontSize=9.0,
        leading=14.2, textColor=colors.HexColor('#44515F'),
        alignment=TA_JUSTIFY, wordWrap='CJK'),
    'math': ParagraphStyle(
        'Math', parent=BASE['BodyText'], fontName=FONT, fontSize=11.2,
        leading=19, textColor=INK, alignment=TA_CENTER,
        spaceBefore=5, spaceAfter=9, wordWrap='CJK'),
    'tablelabel': ParagraphStyle(
        'TableLabel', parent=BASE['BodyText'], fontName=FONT, fontSize=9.8,
        leading=14, textColor=colors.HexColor('#234E7A'),
        spaceBefore=8, spaceAfter=4, wordWrap='CJK'),
    'caption': ParagraphStyle(
        'Caption', parent=BASE['BodyText'], fontName=FONT, fontSize=8.2,
        leading=11, textColor=MUTED, alignment=TA_CENTER, spaceBefore=4,
        spaceAfter=10, wordWrap='CJK'),
    'code': ParagraphStyle(
        'Code', parent=BASE['Code'], fontName=MONO, fontSize=8.2,
        leading=11.2, textColor=colors.HexColor('#26323F'),
        backColor=colors.HexColor('#F3F5F8'), borderColor=RULE,
        borderWidth=0.5, borderPadding=6, leftIndent=2, spaceBefore=4,
        spaceAfter=8),
    'toc1': ParagraphStyle(
        'TOC1', fontName=FONT, fontSize=9.6, leading=13.8,
        textColor=INK, wordWrap='CJK'),
    'toc2': ParagraphStyle(
        'TOC2', fontName=FONT, fontSize=8.4, leading=11.6,
        textColor=colors.HexColor('#44515F'), leftIndent=14, wordWrap='CJK'),
}


def _is_cjk(ch):
    return ('㐀' <= ch <= '鿿' or
            '豈' <= ch <= '﫿' or
            ch in '，。；：、（）《》“”‘’！？·')


def smart_join(parts):
    out = ''
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not out:
            out = part
            continue
        a, b = out[-1], part[0]
        if a in '，。；：、）》”' or b in '，。；：、）《（”':
            out += part
        elif _is_cjk(a) and _is_cjk(b):
            out += part
        elif _is_cjk(a) and not b.isascii():
            out += part
        else:
            out += ' ' + part
    return out


def _group(s, i):
    """Return (content, next_index) for a balanced {...} group at s[i]."""
    if i >= len(s) or s[i] != '{':
        return '', i
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


GREEK = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε',
    'zeta': 'ζ', 'eta': 'η', 'theta': 'θ', 'iota': 'ι', 'kappa': 'κ',
    'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'xi': 'ξ', 'pi': 'π', 'rho': 'ρ',
    'sigma': 'σ', 'tau': 'τ', 'upsilon': 'υ', 'phi': 'φ', 'chi': 'χ',
    'psi': 'ψ', 'omega': 'ω', 'Delta': 'Δ', 'Sigma': 'Σ', 'Omega': 'Ω',
    'Gamma': 'Γ', 'Lambda': 'Λ', 'Pi': 'Π', 'Phi': 'Φ',
}
SYMBOLS = {
    'cdot': '×', 'times': '×', 'pm': '±', 'mp': '∓', 'le': '≤', 'leq': '≤',
    'ge': '≥', 'geq': '≥', 'neq': '≠', 'approx': '≈', 'to': '→',
    'rightarrow': '→', 'infty': '∞', 'prod': '∏', 'sum': 'Σ', 'partial': '∂',
    'left': '', 'right': '', 'quad': '  ', 'qquad': '    ', 'bar': '',
    'hat': '', 'text': '', 'mathrm': '', 'operatorname': '',
}


def latex_to_text(s):
    """Best-effort LaTeX to plain/HTML text for reportlab."""
    out = []
    i, n = 0, len(s)
    while i < n:
        if s.startswith('\\frac', i):
            j = i + 5
            while j < n and s[j] == ' ':
                j += 1
            num, j = _group(s, j)
            while j < n and s[j] == ' ':
                j += 1
            den, j = _group(s, j)
            out.append(f'({latex_to_text(num)})/({latex_to_text(den)})')
            i = j
            continue
        if s.startswith('\\sqrt', i):
            j = i + 5
            while j < n and s[j] == ' ':
                j += 1
            body, j = _group(s, j)
            out.append('√(' + latex_to_text(body) + ')')
            i = j
            continue
        if s.startswith('\\text', i) or s.startswith('\\mathrm', i) or s.startswith('\\operatorname', i):
            j = i + 1
            while j < n and s[j].isalpha():
                j += 1
            while j < n and s[j] == ' ':
                j += 1
            body, j = _group(s, j)
            out.append(latex_to_text(body))
            i = j
            continue
        if s[i] == '\\':
            j = i + 1
            if j < n and s[j].isalpha():
                while j < n and s[j].isalpha():
                    j += 1
                cmd = s[i + 1:j]
                out.append(GREEK.get(cmd, SYMBOLS.get(cmd, '')))
                i = j
                continue
            if j < n:
                if s[j] in ',;:!':
                    out.append(' ')
                elif s[j] == ' ':
                    out.append(' ')
                else:
                    out.append(s[j])
                i = j + 1
                continue
        if s[i] in '_^':
            j = i + 1
            if j < n and s[j] == '{':
                body, j = _group(s, j)
            elif j < n:
                body, j = s[j], j + 1
            else:
                body = ''
            tag = 'sub' if s[i] == '_' else 'super'
            out.append(f'<{tag}>{latex_to_text(body)}</{tag}>')
            i = j
            continue
        if s[i] in '{}':
            i += 1
            continue
        out.append(s[i])
        i += 1
    return ''.join(out)


def inline(text):
    """Markdown/LaTeX inline markup -> reportlab mini-HTML.

    Code spans, links and math are extracted first so that underscores in
    filenames (run_manifest.json) are not mistaken for LaTeX subscripts.
    """
    code, links, math = {}, {}, {}

    def hold_code(m):
        key = f'@@CODE{len(code)}@@'
        code[key] = m.group(1)
        return key

    def hold_link(m):
        key = f'@@LINK{len(links)}@@'
        links[key] = (m.group(1), m.group(2))
        return key

    def hold_math(m):
        key = f'@@MATH{len(math)}@@'
        math[key] = latex_to_text(html.escape(m.group(1), quote=False))
        return key

    s = re.sub(r'`([^`]+)`', hold_code, text)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', hold_link, s)
    s = re.sub(r'\\\((.*?)\\\)', hold_math, s)
    s = re.sub(r'\\\[(.*?)\\\]', hold_math, s, flags=re.S)

    s = html.escape(s, quote=False)
    for sup, digit in (('¹', '1'), ('²', '2'), ('³', '3')):
        s = s.replace(sup, f'<super>{digit}</super>')
    s = s.replace('–', '<font face="Helvetica">–</font>')
    s = re.sub(r'\*\*([^*]+)\*\*', r'<font color="#0B2E4F"><b>\1</b></font>', s)
    s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<i>\1</i>', s)

    for key, value in math.items():
        s = s.replace(key, value)
    for key, (label, _url) in links.items():
        s = s.replace(key, f'<font color="#2A78D6">{html.escape(label, quote=False)}</font>')
    for key, value in code.items():
        s = s.replace(key, f'<font face="Courier" color="#8A3B12">{html.escape(value, quote=False)}</font>')
    return s


def plain_len(text):
    text = re.sub(r'[`*_\\{}]', '', text)
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    return sum(2 if not ch.isascii() else 1 for ch in text)


NUMERIC = re.compile(r'^[\s+\-−]?[\d.,%()eE×xX/²³⁴]+$')


def is_numeric(text):
    t = re.sub(r'[*`\s]', '', text)
    return bool(t) and bool(NUMERIC.match(t)) and any(c.isdigit() for c in t)


def cell_style(size, header=False, right=False):
    return ParagraphStyle(
        f'cell{size}{header}{right}', parent=BASE['BodyText'],
        fontName=FONT, fontSize=size, leading=size * 1.28,
        textColor=colors.HexColor('#1F4E79') if header else INK,
        alignment=TA_CENTER if header else (TA_RIGHT if right else TA_LEFT),
        wordWrap='CJK', splitLongWords=1)


HEADER_SHORT = {
    '年化收益（CAGR）': '年化收益',
    '月频年化波动': '月频波动',
    '月频 Sharpe': '月频Sharpe',
    '日频 Sharpe': '日频Sharpe',
    '平均 gross': '平均gross',
    '平均 net': '平均net',
    '终端 NAV': '终端净值',
}


def build_table(raw_rows):
    rows = []
    for line in raw_rows:
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
            continue
        rows.append(cells)
    if not rows:
        return []
    ncols = max(len(r) for r in rows)
    rows = [r + [''] * (ncols - len(r)) for r in rows]
    size = 6.3 if ncols >= 9 else (6.9 if ncols >= 7 else 7.8)
    data = []
    for ri, row in enumerate(rows):
        out = []
        for cell in row:
            shown = HEADER_SHORT.get(cell, cell) if ri == 0 else cell
            out.append(Paragraph(inline(shown),
                                 cell_style(size, header=(ri == 0),
                                            right=(ri > 0 and ncols > 2
                                                   and is_numeric(cell)))))
        data.append(out)

    raw = [max(4, min(max(plain_len(r[j]) for r in rows), 34))
           for j in range(ncols)]
    total = sum(raw)
    widths = [USABLE * w / total for w in raw]
    min_w = 1.2 * cm
    widths = [max(w, min_w) for w in widths]
    factor = USABLE / sum(widths)
    widths = [w * factor for w in widths]

    table = Table(data, colWidths=widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), BLUE),
        ('GRID', (0, 0), (-1, -1), 0.4, RULE),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#9FB2C8')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ZEBRA]),
    ]))
    block = [Spacer(1, 4), table, Spacer(1, 10)]
    if len(data) <= 16:
        return [KeepTogether(block)]
    return block


def build_image(alt, path):
    p = (ROOT / path).resolve()
    if not p.exists():
        return [Paragraph(f'[缺少图片：{path}]', STYLES['caption'])]
    img = Image(str(p))
    width = USABLE * 0.95
    height = width * img.imageHeight / img.imageWidth
    if height > 17.5 * cm:
        height = 17.5 * cm
        width = height * img.imageWidth / img.imageHeight
    img.drawWidth, img.drawHeight = width, height
    img.hAlign = 'CENTER'
    return [KeepTogether([Spacer(1, 4), img,
                          Paragraph(f'图：{inline(alt)}', STYLES['caption'])])]


def cover():
    meta = [
        ['平台', 'Project 1 的 9 只美国行业 SPDR ETF 固定快照'],
        ['资产', 'XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY'],
        ['样本', '2000-01-03 至 2024-12-31（300 个月，6,289 个交易日）'],
        ['数据', '公开 GitHub 快照，逐文件 SHA-256 校验'],
        ['代码', 'run.py · src/ · config.json'],
        ['证据', 'outputs/ · audit.json · verification.json'],
        ['运行', 'python run.py · python verify.py'],
        ['日期', '2026-10-19'],
        ['作者', 'Miu Zihang'],
    ]
    rows = [[Paragraph(inline(a), cell_style(9.2)),
             Paragraph(inline(b), cell_style(9.2))] for a, b in meta]
    t = Table(rows, colWidths=[2.6 * cm, USABLE - 2.6 * cm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (0, -1), MUTED),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#E1E6ED')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))

    verdict = Table(
        [[Paragraph(
            '<font color="#9A3412"><b>核心结论</b></font><br/>'
            '在 9 只美国行业 ETF、2000–2024 的样本上，'
            '原文的核心结论<font color="#9A3412"><b>没有复现</b></font>：'
            '12 个月符号的 pooled β = -0.000614（t = -0.22），'
            '多元化 TSMOM 的月频 Sharpe 为 0.325（gross）/ 0.242（net 10 bp），'
            '而原文约为 1.01（gross）。',
            ParagraphStyle('verdict', parent=STYLES['body'], fontSize=9.4,
                           leading=15.4, textColor=INK))]],
        colWidths=[USABLE])
    verdict.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FDF1EA')),
        ('LINEBEFORE', (0, 0), (0, -1), 3, colors.HexColor('#D9622B')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))

    title = ParagraphStyle(
        'CoverTitle', parent=STYLES['body'], fontName=FONT, fontSize=25,
        leading=34, textColor=BLUE, alignment=TA_LEFT, spaceAfter=4)
    sub = ParagraphStyle(
        'CoverSub', parent=STYLES['body'], fontSize=11.5, leading=18,
        textColor=colors.HexColor('#3E5369'), alignment=TA_LEFT)
    kicker = ParagraphStyle(
        'CoverKicker', parent=STYLES['body'], fontSize=9, leading=12,
        textColor=ACCENT, alignment=TA_LEFT)

    parts = [
        Spacer(1, 2.2 * cm),
        Paragraph('CF2026 · PROJECT 2 · REPRODUCTION REPORT', kicker),
        Spacer(1, 0.5 * cm),
        Paragraph('Time Series Momentum 的复现', title),
        Paragraph('Moskowitz, Ooi &amp; Pedersen (2012), '
                  '<i>Journal of Financial Economics</i> 104(2), 228–250', sub),
        Spacer(1, 0.5 * cm),
        HRFlowable(width='100%', thickness=2, color=ACCENT,
                   spaceBefore=0, spaceAfter=12),
        Paragraph('以 Project 1 的 9 只美国行业 ETF 为平台，复现原文的核心'
                  '可预测性与组合结论；并给出可比口径、差异归因与单因子扩展。',
                  ParagraphStyle('intro', parent=STYLES['body'], fontSize=10.8,
                                 leading=18, textColor=INK)),
        Spacer(1, 0.8 * cm),
        t,
        Spacer(1, 0.9 * cm),
        verdict,
        Spacer(1, 0.9 * cm),
        Paragraph('提交材料：复现报告 · 代码与配置 · 数据说明 · 运行证据 · '
                  '差异归因 · 手算与测试 · AI 使用说明',
                  ParagraphStyle('materials', parent=STYLES['body'],
                                 fontSize=8.8, leading=14, textColor=MUTED)),
        NextPageTemplate('body'),
        PageBreak(),
    ]
    return parts


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, pagesize=A4,
                                 leftMargin=MARGIN, rightMargin=MARGIN,
                                 topMargin=2.15 * cm, bottomMargin=1.8 * cm,
                                 title='CF2026 Project 2 - Time Series Momentum 复现',
                                 author='Miu Zihang',
                                 subject='CF2026 Project 2 reproduction report',
                                 **kw)
        frame = Frame(MARGIN, 1.8 * cm, USABLE, PAGE_H - 3.95 * cm,
                      id='main', leftPadding=0, rightPadding=0,
                      topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id='cover', frames=[frame], onPage=self.cover_page),
            PageTemplate(id='body', frames=[frame], onPage=self.body_page),
        ])

    def cover_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#F4F7FB'))
        canvas.rect(0, PAGE_H - 1.0 * cm, PAGE_W, 1.0 * cm, stroke=0, fill=1)
        canvas.restoreState()

    def body_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 7.6)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, PAGE_H - 1.25 * cm,
                          'CF2026 Project 2 · Time Series Momentum')
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.25 * cm,
                               f'第 {doc.page} 页')
        canvas.setStrokeColor(colors.HexColor('#DCE3EB'))
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, PAGE_H - 1.48 * cm, PAGE_W - MARGIN, PAGE_H - 1.48 * cm)
        canvas.drawString(MARGIN, 1.05 * cm, '复现报告 · 2026-10-19')
        canvas.drawRightString(PAGE_W - MARGIN, 1.05 * cm,
                               'Time Series Momentum (MOP 2012)')
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            name = flowable.style.name
            if name == 'H2':
                self.notify('TOCEntry', (0, flowable.getPlainText(), self.page))
            elif name == 'H3':
                self.notify('TOCEntry', (1, flowable.getPlainText(), self.page))


def parse_markdown():
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    story = cover()

    toc = TableOfContents()
    toc.levelStyles = [STYLES['toc1'], STYLES['toc2']]
    toc.dotsMinLevel = 0
    toc.tableStyle = TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])
    story.append(Paragraph('目录', ParagraphStyle(
        'TOCTitle', parent=STYLES['h2'], fontSize=18, spaceAfter=12)))
    story.append(toc)
    story.append(PageBreak())

    i = 0
    seen_section = False
    fig_no = 0
    while i < len(lines):
        line = lines[i]

        if line.strip() == '':
            i += 1
            continue

        if line.startswith('```'):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                block.append(lines[i])
                i += 1
            i += 1
            story.append(Preformatted('\n'.join(block), STYLES['code']))
            continue

        if line.startswith('|') and line.rstrip().endswith('|'):
            rows = []
            while (i < len(lines) and lines[i].startswith('|')
                   and lines[i].rstrip().endswith('|')):
                rows.append(lines[i])
                i += 1
            story.extend(build_table(rows))
            continue

        if line.startswith('!['):
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
            if m:
                fig_no += 1
                story.extend(build_image(m.group(1), m.group(2)))
            i += 1
            continue

        if re.fullmatch(r'-{3,}', line.strip()):
            story.append(HRFlowable(width='100%', thickness=0.4, color=RULE,
                                    spaceBefore=2, spaceAfter=8))
            i += 1
            continue

        if line.startswith('# '):
            # The report title is on the cover; skip the first H1 in the body.
            if not (not seen_section and 'CF2026' in line):
                story.append(Paragraph(inline(line[2:].strip()), STYLES['h2']))
            i += 1
            continue

        # The paper title and the metadata block below it duplicate the cover.
        if (not seen_section and line.startswith('## ')
                and 'Time Series Momentum' in line):
            i += 1
            while i < len(lines) and not lines[i].startswith('## '):
                i += 1
            continue

        if line.startswith('## '):
            text = line[3:].strip()
            seen_section = True
            head = Paragraph(inline(text), STYLES['h2'])
            head.keepWithNext = 1
            story.append(head)
            story.append(HRFlowable(width='30%', thickness=2, color=ACCENT,
                                    spaceBefore=0, spaceAfter=10,
                                    hAlign='LEFT'))
            i += 1
            continue

        if line.startswith('### '):
            head = Paragraph(inline(line[4:].strip()), STYLES['h3'])
            head.keepWithNext = 1
            story.append(head)
            i += 1
            continue

        if line.startswith('> '):
            block = []
            while i < len(lines) and lines[i].startswith('>'):
                block.append(lines[i].lstrip('>').strip())
                i += 1
            text = smart_join(block)
            box = Table([[Paragraph(inline(text), STYLES['quote'])]],
                        colWidths=[USABLE])
            box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F6F9FC')),
                ('LINEBEFORE', (0, 0), (0, -1), 2.5, ACCENT),
                ('LEFTPADDING', (0, 0), (-1, -1), 9),
                ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.extend([Spacer(1, 3), box, Spacer(1, 10)])
            continue

        if line.startswith('- '):
            items = []
            while i < len(lines) and lines[i].startswith('- '):
                item = [lines[i][2:].strip()]
                i += 1
                while (i < len(lines) and lines[i].strip()
                       and not re.match(r'^(- |\d+\. |#|\||!\[|> |```)', lines[i])
                       and lines[i].startswith('  ')):
                    item.append(lines[i].strip())
                    i += 1
                items.append(smart_join(item))
            for item in items:
                story.append(Paragraph(inline(item), STYLES['bullet'],
                                       bulletText='•'))
            story.append(Spacer(1, 5))
            continue

        m = re.match(r'^(\d+)\.\s+(.*)$', line)
        if m:
            items = []
            while i < len(lines):
                m2 = re.match(r'^(\d+)\.\s+(.*)$', lines[i])
                if not m2:
                    break
                item = [m2.group(2).strip()]
                i += 1
                while (i < len(lines) and lines[i].strip()
                       and not re.match(r'^(\d+\. |#|\||!\[|> |```)', lines[i])
                       and lines[i].startswith('  ')):
                    item.append(lines[i].strip())
                    i += 1
                items.append((m2.group(1), smart_join(item)))
            for (num, item) in items:
                story.append(Paragraph(f'{num}. {inline(item)}',
                                       STYLES['number']))
            story.append(Spacer(1, 5))
            continue

        # Plain paragraph: collect until a blank line or a structural line.
        para = [line.strip()]
        i += 1
        while (i < len(lines) and lines[i].strip()
               and not re.match(r'^(#{1,3} |\|.*\|$|!\[|- |\d+\. |> |```|-{3,}$)',
                                lines[i])):
            para.append(lines[i].strip())
            i += 1
        text = smart_join(para)
        next_line = next((lines[j] for j in range(i, len(lines))
                          if lines[j].strip()), '')
        if (re.fullmatch(r'\*\*[^*]+\*\*[：:]?', text.strip())
                and next_line.startswith('|')):
            head = Paragraph(inline(text), STYLES['tablelabel'])
            head.keepWithNext = 1
            story.append(CondPageBreak(5.2 * cm))
            story.append(head)
        elif re.fullmatch(r'\\\[.*\\\]', text, flags=re.S):
            story.append(Paragraph(inline(text), STYLES['math']))
        else:
            story.append(Paragraph(inline(text), STYLES['body']))

    return story


def main():
    if not SOURCE.exists():
        raise SystemExit(f'missing {SOURCE}')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    story = parse_markdown()
    doc = ReportDoc(str(OUT))
    doc.multiBuild(story)
    print(f'wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.1f} KiB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
