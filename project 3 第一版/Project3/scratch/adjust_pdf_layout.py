from pathlib import Path

content = Path("src/quantcf/project3_report.py").read_text(encoding="utf-8")

old_sec1 = '''    story.append(Paragraph("一、研究问题、因子卡定义与手算例验证", styles["h1"]))
    formula_text = (
        "<b>新因子构造</b>：$F_1(i,t) = m_{{12}}(i,t) \\times ER_{{63}}(i,t)$，其中 $ER_{{63}} = \\frac{|P_t - P_{{t-63}}|}{\\sum |P_k - P_{{k-1}}|}$。"
        "基准 A 为连续标准化动量；A0 为 P2 原始符号动量；C 为等权合成 $0.5 z_A + 0.5 z_B$。全部组合采用开盘执行与逆 EWMA 波动率加权。"
    )
    story.append(Paragraph(formula_text, styles["body"]))'''

new_sec1 = '''    story.append(Paragraph("一、研究问题、因子卡定义与执行假定", styles["h1"]))
    formula_text = (
        "<b>新因子构造</b>：F₁(i, t) = m₁₂(i, t) &times; ER₆₃(i, t)，其中路径效率比（Efficiency Ratio）严格采用对数价格变化定义：<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>ER_L(t) = |ln(P_t / P_{t-L})| / &Sigma;_{k=1}^L |ln(P_{t-k+1} / P_{t-k})|</b> （分母为 0 之平价路径严格置 0.0）。<br/>"
        "<b>基准与合成策略</b>：基准 A 为连续截面标准化动量；A0 为 P2 原始离散符号动量（空出份额全留现金，不重归一化）；C 为等权合成 0.5 &middot; z_A + 0.5 &middot; z_B。<br/>"
        "<b>开盘执行与零滑点基准假定</b>：全部策略于月初第一个交易日以开盘价执行。将滑点设为 0 作为教学基准假设以隔离纯策略因子信号，同时通过 0、3、10 bps 单边交易费阶梯严密评估执行摩擦稳健性。"
    )
    story.append(Paragraph(formula_text, styles["body"]))'''

content = content.replace(old_sec1, new_sec1)

# Adjust image heights on Page 3
content = content.replace('story.append(Image(str(figures["fig5"]), width=540, height=160))',
                          'story.append(Image(str(figures["fig5"]), width=540, height=125))')
content = content.replace('story.append(Image(str(figures["fig3"]), width=540, height=160))',
                          'story.append(Image(str(figures["fig3"]), width=540, height=125))')

# Also adjust table padding in make_table to be slightly more compact
content = content.replace('("BOTTOMPADDING", (0, 0), (-1, -1), 2),', '("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),')
content = content.replace('("TOPPADDING", (0, 0), (-1, -1), 2),', '("TOPPADDING", (0, 0), (-1, -1), 1.5),')

Path("src/quantcf/project3_report.py").write_text(content, encoding="utf-8")
print("Updated report layout and formula text successfully!")
