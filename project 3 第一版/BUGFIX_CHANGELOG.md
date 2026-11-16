# Project 3 第一轮复核缺陷修复日志 (BUGFIX_CHANGELOG.md)

- **工程版本**: v2.0.0-engineering-repair
- **复核日期**: 2026-11-16
- **修复对象**: 针对 ChatGPT Reviewer 第一轮复核指出的 7 项实质缺陷进行逐项工程纠错、证据重构与同源报告生成。
- **研究边界声明**: 严格保持 $A, B/F_1, C, F_2, F_3, A_0$ 原研究定义、参数与时间边界，不调参、不扩搜、不为追求收益美化结果，诚实接受实际实证结果。

---

## 1. 第 1 节修复：月度收益与费用区间的工程纠错

### 缺陷表现与复核反例确认
- **问题定位**: 原 `src/quantcf/project3_pipeline.py` 中 `execute_broker_simulation` 使用 `sub_leg['daily_return'].iloc[1:]`，计算的是 entry 收盘到 exit 收盘，遗漏了 entry 开盘成交后的日内涨跌与交易手续费，且计入了 exit 开盘以后的日内涨跌；
- **反例复现**:
  1. *反例 1 (日内跳涨)*: 初始资金 100 万，99% 投资，零费率。entry 开盘 100、收盘 110；exit 开盘 110、收盘 220。正确 open-to-open 收益为 $+9.90\%$，原函数报告约 $+99.09\%$；
  2. *反例 2 (平价扣费)*: 价格恒为 100，单边 3 bps。账户因首日开盘建仓扣除约 297 元手续费，正确收益为 $-0.0297\%$，原函数报告 $0.0\%$；
  3. *反例 3 (费用双重统计)*: 月费统计按 `[en, ex]` 双端包含切片，导致相邻月份重叠调仓日的费用被重复累加（US9 基准 3 bps 月费合计被误报为 21,623 元，而真实日账本仅为 10,960 元）。

### 纠错措施与数学实现
1. **统一调仓边界与开盘净值定义**:
   - 设调仓序列为 $T_1, T_2, \dots, T_K$，最终评估边界为 $T_{K+1}$；
   - 第 $k$ 期持有区间严格定义为从 $T_k$ 开盘成交前净值 $W(T_k^-)$ 至 $T_{k+1}$ 开盘成交前净值 $W(T_{k+1}^-)$；
   - 净月度持有期收益严格定义为：
     $$R_{\text{net}}(k) = \frac{W(T_{k+1}^-)}{W(T_k^-)} - 1$$
   - 严格满足开盘边界的代数连乘伸缩性质（Telescoping Compounding）：
     $$\prod_{k=1}^K (1 + R_{\text{net}}(k)) = \frac{W(T_2^-)}{W(T_1^-)} \times \frac{W(T_3^-)}{W(T_2^-)} \times \dots \times \frac{W(T_{K+1}^-)}{W(T_K^-)} = \frac{W(T_{K+1}^-)}{W(T_1^-)}$$
2. **唯一无重叠费用归属**:
   - 第 $k$ 期建仓/调仓发生于 $T_k$ 开盘，其产生之全部手续费（`transaction_cost(T_k)`）唯一归属于第 $k$ 期；
   - $T_{k+1}$ 开盘之调仓费用归属于下一期（第 $k+1$ 期），严禁双端包含；
   - 满足全局费用守恒断言：
     $$\sum_{k=1}^K \text{fees}_k = \sum_{t \in \text{ledger}} \text{transaction\_cost}(t) = \sum \text{fills['fee']}$$
3. **期末边界处理**:
   - 最终持有期在 $T_{K+1}$ 开盘终止，计入 $T_{K+1}$ 开盘成交前以开盘价盯市之持仓市值与现金，不在期末强行执行清仓抛售，避免将未发生的清仓成本混入最后一期。
4. **最大回撤与年化收益指标分列**:
   - 回撤计算序列前置插入初始净值 $1.0$（`np.insert(nav, 0, 1.0)`），确保捕捉首期亏损；
   - 指标表中严格区分标注**算术年化均值（Arithmetic Mean Annualized Return）**与**复合年化增长率（CAGR）**；
   - 严格区分标注**月度最大回撤（Monthly Max Drawdown）**与**日度盯市最大回撤（Daily Max Drawdown）**。
