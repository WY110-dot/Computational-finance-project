# Project 2 候选包定点修复逐项答复报告 (P2 Closing Response)

**答复对象**: `CF2026_Project2_Closing_Fixes_20261022.md` ("Project2 候选包复核结果与定点修复指令")  
**复核基准包**: `project2_acceptance_candidate.zip` (SHA-256: `2a18dec5cda577013d908adf008a9981dcef7e55cce9e7327d60d8115fab500b`)  
**本次交付产物**: `project2_acceptance_candidate.zip` (定点修复后最终验收候选包) 与 `project2_review_bundle.zip`  
**作者**: 袁思扬 (学号: 12411852)  
**完成时间**: 2026-10-22  
**状态**: 针对复核指令第 3、4、5 节提出的 3 项必须定点修复（A、B、C），已在代码、测试、产物、报告及入口文档中彻底落实，全套 60 项测试全数通过，新建空白目录复测绝对数值偏差为 0.00e+00。

---

## 1. 对应必须修复 A（第 3 节）：子区间起止日期与真实持有月份不一致

### 1.1 问题诊断与修复方案
- **原错误根源**: 配置项 `experiments.subperiods[*].start/end` 定义的是**持有期边界**。先前实现将 `start` 直接传入回测引擎的 `evaluation_start`，而引擎筛选的是**形成日期**。由于 2020 年 1 月实际形成日为 `2020-01-23`（早于 `2020-02-01`），2022 年 12 月形成日为 `2022-12-30`（早于 `2023-01-01`），导致两个子区间分别漏掉了首个持有月（2020-02 与 2023-01），实际产出仅为 34 个月与 43 个月。此外，第二段终点曾硬编码继承全样本形成终点。
- **修复实现（遵照指令推荐方案）**:
  1. 在 `src/quantcf/pipeline_p2.py` 中实现独立切片函数 `slice_research_subperiod(res_base, start_date, end_date, name)`；
  2. 严格以全样本基准策略 R1（TSMOM 12M）的实际持有期日期 `holding_end_date` 为依据切分子区间，保持形成期确定的权重、风险预算与真实预热历史；
  3. 关联切片权重表、大类贡献表与单资产收益表；以实际 `holding_end_date` 建立 `pd.DatetimeIndex` 传入 `calculate_monthly_metrics(strict_continuity=True)` 重新独立核算各子区间绩效指标；
  4. 支持各子区间独立配置 `start` 与 `end`，彻底解除对全样本终点的硬编码继承；
  5. 严格边界防御：若 `start > end` 或切片无有效持有月份，立即抛出明确的 `ValueError`。

### 1.2 修复前后真实运行证据对照

| 子区间 | 修复前持有月份 | 修复前月数 | **修复后实际持有月份** | **修复后月数** | **Sharpe** | **年化波动率** | **CAGR** |
|---|---|---:|---|---:|---:|---:|---:|
| **R1_sub_2020_2022** | 2020-03 至 2022-12 | 34 | **2020-02-28 至 2022-12-30** | **35** | **1.180314039853** | **16.4547552101%** | **19.6893779664%** |
| **R1_sub_2023_2026** | 2023-02 至 2026-08 | 43 | **2023-01-31 至 2026-08-31** | **44** | **0.646021360990** | **28.6467627897%** | **14.8571083372%** |
| **合计 / 覆盖性** | 34 + 43 = 77 (漏2月) | 77 | **2020-02 至 2026-08** | **79** | — | — | — |

- **核对结果**: 修复后输出的月数（35 / 44）、Sharpe、年化波动率、CAGR 与指令第 3 节 A3 给出的独立核对参考值在 **12 位浮点精度上完全吻合**。
- **全样本覆盖性**: 两个子区间月数相加 $35 + 44 = 79$，恰好覆盖主样本全部 79 个持有月，首尾相接、无缝衔接、不重复、不遗漏。
- **动态自定义终点复验证据**:
  - 在单元测试 `tests/test_tsmom.py::test_subperiod_slicing_and_dynamic_end_date()` 中，将第二段 end 设置为 `2024-12-31`，切片严格止于 `2024-12-31`，实际持有月数精确为 **24 个月**（2023-01 至 2024-12），经断言确认完全不包含 2025/2026 年数据。
- **差异实验表解释文字同步更新**:
  - `outputs_p2_fixed/difference_experiments.csv` 中 EXP_04 的 `n_months` 准确更新为 `35 / 44`，`baseline_value` 为 `1.180`，`alternative_value` 为 `0.646`，解释文字动态更新为：
    > `Historical regime comparison; 2020-2022 Sharpe was 1.180 under lower volatility (16.45%), while 2023-2026 Sharpe declined to 0.646 with higher volatility (28.65%) due to sharp equity whipsaws`
  - 彻底消除了旧文本中夏普与波动率来自不同区间的脱节问题。

