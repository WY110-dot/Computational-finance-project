# 提交清单（按 CF2026_Project2.pdf 要求）

> 课程要求（从 PDF 归纳）：选一篇方法清晰的论文；在 Project 1 平台上复现
> 一个核心结论；理解方法/未指定细节；把设定写进配置；复用 P1 模块并补充
> 新模块；小样本手算；保存运行证据；在可比口径下并排比较原文与本次的
> 图表/关键指标；解释差异（实现错误、数据/样本、预处理/交易、原文未指定、
> 无法解释）；加入单因子控制的自扩展；保留负结果；提交原论文/协议、代码与
> 数据说明、结果/报告、局限与下一步。评价重点是理解、实现、验证、解释，
> 不只是“结果是否一样”。

## 1. 交付物对照

| 要求 | 文件/位置 | 状态 |
|---|---|---|
| 选定论文与引用 | `PAPER.md` 第 1 节 | ✅ |
| 论文方法、目标表格/数值 | `PAPER.md` 第 2–4 节 | ✅ |
| 原文指定 vs 未指定细节 | `PAPER.md` 第 5–6 节 | ✅ |
| 复现范围 | `PAPER.md` 第 7 节；`REPORT.md` 第 1.3 节 | ✅ |
| 预先登记的问题/假设/判定 | `RESEARCH_PROTOCOL.md` | ✅ |
| 所有设定写进配置 | `config.json`；`run_manifest.json` | ✅ |
| Project 1 模块复用 | `src/data.py`、`src/backtest.py`、`src/plots.py`；`README.md` 表格 | ✅ |
| 新增模块 | `src/tsmom.py`、`src/stats.py`、`tests/`、`verify.py`、`build_report.py` | ✅ |
| 小样本手算 | `HAND_CHECKS.md`；`tests/` | ✅ |
| 运行证据 | `outputs/`（CSV/JSON/PNG）；`audit.json`；`run_manifest.json` | ✅ |
| 原文 vs 本次并排比较 | `REPORT.md` 第 4、5 节；`DIFFERENCE_ATTRIBUTION.md` | ✅ |
| 差异归因五类 | `DIFFERENCE_ATTRIBUTION.md` 第 1–5 节 | ✅ |
| 敏感性证据 | `REPORT.md` 第 5.5、5.6 节；`outputs/sensitivity_*.csv` | ✅ |
| 单因子自扩展 | `REPORT.md` 第 7 节；`outputs/strategy_summary.csv` | ✅ |
| 保留负结果 | `REPORT.md` 摘要/结论；`DIFFERENCE_ATTRIBUTION.md` | ✅ |
| 代码与数据说明 | `README.md`、`DATA.md`、`pyproject.toml` | ✅ |
| 结果/报告 | `REPORT.md`；`output/pdf/CF2026_Project2_Report.pdf`（17 页，已逐页检查） | ✅ |
| 局限与下一步 | `REPORT.md` 第 9 节 | ✅ |
| 原论文 PDF | `paper/`（未自动下载，版权/网络限制） | ⚠️ **需手动放入** |
| AI 使用说明 | `AI_ASSISTANCE.md` | ✅ |

## 2. 运行命令（提交前）

```bash
cd project2
python run.py
python -m unittest discover -s tests -v
python verify.py
python build_report.py
```

预期：

- `run.py` 约 25 秒，生成 9 个策略、敏感性表、图、审计与运行清单；
- 单元测试全部通过；
- `verify.py` 写 `outputs/verification.json`，`status = PASS`；
- `build_report.py` 生成 `output/pdf/CF2026_Project2_Report.pdf`。

## 3. 提交前人工检查

- [ ] 用原文 PDF 核对 `PAPER.md` 第 4 节的 1.01 / 12% / Table A1 t 值；
- [ ] 确认 `paper/` 中已放入原论文（或按课程要求提供链接/引用）；
- [x] 打开 `output/pdf/CF2026_Project2_Report.pdf`，检查中文、表格、图、页码
      （17 页均已渲染检查，无溢出/孤立标题）；
- [x] 抽查 `outputs/audit.json`、`outputs/quality_report.json`、
      `outputs/verification.json`（`status = PASS`，34 个 CSV 最大差异 0）；
- [ ] 确认 `git status` 中没有遗漏的代码/数据/文档；
- [ ] 如课程要求匿名/去标识，检查提交文件中的姓名/路径；
- [ ] 确认负结果的表述符合课程要求（本文：在 9 只行业 ETF、2000–2024
      上未复现；不是“TSMOM 无效”）。

## 4. 文件大小与依赖

- 代码 + 文档：小（< 1 MB）；
- 原始数据：约 7.6 MB（9 个 CSV）；
- `outputs/`：包含每日/逐笔 CSV，可能约数十 MB；提交时可按课程要求
  只保留汇总/图/审计，或压缩；
- 依赖固定版本见 `pyproject.toml`；无网络运行。

## 5. 可能的扣分点与应对

| 风险 | 应对 |
|---|---|
| 原文目标数值引用不精确 | 提交前用原文 PDF 核对；`PAPER.md` 已标注“约”与表格来源 |
| 资产池与原文不可比 | 在 `REPORT.md` 第 4、6 节明确说明；不把负结果过度外推 |
| 数据不是 point-in-time | `DATA.md` 第 5 节明确披露；下一步用期货/point-in-time 数据 |
| 负结果被误读为“实现失败” | `HAND_CHECKS.md`、`audit.json`、`tests/`、`verify.py` 提供证据 |
| PDF 中文字体缺失 | `build_report.py` 使用 reportlab 的 `STSong-Light` CID 字体，离线可用 |
| 输出太大 | 提交时保留汇总 CSV/JSON/PNG；每日/逐笔 CSV 可按需删除（但会削弱运行证据） |
