# 数据说明、来源与局限

CN21：data/raw/prices_raw.parquet 与 adjustment_raw.parquet；Tushare 固定日行情和复权因子，来源和 SHA-256 在 data/manifests/source_manifest.json。按形成时历史有效性决定入池，当前 21 个代码为固定候选集合，不是无幸存者偏差的全市场历史成分。原始价用于 P1 交易，调整价用于收益与信号。复权价不再额外加分红，防止重复计入。

US9：data/us_sector/*.csv，格式来自公开仓库 miguel-merlin/etf-directional-forecasting，固定 commit b3b583b10cce9a29cb97ab65d08f5854c0ffd001。逐文件下载地址、blob SHA 与 SHA-256 在 source_manifest.json。组员原快照已调整 OHLC，上游调整方法不能完全反推；保留调整价代理局限。Date 字符串取前 10 位为当地交易日期，不以 UTC 转换造成跨日；截止 2024-12-31。

候选资产 XLB/XLE/XLF/XLI/XLK/XLP/XLU/XLV/XLY；历史从 1998-12-22 起作暖机。每日收益不向前填补。双方样本均需 13 个连续月末与至少 252 个连续日收益，原始数据保留供检查。

AQR：data/reference/Time-Series-Momentum-Original-Paper-Data.xlsx。来源 https://images.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Original-Paper-Data.xlsx 。使用已保存快照，不声称本包数据为最新。原文元数据和论文 PDF 来源在 quantcf/reference_data.py。

## 核心字段

| 字段 | 含义与单位 |
|---|---|
| date / asset | 当地交易日期 / ETF 代码 |
| open, close / open_adj, close_adj | 原始价 / 复权价格；CN 为人民币，US 为美元 |
| volume / amount | 成交量 / 成交额；原始 Tushare 单位在加载器中转换并校验 |
| formation_date / holding_end_date | 信号形成日 / 对应持有期末；合并两市场时按经济月份对齐 |
| sigma_ewma / s12 / signal_multi | 事前年化波动率 / 12M 符号 / 3/6/12 等权符号 |
| formation_eligible / n_eligible | 仅基于历史可得数据的形成资格 / 合格资产数 |
| weight / contrib | 资产名义权重占 NAV / 对组合该月收益的贡献 |
| ann_mean / cagr / ann_vol | 算术年化均值 / 复利年化 / 年化标准差；均用小数保存 |
| mean_gross / net_exposure | 绝对权重之和 / 有符号权重之和 |

离线复现不需要 Token。不提交账户密码、API 密钥或 .env。数据快照用于本课程研究，保留原始来源与限制。当前研究设置以 docs/PROTOCOL.md 与配置为准。
