# Project 2 开发与修改日志 (Project Log)

**项目名称**: Time Series Momentum: Method Replication on an ETF Sample and a Multi-horizon Signal Extension  
**开发目标**: 在 Project 1 平台基础上，复现 Moskowitz, Ooi & Pedersen (2012) 核心时间序列动量策略，完成自主扩展与差异归因分析，产出完整实证报告与演示材料。  
**作者**: 袁思扬 (学号: 12411852)  
**基础代码库**: `F:\金融数学\计算金融\Project\project2 ysy` (严格保护 `final_project` 原版不作任何改动)  
**依据文档**: `CF2026_Project2.pdf` 及 `CF2026 Project2 开发执行方案`  

---

## 修改日志记录 (Changelog)

### [2026-10-22 01:20] 初始化项目日志与开发环境检查
- **修改范围**: 
  - 新建 `PROJECT_LOG.md` 项目日志记录规范。
  - 检查并确认原有 Project 1 测试套件运行状态（40 passed）。
  - 安装并锁定新增依赖 `openpyxl` 与 `pypdf` 至 `pyproject.toml` 和 `uv.lock`。
- **状态**: 完成，基础测试与依赖环境就绪。

---

### [2026-10-22 01:25] 阶段 1 完成：研究协议冻结、架构规范与官方基准接入
- **修改文件**:
  - `config/project2_tsmom.json`: 建立 P2 完整独立配置（切分 2019-01 数据起点、暖机期与 2020-02 至 2026-08 正式评价期）。
  - `docs/project2/protocol.md`: 冻结核心假设、目标图表定义、样本规则与实验设计。
  - `docs/project2/method_mapping.md`: 梳理原文节/式/页与本项目函数映射及已知边界。
  - `docs/project2/platform_changes.md`: 明确 P1 复用与 P2 新增模块对应表。
  - `docs/project2/data_dictionary.md`: 规范 21 只 ETF 样本池与中间/结果指标字段。
  - `src/quantcf/reference_data.py`: 实现 AQR 官方原论文数据（1985–2009，300个月）与论文 PDF 获取与解析。
  - `prepare_project2_sources.py`: 建立离线资料下载与 SHA-256 校验入口。
  - `references/`: 成功渲染论文高分辨率原始图表（Fig. 2 上部单资产夏普分布、Fig. 3 累计表现）。
- **核验结果**:
  - AQR 官方基准数据 O1 解析成功：300 个月年化平均收益 17.08%，年化波动 12.33%，夏普比率 1.385（与原文 Table 4 报出的 1.38 一致），最大回撤 -15.23%。
- **状态**: 阶段 1 达成。

### [2026-10-22 01:27] 阶段 2 完成：核心方法纯函数实现与独立小样本手算核验
- **修改文件**:
  - `src/quantcf/tsmom.py`: 实现自然月末提取、连续日收益截取、EWMA 有限历史方差与年化波动率（年化 261）、动量符号映射、多期限趋势复合等纯数学计算。
  - `tests/test_tsmom.py`: 建立针对第 9.1 节手算预期的独立单元测试（12 月动量映射、衰减 1/2 手算 EWMA、理论多空权重、收益贡献加总、执行模式逆波动率预算分配及多期限复合）。
  - `docs/project2/method_checks.md`: 完整编写手算核验推导过程、预期数值表及工程检查审计规范。
- **核验结果**:
  - 运行 `uv run pytest tests/test_tsmom.py`，5 项独立数学核算全部通过（0.40s）。
- **状态**: 阶段 2 达成。