5. **单元测试与对账证据**:
   - 新增 `tests/test_project3_counterexamples.py`，完整覆盖上述反例 1（验证 $9.9\%$）、反例 2（验证 $-0.0297\%$ 与 297 元手续费）、反例 3（费用守恒与连乘对账），全部通过；
   - 生成 `outputs/reconciliation.csv` 与 `outputs/reconciliation.json`，48 组策略/成本情景全部实现费用 0 偏差与复利 0 偏差。

---

## 2. 第 2 节修复：严格 P5 物理隔离与保留段历史暴露说明

### 缺陷表现与事实确认
- **问题定位**: 原 `load_universe_data` 将包含 2025–2026 年快照的数据面板完整加载，并在 `run_project3.py` 中直接计算了全历史每日截面相关性，导致 `outputs/diagnostics/daily_correlations.csv` 中包含 CN21（至 2026-09-18 共 417 条）与 US9（至 2026-02-06 共 275 条）的保留期记录，且 PDF 第 2 页图表绘制了该保留段曲线；
- **纠错与事实诚实说明**:
  1. **保留段暴露范围**: 经排查，第一轮运行中暴露的内容为新因子 $F_1$ 与 12M 动量在 2025–2026 年的**每日截面相关系数（Pearson / Spearman）**。因 `get_holding_periods` 已设置 `exit_date <= 2024-12-31`，2025+ 的持仓标签与策略回测净值并未在第一轮生成或查看；
  2. **绝对无调参承诺**: 我们未利用暴露的截面相关性进行任何因子定义修改、阈值调整或参数微调，原 F1/F2/F3/A/B/C 定义保持绝对冻结；
  3. **受限说明**: 鉴于相关性时间序列曾在第一轮被绘制，根据学术诚信要求，如实在此记录该暴露事实，不再声称“物理上从未接触”。

### 物理隔离纠错措施
1. **数据加载入口物理截断**:
   - 在 `src/quantcf/project3_pipeline.py` 的 `load_universe_data` 中引入 `max_date="2024-12-31"` 硬性截断参数：
     ```python
     cn_panel = cn_panel[cn_panel["date"] <= pd.Timestamp("2024-12-31")].copy()
     us_panel = us_panel[us_panel["date"] <= pd.Timestamp("2024-12-31")].copy()
     assert cn_panel["date"].max() <= pd.Timestamp("2024-12-31")
     assert us_panel["date"].max() <= pd.Timestamp("2024-12-31")
     ```
   - 截断后，CN21 面板最大日期为 2024-12-31，US9 面板最大日期为 2024-12-31；
2. **全派生表与图表输入断言**:
   - 在因子生成、每日相关性、标签计算等所有下游函数前设置硬断言，确保进入运算的面板最大日期 $\le 2024-12-31$；
   - 彻底清除所有包含 2025+ 记录的旧派生表；
   - 重新生成 `daily_correlations.csv`，确认 CN21 与 US9 的最大日期均严格停留在 2024-12-31，2025+ 记录数确凿为 0。

---

## 3. 第 3 节修复：报告、CSV 与执行摘要同源化与硬编码清除

### 缺陷表现
- 原 `VSCODE_REPORT.md` 与图表文字残留了早期粗算或探索草稿的陈旧数字（如 CN21 A 被误写为 10.26%，而底层 CSV 实际为 2.38%）；
- 子区间稳健性表格正负号与 CSV 相反；
- 原 `src/quantcf/project3_report.py` 中包含大量硬编码实证数值与结论摘要，未能完全动态驱动。

### 纠错措施
1. **清除所有硬编码**:
   - 重构 `src/quantcf/project3_report.py` 与 `build_project3_report.py`，所有表格、正文数值、子区间、成本敏感性、残差回归统计量、Bootstrap 置信区间全部通过读取最新生成的 CSV 产物动态填充；
2. **构建全量数字溯源表 (`report_trace.csv`)**:
   - 扩展 `outputs/report/report_trace.csv`，详细记录报告位置、源文件名、筛选键、列名、原始浮点值及显示格式化字符串；
   - 在验证程序中加入自动比对断言，确保报告中每一个数字与底层 CSV 严格一致；
