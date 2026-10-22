# Project 2 最终验收与交付核验报告 (FINAL ACCEPTANCE)

**项目名称**: Computational Finance (CF2026) — Project 2: Time Series Momentum Replication & Multi-Horizon Extension  
**作者/学生**: 袁思扬 (学号: 12411852)  
**验收基准指令**: `CF2026_Project2_Closing_Fixes_20261022.md` ("Project2 技术复核结论与最终验收、打包指令")  
**基准候选包 SHA-256**: `12488cc02b9216ff421314a6f54ad99428f6e65bf5c43c92b69d72b40a3935dd`  
**代码/配置版本**: Git Commit / Workspace Snapshot `20261022-p2-final`  
**验收日期**: 2026-10-22  
**最终判定**: **PASS** (全部技术与规范要求 100% 达成，零真实缺失项)

---

## 1. 对应课程与教师核心要求的文件映射索引

| 课程/教师任务书要求 | 核心考察内容 | 项目对应交付文件与位置 | 本地核验状态 |
|---|---|---|---|
| **第 2 页：理解原方法并比较核心结论** | 动量方向、波动率缩放、原图原表与复现对比 | `references/` (原论文 PDF 及提取矢量原图)<br/>`outputs_p2_fixed/original_vs_replication.csv`<br/>`outputs_p2_fixed/figures/fig2_single_asset_sharpe.png`<br/>`outputs_p2_fixed/figures/fig3_cumulative_comparison.png` | **PASS** (17/21 正夏普，来源与定性走势清晰区分) |
| **第 4 页：P1 平台接入、配置、手算与运行证据** | 架构复用、配置驱动、独立小样本手算、运行生命周期 | `docs/project2/platform_changes.md`<br/>`config/project2_tsmom.json`<br/>`docs/project2/method_checks.md`<br/>`tests/test_tsmom.py`<br/>`outputs_p2_fixed/runs/`<br/>`outputs_p2_fixed/reproducibility_check.json` | **PASS** (P1 模块解耦复用，手算精度 $< 10^{-12}$，指纹全记录) |
| **第 5 页：原/新结果、可比性与中间证据** | 样本边界声明、中间权重、大类贡献分解 | `docs/project2/protocol.md`<br/>`outputs_p2_fixed/research/R1_tsmom12_monthly_weights.csv`<br/>`outputs_p2_fixed/research/R1_asset_class_contributions.csv`<br/>`outputs_p2_fixed/research/asset_class_variance_decomposition.csv` | **PASS** (79 个持有月，四大类收益贡献守恒且方差分解明确) |
| **第 6 页：排错、单因素差异实验与限制** | 控制变量实验、宏观机制差异、剩余限制 | `outputs_p2_fixed/difference_experiments.csv` (EXP_01 至 EXP_07)<br/>`outputs_p2_fixed/report_en.md` (Sections 6, 9, 10) | **PASS** (7 组单因素对比，含缩放、做空限制、估计器、子区间等) |
| **第 7 页：原方案与多期限扩展同条件对照** | 3/6/12M 等权扩展、全指标矩阵、客观保留负面结果 | `outputs_p2_fixed/strategy_summary.csv`<br/>`outputs_p2_fixed/experiments_inventory.csv`<br/>`outputs_p2_fixed/figures/fig_multi_horizon_comparison.png`<br/>`outputs_p2_fixed/backtests/` (8 组交易明细与审计) | **PASS** (R1 vs R4、T1 vs T2 同表列出全部收益/风险/换手/费用，客观保留代价) |
| **第 8 页：协议规范、代码数据说明、报告与演示** | 研究协议、数据字典、中英文报告、PDF 排版、演示指导 | `docs/project2/protocol.md`, `data_dictionary.md`<br/>`README_PROJECT2.md`, `DEMO_P2.md`, `PROJECT_LOG.md`<br/>`outputs_p2_fixed/report_en.md`, `report_en.html`<br/>`outputs_p2_fixed/report_en.pdf`, `summary_zh.md` | **PASS** (四份报告格式完备，7 页专业版式 PDF 成功渲染) |

---

## 2. 验收核验细项：本地检查结果与外部复核区分

### 2.1 本地实际检查结果 (Local Verification)
1. **测试套件**: 执行 `uv run --locked pytest`，**60 项测试全部通过** (用时约 8.63s)；
2. **交易账本审计**: 8 套真实执行层账本审计（0 bps, 3 bps, 10 bps）全数通过资金守恒与无负持仓核验；
3. **样本月数与区间对齐**:
   - 主研究样本（R1, R2, R3, R4, Bridge, Estimator, Broad）全样本保持 **79 个持有月**（2020-02 至 2026-08）；
   - 执行层 T1, T2, T3 保持 **1599 个交易日**（2020-02-03 至 2026-08-31），含首日收益；
   - 子区间 1 (`R1_sub_2020_2022`)：**35 个持有月**（2020-02-28 至 2022-12-30），Sharpe = `1.180314039853`，年化波动率 = `16.4547552101%`，CAGR = `19.6893779664%`；
   - 子区间 2 (`R1_sub_2023_2026`)：**44 个持有月**（2023-01-31 至 2026-08-31），Sharpe = `0.646021360990`，年化波动率 = `28.6467627897%`，CAGR = `14.8571083372%`；
   - 两段合计 $35 + 44 = 79$ 个月，完全覆盖 R1 主样本持有期，无重复无遗漏；
