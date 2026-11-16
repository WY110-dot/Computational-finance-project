# Update docs/AI_ASSISTANCE.md
with open("docs/AI_ASSISTANCE.md", "r", encoding="utf-8") as f:
    ai_text = f.read()

# Replace tool section with unverified note
old_tools = """- **工具/助手**：
  - **ChatGPT (GPT-4o)**：用于编制研究执行书、制定总体实验设计协议、提出否定条件与验收指标。
  - **Antigravity (Gemini 3.8 Flash)**：用于在 VSCode/本地工作区实际执行代码架构搭建、数据审计、因子计算、P1 账本执行、统计检验、自动生成报告及复现验证。"""

new_tools = """- **工具/助手**：
  - **ChatGPT**（Web 端 / API 对话交互，具体底层模型路由版本未在输出中逐一技术核实，以 Web 端默认交互为参考）：用于编制研究执行书、制定总体实验设计协议、提出否定条件、提供复核反例与验收指标。
  - **Antigravity 编程助手**（VS Code / IDE 集成智能体环境，具体模型底层调用版本未在本地环境中显式返回或核实）：用于在工作区实际执行代码架构搭建、数据审计、因子计算、P1 账本执行、统计检验、自动生成报告及复现验证。"""

ai_text = ai_text.replace(old_tools, new_tools)

# Replace table section title and add note
old_sec2 = "## 2. 代表性交互与采纳/拒绝记录\n\n| 序号 | 日期 | 提示词核心摘要 |"
new_sec2 = """## 2. 代表性交互与采纳/拒绝记录 (交互任务摘要，非逐字对话实录)

> **声明**：以下问答记录为各阶段工程与研究任务核心摘要，旨在清晰呈现 AI 建议采纳与拒绝的学术与工程理由，非逐字对话实录。

| 序号 | 日期 | 提示词核心摘要 |"""

ai_text = ai_text.replace(old_sec2, new_sec2)

# Append entry 07 to table if not present
entry_07 = """| **07** | 2026-11-16 | “如何根据最后一轮复核意见修正报告与生成代码？” | 指出：1. 修正 PDF 第一页对数价格 ER 公式与规范渲染，杜绝 LaTeX 源码外露；2. 准确区分 C 与 A0 在 CN21 的收益（3.58% > 3.14%）与夏普（1.123 < 2.136）关系；3. 统一采用“本样本未取得稳健正增量证据”，表头规范为“重采样中收益差为正的比例”；4. 动态提取 daily_correlations.csv 全区间日均值并注明类型与区间；5. 明确教学零滑点假设（slippage_bps=0）与终局净值比（约 2.141631）单位；6. 披露 AI 底层版本未核实，标注问答为任务摘要，成员分工待人工核验。 | **完全采纳**：保持原因子、参数、时间划分和回测数据 100% 不变，集中在真正的报告生成器中修正渲染与学术表述。 | PDF 逐页审查、Markdown/VSCode 报告对比及 `verify_project3.py` 自动化核验。 |
"""

if "| **07** |" not in ai_text:
    # Insert entry_07 before the end of the table
    idx_tbl_end = ai_text.find("\n---\n\n## 3. 独立核验与人类审核状态")
    if idx_tbl_end != -1:
        ai_text = ai_text[:idx_tbl_end] + entry_07 + ai_text[idx_tbl_end:]

# Add Section 6 for v4 review log
v4_log_section = """
---

## 6. 最后一轮独立复核意见及工程修复闭环 (v3 $\\to$ v4 Final Polish Log)

- **复核输入**：ChatGPT 对 v3 审核包复核确认：核心收益、费用对账、A0 现金映射和边界测试已有支持。本轮保持原因子、参数、时间划分和回测计算不变，不换因子、不调参，集中修正实际报告及生成代码：
  1. **PDF 第一页对数价格路径 ER 公式**：修复公式定义为 $ER_L = |\\ln(P_t/P_{t-L})| / \\sum |\\ln(P_k/P_{k-1})|$，平价路径分母为零时置 0；PDF 不得外露 LaTeX 源码；
  2. **CN21 市场 C 与 A0 精确比较**：明确收益维度 C 较高（3.58% > 3.14%），夏普维度 C 较低（1.123 < 2.136），删除“C 整体表现低于 A0”笼统表述；
  3. **统一弱化过强结论**：统一为“US9 增量点估计为负，两市场 Bootstrap 区间均跨零，本样本未取得稳健正增量证据”；Bootstrap 表头统一为“重采样中收益差为正的比例”；
  4. **动态截面相关系数均值**：从 `daily_correlations.csv` 动态计算日均值并注明区间与类型（US9 0.781770 / 0.759061; CN21 0.842162 / 0.871730）；
  5. **教学零滑点与净值比单位**：明确 `slippage_bps=0` 教学假设；终局开盘净值比约 2.141631，连乘累计收益 +114.16%，不适用值统一标为“—”；
  6. **真实性说明与签字核验**：AI 底层版本注明未逐一技术核实，问答标为任务摘要非逐字实录，成员签字标注为 `PENDING_HUMAN_REVIEW`，严禁 AI 代签。
- **修复与采纳行动（v4 闭环）**：
  1. 重构 `src/quantcf/project3_report.py` 与 `build_project3_report.py`，全面规范 Unicode / HTML 渲染与表格表头；
  2. 同步重新生成 `Project3_Report.pdf`（严格 5 页）、`Project3_Report.md`、`VSCODE_REPORT.md` 与 `report_trace.csv`；
  3. 完善 `docs/AI_ASSISTANCE.md`、`docs/CONTRIBUTIONS.md` 与 `BUGFIX_CHANGELOG.md`；
  4. 自动化回归测试与对账验证 100% PASS。
"""

if "## 6. 最后一轮独立复核意见及工程修复闭环" not in ai_text:
    ai_text += v4_log_section

with open("docs/AI_ASSISTANCE.md", "w", encoding="utf-8") as f:
    f.write(ai_text)
print("Updated docs/AI_ASSISTANCE.md successfully!")

# Update docs/CONTRIBUTIONS.md
with open("docs/CONTRIBUTIONS.md", "r", encoding="utf-8") as f:
    contrib_text = f.read()

old_members = """- **小组成员**：
  - **杨皓博**（学号：待真实资料补充，不推测填写）
  - **袁思扬**（学号：12411852）
  - **缪梓航**（学号：待真实资料补充，不推测填写）"""

new_members = """- **小组成员**：
  - **杨皓博**（学号：待团队成员线下核实补充；分工：待本人最终确认签字，无 AI 代签）
  - **袁思扬**（学号：12411852；分工：待本人最终确认签字，无 AI 代签）
  - **缪梓航**（学号：待团队成员线下核实补充；分工：待本人最终确认签字，无 AI 代签）
- **分工审核状态**: `PENDING_HUMAN_REVIEW`（待答辩前由小组成员线下审核确认，严禁由 AI 伪造代签）"""

contrib_text = contrib_text.replace(old_members, new_members)

with open("docs/CONTRIBUTIONS.md", "w", encoding="utf-8") as f:
    f.write(contrib_text)
print("Updated docs/CONTRIBUTIONS.md successfully!")
