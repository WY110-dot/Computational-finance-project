# 数据说明（Code & Data Description）

## 1. 来源与许可

- 数据提供方：公开 GitHub 仓库快照
  [`miguel-merlin/etf-directional-forecasting`](https://github.com/miguel-merlin/etf-directional-forecasting)
- 固定 commit：`b3b583b10cce9a29cb97ab65d08f5854c0ffd001`
- 获取时间（UTC）：2026-09-20T11:27:46Z
- 文件：`data/etfs/{XLB,XLE,XLF,XLI,XLK,XLP,XLU,XLV,XLY}.csv`
- 格式：Yahoo Finance 风格的日频 OHLCV（`Date, Open, High, Low, Close, Volume`）
- 价格：源文件已是**调整后价格**（没有 `Adj Close` 列；根据上游仓库与列结构推断）。
  调整后的价格用于总收益代理，但**没有单独的股息现金流**。
- 许可/使用：上游为第三方归档的 vendor 数据，非交易所认证、非 point-in-time；
  仅用于课程/个人研究，不主张再分发权利。详见 `data/source_manifest.json`
  的 `limitation` 字段。

## 2. 资产与哈希

`data/source_manifest.json` 记录每个文件的 SHA-256。`src/data.py` 在读取前
逐个校验；校验时把 CRLF 规范化为 LF（上游 manifest 基于 LF 计算，Windows
`core.autocrlf=true` 的 checkout 只改行尾，不应被视为数据变化）。

| 资产 | 行业 | SHA-256（前 16 位） | 原始行数 |
|---|---|---|---|
| XLB | Materials | `8a791971ec1fb828` | 6,823 |
| XLE | Energy | `ad0deb56c6f966ff` | 6,823 |
| XLF | Financials | `36a99ee87505f1ae` | 6,823 |
| XLI | Industrials | `954c7ac7815f35b4` | 6,823 |
| XLK | Technology | `05ff8f45ad1bfc98` | 6,823 |
| XLP | Consumer Staples | `79aebfbad3509a5f` | 6,823 |
| XLU | Utilities | `4991b1d55f69bfe9` | 6,823 |
| XLV | Health Care | `e23edbaf0fdc39f4` | 6,823 |
| XLY | Consumer Discretionary | `3dcaa347f34ffedc` | 6,823 |

完整哈希、URL、bytes 与 blob SHA 见 `data/source_manifest.json`。
本研究不修改原始 CSV 的数值；复制到 `project2/data/raw/` 时只统一了行尾
（CRLF→LF），并在 `.gitattributes` 中标记 `data/raw/*.csv -text`，防止
Git 再次转换行尾。

## 3. 字段与单位

| 字段 | 说明 |
|---|---|
| `date` | 交易日（YYYY-MM-DD），取源文件 `Date` 前 10 位 |
| `asset` | ETF ticker |
| `open/high/low/close` | 调整后价格（美元） |
| `volume` | 成交量（股） |

- 价格单位不影响收益率与权重；账本以美元 notional 记账。
- 原始数据没有拆股/分红字段，也没有调整因子；因此无法独立复原“原始价格”。
- 账本使用调整后价格单位，相当于总收益价格代理；没有把股息作为现金入账。

## 4. 清洗与样本

`src/data.py` 的 `load_panel()` 执行以下步骤：

1. 读取 `source_manifest.json`，逐个文件校验 SHA-256；
2. 检查必需列、日期解析、重复日期、无穷值、非正价格/负成交量；
3. 检查 OHLC 一致性（high 不低于 open/close/low，low 不高于 open/close/high；
   容差为 close 的 1e-6）；
4. 按日期排序，截取 `[warmup_start, end]`；
5. 以 9 只 ETF 的交易日期并集为固定网格，pivot 成 `date × asset`；
6. 若固定网格的 close 有缺失，直接报错（不插值、不零填充）。

参数（`config.json`）：

- `warmup_start = 1998-12-22`（数据首日）
- `start = 2000-01-01`
- `end = 2024-12-31`
- 研究区间首个交易日：2000-01-03；最后交易日：2024-12-31
- 9 只资产 × 6,548 个交易日 = 58,932 个资产-日观测
- 日频账本：6,289 个交易日；月频再平衡：300 次；月频收益：300 个

质量报告（`outputs/quality_report.json`）：

| 指标 | 值 |
|---|---|
| 原始行数 | 61,407 |
| 清洗后行数 | 58,932 |
| 交易日 | 6,548 |
| 固定网格缺失 close | **0** |
| 重复键 | 0 |
| 非法行 | 0 |
| 零成交量 | 1（XLI，单日） |
| 价格/成交量非正 | 0 |
| OHLC 不一致 | 0 |

## 5. 已知数据限制

1. **不是 point-in-time 全市场样本**：只包含当前仍在的 9 只行业 SPDR ETF；
   存在幸存者/选择偏差。它们都是大型、流动性好的 ETF。
2. **没有股息现金流**：调整后价格隐含再投资，但没有逐笔股息；账本不是券商
   股份/现金账本。
3. **没有期货/远期数据**：无法重建原文的 58 个合约、4 大资产类别、展期收益、
   保证金与空头借券。
4. **交易日历是 9 只 ETF 的并集**，不是独立交易所节假日表；若某只 ETF 某日
   停牌而其他 ETF 交易，网格会保留该日，但本研究的数据在网格上无缺失。
5. **调整因子不可得**：无法区分价格变动、拆股、分红；只能使用上游调整后价格。
6. **样本区间受数据起点限制**：1998-12 起，无法覆盖原文 1965–2009 的早期样本；
   2000–2024 应视为对原文的样本外检验。
7. **行业 ETF 高度相关**：平均两两相关 0.609（日频）/0.564（月频），
   组合分散度远低于原文的跨资产组合。

## 6. 复现数据与代码的对应

| 文件 | 作用 |
|---|---|
| `data/raw/*.csv` | 不可变原始快照（行尾统一为 LF） |
| `data/source_manifest.json` | 来源、commit、URL、bytes、SHA-256 |
| `src/data.py` | 校验、清洗、固定网格、质量报告 |
| `outputs/clean_panel.csv` | 清洗后的长表（date, asset, OHLCV） |
| `outputs/quality_report.json` | 逐资产与汇总质量指标 |
| `outputs/run_manifest.json` | 数据/代码/配置哈希与运行环境 |

## 7. 数据获取的可重复性

本研究不依赖运行时网络。要重新获取同一快照，可按 manifest 中的
`url` + `commit` 下载，并用 `sha256` 校验；注意下载后的行尾可能是 CRLF，
需按 `sha()` 的规范化规则比较。若上游仓库删除或改写历史，固定 commit 的
raw URL 仍应可用；若不可用，本研究无法从零重建数据，这是第三方快照的
固有风险。