---

## 2. 对应必须修复 B（第 4 节）：报告中收益贡献与方差分解数值完全同步

### 2.1 底层文件与计算口径确认
经核对底层两个核心计算文件 `outputs_p2_fixed/research/R1_asset_class_contributions.csv` 与 `outputs_p2_fixed/research/asset_class_variance_decomposition.csv`，其数学定义与指标计算完全一致：
- 年化算术收益贡献定义为：$$12 \times \frac{1}{M}\sum_{m=1}^M \text{contrib}_{c,m}$$
- 组合收益方差分解定义为：$$\beta_c = \frac{\operatorname{Cov}(r_c, R)}{\operatorname{Var}(R)}, \quad \sum_c \beta_c = 100\%$$

底表计算出的真实数值如下：

| 资产大类 | 年化算术收益贡献 (百分点) | 占 R1 年化算术均值比例 | 组合收益方差贡献率 $\beta_c$ | 规范表述口径 |
|---|---:|---:|---:|---|
| **债券 Bonds** | **+10.1944 个百分点** (10.19%) | **53.90%** | **4.56%** | 年化算术收益贡献 +10.19 个百分点，占 R1 均值 53.9% |
| **境内权益 Domestic_Equity** | **+3.0550 个百分点** (3.06%) | **16.15%** | **84.76%** | 年化算术收益贡献 +3.06 个百分点，贡献 84.76% 组合方差 |
| **跨境权益 Cross_Border_Equity** | **+3.2233 个百分点** (3.22%) | **17.04%** | **10.04%** | 年化算术收益贡献 +3.22 个百分点，贡献 10.04% 组合方差 |
| **黄金 Gold** | **+2.4392 个百分点** (2.44%) | **12.90%** | **0.64%** | 年化算术收益贡献 +2.44 个百分点，贡献 0.64% 组合方差 |
| **合计** | **+18.9120 个百分点** (18.91%) | **100.00%** | **100.00%** | **严格等于 R1 年化算术均值 18.91%** |

### 2.2 守恒性检验与单元测试
在新增的回归测试 `tests/test_tsmom.py::test_asset_class_contributions_and_variance_decomposition_conservation()` 中执行了严格的守恒性断言：
1. **逐月守恒**: 79 个月度中，各大类资产当月贡献之和与组合总月收益之差的最大绝对值为 **1.01e-16**（小于 $10^{-15}$，完全符合浮点精度）；
2. **全年化算术贡献守恒**: 四个大类的年化算术贡献之和（18.9119590006%）与 R1 年化算术均值（18.9119590006%）的绝对偏差为 **2.22e-16**（远优于指令要求的 $10^{-10}$ 容差）；
3. **方差分解归一守恒**: 四个大类的方差贡献比例之和严格等于 **1.000000000000**（偏差 0.00e+00）。

### 2.3 报告模板与正文全渠道动态化修复
重构 `src/quantcf/report_p2.py`，新增统一数据解析器 `load_asset_class_attribution_summary()`，在所有输出媒介中彻底删除硬编码的 `9.59` 与 `3.17`，实现动态注入：
1. **Markdown 报告 (`report_en.md`)**:
   - Executive Summary 第 3 点：
     > `Fixed-weight removal attribution shows that Bond ETFs provided an annualized arithmetic return contribution of +10.19 percentage points (accounting for 53.9% of R1's annualized arithmetic mean return)... Conversely, domestic equity ETFs contributed +3.06 percentage points of return but accounted for 84.76% of total portfolio return variance via Cov(rc, R)/Var(R)...`
   - Section 6.2 正文：明确分列 Bonds (+10.19 pp, 53.9% of R1), Domestic Equities (+3.06 pp, 84.76% risk share), Cross-Border (+3.22 pp), Gold (+2.44 pp)，明确标注合计等于 R1 年化算术均值。
2. **HTML 报告 (`report_en.html`)**: 与 Markdown 完全同步呈现 +10.19 与 +3.06。
3. **中文摘要 (`summary_zh.md`)**:
   - 第 2 节第 3 点准确使用“年化算术收益贡献，百分点”：
     > `债券类: 年化算术收益贡献 +10.19 个百分点（占 R1 年化算术均值的 53.9%）；若移除债券，组合夏普由 0.792 跌至 0.371。`  
     > `境内权益: 年化算术收益贡献 +3.06 个百分点，但通过协方差分解证实境内权益贡献了组合 84.76% 的总收益方差...`
