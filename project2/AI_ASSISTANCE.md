# AI 使用说明

## 1. 使用的工具

- **Claude Code**（Anthropic）：代码实现、调试、文档草稿、图表与 PDF 生成、
  测试与验证脚本。
- Python 3.13.7；numpy / pandas / scipy / statsmodels / matplotlib / reportlab。
- 无联网数据下载；数据来自 Project 1 的固定快照。

## 2. AI 做了什么

| 任务 | AI 的角色 | 人类应复核的点 |
|---|---|---|
| 选择复现论文 | 提议 TSMOM（适配 9 资产平台），说明理由 | 是否同意选题与范围 |
| 实现信号/权重/账本 | 编写 `src/tsmom.py`、扩展 `src/backtest.py` | 公式是否与原文一致 |
| 统计推断 | 编写 `src/stats.py`（HAC、pooled FE、alpha、极值） | 标准误/聚类设定 |
| 运行与输出 | 编写 `run.py`、`verify.py`、测试 | 是否接受负结果 |
| 图表 | 编写 `src/plots.py`，生成 PNG | 视觉是否清晰、是否误读 |
| 文档 | 起草 `PAPER.md`、`REPORT.md`、归因等 | 目标数值、引用、表述 |
| PDF | 编写 `build_report.py`，生成提交版 | 字体/排版/页码 |

## 3. 没有做什么

- **没有伪造数据或结果**。所有数字来自 `run.py` 的实际输出；`outputs/` 中的
  CSV/JSON 可逐项复核。
- **没有代替人类做学术判断**。负结果的解释、是否接受“未复现”、是否调整
  范围，应由作者决定。
- **没有下载原论文 PDF**（版权/网络限制）；`PAPER.md` 给出引用、方法和
  目标数值，提交时请按课程要求附上原文。
- **没有使用未来数据**。信号/权重/账本均有测试与手算复核。

## 4. 关键提示与决策记录

1. 用户要求“根据 CF2026_Project2.pdf 完成 project2，放进新建目录”。
   AI 阅读了 PDF 的要求（选择论文、复现核心结论、可比口径、差异归因、
   自扩展、保留负结果、运行证据），据此设计目录与文档。
2. AI 先确认 Project 1 平台只有 9 只行业 ETF，选择 TSMOM 而非横截面动量；
   原因是 TSMOM 可逐资产构造，不依赖宽横截面。
3. AI 在写死参数前只做了数据可用性检查（ETF 从 1998-12 开始，12 个月信号
   可在 2000-01 前预热），没有根据回测结果挑样本/参数。
4. 第一次运行发现 `tsmom_12m` 权重为空（函数返回 diagnostics 而非 parts），
   修复后重跑；这类实现错误已在测试中覆盖。
5. 发现原始 CSV 的 SHA-256 与 manifest 不匹配，原因是 Windows CRLF；通过
   `sha()` 规范化 + `.gitattributes` + 统一 LF 解决。
6. 发现图表的标签重叠/刻度拥挤，修复后重新生成；`verify.py` 可重跑对比。

## 5. 数字的可追溯性

| 文档中的数字 | 来源 |
|---|---|
| 收益、波动、Sharpe、回撤、换手、暴露 | `outputs/strategy_summary.csv` |
| 预测回归 | `outputs/predictive_regressions.csv` |
| 符号后的条件收益 | `outputs/signal_diagnostics.csv` |
| Alpha | `outputs/alpha_tests.csv` |
| 极端月份 | `outputs/extreme_months.csv` |
| 敏感性 | `outputs/sensitivity_*.csv` |
| 子样本 | `outputs/sensitivity_subperiods.csv` |
| 相关/市场/事前波动 | `outputs/diagnostics.json` |
| 账本误差 | `outputs/audit.json` |
| 数据质量 | `outputs/quality_report.json` |
| 代码/数据哈希 | `outputs/run_manifest.json` |

原文目标数值（Sharpe 约 1.01、波动约 12%、Table A1 t 值、Table 3 极端月份）
来自论文的公开表格/摘要；不同版本/子样本可能略有差异。提交前请用原文
PDF 核对 `PAPER.md` 第 4 节的引用。

## 6. 建议人类做的复核

1. 用原文 PDF 核对：58 个合约、4 大资产类别、1965–2009、Sharpe 约 1.01、
   波动约 12%、Table A1 的 t 值。
2. 运行 `python run.py`、`python -m unittest discover -s tests -v`、
   `python verify.py`，确认在本机可重复。
3. 抽查 `outputs/audit.json`、`outputs/quality_report.json` 和
   `HAND_CHECKS.md` 的手算。
4. 判断负结果的表述是否适合作业要求：本文的立场是“在这个平台/样本上
   未复现”，不是“TSMOM 无效”。
5. 检查提交清单（`SUBMISSION_CHECKLIST.md`），补上原论文 PDF（如需要）。

## 7. 学术诚信声明

AI 生成了代码与文字草稿，但：

- 所有实证结果由可执行的 `run.py` 产生，不是语言模型编造；
- 所有目标数值都标注了来源（原文表格/摘要）；
- 负结果被保留，没有为了“好看”而隐藏或挑选设定；
- 差异归因明确区分了“有证据的解释”和“未解释的残差”。

如课程要求披露 AI 使用，可直接引用本文件。
