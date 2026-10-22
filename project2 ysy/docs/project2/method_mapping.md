# 论文公式与系统实现映射表 (Method Mapping)

**论文依据**: Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). *Time series momentum*. Journal of Financial Economics, 104(2), 228–250.

---

## 1. 原文公式与代码实现对应

| 原文章节 / 公式 | 原文定义与用途 | 项目 2 对应实现模块与函数 | 实现设定与补充说明 |
|---|---|---|---|
| Section 2.4, Eq. (1) | 事前波动率估计: $\sigma_{t}^2 = \sum_{j=0}^\infty (1-\lambda)\lambda^j (r_{t-j} - \bar{r}_t)^2$，其中 $\lambda = 60/61$ | `src/quantcf/tsmom.py::calculate_ewma_volatility()` | 补充有限历史归一化权重 $a_j = \frac{(1-\lambda)\lambda^j}{1-\lambda^n}$；要求连续有效交易日 $n \ge 252$；年化因子固定采用 261（原文标准）。 |
| Section 4.1, Eq. (5) | 单资产 12 月 TSMOM 策略收益: $r^t_{t+1} = \operatorname{sign}(r^t_{t-12,t}) \frac{40\%}{\sigma_t} r_{t+1}$ | `src/quantcf/tsmom.py::calculate_momentum_signals()` 及 `src/quantcf/research_backtest.py::run_research_backtest()` | 单资产名义缩放尺度 0.40；信号由自身过去 12 个自然月净复权收益的符号决定（+1, -1, 0），不进行截面去均值或排序。 |
| Section 4.1 (p. 235) | 跨资产组合等权平均: $R^{TS}_{t+1} = \frac{1}{N_t} \sum_i \operatorname{sign}(r^i_{t-12,t}) \frac{40\%}{\sigma^i_t} r^i_{t+1}$ | `src/quantcf/research_backtest.py::run_research_backtest(mode='tsmom12')` | 按形成月末全部合格资产 $N_t$ 平均；每月统计总绝对敞口、净敞口与资产贡献；零利率研究假设下使用超额收益近似。 |
| Section 4.1, Fig. 3 对照组 | 被动多头对照: $R^{PL}_{t+1} = \frac{1}{N_t} \sum_i \frac{40\%}{\sigma^i_t} r^i_{t+1}$ | `src/quantcf/research_backtest.py::run_research_backtest(mode='passive_long')` | 保持相同单资产事前波动率预算，仅将动量符号强制置为 +1，严格控制风险预算可比性。 |
| 自主扩展 (Extension) | 多期限复合动量: $a_{i,m} = \frac{1}{3} [s^{(3)}_{i,m} + s^{(6)}_{i,m} + s^{(12)}_{i,m}]$ | `src/quantcf/tsmom.py::calculate_multi_horizon_signal()` 及 `src/quantcf/research_backtest.py::run_research_backtest(mode='multi_horizon')` | 固定 3、6、12 个月权重为各 1/3，不做样本内网格调参；复合后信号取值范围为 $\{-1, -1/3, 1/3, 1\}$。 |
| 交易约束迁移 (Execution) | 真实多头执行目标权重: $w^{LC}_{i,m} = 0.99 \frac{1/\sigma_{i,m}}{\sum_j 1/\sigma_{j,m}} \max(s_{i,m}, 0)$ | `src/quantcf/portfolio.py::generate_tsmom_long_cash_targets()` | 严格遵守无借券、无杠杆限制；负信号资产预算保留在现金；接入 P1 账本以次日开盘价撮合成交并扣除手续费。 |

---

## 2. 原文与本项目实现的已知差异 (Methodological Adjustments)

1. **资产类别与做空机制**:
   - 原文：全球跨国期货合约（58 只），多空双向均有高度流动性与保证金支持。
   - 本项目：中国市场 ETF（21 只），受制于现货融券限制，执行模式（T1/T2）采用 Long/Cash 结构，研究模式（R1/R4）采用多空线性收益作为理论基准。
2. **时间跨度与宏观环境**:
   - 原文：1985–2009（25 年，共 300 个月），跨越全球大宗商品超级周期与利率长期下行期。
   - 本项目：2019–2026（正式评价期 79 个月），处于结构性分化与国内震荡/下行并存的市场周期。
3. **无风险利率处理**:
   - 原文：期货收益天然为超额收益（无需扣除融资成本，仅需加回保证金利息）。
   - 本项目：使用复权现货价格作为总收益代理，在无统一基准存款/回购利率可靠输入时设定日度/月度无风险利率为 0，并在所有对比策略间保持一致。

