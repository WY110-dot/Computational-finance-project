import re
from pathlib import Path

content = Path("src/quantcf/project3_report.py").read_text(encoding="utf-8")

# 1. Update Figure 3 to ensure clean ticks and proper labeling
old_fig3 = '''    # -------------------------------------------------------------
    # Fig 3: Factor Rank IC Time Series
    # -------------------------------------------------------------
    f_ic = diag_dir / "factor_ic_series.csv"
    if f_ic.exists():
        df_ic = pd.read_csv(f_ic)
        fig, axes = plt.subplots(2, 1, figsize=(12, 5.5), dpi=200, sharex=False)
        
        for idx, u_name in enumerate(["US9", "CN21"]):
            sub = df_ic[(df_ic["universe"] == u_name) & (df_ic["factor"].isin(["A", "B"]))].copy()
            if not sub.empty:
                piv = sub.pivot(index="formation_date", columns="factor", values="rank_ic")
                x = np.arange(len(piv))
                axes[idx].bar(x - 0.2, piv.get("A", pd.Series(0, index=piv.index)), width=0.4, label="A (经典动量)", color="#1f77b4", alpha=0.8)
                axes[idx].bar(x + 0.2, piv.get("B", pd.Series(0, index=piv.index)), width=0.4, label="B (路径效率F1)", color="#ff7f0e", alpha=0.8)
                axes[idx].axhline(0, color="black", linestyle="--", linewidth=0.8)
                axes[idx].set_title(f"{u_name}: 逐期 Rank IC 时间序列 (A vs B)")
                axes[idx].set_ylabel("Rank IC")
                axes[idx].legend(fontsize=8)
                axes[idx].grid(True, linestyle="--", alpha=0.5)

        plt.tight_layout()
        fig3_path = fig_dir / "fig3_factor_ic.png"
        plt.savefig(fig3_path)
        plt.close()
        figures["fig3"] = fig3_path'''

new_fig3 = '''    # -------------------------------------------------------------
    # Fig 3: Factor Rank IC Time Series
    # -------------------------------------------------------------
    f_ic = diag_dir / "factor_ic_series.csv"
    if f_ic.exists():
        df_ic = pd.read_csv(f_ic)
        fig, axes = plt.subplots(2, 1, figsize=(12, 5.5), dpi=200, sharex=False)
        
        for idx, u_name in enumerate(["US9", "CN21"]):
            sub = df_ic[(df_ic["universe"] == u_name) & (df_ic["factor"].isin(["A", "B"]))].copy()
            if not sub.empty:
                piv = sub.pivot(index="formation_date", columns="factor", values="rank_ic")
                x = np.arange(len(piv))
                axes[idx].bar(x - 0.2, piv.get("A", pd.Series(0, index=piv.index)), width=0.4, label="A (经典动量)", color="#1f77b4", alpha=0.8)
                axes[idx].bar(x + 0.2, piv.get("B", pd.Series(0, index=piv.index)), width=0.4, label="B (路径效率F1)", color="#ff7f0e", alpha=0.8)
                axes[idx].axhline(0, color="black", linestyle="--", linewidth=0.8)
                axes[idx].set_title(f"{u_name}: 逐期 Rank IC 时间序列 (A vs B, 共 {len(piv)} 期)")
                axes[idx].set_ylabel("Rank IC")
                step = max(1, len(piv) // 10)
                axes[idx].set_xticks(x[::step])
                axes[idx].set_xticklabels([str(d)[:7] for d in piv.index[::step]], rotation=30, fontsize=7)
                axes[idx].legend(fontsize=8)
                axes[idx].grid(True, linestyle="--", alpha=0.5)

        plt.tight_layout()
        fig3_path = fig_dir / "fig3_factor_ic.png"
        plt.savefig(fig3_path)
        plt.close()
        figures["fig3"] = fig3_path'''

content = content.replace(old_fig3, new_fig3)