### [2026-10-22 01:31] 阶段 3 & 4 完成：研究模式回测引擎与交易约束 Long/Cash 目标生成器
- **修改文件**:
  - `src/quantcf/research_backtest.py`: 开发月频理论研究回测引擎，支持 R1（12月 TSMOM 多空与波动率缩放）、R2（被动做多对照）、R3（等额名义权重敏感性）、R4（多期限趋势自主扩展）、Bridge（只做多研究桥接）、滚动样本方差对比及 Fig. 2 单资产策略夏普比率计算。
  - `src/quantcf/portfolio.py`: 扩展新增 `generate_tsmom_long_cash_targets()`，严格落实逆波动率预算分配 $b_{i,m} = 0.99 \frac{1/\sigma_i}{\sum 1/\sigma_j}$，负信号预算留存现金（非赋给多头），合格资产不足或全负时对全资产发出清仓指令（权重为 0）。
  - `tests/test_portfolio_tsmom.py`: 建立目标生成器针对非负权重、预算上限及资产不足自动清仓的单元测试。
- **核验结果**:
  - 实证全样本（79 个完整月，2020-02 至 2026-08）试跑：
    - R1 (TSMOM 12m): 年化收益 18.40%，年化波动 23.88%，夏普 0.770，胜率 70.89%，单资产正夏普比例 17/21 (81.0%)。
    - R2 (Passive Long): 年化收益 24.02%，年化波动 24.90%，夏普 0.965。
    - R4 (Multi-horizon): 年化收益 12.38%，年化波动 22.15%（波动率显著下降），最大回撤由 -35.73% 改善至 -33.74%。
  - 全套测试通过（47 passed in 0.39s）。
- **状态**: 阶段 3 与阶段 4 达成。

### [2026-10-22 01:34] 阶段 5 完成：全流程管线搭建、全套实验运行与差异归因产出
- **修改文件**:
  - `src/quantcf/pipeline_p2.py`: 建立完整的 Project 2 研究管线，自动化编排核心复现、自主扩展、差异归因、图表绘制与实验哈希记录。
  - `run_project2.py`: 建立 Windows/Unicode 安全的顶层 CLI 入口脚本，支持 `--config`, `--out`, `--offline`, `--seed` 等参数。
  - `outputs_p2/`:
    - `strategy_summary.csv`: 汇总 R1–R4, Bridge, R1_sample_vol, 分段, 宽基子集, T1–T3 各费率（3bps, 0bps, 10bps）及 O1 AQR 原因子指标。
    - `original_vs_replication.csv`: 严密对比原文 Fig. 2 / Fig. 3 核心结论与替代样本复现结果。
    - `difference_experiments.csv`: 产出 7 组单因素控制归因实验结果（缩放效应、做空限制、波动率估计器、时段稳定性、资产子集、交易摩擦、多期限自主扩展）。
    - `figures/`: 生成并排出版级对比图表（`fig2_single_asset_sharpe.png`, `fig3_cumulative_comparison.png`, `fig_multi_horizon_comparison.png`, `fig_execution_performance.png`, `fig_signals_and_exposures.png`）。
    - `runs/`: 记录完整运行配置、源码指纹与运行清单。
- **核验结果**:
  - 全流程离线运行通过（退出码 0）。
  - 核心结论得到严密检验：单资产时间序列动量在替代样本中 81.0% (17/21) 展现正夏普；自主扩展多期限组合（R4/T2）有效降低了最大回撤（-35.73% -> -33.74%），在执行模式下夏普比率提升至 1.332。
- **状态**: 阶段 5 达成。

### [2026-10-22 01:52] 阶段 6 & 7 完成：中英文研究报告、演示指南与最终自检复跑
- **修改文件**:
  - `src/quantcf/report_p2.py`: 建立多格式报告生成器，支持 Markdown、HTML、PDF（ReportLab Platypus 编译，含内嵌图表与表格）及中文执行摘要。
  - `build_report_project2.py`: 建立报告与 PDF 一键独立重建脚本。
  - `DEMO_P2.md`: 制定 5–8 分钟现场答辩与演示指南（问题目标、手算核查、平台接入、原/新对照、归因与改进、复现命令）。
  - `README_PROJECT2.md`: 编写完整的 Project 2 项目说明、结构目录、一键复现指南与关键结果矩阵。
  - `AI_ASSISTANCE.md`: 更新 Project 2 真实详细的 AI 辅助使用情况披露，明确作者独立学术责任。