3. **补全正式完整多页 PDF 报告 (`Project3_Report.pdf`)**:
   - 不再强行压缩至两页简报，扩展为结构完整的 5 页正式学术实证报告：
     - 第 1 页：研究假设、Kaufman 路径效率机制、F1/F2/F3/A/B/C 数学公式与因子卡；
     - 第 2 页：数据源说明、P5 物理隔离与截断审计、单因子覆盖率、每日截面相关性检验；
     - 第 3 页：主策略表现对比（A vs B vs C）、预定共同 2023–2024 区间双市场同期比较、截面残差回归与正交性诊断；
     - 第 4 页：时间子区间稳健性、成本阶梯稳健性（0/3/10 bps）、成对分块 Bootstrap 显著性检验；
     - 第 5 页：费用与复利对账矩阵、候选搜索日志、失效分析、研究局限与复现说明。
4. **增设预定共同 2023–2024 区间同期横向对比**:
   - 落实 `config/project3.json` 中预定的 `common_evaluate` 区间（2023-01-01 至 2024-12-31）；
   - 在相同 23 个月持有期下输出 `common_period_comparison.csv`，杜绝把 US9 2020–2024 与 CN21 2023–2024 混为同期的不当比较；
5. **严谨审慎的学术语言表述**:
   - 全文规范结论表述为“**本样本未获得稳健正增量证据**”；
   - 说明 Bootstrap 95% 置信区间跨越 0 表明无法拒绝增量为零的零假设，但并非在全域数学上“证伪”真实效应；残差 Rank IC 近零说明路径效率信息未在传统动量之外带来截面超额选券能力。

---

## 4. 第 4 节修复：真实复用 P1 Broker 引擎与标准输出持久化

### 缺陷表现
- 原代码在 `project3_pipeline.py` 内另写了一套撮合循环，未直接调用项目共享的 `quantcf.backtest.run_backtest` 与 `audit_backtest`；
- 标准长表 `factors_long.csv` 与覆盖率明细 `coverage.csv` 在内存计算后未持久化到磁盘；
- 当市场无正动量资产时，空仓逻辑缺失明确的零权重指令，存在沿用旧仓隐患。

### 纠错措施
1. **完全接入官方 P1 Broker**:
   - 将策略生成的目标权重适配为标准目标格式（`signal_date`, `execution_date`, `asset`, `target_weight`）；
   - 实例化 `BacktestConfig(initial_cash=1_000_000.0, buy_fee=fee_rate, sell_fee=fee_rate, allow_fractional_units=True, capacity_limited=False, start=entry_0, end=exit_last)`；
   - 调用 `run_backtest(prices=panel, targets=targets, config=cfg)` 驱动全流程执行；
   - 48 组策略/成本情景全部通过 `audit_backtest` 审计，并在 `outputs/backtests/` 落盘完整的 ledger、orders、fills、holdings 与 audit.json；
2. **空信号强制清仓保护**:
   - 在 `generate_portfolio_target_weights` 中加入保护逻辑：当某一期无合格资产或无正动量资产（如 A0 处于熊市）时，强制向该期 `execution_date` 发送 `target_weight = 0.0` 目标行；
   - P1 Broker 接收到零权重目标后，将主动卖出全部存量多头、支付卖出手续费并保持 100% 现金，杜绝因 targets 无行而静默沿用旧持仓；
3. **标准因子长表落盘**:
   - 持久化 `outputs/factors/factors_long.csv`，标准列结构为 `date, asset, factor, value, universe, split`；
4. **覆盖率明细表落盘**:
   - 持久化 `outputs/coverage.csv`，标准列结构为 `date, formation_date, universe, split, total_assets, qualified_assets, coverage_ratio, min_assets_met, excluded_count, excluded_reasons`，记录逐期因历史不足、缺价或退化而剔除的资产清单。

---

## 5. 第 5 节修复：验收矩阵真实断言驱动与负例测试

### 缺陷表现
- 原 `verify_project3.py` 的 `build_acceptance_matrix` 将 R01–R20 的 `status` 直接写成了硬编码字符串 `"PASS"`，缺乏真实判定。

