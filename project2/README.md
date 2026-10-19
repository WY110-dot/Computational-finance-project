# CF2026 Project 2 — Time-Series Momentum 复现

本目录是对 **Moskowitz, Ooi & Pedersen (2012), “Time Series Momentum”, *Journal of
Financial Economics* 104(2), 228–250** 的一次可审计复现。平台沿用 Project 1
的 9 只美国行业 SPDR ETF 固定快照，研究区间为 **2000-01-03 至 2024-12-31**。

## 一句话结论

**在 9 只美国行业 ETF、2000–2024 的样本上，原文的核心结论没有复现。**
12 个月符号对下月收益的 pooled 固定效应回归系数为 **-0.000614**
（HAC t = **-0.22**，N = 2,700），符号策略没有择时能力；多元化 TSMOM
的月频 Sharpe 为 **0.325（gross）/ 0.242（net 10 bp）**（日频为 0.308/0.237），
低于等权基准的 **0.610（月频）**，也远低于原文的约 **1.01**。这是一个有解释力的
负结果，而不是代码失败：账本审计误差小于 2e-8，单元测试和手算复核均通过。
详见 [REPORT.md](REPORT.md) 与 [DIFFERENCE_ATTRIBUTION.md](DIFFERENCE_ATTRIBUTION.md)。

## 快速开始

```bash
# 在 project2/ 目录下
python -m venv .venv
# Windows:
.venv/Scripts/activate
# macOS/Linux:
# source .venv/bin/activate

pip install -e .
python run.py                 # 约 25 秒，生成 outputs/
python -m unittest discover -s tests -v
python verify.py              # 重跑 + 对比 + 写 outputs/verification.json
python build_report.py        # 生成 output/pdf/CF2026_Project2_Report.pdf
```

全流程离线，不需要联网。数据快照由 `data/source_manifest.json` 的 SHA-256
锁定；`run.py` 在读取前逐个校验。

## 目录结构

```text
project2/
├── run.py                     # 唯一入口：数据校验 → 信号 → 权重 → 账本 → 统计 → 图 → 溯源
├── config.json                # 所有研究设定（样本、资产、波动率目标、费用、敏感性网格）
├── pyproject.toml             # 固定依赖版本
├── data/
│   ├── raw/*.csv              # 9 只 ETF 的已调整 OHLC 快照
│   └── source_manifest.json   # 原始行数、日期范围、SHA-256
├── src/
│   ├── data.py                # P1 数据校验/面板（复用并显式化 warm-up）
│   ├── tsmom.py               # 信号、EWMA 波动率、权重（新增）
│   ├── backtest.py            # 带符号、可做空的日频账本（P1 账本扩展）
│   ├── stats.py               # HAC、pooled FE、alpha、极值月份（新增）
│   └── plots.py               # 静态图（P1 配色/风格，新增图）
├── tests/                     # unittest：信号、权重、账本、统计、可重复性
├── verify.py                  # 重跑基线并逐表对比，生成 verification.json
├── build_report.py            # 从 outputs/ 生成中文 PDF 报告
├── outputs/                   # 运行证据（CSV/JSON/PNG）
├── output/pdf/                # 提交版 PDF
├── PAPER.md                   # 原文方法、目标表格与数值、指定/未指定细节
├── RESEARCH_PROTOCOL.md       # 预先登记的问题、假设、设计与判定规则
├── DATA.md                    # 数据说明、清洗、哈希与局限
├── REPORT.md                  # 主报告（中文）
├── DIFFERENCE_ATTRIBUTION.md  # 原文 vs 本次差异的逐项证据与归因
├── HAND_CHECKS.md             # 小样本手算复核
├── AI_ASSISTANCE.md           # AI 使用说明
└── SUBMISSION_CHECKLIST.md    # 按 PDF 要求逐项对照
```

## Project 1 复用与新增

| 模块 | 来源 | 说明 |
|---|---|---|
| `src/data.py` | P1 复用 | 原始 CSV → 校验 → 固定网格；新增显式 `warmup_start`，保证 12 个月信号和 60 日 EWMA 在样本开始前已预热 |
| `src/backtest.py` | P1 扩展 | P1 是 long-only、自融资账本；本目录允许负 units/负现金、做空、按 |Δnotional| 收双边费用，并保留逐日审计 |
| `src/plots.py` | P1 风格复用 | 相同浅色表面、固定分类色序、直接标注、单一坐标轴；新增 TSMOM 图 |
| `config.json` | P1 思路复用 | 所有参数外置，运行清单记录配置哈希 |
| `src/tsmom.py` | **新增** | 符号信号、多期限、EWMA 波动率/协方差、40% 单资产目标、1/N、gross cap |
| `src/stats.py` | **新增** | Newey–West/HAC、pooled 固定效应、月份聚类、alpha、极值月份 |
| `verify.py` / `tests/` | **新增** | 可重复性与账本一致性检查 |

## 关键输出

运行后 `outputs/` 中包含：

- `strategy_summary.csv` — 所有策略的收益、波动、Sharpe（日频/月频）、回撤、换手、暴露、成本
- `predictive_regressions.csv` — 1/3/6/12/24 个月、逐资产 + pooled FE
- `signal_diagnostics.csv` — 符号为正的比例、正/负符号后的下月平均收益与差
- `sensitivity_lookback.csv` / `sensitivity_cost.csv` / `sensitivity_vol_target.csv`
- `sensitivity_subperiods.csv` / `sensitivity_risk_free.csv`
- `alpha_tests.csv` — 相对等权基准的月频 alpha（HAC）
- `extreme_months.csv` — 市场极端月份的 TSMOM 表现
- `diagnostics.json` — 平均两两相关、等权市场统计、事前组合波动率、long bias
- `audit.json` — 账本恒等式误差
- `run_manifest.json` — 代码/配置/数据哈希、运行环境、运行时间
- `figures/*.png` — 报告图
- `*_daily.csv` / `*_trades.csv` — 逐日净值与逐笔交易（主策略与扩展）

## 环境

- Python 3.13.7（`run_manifest.json` 记录）
- numpy 2.3.5, pandas 2.3.3, scipy 1.16.3, statsmodels 0.14.5,
  matplotlib 3.10.8, reportlab 5.0.1
- 无随机数、无网络、无外部数据下载；同一输入应逐位可重复（浮点求和顺序固定）

## 重要限制

1. 快照是**当前** 9 只行业 ETF 的已调整价格，不是 point-in-time 全市场样本；
   存在幸存者偏差，且没有股息现金流、没有期货展期收益。
2. 9 只 ETF 同属美国股票、平均两两相关约 0.61（日频）/0.56（月频），
   与原文 58 个期货、4 大资产类别的分散度不可比。
3. 账本不建模融资、借券、保证金、卖空 locate；它是研究用总收益代理，不是券商账户。
4. 所有结论仅适用于本快照、本区间、本实现；不能外推为“TSMOM 无效”。