4. **PDF 报告 (`report_en.pdf`)**:
   - 通过 PyMuPDF 真实提取文本验证：
     - **第 1 页 Executive Summary**: 包含 `+10.19 percentage points ann. arithmetic contribution, 53.9% of R1 mean` 与 `84.76% of portfolio return variance (ann. arithmetic contribution +3.06 percentage points)`；旧值 9.59% 已彻底不存在；
     - **第 5 页 Section 7**: 增加了对四大类年化算术贡献（Bonds +10.19 pp, Cross-Border +3.22 pp, Equities +3.06 pp, Gold +2.44 pp，合计等于 R1 均值 18.91%）及方差分解（权益 84.76%）的明确段落阐述；
   - 经自动化脚本断言确认：全篇 PDF 中 10.19 与 3.06 均正常呈现，旧值 9.59 与 3.17 出现次数为 0。

---

## 3. 对应必须修复 C（第 5 节）：当前入口文档的残留清理与规范表述

### 3.1 `README_PROJECT2.md`
1. **多期限执行对比指标纠正**:
   - “Core Takeaways” 第 3 点纠正为：`Under realistic execution constraints with 3 bps transaction fees, the multi-horizon strategy achieved a higher Sharpe ratio (T2 1.350 vs T1 1.303; 1.279 under 10 bps friction) and a lower maximum drawdown (-3.38% vs -4.25%) than the single 12-month lookback.`
   - 修正了 `1.332 vs 1.279` 的笔误，与上方综合指标表格（T1 1.303, T2 1.350）完全对齐，并保留了 10 bps 摩擦下 T1 达到 1.279 的说明。
2. **目录树修正**:
   - 彻底移除了未随包交付的旧 `outputs_p2/`，将目录结构修正为唯一的现行主交付目录 `outputs_p2_fixed/`，并将下属全部 CSV 指标表、图表集、报告、交易明细与运行指纹正确归于其下。
3. **单资产动量结论措辞收紧**:
   - 将原“confirming Moskowitz et al.'s finding across an independent ETF asset class”修改为与正文一致的严谨学术措辞：
     > `providing partial empirical support in a different ETF sample for Moskowitz et al.'s directional finding (where 58 of 58 global contracts were positive, and 52 of 58 were significant at 5%, p. 236)`
   - 明确指出 17/21 正夏普构成了宏观方向的部分支持，不把 17/21 夸大为完全复现原文全部 58 个合约的结论。

### 3.2 `docs/project2/remaining_work.md`
- 在文件顶部新增醒目的 GitHub 规范警告横幅（Alert Banner），明确标注该文件为“历史阶段开发计划归档说明”，记载基准测试 47 项及旧目录 `outputs_p2/` 属于前期开发历史状态；
- 指引读者直接查阅现行主答复文件 `P2_CLOSING_RESPONSE.md` 与根目录 `README_PROJECT2.md`。

### 3.3 `DEMO_P2.md`
- 将配套资料中的“审查回复说明”明确指向本文件 `P2_CLOSING_RESPONSE.md`，并将前序答复标为历史备查；
- 在演示要点第 5 节中，同步补充资产类别收益贡献（+10.19 pp / 84.76% 方差）与子区间（35/44 月）切片实证数据。

---

## 4. 前序复核确认项继续保持状态

本轮修复在完全保持前期已确认成果的前提下进行，所有已确认项状态如下：

| 项目 | 确认依据 | 现行状态 |
|---|---|---|
| **代码与目录绝对隔离** | `git status` 严格确认 | `final_project` 目录 **100% 保持原始状态，0 字节改动** |
| **文献出处区分** | `original_vs_replication.csv` | Figure 3 标注为未标记数值（N/A），独立复算值 1.385 / 17.08% 归入参考列，删除 Table 4 错误出处 |
| **主样本持有月数** | `strategy_summary.csv` | R1、R2、R3、R4 主研究保持严格 79 个月 |
| **执行模式与交易审计** | `backtests/` | T1/T2 保持严格 1599 个交易日（2020-02-03 至 2026-08-31），8 套账本全部通过资金守恒与调仓审计 |
| **配置强约束** | `pipeline_p2.py`, `tsmom.py` | 非等权多期限（如 `[1, 0, 0]`）、非法费用档位、错误年化参数在主入口直接抛出 `ValueError` 拒绝 |
| **时序与缺月处理** | `research_backtest.py` | 组合与单资产主流程均采用 DatetimeIndex，缺月反例不输出错误 CAGR |
| **独立解析手算核验** | `test_tsmom.py` | EWMA、两资产多空权重（+1.0/-2.0）、预算分配与手算完全一致（偏差 $< 10^{-12}$） |

---

## 5. 运行验证与空白目录复测证据