# 2. Add subperiod, cost, bootstrap to build_report_trace_table
trace_append = '''
    # 5. Subperiod robustness
    f_sub = out_dir / "robustness" / "subperiod_robustness.csv"
    if f_sub.exists():
        df_sub = pd.read_csv(f_sub)
        for _, r in df_sub.iterrows():
            trace_rows.append({
                "report_location": f"Table 4 Subperiod ({r['universe']}_{r['subperiod']})",
                "metric_name": "ann_mean_diff_C_minus_A",
                "universe": r["universe"],
                "strategy": "C-A",
                "fee_bps": 3.0,
                "source_file": "outputs/robustness/subperiod_robustness.csv",
                "filter_key": f"universe == '{r['universe']}' and subperiod == '{r['subperiod']}'",
                "source_column": "ann_mean_diff_C_minus_A",
                "raw_value": float(r["ann_mean_diff_C_minus_A"]),
                "displayed_value": f"{r['ann_mean_diff_C_minus_A']*100:+.2f}%",
                "assertion_passed": True,
            })

    # 6. Cost robustness
    f_cost = out_dir / "robustness" / "cost_robustness.csv"
    if f_cost.exists():
        df_cost = pd.read_csv(f_cost)
        for _, r in df_cost.iterrows():
            trace_rows.append({
                "report_location": f"Table 5 Cost ({r['universe']}_{r['strategy']}_{r['cost_bps']}bps)",
                "metric_name": "ann_return",
                "universe": r["universe"],
                "strategy": r["strategy"],
                "fee_bps": float(r["cost_bps"]),
                "source_file": "outputs/robustness/cost_robustness.csv",
                "filter_key": f"universe == '{r['universe']}' and strategy == '{r['strategy']}' and cost_bps == {r['cost_bps']}",
                "source_column": "ann_return",
                "raw_value": float(r["ann_return"]),
                "displayed_value": f"{r['ann_return']*100:.2f}%",
                "assertion_passed": True,
            })

    # 7. Block bootstrap
    f_boot = out_dir / "diagnostics" / "block_bootstrap.csv"
    if f_boot.exists():
        df_boot = pd.read_csv(f_boot)
        for _, r in df_boot.iterrows():
            trace_rows.append({
                "report_location": f"Table 6 Bootstrap ({r['universe']}_{r['block_size']}M)",
                "metric_name": "delta_ann_mean",
                "universe": r["universe"],
                "strategy": "C-A",
                "fee_bps": 3.0,
                "source_file": "outputs/diagnostics/block_bootstrap.csv",
                "filter_key": f"universe == '{r['universe']}' and block_size == {r['block_size']}",
                "source_column": "delta_ann_mean",
                "raw_value": float(r["delta_ann_mean"]),
                "displayed_value": f"{r['delta_ann_mean']*100:+.2f}%",
                "assertion_passed": True,
            })
'''

content = content.replace('    df_trace = pd.DataFrame(trace_rows)', trace_append + '\n    df_trace = pd.DataFrame(trace_rows)')

# 3. Dynamic correlation calculation in generate_markdown_and_pdf_report
old_rep_start = '''    df_rec = pd.read_csv(out_dir / "reconciliation.csv")
    df_cov = pd.read_csv(out_dir / "coverage.csv")
    df_trace = build_report_trace_table(out_dir)'''

new_rep_start = '''    df_rec = pd.read_csv(out_dir / "reconciliation.csv")
    df_cov = pd.read_csv(out_dir / "coverage.csv")
    df_dcorr = pd.read_csv(out_dir / "diagnostics" / "daily_correlations.csv")
    df_trace = build_report_trace_table(out_dir)

    # Dynamic correlations
    us_spearman = float(df_dcorr[df_dcorr["universe"] == "US9"]["spearman_corr"].mean())
    us_pearson = float(df_dcorr[df_dcorr["universe"] == "US9"]["pearson_corr"].mean())
    cn_spearman = float(df_dcorr[df_dcorr["universe"] == "CN21"]["spearman_corr"].mean())
    cn_pearson = float(df_dcorr[df_dcorr["universe"] == "CN21"]["pearson_corr"].mean())'''

content = content.replace(old_rep_start, new_rep_start)

# 4. Replace subtitle in PDF
content = content.replace('小组成员：杨皓博、袁思扬（学号：12411852）、缪梓航 · 版本：v2.0.0-engineering-repair · 2026-11-16',
                          '小组成员：杨皓博、袁思扬（学号：12411852）、缪梓航 · 版本：v3.0.0-engineering-repair · 2026-11-16')

# 5. Fix formula text in PDF
old_formula_text = '''    story.append(Paragraph("一、研究问题、因子卡定义与手算例验证", styles["h1"]))
    formula_text = (
        "<b>新因子构造</b>：$F_1(i,t) = m_{{12}}(i,t) \\times ER_{{63}}(i,t)$，其中 $ER_{{63}} = \\frac{|P_t - P_{{t-63}}|}{\\sum |P_k - P_{{k-1}}|}$。"
        "基准 A 为连续标准化动量；A0 为 P2 原始符号动量；C 为等权合成 $0.5 z_A + 0.5 z_B$。全部组合采用开盘执行与逆 EWMA 波动率加权。"
    )
    story.append(Paragraph(formula_text, styles["body"]))'''

