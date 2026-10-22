# Project 2 任务完成状态与待办追踪清单 (Remaining Work & Status)

**编制日期**: 2026-10-22  
**作者**: 袁思扬 (学号: 12411852)  
**依据文档**: `CF2026_Project2_Next_Development_Instructions_20261022.md`  

---

## 1. 已由现有文件与测试确认项 (Confirmed by Files & Tests)

| 项目 | 确认依据与路径 | 确认状态 |
|---|---|---|
| **代码库与环境隔离** | `final_project/` 目录完全保持原始快照状态；P2 工作严格局限在 `project2 ysy/` | 已确认（git status 无修改） |
| **基础与新增测试** | 47 项单元测试在 `uv run --locked pytest` 下全部通过（8.0s） | 已确认 |
| **官方参考数据接入 (O1)** | AQR 官方 Excel 数据已完整解析（300 个月，1985-01 至 2009-12），年化收益 17.08%，夏普 1.385 | 已确认 (`outputs_p2/reference/aqr_tsmom_original_paper_factors.csv`) |
| **核心复现框架 (R1, R2)** | 12M TSMOM 与 Passive Long 研究回测运行通畅，产出月频收益、权重、贡献表 | 已确认 (`outputs_p2/research/`) |
| **自主扩展框架 (R4, T2)** | 3/6/12M 多期限等权信号生成与理论/执行层运行通畅 | 已确认 (`outputs_p2/research/`, `outputs_p2/backtests/`) |
| **交易约束执行层 (T1, T2, T3)** | 接入 P1 Broker 账本，完成次日开盘成交、非负持仓、真实费用与零费用重跑 | 已确认 (`outputs_p2/backtests/`) |
| **论文原图矢量提取** | 已使用 PyMuPDF 裁切出论文刊发版高分辨率原始图表 | 已确认 (`references/fig2_upper_original.png`, `fig3_original.png`) |

---

## 2. 本轮需修正与深度补强项 (To Be Fixed / Enhanced This Round)

| 待办事项 | 问题诊断与改动方案 | 计划成果路径 |
|---|---|---|
| **过强论断措辞收紧** | 第一轮结论中“大类资产起决定性作用”“改进全面优于”等表述超出直接实证证据边界。需收紧为严谨的描述性实证观察，并阐明收益/风险/暴露的权衡代价。 | `outputs_p2/report_en.md`, `summary_zh.md`, `report_en.pdf` |
| **大类资产贡献证据补全** | 补充现有 21 只 ETF 的大类资产类别映射（债券、黄金、美股跨境、国内权益），计算各类别月度实际收益与权重贡献序列，并进行**固定原权重下的类别移除归因实验**。 | `outputs_p2/research/R1_asset_class_contributions.csv`, `outputs_p2/experiments/asset_class_removal_attribution.csv` |
| **核心指标计算与口径核实** | 严格区分并分列算术年化均值 (`ann_arithmetic_mean`)、复利年化 (`cagr`)、年化波动率 (`ann_vol`)、夏普比率 (`sharpe`)、最大回撤 (`max_drawdown`) 与胜率 (`win_rate`，明确标注月胜率 vs 日胜率)；确认单资产 Sharpe 未除以动态 $N_m$。 | `outputs_p2/strategy_summary.csv`, `outputs_p2/research/R1_single_asset_metrics.csv` |
| **主张数值全链条追踪表** | 建立 `key_result_trace.csv`，将报告中所有核心数据主张（17/21 正夏普、R1/R2、Bridge、R1/R4、T1/T2、宽基子集、O1）与底层数据文件、列名及计算公式逐一锚定。 | `outputs_p2/key_result_trace.csv` |
| **实验清单盘点表** | 将 18 组实验整理为包含 `run_id, strategy_id, mode, signal, sample, weighting, cost, outputs, status` 的完整清单表。 | `outputs_p2/experiments_inventory.csv` |
| **多期限扩展同表对照** | 将 R1 vs R4 与 T1 vs T2 放在同张全指标对照表中，列明收益、CAGR、波动率、夏普、回撤、换手率、交易手续费与成交笔数。 | `outputs_p2/report_en.md`, `summary_zh.md` |
| **空目录数值一致性复跑** | 使用全新输出目录（`outputs_p2_verification`）完整复跑，记录浮点容差比较与复验日志。 | `outputs_p2/development_completion.log`, `outputs_p2/reproducibility_check.json` |
| **外部复核材料打包** | 生成包含所有代码、文档、配置、CSV 产物、测试与运行日志的压缩包。 | `project2_review_bundle.zip` |
| **继续开发进展汇报** | 编写中文继续开发报告，逐一回答本轮确认、修复、数字变动、补充证据、收紧结论及未完成事项。 | `P2_CONTINUATION_REPORT.md` |

---

## 3. 尚缺资料与外部依赖 (Missing Data / External Dependencies)

| 资料项 | 现状与处理策略 | 影响说明 |
|---|---|---|
| **原论文 58 种期货/远期底层逐笔持仓与逐日价格** | 原文数据作者未公开底层逐日成交明细，仅公开了最终月度组合因子收益（AQR 官方 Excel 数据已纳入本项目）。 | 属于客观不可得，本项目在协议与报告中明确声明为“替代样本上的方法复现”，不伪造逐笔期货对齐。 |

---

## 4. 选定范围外内容声明 (Declared Out of Scope)

以下内容已由任务书明确排除在本次复现范围外，无需为此扩展：
1. **CFTC COT 交易员持仓报告多空回归分析**；
2. **跨国股票资产定价多因子 Alpha 检验（Fama-French / Carhart 4-factor）**；
3. **VAR 宏观溢出效应模型**；
4. **商品期货展期收益（Roll Yield / Convenience Yield）分解**。

上述内容在报告局限性章节中如实披露，不影响本次核心时间序列动量复现与自主多期限扩展的完整性。