### 5.1 全套测试套件运行
在当前代码库执行：
```powershell
uv run --locked pytest
```
**结果**: **60 passed in 8.63s**（全套 60 项测试全数通过，包含新增的子区间切片测试与大类贡献守恒性测试）。

### 5.2 离线全管线运行与报告生成
```powershell
uv run --locked python run_project2.py --config config/project2_tsmom.json --out outputs_p2_fixed --offline
uv run --locked python build_report_project2.py --out outputs_p2_fixed
```
**结果**: 全流程离线顺畅完成，生成全部 18 套实验产物、8 套执行交易账本与审计、图表集及四份报告。

### 5.3 新建空白目录确定性复跑比对
运行至全新空白目录 `outputs_p2_verification`：
```powershell
uv run --locked python run_project2.py --config config/project2_tsmom.json --out outputs_p2_verification --offline
```
比对 `outputs_p2_fixed` 与 `outputs_p2_verification` 对应文件：

| 校验产物 | 数据形状 | 数值最大绝对偏差 | 字符串内容一致性 | 判定状态 |
|---|---|---:|---|---|
| `strategy_summary.csv` | (18, 19) | **0.00e+00** | 100% 相同 | **PASS** |
| `original_vs_replication.csv` | (5, 13) | **0.00e+00** | 100% 相同 | **PASS** |
| `difference_experiments.csv` | (7, 17) | **0.00e+00** | 100% 相同 (路径已归一化) | **PASS** |
| `experiments_inventory.csv` | (18, 14) | **0.00e+00** | 100% 相同 | **PASS** |
| `key_result_trace.csv` | (12, 13) | **0.00e+00** | 100% 相同 (路径已归一化) | **PASS** |
| `research/R1_tsmom12_monthly_portfolio.csv` | (79, 10) | **0.00e+00** | 100% 相同 | **PASS** |
| `research/R1_sub_2020_2022_monthly_portfolio.csv` | (35, 10) | **0.00e+00** | 100% 相同 | **PASS** |
| `research/R1_sub_2023_2026_monthly_portfolio.csv` | (44, 10) | **0.00e+00** | 100% 相同 | **PASS** |
| `research/R1_asset_class_contributions.csv` | (79, 7) | **0.00e+00** | 100% 相同 | **PASS** |
| `research/asset_class_variance_decomposition.csv` | (4, 6) | **0.00e+00** | 100% 相同 | **PASS** |
| `backtests/T1_base_3bps_ledger.csv` | (1599, 31) | **0.00e+00** | 100% 相同 | **PASS** |
| `backtests/T2_base_3bps_ledger.csv` | (1599, 31) | **0.00e+00** | 100% 相同 | **PASS** |

比对日志已更新至 `outputs_p2_fixed/reproducibility_check.json`，验证目录 `outputs_p2_verification` 已安全清理。

---

## 6. 最终验收候选包与交付材料清单

### 6.1 压缩包打包规范
我们已在 `project2 ysy/` 及工作区根目录同步生成最新的交付压缩包：
- **`project2_acceptance_candidate.zip`**: 最终验收候选包
- **`project2_review_bundle.zip`**: 外部复核材料包

### 6.2 包含内容
1. **源码与配置**: `src/quantcf/` (含纯函数数学模块、切片模块、研究与真实执行引擎、报告生成引擎)、`config/project2_tsmom.json`、`pyproject.toml`、`uv.lock`；
2. **测试套件**: `tests/test_tsmom.py` (60 项全覆盖测试)；
3. **方法与协议文档**: `docs/project2/protocol.md`、`method_mapping.md`、`method_checks.md`、`platform_changes.md`、`remaining_work.md` (已归档)；
4. **主输出目录 (`outputs_p2_fixed/`)**:
   - `strategy_summary.csv`、`original_vs_replication.csv`、`difference_experiments.csv`、`experiments_inventory.csv`、`key_result_trace.csv`；
   - `research/` (月度组合收益、权重、贡献分解、子区间 35/44 月切片)；
   - `backtests/` (8 套执行模式明细账本与审计记录)；
   - `figures/` (高分辨率图表集，含 Fig 2 上部、Fig 3 并排图、大类贡献分解图、多期限对比图)；
   - `runs/` (实验记录器全生命周期哈希指纹)；
   - `reproducibility_check.json` (最新确定性复验结果)；
   - `report_en.md`, `summary_zh.md`, `report_en.html`, `report_en.pdf`；
5. **项目说明与答复**: `README_PROJECT2.md`、`DEMO_P2.md`、`PROJECT_LOG.md` 以及本答复 `P2_CLOSING_RESPONSE.md`。

本候选包已满足定点修复指令的所有技术与规范要求，可供进行最终验收。
