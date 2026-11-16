from pathlib import Path

content = Path("BUGFIX_CHANGELOG.md").read_text(encoding="utf-8")

old_sec8 = '''## 8. 修复前后主结果对比摘要

| 市场 / 策略 / 费率 | v1 存在缺陷的旧数值 (Close-to-Close) | v2 修复后的正确数值 (Open-to-Open) | 差异原因说明 |
| :--- | :---: | :---: | :--- |
| **US9 基准 A (3 bps) 年化收益** | 16.52% | 待重跑最新输出填入 | 修正开盘到开盘、计入首日交易成本与日内波动 |
| **US9 增强 C (3 bps) 年化收益** | 15.45% | 待重跑最新输出填入 | 修正开盘到开盘、消除调仓边界日内错位 |
| **CN21 基准 A (3 bps) 年化收益** | 2.38% (报告误写 10.26%) | 待重跑最新输出填入 | 纠正报告硬编码错别、统一切片与对账口径 |
| **CN21 增强 C (3 bps) 年化收益** | 3.95% (报告误写 11.83%) | 待重跑最新输出填入 | 纠正报告硬编码错别、统一切片与对账口径 |
| **US9 3 bps 策略累计费用** | 21,623 元 (重复统计) | 10,960 元 (唯一归属) | 消除相邻月份共享调仓日手续费双重计算 |
| **CN21 3 bps 策略累计费用** | 8,543 元 (重复统计) | 4,420 元 (唯一归属) | 消除相邻月份共享调仓日手续费双重计算 |
| **P5 保留期数据泄漏记录数** | 692 条 (2025–2026 暴露) | **0 条** (严格截断至 2024-12-31) | 数据加载入口物理截断，图表与表单全面净化 |
| **R01–R20 验收状态** | 全部硬编码为 "PASS" | **程序真实判定驱动** (R20 为 PENDING) | 消除硬编码，真实断言全部自动化执行 |

*(注：待流水线计算完成，表格将自动同步填入最终确认之新数值)*'''

new_sec8_sec9 = '''## 8. 修复前后主结果对比摘要

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

## 9. 第二轮复核 (v2 $\\to$ v3) 深度工程修复闭环说明

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
     - PDF 报告全面清除原生 LaTeX 数学符号（`$`、`\\times`、`\\frac`、`\\alpha`、`\\beta`、`\\epsilon`、`\\Delta`），转换为标准 Unicode / HTML 标签；
     - 明确路径效率比公式严格基于对数价格变化：$ER_L(t) = |\\ln(P_t/P_{t-L})| / \\sum |\\ln(P_k/P_{k-1})|$，平价路径分母为 0 时置 0.0；
     - 每日截面相关系数均值从 `daily_correlations.csv` 动态计算输出（US9 Spearman 均值 ~0.759、Pearson ~0.782；CN21 Spearman ~0.841、Pearson ~0.846），绝不硬编码；
     - 明确月度开盘执行中将滑点设为 0 作为教学基准假设以隔离因子纯信号，同时通过 0、3、10 bps 费用阶梯严格评估交易成本稳健性；
     - 明确区分复利连乘累计收益率 $R_{\\mathrm{cum}}$ 与终局开盘净值比 $W(T_{K+1}^-) / W(T_1^-) = 1 + R_{\\mathrm{cum}}$。
  7. **P1-2: 日度最大回撤严格截断至退出日开盘前净值**:
     - `execute_broker_simulation` 中日账本回撤序列严格限制在 $d < T_{K+1}$ 并拼接开盘前净值 $W(T_{K+1}^-)$，确保期末退出日收盘价异动不污染回测统计。
  8. **P1-3: 阶段数据视图与数据覆盖率完备性**:
     - 因子与相关性计算全程采用阶段受限视图 $t \\le \\text{split\\_end}$；
     - `coverage.csv` 扩充记录原始因子覆盖、平价路径数、排除原因，并标注 warmup 与 evaluate 分期。
'''

content = content.replace(old_sec8, new_sec8_sec9)
Path("BUGFIX_CHANGELOG.md").write_text(content, encoding="utf-8")
print("Updated BUGFIX_CHANGELOG.md successfully!")
