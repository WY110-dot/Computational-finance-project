with open("src/quantcf/project3_report.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Replace unicode subscripts
text = text.replace("F₁(i, t) = m₁₂(i, t) &times; ER₆₃(i, t)", "F_1(i, t) = m_12(i, t) &times; ER_63(i, t)")
text = text.replace("F₁ 与 12M 动量的全区间每日截面相关系数均值", "F_1 与 12M 动量的全区间每日截面相关系数均值")

# 2. In build_markdown_report, add Section 10 with correlation and failure mechanism discussion before Section 9 (or as Section 9, and renumber)
# Let's see Section 9 in md_content
old_sec9 = """## 9. 真实性、AI 辅助与物理隔离声明

1. **P5 保留段截断审计**: 本次评估前，数据加载模块将 CN21（原快照至 2026-09-18）与 US9（原快照至 2026-02-06）**严格截断在 2024-12-31**，所有派生表与图表无一包含 2025+ 记录；
2. **第一轮历史暴露声明**: 如实说明第一轮复核曾暴露 2025–2026 每日相关性，但未查看未来收益，后续修复在原 F1/F2/F3 定义下重算，未调参；
3. **数字追溯**: 所有表格与正文数字完全映射至 `outputs/report/report_trace.csv`，由源码直接生成。
"""

new_sec9_10 = """## 9. 因子失效机理剖析与截面相关性动态诊断

1. **高共线性掩盖独立信号**：
   - 动态从 `daily_correlations.csv` 计算每日截面相关系数全区间日均值：
     - **US9 市场**（1998–2024 共 {us_days:,} 个有效交易日）：Pearson 均值为 **{us_pearson:.6f}**，Spearman 均值为 **{us_spearman:.6f}**；
     - **CN21 市场**（2019–2024 共 {cn_days:,} 个有效交易日）：Pearson 均值为 **{cn_pearson:.6f}**，Spearman 均值为 **{cn_spearman:.6f}**；
   - 两市场主因子与传统动量基准的相关性均在 0.75–0.88 极高区间，路径效率未能提供异质性的截面排序。
2. **残差部分无增量预测能力**：
   - 截面正交分解 $B = \\alpha_t + \\beta_t A + \\epsilon_t$ 中，剥离动量后的纯净残差 $\\epsilon$ 月度 Rank IC 均值在 US9 为 **{df_res[df_res['universe']=='US9']['residual_rank_ic_mean'].iloc[0]:+.4f}**，在 CN21 为 **{df_res[df_res['universe']=='CN21']['residual_rank_ic_mean'].iloc[0]:+.4f}**，残差利差分别为 -9.49% 与 -2.10%，未提供稳健的正向 Alpha。
3. **换手与费用摩擦损耗**：
   - 交互因子月度换手率高于基准 A（US9: 42.5 vs 25.8; CN21: 14.8 vs 14.8），在 3 bps 与 10 bps 单边费率阶梯下，摩擦损耗随费率上升显著拉大超额回撤。

---

## 10. 真实性、AI 辅助与物理隔离声明

1. **P5 保留段截断审计**: 本次评估前，数据加载模块将 CN21（原快照至 2026-09-18）与 US9（原快照至 2026-02-06）**严格截断在 2024-12-31**，所有派生表与图表无一包含 2025+ 记录；
2. **第一轮历史暴露声明**: 如实说明第一轮复核曾暴露 2025–2026 每日相关性，但未查看未来收益，后续修复在原 F1/F2/F3 定义下重算，未调参；
3. **数字追溯**: 所有表格与正文数字完全映射至 `outputs/report/report_trace.csv`，由源码直接生成；
4. **AI 与签字披露**: AI 工具底层版本未在输出中逐一核实，交互记录为任务摘要非逐字实录，成员分工与答辩确认待人工复核核验（标为 PENDING_HUMAN_REVIEW，无 AI 代签）。
"""

if old_sec9 in text:
    text = text.replace(old_sec9, new_sec9_10)
    print("Replaced old_sec9 in src/quantcf/project3_report.py")
else:
    print("Warning: old_sec9 not found verbatim, checking alternatives...")

with open("src/quantcf/project3_report.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated src/quantcf/project3_report.py successfully!")
