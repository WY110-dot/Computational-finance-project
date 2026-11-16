# 数据字典

## 原始快照

| 字段 | 含义 | 单位 |
|---|---|---|
| `ts_code` | Tushare ETF 代码 | 字符串 |
| `trade_date` | 交易日 | `YYYYMMDD` |
| `open/high/low/close` | 原始 OHLC | 元/份 |
| `vol` | 成交量 | 手，1手=100份 |
| `amount` | 成交金额 | 千元 |
| `adj_factor` | Tushare 基金复权因子 | 无量纲 |

## 标准面板

| 字段 | 含义 | 单位/约定 |
|---|---|---|
| `date` | 交易日 | pandas datetime |
| `asset` | ETF 代码 | 字符串 |
| `open_raw/high_raw/low_raw/close_raw` | 原始价格 | 元/份 |
| `adj_factor` | 当日复权因子 | 无量纲 |
| `adjustment_reference_date` | 固定复权参考日 | 日期 |
| `open_adj/high_adj/low_adj/close_adj` | 固定参考日复权价格 | 一致价格尺度 |
| `volume_lots` | 原始成交量 | 手 |
| `volume_units` | 换算成交份额 | `volume_lots × 100` |
| `amount_raw_thousand` | 原始成交金额 | 千元 |
| `amount` | 执行层使用的成交金额 | 元 |
| `ret_total` | 复权收盘到收盘收益 | 小数 |

复权价格只改变计价单位，不向策略注入未来收益信息；因子在形成日仅使用历史复权序列。流动性限制优先使用原始成交金额，而不是使用复权价格乘原始成交量。