### 纠错措施
1. **全项真实布尔判定重构**:
   - 重写 `build_acceptance_matrix`，每一项标准均连接到实际文件检查、数值容差检验或审计布尔值：
     - R01: 校验 P2 Baseline SHA256 与只读完整性；
     - R02: 校验 P2 64 项继承测试通过率与 0.0 差异；
     - R05: 校验 factors_long.csv 结构与 P1 broker 审计状态；
     - R07: 校验全表最大日期 $\le 2024-12-31$；
     - R12: 校验对账表中全部 48 组费用与连乘复利的一致性；
     - R17: 校验包含入口脚本的新冻结清单哈希匹配度；
     - R20: 判定为 `PENDING_HUMAN_REVIEW`，真实体现人工签认待审核状态；
2. **新增验证器负例单元测试**:
   - 编写 `tests/test_project3_verification_negative.py`，包含 5 项负例拒绝测试：
     - 测试 1：人为注入 2025 日期行，验证器必须报错拒绝；
     - 测试 2：篡改月费合计制造不一致，验证器必须报错拒绝；
     - 测试 3：篡改冻结文件哈希，验证器必须报错拒绝；
     - 测试 4：删除必要输出表，验证器必须报错拒绝；
     - 测试 5：无有效运行证据时，验收矩阵必须真实输出 FAIL，严禁输出全 PASS。
3. **残差正交性严格测试**:
   - 在 `tests/test_project3_pipeline.py` 中完善 `test_residual_factor_orthogonality`，断言逐期残差均值绝对值 $< 10^{-10}$、残差与解释变量内积绝对值 $< 10^{-10}$，并加入共线性退化处理保护。

---

## 6. 第 6 节修复：重跑证据去污染与冻结清单扩充

### 缺陷表现
- 原 `verify_project3.py --rerun` 在重跑前将旧的 `outputs/research/*.csv` 及 P2 摘要复制进临时目录再做对比，虚增了 36 张所谓“重新生成”的比对表；
- 原冻结清单未包含流水线核心入口 `run_project3.py`；
- `package_project3.py` 在二次打包时扫描自身 `FILE_MANIFEST.json` 导致自引用哈希过期。

### 纠错措施
1. **完全纯净的临时隔离重跑**:
   - 移除所有向临时目录预复制旧结果的代码。临时目录仅由源码、配置、数据快照与冻结元数据启动，由 `run_project3.py --phase evaluate --out <temp_dir>` 从零生成全量 Project 3 产物；
   - 产物分类核算：明确区分 `regenerated_tables`（本次全量重跑生成并比对的 Project 3 表格）与 `reference_only`（P2 历史基线文件，不计入重跑生成表数）；
   - 对比所有生成的 CSV 表格，要求主键、Schema 与数值差异最大绝对值严格为 0.0；
2. **冻结清单扩充与版本管理**:
   - 将 `run_project3.py` 与 `src/quantcf/backtest.py` 纳入冻结文件清单（扩充至 14 项）；
   - 保留原 v1 冻结记录为 `outputs/freeze_manifest_v1.json`；
   - 登记新的工程纠错冻结清单 `outputs/freeze_manifest.json`，注明版本 `2.0.0-engineering-repair`、当前 Git Commit（`8cd7eede...`）与修复说明，不伪造旧时间戳；
3. **打包自引用哈希修复**:
   - 在 `package_project3.py` 的 `build_file_manifest` 中显式排除 `FILE_MANIFEST.json` 自身以及 `*.zip*`，消除自引用更新死循环；
   - 打包生成 `Project3_Review_Bundle_v2.zip` 及其对应的 `.sha256.txt` 文件。

---

## 7. 第 7 节修复：AI 辅助与人工贡献真实记录

### 纠错措施
- 更新 `docs/AI_ASSISTANCE.md` 与 `docs/CONTRIBUTIONS.md`；
- 真实记录本次 ChatGPT Review 1 独立复核发现的各项缺陷、提供的反例以及工程修复采纳过程；
- 剔除无法核实的虚构问答与虚构模型代号；
- 成员学号、分工说明与人工理解确认保持 `PENDING_HUMAN_REVIEW` 待人工核实签认状态，绝不使用 AI 代签伪造通过。

---

## 8. 修复前后主结果对比摘要

