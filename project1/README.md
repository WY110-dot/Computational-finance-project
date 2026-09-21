# MA216 Computational Finance — Project 1
## AI-Assisted Quantitative Research Framework (Fall 2026)

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/pytest-26%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

---

## 1. Project Description
本项目为 **MA216 Computational Finance (Fall 2026) Project 1** 的官方标准实现。
遵循课程核心设计哲学：
> **Correctness > Reproducibility > Interpretability > Extensibility > Performance > Complexity**

本框架实现了从多资产数据下载、前复权清洗、Alpha 因子挖掘、全要素因子诊断（IC/Rank IC/分组收益）、到基于配置文件的目标组合回测（考虑调仓摩擦、双边交易税费与会计账本恒等式）的完整量化研究闭环。

---

## 2. Environment
- **操作系统**：Windows 10/11, macOS, Linux
- **开发语言**：Python 3.11 - 3.13
- **核心依赖**：`pandas >= 2.0`, `numpy >= 1.24`, `scipy >= 1.10`, `tushare >= 1.2`, `pyarrow >= 14.0`, `pyyaml >= 6.0`, `matplotlib >= 3.7`, `pytest >= 8.0`

---

## 3. Installation
克隆仓库并建立 Python 虚拟环境：

```bash
git clone <your-repo-url>
cd CF2026_Quant_System

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate
# 激活虚拟环境 (macOS/Linux)
# source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install scipy pyarrow pyyaml
```

---

## 4. Data Source
- **主要数据源**：[Tushare Pro](https://tushare.pro/)
- **资产池 (Universe)**：精选 21 只 A 股核心高流动性 ETF（涵盖大盘宽基 50/300/500、行业主题芯片/医药/新能源、海外互联/纳指以及国债 ETF）。
- **时间范围**：2019-01-02 至 2026-09-18（1,873 个交易日，38,407 条记录）。
- **复权机制**：使用官方累计复权因子 (`fund_adj`) 进行前复权计算，固定基准日为 `20260918`，彻底隔绝因复权时序变动带来的前视偏差。

---

## 5. How to Configure Tushare
在项目根目录下创建 `.env` 文件，填入你的 Tushare Pro API Token：

```ini
TUSHARE_TOKEN=your_personal_tushare_token_here
```

---

## 6. How to Build Data
一键拉取原始数据、清洗并生成标准面板 Parquet 文件、数据字典、样本集及数据质量报告：

```bash
python run_phase_d1.py
```
- 输出至：
  - `data/raw/prices_raw.parquet`
  - `data/processed/prices_daily.parquet`
  - `data/sample/prices_sample.csv`
  - `docs/data_dictionary.md`
  - `outputs/quality/data_quality_report.md`

---

## 7. How to Run Factors
计算三大核心 Alpha 因子（20日动量 `MOM20`、5日反转 `REV5`、20日低波动 `LOWVOL20`）并生成统一长表及 Factor Cards：

```bash
python run_phase_f1.py
```
- 因子统一采用截面百分位排序（Cross-sectional Rank: 0.0~1.0）标准化；
- 输出至：`data/processed/factors/core_factors_long.parquet` 与 `docs/factors/*_card.md`。

---

## 8. How to Run Diagnostics
执行全要素因子体检（计算前向 1 日与 5 日的 Pearson IC、Spearman Rank IC、Rank IC IR、K=5 分组平均收益、High-Low Spread 与单调性检验）：

```bash
python run_phase_a1.py
```
- 输出至：
  - `outputs/analysis/ic_report.csv` (汇总统计)
  - `outputs/analysis/ic_timeseries.csv` (8,237 行逐日时序明细)
  - `outputs/analysis/group_return_report.csv`
  - `outputs/analysis/factor_distribution_report.csv`

---

## 9. How to Run Backtest
执行基于配置文件的多资产投资组合回测引擎：

```bash
python run_project1.py --phase backtest
```

---

## 10. How to Reproduce Baseline
基准测试为 **MOM20 因子等权重（Monthly Rebalance），选取 Top 5 等权配置，双边交易费 0.03%**。

执行对应脚本：
```bash
python run_phase_p1_to_r1.py
```
- 输出至：`outputs/tables/portfolio_baseline_monthly_ledger.csv`
- 基准绩效指标（截至 2026-09-18）：Net Cumulative Return **+45.45%**, Annualized Return 5.17%, Volatility 21.92%, Sharpe Ratio 0.250, Max Drawdown -38.80%。

---


## 11. How to Reproduce Controlled Experiment
严格遵循“控制变量法”，保持资产、因子、持仓数量、费用率完全一致，仅将调仓频率改为 **周度调仓（Weekly Rebalance）**。

执行对应脚本：
```bash
python run_project1.py --phase backtest
```
- 输出实验结果：`outputs/tables/experiment_comparison_monthly_vs_weekly.csv`
- 输出对比净值曲线：`outputs/figures/rebalance_frequency_experiment.png`
- **样本内比较结果**：在当前样本和配置下，周度调仓的 Net Cumulative Return 为 **+172.85%**，Sharpe Ratio 为 **0.622**，高于月度调仓基准。该结果表明，在本样本中周度调仓表现更好；由于未进行统计显著性检验，不将其表述为普遍有效或因果结论。

---


## 12. Project Structure
```text
CF2026_Quant_System/
├── README.md                           # 顶层项目说明与操作指南
├── requirements.txt                    # Python 依赖清单
├── run_project1.py                     # 全流程统一命令行入口
├── config/                             # 策略配置文件 (Section 26)
│   ├── project1_baseline.yaml          # 月度调仓基准配置
│   └── project1_experiment_weekly.yaml # 周度调仓实验配置
├── data/
│   ├── raw/                            # 原始拉取数据
│   ├── processed/                      # 标化清洗后数据 (Parquet)
│   ├── sample/                         # 可公开分享小样本 (CSV)
│   └── manifests/                      # 数据元数据清单与 Checksum
├── src/
│   ├── data/                           # 数据下载与复权模块
│   ├── factors/                        # 因子定义、基类与注册中心
│   ├── analysis/                       # 因子诊断套件 (IC/分组/分布)
│   ├── portfolio/                      # 目标组合生成器 (Phase P1)
│   ├── backtest/                       # 组合账本与回测引擎 (Phase B1)
│   ├── metrics/                        # 收益与组合绩效评价器 (Phase M1)
│   └── utils/                          # 复现系统与环境记录 (Phase R1)
├── tests/                              # 26 项全流程自动化单元测试套件
├── docs/                               # 架构图、数据字典、因子卡片与方法论
│   ├── architecture.md
│   ├── data_dictionary.md
│   └── factors/
└── outputs/                            # 报告、图表、指标表与复现元数据
    ├── quality/
    ├── analysis/
    ├── tables/
    ├── figures/
    └── manifests/
```

---

## 13. Known Limitations
1. **资产池规模**：当前 Universe 为 21 只核心上交所 ETF。深交所部分 ETF 在 Tushare 免费接口层存在日线字段兼容性差异，已在第一版中安全过滤；
2. **滑点模型**：目前基准回测假设以当日收盘价（Close）无滑点成交，在大资金规模下应在 YAML 中进一步配置冲击成本；
3. **等权配置**：第一版未引入协方差均值-方差优化或风险平价，以保持逻辑的最大透明度与可解释性。
