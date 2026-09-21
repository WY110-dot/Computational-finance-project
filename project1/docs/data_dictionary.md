# Data Dictionary

| Field | Definition | Unit | Notes |
|---|---|---|---|
| date | 交易日 | YYYYMMDD | |
| asset | Tushare 代码 | string | |
| open_raw | 原始开盘价 | RMB | |
| close_raw | 原始收盘价 | RMB | |
| adj_factor | 复权因子 | dimensionless | |
| close_adj | 复权收盘价 | adjusted RMB | |
| volume | 成交量 | 手 | 1手=100份 |
| amount | 成交金额 | 千元 | |
| ret_total | 总收益率 | decimal | |
| adjustment_reference_date | 复权基准日 | YYYYMMDD | Phase C1 固定 reference date |