| 市场 / 策略 / 费率 | v1 存在缺陷的旧数值 (Close-to-Close) | v2/v3 修复后的确凿数值 (Open-to-Open) | 差异原因说明 |
| :--- | :---: | :---: | :--- |
| **US9 基准 A (3 bps) 年化收益** | 16.52% | **16.92%** (夏普 1.026) | 修正开盘到开盘、计入首日交易成本与日内波动 |
| **US9 增强 C (3 bps) 年化收益** | 15.45% | **15.86%** (夏普 0.946) | 修正开盘到开盘、消除调仓边界日内错位 (C - A = -1.06%) |
| **CN21 基准 A (3 bps) 年化收益** | 2.38% (报告误写 10.26%) | **2.01%** (夏普 0.585) | 纠正报告硬编码错误、统一切片与对账口径 |
| **CN21 增强 C (3 bps) 年化收益** | 3.95% (报告误写 11.83%) | **3.58%** (夏普 1.123) | 纠正报告硬编码错误、统一切片与对账口径 (C - A = +1.57%) |
| **US9 3 bps 策略累计费用** | 21,623 元 (重复统计) | **10,960.02 元** (唯一归属) | 消除相邻月份共享调仓日手续费双重计算 (偏差 0.00 元) |
| **CN21 3 bps 策略累计费用** | 8,543 元 (重复统计) | **4,420.42 元** (唯一归属) | 消除相邻月份共享调仓日手续费双重计算 (偏差 0.00 元) |
| **P5 保留期数据泄漏记录数** | 692 条 (2025–2026 暴露) | **0 条** (严格截断至 2024-12-31) | 数据加载入口物理截断，图表与表单全面净化 |
| **R01–R20 验收状态** | 全部硬编码为 "PASS" | **程序真实判定驱动** (R01-R19 PASS, R20 PENDING) | 消除硬编码，真实断言全部自动化执行 |

---

## 9. 第二轮复核 (v2 $\to$ v3) 深度工程修复闭环说明

- **工程版本**: v3.0.0-engineering-repair
- **针对问题与修复落实**:
  1. **P0-1: 空输出目录干净重跑自闭环**:
     - `run_project3.py` 增设 `--freeze-manifest` 参数，并在未传参时自动从 `outputs/freeze_manifest.json` 回退加载；同时在生成结果后自动将冻结清单自持久化至全新的 `--out` 目标目录；
     - `verify_project3.py --rerun` 显式传参 `--freeze-manifest outputs/freeze_manifest.json`，在完全干净的空临时目录实现从原始快照重跑 260 张表且逐键比对 delta 严格为 0.0。
  2. **P0-2: 验收矩阵 R01/R02 键名对齐与真实程序判定**:
     - 统一 `p2_baseline_verification.json` 架构，补充 `zip_sha256`、`baseline_zip_sha256_match`、`unmodified_original`、`tests`（含 passed: 64, failures: 0, errors: 0, skipped: 0）；
     - `verify_project3.py` 支持直接核验父目录 `CF2026_Project2_Final.zip` 的哈希值（`c1f3bd2911a4f296baa440259e837187bf4ed78954157ad5b13830e544df8c43`）与基线 64 项测试，确保 R01 和 R02 均真实输出 PASS。
  3. **P0-3: 验证器深度防伪重构与针对性负面注入测试**:
     - `check_report_trace`：逐行遍历 `report_trace.csv`，读取底层源 CSV，以 `filter_key` 过滤并断言 `abs(raw_value - actual_value) < 1e-5`，同时比对 `displayed_value` 格式化数值；
     - `check_reconciliation`：彻底移除对布尔列的信任，针对 48 组回测逐一读取底层的 `fills.csv`、`ledger.csv` 与 `monthly_returns.csv`，重新计算三者费用求和并严格断言相等，重新计算连乘积并断言等于开盘净值比；
     - `check_p5_quarantine`：移除 `nrows=50000` 限制，采用 `chunksize=100000` 完整扫描所有 CSV，日期解析严禁静默吞掉异常；
     - 编写 `tests/test_project3_verification_negative.py` 中的 7 项针对性负面注入测试（包括篡改 report_trace 数值至 999999、篡改月费至 10 亿、在第 50001 行注入 2026 年日期、损坏日期字符串等），全量在 pytest 中稳定通过。
  4. **P0-4: 严格恢复 P2 A0 离散符号 Long/Cash 资金逻辑**:
     - 修正 `src/quantcf/project3_pipeline.py`：对 A0 策略，逆波动率预算基于全集资产计算，仅对正动量资产分配其预算份额，负动量资产的预算份额严格留存为现金，不进行重归一化；
     - 在 `test_project3_counterexamples.py` 中补充 6 资产等权重测试，断言总仓位严格为 49.5%（3 正 3 负），50.5% 留存现金，绝不重归一化至 99%。
  5. **P0-5: 补齐 factor_ic_series 字段并完整绘制 CN21 23 个月度样本**:
     - `run_project3.py` 保存 `factor_ic_series.csv` 前显式压盖 `universe` 与 `split` 字段；
     - `src/quantcf/project3_report.py` 中图 3 完整绘制 CN21 的全部 23 期 Rank IC 时间序列（包含有效合格资产数为 18–21 的所有月份），彻底解决由于单日资产数过滤引起的漏期问题。
  6. **P1-1: 规范 PDF 格式、对数价格 ER 公式、动态相关性与零滑点假定**:
     - PDF 报告全面清除原生 LaTeX 数学符号（`$`、`\times`、`\frac`、`\alpha`、`\beta`、`\epsilon`、`\Delta`），转换为标准 Unicode / HTML 标签；
     - 明确路径效率比公式严格基于对数价格变化：$ER_L(t) = |\ln(P_t/P_{t-L})| / \sum |\ln(P_k/P_{k-1})|$，平价路径分母为 0 时置 0.0；
     - 每日截面相关系数均值从 `daily_correlations.csv` 动态计算输出（US9 Spearman 均值 ~0.759、Pearson ~0.782；CN21 Spearman ~0.841、Pearson ~0.846），绝不硬编码；
     - 明确月度开盘执行中将滑点设为 0 作为教学基准假设以隔离因子纯信号，同时通过 0、3、10 bps 费用阶梯严格评估交易成本稳健性；
     - 明确区分复利连乘累计收益率 $R_{\mathrm{cum}}$ 与终局开盘净值比 $W(T_{K+1}^-) / W(T_1^-) = 1 + R_{\mathrm{cum}}$。
  7. **P1-2: 日度最大回撤严格截断至退出日开盘前净值**:
     - `execute_broker_simulation` 中日账本回撤序列严格限制在 $d < T_{K+1}$ 并拼接开盘前净值 $W(T_{K+1}^-)$，确保期末退出日收盘价异动不污染回测统计。
  8. **P1-3: 阶段数据视图与数据覆盖率完备性**:
     - 因子与相关性计算全程采用阶段受限视图 $t \le \text{split\_end}$；
     - `coverage.csv` 扩充记录原始因子覆盖、平价路径数、排除原因，并标注 warmup 与 evaluate 分期。


