# 小样本手算与账本审计

本文件记录对实现的手工复核，目的不是重复全部回测，而是确认最关键的三类
计算：**信号/权重**、**交易/费用**、**月收益/回归**。所有数字都可以用
`outputs/` 中的 CSV 复现。

## 1. 信号与权重：XLB 2019-12-31

### 1.1 原始价格

从 `data/raw/XLB.csv`：

| 日期 | Close |
|---|---:|
| 2018-12-31 | 21.91522598 |
| 2019-12-31 | 27.20317268 |

12 个月收益：

\[
r^{(12)} = \frac{27.20317268}{21.91522598} - 1 = 0.2412909958 = 24.1291\%.
\]

符号：

\[
s = \operatorname{sign}(0.2412909958) = +1.
\]

### 1.2 波动率

对 XLB 的日收益做 EWMA（center of mass 60，min_periods 40，
`adjust=True`, `bias=True`），2019-12-31 的年化波动率：

\[
\sigma = 0.1307653509 = 13.0765\%.
\]

### 1.3 权重

12 个月 TSMOM 的权重（\(N=9\)）：

\[
w = \frac{1}{9}\cdot\frac{0.40}{0.1307653509}\cdot(+1)
= 0.3398793652.
\]

`outputs/weights.csv` 中 `portfolio=tsmom_12m, asset=XLB, date=2019-12-31`
的权重为 **0.339879**。✓

### 1.4 命令

```bash
python - <<'PY'
import pandas as pd, numpy as np
from src import tsmom as ts
raw = pd.read_csv('data/raw/XLB.csv')
raw['Date'] = pd.to_datetime(raw.Date.astype(str).str[:10])
raw = raw.set_index('Date').sort_index()
p0 = raw.loc['2018-12-31','Close']; p1 = raw.loc['2019-12-31','Close']
print(p1/p0 - 1, np.sign(p1/p0 - 1))
panel = pd.read_csv('outputs/clean_panel.csv', parse_dates=['date'])
close = panel.pivot(index='date', columns='asset', values='close')
vol = ts.ewma_vol(close.pct_change(fill_method=None), 60, 40, 252)
sig = ts.sign_signal(ts.monthly_close(close), 12)
print(vol.loc['2019-12-31','XLB'], sig.loc['2019-12-31','XLB']*0.4/vol.loc['2019-12-31','XLB']/9)
PY
```

---

## 2. 首笔交易与费用：2000-01-03 XLB

`outputs/tsmom_diversified_trades.csv` 的首行：

| 字段 | 值 |
|---|---:|
| signal_date | 1999-12-31 |
| date（执行） | 2000-01-03 |
| asset | XLB |
| target_weight | 0.187720 |
| target_dollars | 187,719.624890 |
| execution_price（open） | 7.456982 |
| units | 25,173.672577 |
| fee | **187.719625** |

手算：

\[
\text{target} = 0.187720 \times 1{,}000{,}000 = 187{,}720,
\]

\[
\text{fee} = 187{,}719.62 \times 0.001 = 187.72.
\]

买卖各 10 bp；这是买入，费用 187.72。✓

时序：1999-12-31（信号）< 2000-01-03（执行），没有未来数据。

---

## 3. 月收益：2020 年 3 月

`outputs/tsmom_diversified_daily.csv` 中 2020-03-01 至 2020-03-31 共 22 个
交易日。日收益复合：

\[
\prod_{d}(1+r_d)-1 = 0.1904548695 = +19.0455\%.
\]

`outputs/monthly_returns.csv` 的 `2020-03-31, tsmom_diversified` 为
**0.190454869479**。✓

该月是 COVID 崩盘后的反弹月；策略因长期多头暴露获得大幅正收益。这也说明
单月收益不能代表择时能力——它在同一个样本的 2016–2024 子样本里整体为负。

---

## 4. 小样本 OLS：手算 vs 代码

取 1999-12 至 2001-11、9 个资产、12 个月信号，共 216 个观测：

\[
y_{i,t+1} = a + b \cdot s_{i,t} + e.
\]

用 `numpy.linalg.lstsq` 手算：

| 参数 | 手算 | `stats.nw_regression` |
|---|---:|---:|
| a | 0.00021472 | 0.00021472 |
| b | **-0.0094922** | **-0.0094922** |
| t(b) | — | -1.7326 |
| R² | — | 0.01657 |

点估计完全一致；t 值由 HAC 标准误给出，手算不重复协方差矩阵。✓

注意：这是**小样本**（216 个观测、24 个月），t=-1.73 不显著；它只用于
核对实现，不用于推断。全样本 pooled 结果见 `predictive_regressions.csv`。

---

## 5. 账本与暴露恒等式

### 5.1 最后一次再平衡

`outputs/tsmom_diversified_daily.csv` 中 2024-12-02：

| 字段 | 值 |
|---|---:|
| gross_exposure | 2.462681 |
| net_exposure | 2.462681 |
| n_long | 9 |
| n_short | 0 |

9 个多头、0 个空头；gross = net，符合定义。✓

### 5.2 所有再平衡日

对 300 个再平衡日逐行检查：

\[
\text{net} \le \text{gross}
\]

最大差为 0（`net - gross` 的最大值为 0）。✓

### 5.3 账本审计

`outputs/audit.json`：

| 检查 | 最大误差 |
|---|---:|
| 日收益 vs NAV | 2.22e-16 |
| 复利 vs 终端 NAV | 1.05e-13 |
| NAV 定义 | 0 |
| 成本非负 | 0 |
| 换手定义 | 0 |
| 现金账本 | 1.68e-8 |
| 费用求和 | 1.16e-10 |

全部小于 1e-5 阈值。✓

---

## 6. 数据质量抽查

`outputs/quality_report.json`：

- 9 个资产 × 6,548 天 = 58,932 行；
- 固定网格缺失 close = 0；
- 重复键 = 0；
- 非法行 = 0；
- 零成交量 = 1（XLI，单日）；
- OHLC 不一致 = 0；
- 原始 61,407 行，保留 58,932 行（截取 warm-up 至 2024-12-31）。

抽查 XLB 2000-01-03：

| 字段 | 值 |
|---|---:|
| Open | 7.456982 |
| High | 7.461350 |
| Low | 7.251663 |
| Close | 7.260400 |
| Volume | 281,000 |

本文只用 Open/Close 记账；原始 CSV 的 OHLC 一致性检查已通过
（High ≥ Open/Close/Low，Low ≤ Open/Close/High）。

---

## 7. 自动测试与重跑

```bash
python -m unittest discover -s tests -v
python verify.py
```

测试覆盖：

- `test_signal.py`：月末日期、trailing return、sign、多期限、skip-month；
- `test_weights.py`：权重公式、1/N、40% 目标、gross cap、min_assets；
- `test_backtest.py`：多头/空头账本、费用、现金、月收益、子样本；
- `test_stats.py`：NW 回归、pooled FE、alpha、极值分尾；
- `test_no_lookahead.py`：改变未来价格不影响信号/权重；
- `test_reproducibility.py`：重复运行关键输出一致。

`verify.py` 输出 `outputs/verification.json`，包含：

- 单元测试是否通过；
- 重跑输出与 `outputs/` 的逐表最大绝对差；
- 账本审计是否通过；
- 数据哈希是否匹配；
- 运行环境与时间。

如果任何一项失败，`verification.json` 的 `status` 为 `FAIL`，不应提交。
