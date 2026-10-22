# Project 1 平台复用与新增架构说明 (Platform Changes)

**版本**: Project 2  
**作者**: 袁思扬 (学号: 12411852)  
**更新日期**: 2026-10-22  

---

## 1. 模块复用与新增对应表

| 功能域 | Project 1 原有模块 | Project 2 复用与新增方案 | 说明 |
|---|---|---|---|
| 数据加载与复权 | `src/quantcf/data.py` | **完全复用**：`load_panel()`, `DataPanel`, `reconstruct_price_series()` | 继续沿用原始 Parquet 快照与复权因子计算机制；P2 增设评价区间与暖机区间切分。 |
| 原因子与排名 | `src/quantcf/factors.py` | **保留原接口**，新增独立 `src/quantcf/tsmom.py` | 原 P1 逻辑进行截面百分位 rank；P2 的 TSMOM 依赖自身绝对历史收益符号，因此新开独立纯函数模块，互不干扰。 |
| 组合目标生成 | `src/quantcf/portfolio.py` | **扩展新增**：`generate_tsmom_long_cash_targets()` | 保留 P1 的 Top-N 截面排序目标生成器；新增基于逆波动率预算分配的 TSMOM Long/Cash 目标生成函数。 |
| 真实账户回测 | `src/quantcf/backtest.py` | **完全复用**：`run_backtest()`, `Broker`, `Account` | 用于执行模式（T1, T2, T3）；严格复用非负持仓、无现金借款、次日开盘价成交及真实买卖费率扣减。 |
| 理论研究回测 | 无（P1 仅有日频现货执行） | **全新开发**：`src/quantcf/research_backtest.py` | 实现原论文风格的月频研究模式（R1–R4，多空、缩放杠杆、线性加总、持仓敞口统计及单资产 Sharpe 计算）。 |
| 性能指标评估 | `src/quantcf/metrics.py` | **复用并补充**：月度指标计算接口 | 复用现有日频账本指标；新增纯月度收益率序列的 Sharpe（年化 $\sqrt{12}$）、CAGR、最大回撤等指标函数。 |
| 实验追踪记录 | `src/quantcf/recorder.py` | **完全复用**：`ExperimentRecorder`, 严格 JSON 与文件哈希 | 将 P2 所有配置、新增源码、官方数据文件哈希和运行环境纳入审计追踪。 |
| 官方数据参考 | 无 | **全新开发**：`src/quantcf/reference_data.py` | 获取并解析 AQR 官方 1985–2009 原论文月度因子数据，复算 O1 基准指标。 |
| 全流程管线 | `src/quantcf/pipeline.py` | **新建独立**：`src/quantcf/pipeline_p2.py` | 驱动 P2 全部实验（R1–R4, T1–T3, O1, 归因实验、图表与汇总表输出），不覆盖 P1 管线。 |
| 报告与可视化 | `src/quantcf/report.py` | **新建独立**：`src/quantcf/report_p2.py` | 生成双语报告（Markdown, HTML, PDF）及并排对比图表。 |

---

## 2. 关键接口改造与隔离原则

1. **绝对信号 vs 截面排序**:
   - P1 中的动量因子先排序取 Top 5；P2 的 TSMOM 是时间序列动量，所有资产的正负号由自身决定，互不挤占。
2. **全负信号退出与资产不足安全处理**:
   - 若月末所有资产 12 个月收益均为负，Long/Cash 目标生成器生成所有旧持仓退出为 0 的目标权重，资金 100% 保持现金，绝不因为目标表为空而导致账本被动持有旧仓。
   - 当合格资产数少于 6 只时，同样生成全部清仓退出指令。
3. **暖机期与正式评价期严格解耦**:
   - P1 的 `load_panel()` 接受的 `start` 为数据起点；P2 在回测与指标统计时将暖机区间（2019-01 至 2020-01）的现金收益剔除，指标严格从首个正式调仓月生效日（2020-02 首个交易日）起算。