---

## 10. 最后一轮复核 (v3 $\to$ v4) 报告与规范深度修正闭环说明

- **工程版本**: `v4.0.0-final-review`
- **日期**: 2026-11-16
- **核心原则**: 保持原因子定义（$F_1, F_2, F_3$）、基准与合成组合（$A, A_0, C$）、超参数（$L=63, 126$）、时间切分（US9 2020–2024, CN21 2023–2024）以及回测计算与对账结果 100% 绝对冻结不变；不换因子、不调参，集中修正实际报告生成器、报告文档、文字描述精度及真实性披露。

### 具体修改清单与闭环证据

1. **修正 PDF 第一页对数价格路径 ER 公式与规范渲染**：
   - **问题定位**: 代码实现严格采用对数价格变化路径，但早期报告遗留了价格差绝对值定义；且 ReportLab 早期版本直接包含原生 LaTeX 源码标记。
   - **工程修复**: 修改 `src/quantcf/project3_report.py` 与 `build_project3_report.py`，规范对数价格路径公式：
     $$ER_L(t) = \frac{|\ln(P_t / P_{t-L})|}{\sum_{k=1}^L |\ln(P_k / P_{k-1})|}$$
     求和覆盖过去 $L$ 个交易区间（主因子 $L=63$，变体 $L=126$）；当所有价格恒定（分母为零）时严格置 $ER = 0.0$。
   - **PDF 渲染**: PDF 中杜绝直接出现 `$`、`\frac`、`\times`、双大括号等 LaTeX 源码，采用规范 HTML 实体（如 `&times;`、`&Sigma;`）与 Unicode 排版；文本抽取审计确认无任何原生 LaTeX 标记外露。