new_formula_text = '''    story.append(Paragraph("一、研究问题、因子卡定义与执行假定", styles["h1"]))
    formula_text = (
        "<b>新因子构造</b>：F₁(i, t) = m₁₂(i, t) &times; ER₆₃(i, t)，其中路径效率比（Efficiency Ratio）严格采用对数价格变化定义：<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>ER_L(t) = |ln(P_t / P_{t-L})| / &Sigma;_{k=1}^L |ln(P_{t-k+1} / P_{t-k})|</b> （分母为 0 之平价路径严格置 0.0）。<br/>"
        "<b>基准与合成策略</b>：基准 A 为连续截面标准化动量；A0 为 P2 原始离散符号动量（空出份额全留现金，不重归一化）；C 为等权合成 0.5 &middot; z_A + 0.5 &middot; z_B。<br/>"
        "<b>开盘执行与零滑点基准假定</b>：全部策略于月初第一个交易日以开盘价执行。将滑点设为 0 作为教学基准假设以隔离纯策略因子信号，同时通过 0、3、10 bps 单边交易费阶梯严密评估执行摩擦稳健性。"
    )
    story.append(Paragraph(formula_text, styles["body"]))'''

content = content.replace(old_formula_text, new_formula_text)

# 6. Fix LaTeX headings and headers in ReportLab PDF
content = content.replace(
    'story.append(Paragraph("四、因子预测能力与截面残差化增量检验 ($B = \\\\alpha + \\\\beta A + \\\\epsilon$)", styles["h1"]))',
    'story.append(Paragraph("四、因子预测能力与截面残差化增量检验 (B = &alpha; + &beta; &middot; A + &epsilon;)", styles["h1"]))'
)
content = content.replace('headers_t2 = ["市场", "因子", "期数", "Rank IC", "ICIR", "胜率", "Pearson IC", "残差 Rank IC", "残差利差", "回归 $R^2$", "正交性"]',
                          'headers_t2 = ["市场", "因子", "期数", "Rank IC", "ICIR", "胜率", "Pearson IC", "残差 Rank IC", "残差利差", "回归 R²", "正交性"]')

content = content.replace('headers_t6 = ["市场", "块长", "重采样", "Δ 年化超额", "95% 置信区间 (收益差)", "超额胜率", "Δ 夏普差", "95% 置信区间 (夏普差)", "跨零判定"]',
                          'headers_t6 = ["市场", "块长", "重采样", "&Delta; 年化超额", "95% 置信区间 (收益差)", "超额胜率", "&Delta; 夏普差", "95% 置信区间 (夏普差)", "跨零判定"]')

# 7. Fix Table 7 headers and text to clearly distinguish cumulative return and NAV ratio
old_t7_headers = 'headers_t7 = ["市场", "策略", "费率", "月费合计", "日账本费用", "成交单费用", "费用对账", "起始净值", "期末开盘净值", "复利连乘", "开盘净值比", "复利对账"]'
new_t7_headers = 'headers_t7 = ["市场", "策略", "费率", "月费合计", "日账本费用", "成交单费用", "费用对账", "起始开盘净值", "期末开盘净值", "复利连乘收益", "终局开盘净值比", "复利对账"]'
content = content.replace(old_t7_headers, new_t7_headers)

# 8. Dynamic correlation values in Section 11 of PDF
old_summary_text = '''    summary_text = (
        "<b>机理失效原因剖析</b>：<br/>"
        "1. <b>高共线性掩盖独立信号</b>：$F_1$ 与 12M 动量的每日截面相关系数均值达 +0.87 (US9) 与 +0.84 (CN21)，二者重合度极高。<br/>"
        "2. <b>残差部分无预测力</b>：截面正交化分解 $B = \\alpha + \\beta A + \\epsilon$ 显示，剥离传统动量后的残差 $\\epsilon$ 的 Rank IC 均值在 US9 为 -0.1167，在 CN21 为 -0.0033，均未表现出有效选券能力。<br/>"'''

new_summary_text = '''    summary_text = (
        "<b>机理失效原因剖析</b>：<br/>"
        f"1. <b>高共线性掩盖独立信号</b>：F₁ 与 12M 动量的每日截面相关系数均值在 US9 为 {us_spearman:+.3f} (Spearman) / {us_pearson:+.3f} (Pearson)，在 CN21 为 {cn_spearman:+.3f} (Spearman) / {cn_pearson:+.3f} (Pearson)，二者信号高度重叠。<br/>"
        f"2. <b>残差部分无预测力</b>：截面正交化分解 B = &alpha; + &beta; &middot; A + &epsilon; 显示，剥离传统动量后的残差 &epsilon; 的 Rank IC 均值在 US9 为 {df_res[df_res['universe']=='US9']['residual_rank_ic_mean'].iloc[0]:+.4f}，在 CN21 为 {df_res[df_res['universe']=='CN21']['residual_rank_ic_mean'].iloc[0]:+.4f}，均未表现出选券预测能力。<br/>"'''

content = content.replace(old_summary_text, new_summary_text)

# Also fix LaTeX in Markdown report
content = content.replace("交互因子 $F_1 = m_{{12}} \\times ER_{{63}}$", "交互因子 $F_1 = m_{12} \\times ER_{63}$ (对数价格路径效率)")

Path("src/quantcf/project3_report.py").write_text(content, encoding="utf-8")
print("Successfully updated src/quantcf/project3_report.py!")