- **最终综合核验结果**:
  - **测试套件**: `uv run pytest` 全套 47 项测试通过（8.00s），覆盖原有 P1 回测审计与新增 P2 动量、EWMA、多期限及执行目标测试。
  - **全流程复跑**: `uv run python run_project2.py --config config/project2_tsmom.json --out outputs_p2 --offline` 执行成功，生成全部 18 项策略结果、对比表、归因表及高分辨率图表。
  - **报告编译**: `uv run python build_report_project2.py --out outputs_p2` 成功产出 `report_en.pdf` (6 页出版排版，2.1MB)、`report_en.md`、`summary_zh.md`、`report_en.html`。
  - **目录隔离**: 经检查，`final_project` 目录内未发生任何改动（git status 确认 100% 原始状态保留）。
- **状态**: 阶段 6 与阶段 7 达成。

---

### [2026-10-22 10:45] 阶段 8 完成：结论收紧、计算复核、独立可复现性检验与审查包生成
- **核心修改范围**:
  1. **结论收紧与证据强化**:
     - 全面收紧“大类资产起决定性作用”为“资产类别异质性与样本敏感性”，补全固定权重移除归因证据（`outputs_p2/experiments/asset_class_removal_attribution.csv` 与 `fig_asset_class_attribution.png`）。
     - 全面收紧“改进全面优于”为“多期限信号平滑的风险收益权衡”，明确列出绝对收益削减与换手率上升（1.42x -> 2.33x）、费用增加 63% 的摩擦代价。
  2. **计算与对齐复核**:
     - 确认严格对齐 79 个完整活跃持有月（2020-02 至 2026-08），坚决剔除 2026 年 9 月未完成月。
     - 确认单资产夏普比率计算公式 $s_{i,m} \frac{0.40}{\sigma_{i,m}} r_{i,m+1}$，严禁除以 $N_m$。
     - 确认三套年化系数：EWMA 日波动率取 261，月度取 12，真实执行日台账取 252。
  3. **成果与图表齐全性**:
     - 确认 18 组实验清单（`experiments_inventory.csv`）与 12 项核心结论数据追踪表（`key_result_trace.csv`）。
     - 确认 7 组单因素控制差异实验（`difference_experiments.csv`）与原图/新图并排对比图集（`outputs_p2/figures/`）。
     - 重新编译生成规范 6 页英文报告 `report_en.pdf` 与中文执行摘要 `summary_zh.md`。
  4. **独立复验与可复现性日志**:
     - 运行独立目录测试：`uv run --locked python run_project2.py --config config/project2_tsmom.json --out outputs_p2_verification --offline`。
     - 逐行比对 `strategy_summary.csv`, `difference_experiments.csv`, `key_result_trace.csv`, `experiments_inventory.csv`，最大数值绝对偏差为 0.00000000（完全确定性复现）。
     - 记录复验结论至 `outputs_p2/reproducibility_check.json` 与 `outputs_p2/development_completion.log`。
  5. **推进报告与审查归档**:
     - 编写完成 `P2_CONTINUATION_REPORT.md`，逐项回答第 10 节规定的 6 大核心核实问题。
     - 打包生成供评审检查的完整压缩包 `project2_review_bundle.zip`（严格排除 `.venv`, `.git`, `__pycache__` 等冗余内容）。
- **核验结论**:
  - 全套 47 项单元测试继续 100% 通过（0.40s）。
  - `final_project` 保持 100% 原始未触碰。
- **状态**: Project 2 全部核实、修整与交付打包工作就绪，可供用户与外部评审检阅。

---