2. **修正 CN21 市场 C 与 A0 的横向比较关系**：
   - **问题定位**: 原报告部分语句笼统表述为“C 整体表现低于 A0”，未能准确反映收益与夏普比率的不同维度。
   - **工程修复**: 全面拆解并精确区分两个维度的表现：
     - **收益维度**: 合成组合 C 算术年化收益为 **3.58%**，高于 P2 离散符号基准 A0（**3.14%**）与连续动量基准 A（**2.01%**）；
     - **风险调整维度**: C 的夏普比率（**1.123**）高于 A（**0.585**），但低于 A0（**2.136**，源于 A0 在熊市期间留存现金带来的极低波动率 1.47%）。
   - **同步范围**: 同步更新 `outputs/report/Project3_Report.pdf`（第 1 页摘要）、`outputs/report/Project3_Report.md`、`VSCODE_REPORT.md` 以及 `README.md`。

3. **弱化过强学术结论，统一规范统计表述**：
   - **问题定位**: 早期文稿中存在“主假说被明确否定/证伪”等过于绝对化的断言；未严格区分“未能拒绝零假设”与“证明效应为零”。
   - **工程修复**: 全文删除“主假说被明确否定/证伪”字样，统一表述为：
     > **“US9 增量点估计为负，两市场 Bootstrap 区间均跨零，本样本未取得稳健正增量证据。”**
   - **统计严谨性**: 明确阐明“统计检验不显著不等于证明效应为零”；
   - **表头规范**: 将成对分块 Bootstrap 检验表格中的“超额正收益概率 / 超额胜率”列头统一修改为“**重采样中收益差为正的比例**”，严格符合统计学重采样定义。

4. **动态计算每日截面相关系数均值并注明区间**：
   - **问题定位**: PDF 第 5 页早期包含市场错配与硬编码的旧版相关性数值。
   - **工程修复**: 改由 `src/quantcf/project3_report.py` 动态加载 `daily_correlations.csv`，并在报告中完整注明样本区间与系数类型：
     - **US9 市场**（1998–2024 全区间共 6,311 个有效交易日）：Pearson 日均值为 **0.781770**，Spearman 日均值为 **0.759061**；
     - **CN21 市场**（2019–2024 全区间共 1,212 个有效交易日）：Pearson 日均值为 **0.842162**，Spearman 日均值为 **0.871730**；
   - 彻底删除 PDF 第 5 页旧的市场错配数字，杜绝任何硬编码。

5. **修正滑点假设与净值比/累计收益单位**：
   - **执行假设明确**: 删除“已计入滑点”的混淆表述，明确采用教学零滑点基准假定（`slippage_bps = 0`），交易摩擦完全由单边 0/3/10 bps 手续费阶梯独立刻画；
   - **指标与单位规范**:
     - “**终局开盘净值比**”：严格显示为无量纲比率 $W(T_{K+1}^-) / W(T_1^-)$（如 US9 基准 A 为 **2.141631**）；
     - “**连乘累计收益**”：严格显示为百分比形式 $\prod (1 + R_k) - 1$（如 US9 基准 A 为 **+114.16%**），清晰体现 $\text{净值比} = 1 + \text{累计收益}$；
   - **空值统一格式**: 差值组合（C - A）中不适用的统计量（如 CAGR、最大回撤、手续费）统一显示为“**—**”，消除所有 `nan%` 或 `¥nan`。

6. **真实性、AI 辅助与分工签署真实披露**：
   - **AI 工具与版本披露**: 在 `docs/AI_ASSISTANCE.md` 中说明 ChatGPT 与 Antigravity 的具体底层大模型版本未在输出中逐一进行技术核实，以 Web UI 及集成环境默认路由为准；
   - **交互问答属性**: 明确问答表格为“交互任务摘要，非逐字对话实录”；
   - **分工签署真实性**: 在 `docs/CONTRIBUTIONS.md` 中将成员分工与签字标注为 `PENDING_HUMAN_REVIEW`，严禁由 AI 伪造人类签署；待线下审核后人工最终签字。

7. **同源生成、PDF 严格 5 页与全自动化验证**：
   - 重新运行 `build_project3_report.py`，生成最新版 PDF（严格 5 页，布局精巧不跨页超流）、Markdown、VSCODE_REPORT.md 与 376 行 `report_trace.csv`；
   - 运行 `verify_project3.py`，全套 90 项单元测试全部 PASS，trace 底层真实值比对 100% 吻合，R01–R19 全部 PASS，R20 稳健保持 `PENDING_HUMAN_REVIEW`。