4. **大类资产收益贡献与方差分解数值**:
   - 债券类 Bonds：年化算术收益贡献 **+10.1944 个百分点**（报告格式化为 `+10.19`），占 R1 年化算术均值（18.91%）的 **53.90%**；
   - 境内权益 Domestic_Equity：年化算术收益贡献 **+3.0550 个百分点**（报告格式化为 `+3.06`），通过协方差分解贡献了 **84.76%** 的总组合方差；
   - 四大类年化算术收益贡献之和（18.9120%）与 R1 年化算术均值（18.9120%）偏差仅为 **2.22e-16**；逐月大类贡献之和与组合月收益偏差最大为 **1.01e-16**；
   - Markdown、HTML、PDF（第 1 页与第 5 页）及中文摘要四份报告中数字完全一致，旧值 `9.59%` 与 `3.17%` 已彻底清除；
5. **新建空目录确定性复测**:
   - 在空白目录 `outputs_p2_verification` 独立重跑，12 张核心表格与明细账本比对最大数值绝对偏差为 **0.00e+00**，生成 `reproducibility_check.json`。

### 2.2 与外部独立复核证据的区别说明 (External Audit Alignment)
- 本地在 Windows 环境下验证最大绝对数值偏差为 0.00e+00；
- 外部复核在 Linux / 跨系统环境下复跑时，汇总指标存在约 $2.75 \times 10^{-14}$、交易账本金额存在约 $1.40 \times 10^{-9}$ 的微小偏差，属于 IEEE 754 双精度浮点库在跨操作系统编译环境下的正常精度差异，而非代码确定性缺陷；
- 外部复核修改配置将第二段 end 设置为 `2024-12-31` 跑通真实主流程，实际输出为 2023-01 至 2024-12 共 24 个月，已在本地集成测试与主入口验证中双重闭环确认。

---

## 3. 打包交付策略与目录清理

根据指令第 3.1 节要求：
1. **彻底排除旧目录**: 旧的 `outputs_p2/`（含 65 个前期过程文件及旧版报告）被**完全排除在最终提交包之外**；
2. **唯一现行交付目录**: 最终包中唯一的正式交付成果目录为 **`outputs_p2_fixed/`**；
3. **保留本地原始历史**: 本地工作区磁盘上保留原始研究目录，不强制删除本地历史，仅在打包暂存阶段做严格过滤；
4. **排除无关项**: 排除虚拟环境 `.venv/`、缓存 `__pycache__/`、`.pytest_cache/`、版本控制 `.git/`、过程临时目录 `outputs_p2_verification/` 及嵌套旧 ZIP 文件。

---

## 4. 作者独立学术责任与 AI 辅助真实情况确认

- **学生作者**: 袁思扬 (学号: 12411852)
- **学术责任声明**: 本人独立构思并核查了全部研究方案、数学推导、核心代码算法、测试用例断言、实证结果与最终报告。对于本成果中所有数据真实性、逻辑严谨性及合规性承担独立完整的学术责任。
- **AI 协作披露**: 详细记录于 [AI_ASSISTANCE.md](AI_ASSISTANCE.md)。ChatGPT 辅助用于前期方案探讨与复核反例分析；Antigravity (Gemini 3.8 Flash High) 与 VSCode + Codex 辅助用于工程管线脚手架、图表排版排版代码及 ReportLab PDF 跨平台字体编译；所有实证数据与指标均由本地 Python 代码基于真实数据快照实际计算生成，绝无人工或 AI 虚构数据。

---

## 5. 验收结论汇总

| 验收维度 | 核心标准 | 结论 |
|---|---|:---:|
| 基础研究复现 | 12M TSMOM (R1) vs 被动多头 (R2) 及单资产动量 (Fig 2, Fig 3) | **PASS** |
| 自主多期限扩展 | 3/6/12M 等权扩展 (R4, T2) 及收益/回撤/换手/费用权衡对照 | **PASS** |
| 单因素控制实验 | 7 项单因素控制实验及大类资产移除归因、方差分解 | **PASS** |
| 交易账本与执行 | T1/T2/T3 次日开盘、无负持仓、无借贷、1599 交易日及 8 套审计 | **PASS** |
| 代码质量与测试 | 60 项 Pytest 测试 100% 通过，两资产手算及各项反例守恒 | **PASS** |
| 可复现性与一致性 | 新建空白目录复测数值偏差 0.00e+00，数据/代码哈希全记录 | **PASS** |
| 交付规范与目录过滤 | 唯一交付 `outputs_p2_fixed/`，彻底排除旧 `outputs_p2/` | **PASS** |
| **综合总体判定** | **全部达到课程 Project 2 任务书及复核指令验收标准** | **PASS** |