### [2026-10-22 11:45] 阶段 9 完成：系统性深度修复全面落地、空白目录复验与复核包打包
- **复核输入**: `CF2026_Project2_Code_Review_Required_Fixes_20261022.md`
- **基线保留**: 保留 `outputs_p2/` 作为修前基准，独立重跑并产出到 `outputs_p2_fixed/`。
- **本阶段完成改动与核验**:
  1. **执行区间截断与首日纳入**: 
     - 严格截断 2020-02-03 至 2026-08-31（1599 个交易日），剔除 9 月 14 天，将首日收益 (+0.471879% for T1) 真实纳入。
     - T1 真实 Sharpe 达到 **1.3033019**，CAGR 为 **5.2375%**，最大回撤 **-4.2500%**；T2 真实 Sharpe 达到 **1.3502555**，CAGR 为 **4.2930%**，最大回撤 **-3.3803%**，完全吻合外部复核独立核对数值。
  2. **形成资格与未来数据解耦**:
     - 将 `formation_eligible`（仅依赖形成时历史指标）与 `holding_return_observed` 彻底解耦；`generate_tsmom_long_cash_targets()` 严格仅读取形成时资格，杜绝利用未来收益可得性；研究回测在缺失持有期收益时标记月份无效并填 NaN，绝不事后剔除资产或缩小 $N_m$。
  3. **252 日滚动样本波动率估计器**:
     - 修复 `calculate_sample_volatility()` 取切片最后 252 个交易日，`ddof=1`，年化 261。在 756 日反例上精确输出 `0.323753`（消除修前 0.187137 扩展历史偏差）。
     - 实证重算 R1_sample_vol：Sharpe 0.7299，年化收益 17.01%，年化波动 23.30%，最大回撤 -34.37%。
  4. **回撤基准、Calmar 符号与月份连续性**:
     - 累计财富序列与回撤显式包含初始权益 1.0，反例 `[-10%, +1%]` 正确输出最大回撤 `-10.0%`。
     - Calmar 保留负号，反例 `[-10%, -10%]` 正确输出 `-3.7767`。
     - 月度非连续或存在内部 NaN 时标记 `is_continuous=False` 并置 `cagr=np.nan`，杜绝跨缺口复利。
  5. **配置驱动与真实配置哈希、Recorder 生命周期**:
     - 运行日期、成本与年化参数由 `config/project2_tsmom.json` 驱动；实现 `compute_fixed_config_hash()` 计算每组实验固定项的 16 位 SHA-256 哈希，真实记录数据快照哈希（`2b1821608563a5b5`）；Recorder 提早启动并包裹在 `try ... finally` 中。
  6. **交易明细、审计与收益序列完整归档**:
     - 导出 8 组执行配置的 orders, fills, holdings, ledger, audit.json 与 monthly_returns 到 `backtests/`。
     - 导出单资产月收益、分段月收益及协方差方差贡献分解表（境内权益贡献 **84.76%** 的总方差风险）。
  7. **报告生成源彻底修正与 PDF 字体跨平台适配**:
     - 消除模板中所有旧硬编码（宽基 Sharpe 为动态 0.052，分段为 1.180 与 0.646）；纠正 p.236 事实为“58 个为正，52 个显著”；规范 AQR 引用为公开参考因子 O1 复算（1.385 / 17.08%，对应 Table 4 1.38 / 17.1%）；注册微软雅黑等 Windows 字体消除方块豆腐块，非 Windows 优雅降级；全面披露 ChatGPT、Gemini 及 VSCode + Codex 并签署学术责任。
  8. **测试套件与独立空白目录复验**:
     - 55 项单元与真实主流程集成测试 100% 通过（7.19s）。
     - 在空白目录 `outputs_p2_verification` 独立复跑，核心表格最大浮点偏差为 0.00000000，生成 `reproducibility_check.json`。
  9. **审查回复与打包归档**:
     - 编写完成详细的第 2–8 节逐项响应说明 `P2_FIX_RESPONSE.md`。
     - 生成符合规范的审查打包压缩包 `project2_review_bundle.zip` 与 `project2_review_bundle_fixed.zip`。
  10. **目录隔离状态**:
     - `final_project` 目录保持 100% 原始未触碰（git status 确认）。
- **状态**: 阶段 9 全部修复工作圆满完成。



