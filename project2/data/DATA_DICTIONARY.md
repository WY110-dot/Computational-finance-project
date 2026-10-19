# 数据字典与来源边界

|字段|含义|单位/处理|
|---|---|---|
|Date|来源美国交易日，含时区偏移|保留原字符串，清洗取本地日期前10字符，不转UTC跨日|
|Open/High/Low/Close|来源已经调整的OHLC价格|美元/调整后单位；不再重复复权|
|Volume|来源日成交量|来源标称份数；与调整后单位不完全同口径|
|Dividends/Stock Splits/Capital Gains|来源公司行动字段|保留原始文件，不额外加入回测现金|
|ticker|来源资产代码|与配置及文件名对应|
|date,asset,open,high,low,close,volume|标准化日频长表|`outputs/clean_panel.csv`，date×asset唯一|
|date,asset,factor,value|统一因子长表|原始因子值，不统一填补缺失|
|adjusted_units|研究账本持仓|调整后价格单位，不是真实原始股数|
|capacity|单次成交额压力上限|前20日价格成交量代理×参与率，美元代理|

来源仓库：https://github.com/miguel-merlin/etf-directional-forecasting

固定提交：`b3b583b10cce9a29cb97ab65d08f5854c0ffd001`。各资产原始文件路径：`data/etfs/{asset}.csv`。原下载时间未记录于源CSV，本项目获取时间另在`source_manifest.json`标明，不能混同。原文件一直保留至2026-02-06，但本次回测导入时严格截断至2024-12-31；信号预热从2014-09-23开始。

源仓库的`README.md`说明Yahoo/yfinance来源；`screener/utils.py`中获取历史的调用为`stock.history(period="max")`。现有CSV没有`Adj Close`和复权因子，结合当前库默认调整行为，按已调整价格使用属于有依据但未得到供应商逐日独立确认的口径判断。若后续需要真实成交容量或原股数公司行动账本，应更换为同时提供未复权价、复权因子和公司行动时点的数据源。

参考说明：

- Yahoo Adjusted Close：https://help.yahoo.com/kb/SLN28256.html
- yfinance价格历史接口：https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html

本项目不使用源仓库的预测模型、策略或结果，只读取公开行情事实快照，所有研究模块独立实现。不要将上游项目的模型结论当作本项目证据。
