# 原文到代码的映射与核验

| 原文或检查 | 实现 | 证据 |
|---|---|---|
| p.233 Eq.(1)，EWMA λ=60/61、年化 261 | quantcf/tsmom.py | tests/test_tsmom.py 的独立 [1,2,4]/7 手算 |
| p.236 Eq.(5)，12M / 1M | tsmom.py + research_backtest.py | signals/、research/ 权重和月收益 |
| p.237 Fig.2 上部 | pipeline_p2.py | 单资产指标，不除以动态 N |
| p.239 Fig.3 | pipeline_p2.py + integration.py | 同样逆波动预算 passive long；不同数据明确标注 |
| p.233 Eq.(3) 型 pooled 回归 | integration.diagnostic_regressions | 单个滞后月符号、y/σ、月份聚类；没有资产固定效应 |
| 额外累计 12M 回归 | integration.diagnostic_regressions | 单独 model 标签，不冒充 Fig.1 |
| 相对被动基准 alpha | integration.py | HAC6；不是论文多因子 alpha |
| p.239 Fig.4 型扩展 | integration.py | 完整非重叠季度，横轴用 ETF passive 代理；非原 S&P500 |
| 同事前风险 | integration.risk_scaled_series | 改未来价格不改变形成日 scale；目标与 cap 单独检验 |
| 重采样 | integration.paired_bootstrap | 共同月份成对循环抽块、固定种子；相同序列差值为零 |
| P1 执行账本 | backtest.py | orders/fills/holdings/ledger/audit、合成反例测试 |

EWMA 使用有限样本归一化权重与总体加权方差。252 为最少连续日收益数，261 为原论文日方差年化因子；执行日频绩效年化采用 252，月频采用 12。这三个数的用途不同。

交易预算 b_i = 0.99×(1/σ_i)/Σ(1/σ_j)，目标 w_i=b_i max(s_i,0)。多期限先平均符号，再截断负值留现金。B2 桥接保持此分母，仅以月末线性收益；B3 切换整个 next-open Broker 约定，故该步骤含估值/单位/持仓漂移机制，不声称只改变一个价格因素。

月频 Sharpe=√12×mean(R)/std(R,ddof=1)，执行日收益先按月复合；算术年化=12×mean(R)，CAGR=累计财富^(12/月数)-1。月回撤与日回撤都包含初始资本 1，分表披露。所有 rf=0 的主结果为零无风险基准，不冒称已经扣除市场无风险利率。
