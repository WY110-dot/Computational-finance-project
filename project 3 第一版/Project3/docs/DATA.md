# CF2026 Project 3 数据审计与时点规范 (Data Specification)

- **编制日期**：2026-11-16
- **数据源状态**：离线固定快照（无需外部 API Token）

---

## 1. 资产池与数据来源

### 1.1 CN21 资产池
- **资产范围**：21 只中国境内流动性最高、代表性最强的 ETF，涵盖沪深300、中证500、科创50、创业板指等宽基，芯片、医药、消费、证券等行业，以及恒生、黄金、国债、纳指等跨境和跨资产类别品种。
- **底层文件**：
  - `data/raw/prices_raw.parquet`：原始日度交易行情（包含 `open_raw, high_raw, low_raw, close_raw, pre_close_raw, vol_raw, amount_raw` 等）。
  - `data/raw/adjustment_raw.parquet`：除权除息及复权因子表（包含 `adj_factor`）。
- **复权机制**：
  采用后复权口径：$P_{\text{adj}} = P_{\text{raw}} \times (\text{adj\_factor} / \text{ref\_adj\_factor})$。
  在计算日度收益率与累计动量时，严格使用后复权开盘价与后复权收盘价，确保除权除息日不产生人为虚假收益。
- **单位换算**：
  - `vol_raw` 为手（100 股），转换为股数 `volume = vol_raw * 100`。
  - `amount_raw` 为千元，转换为元 `amount = amount_raw * 1000`。
- **时间跨度**：2019-01-02 至 2026-09-18。
- **P5 隔离截断**：在进入特征生成与回测之前，默认将时间截断至 2024-12-31；2025-01-01 之后的数据物理隔离，留作未来 P5 项目。

### 1.2 US9 资产池
- **资产范围**：9 只美国标普行业精选 SPDR ETF：
  - XLB (Materials)
  - XLE (Energy)
  - XLF (Financial)
  - XLI (Industrial)
  - XLK (Technology)
  - XLP (Consumer Staples)
  - XLU (Utilities)
  - XLV (Health Care)
  - XLY (Consumer Discretionary)
- **底层文件**：
  - `data/us_sector/source_manifest.json`：包含 9 只 ETF 的文件名及 SHA-256 校验和。
  - `data/us_sector/{asset}.csv`：包含 `Date, Open, High, Low, Close, Adj Close, Volume`。
- **复权机制**：数据已经完成股息与拆分复权，直接使用调整后 OHLC 序列。
- **时间跨度**：1998-12-22 至 2026-02-06。
- **P5 状态**：2025 年及之后的 US 快照当前不存在，正式标记为“待未来数据提供”，避免任何外推推测。

---

## 2. 形成资格与缺失值处理纪律

1. **历史回溯充足性 (Warmup)**：
   - 形成日 $t$ 计算 12M 动量时，要求资产必须至少有完整的 13 个历史月末收盘价（第 12 个历史月末收盘价至当前月末收盘价）。
   - 计算日度 EWMA 波动率和 63 日/126 日路径效率比率时，要求资产截至形成日必须具备至少 252 个有效交易日的连续收益率序列。
2. **缺失与停牌处理**：
   - 若某资产在形成日停牌或无价格记录，当日不纳入截面形成池。
   - 严禁前向填补停牌期间收益率，严禁将确实由于停牌导致的缺失填零。
   - 若调仓日下一交易日开盘价缺失，整笔交易标记为未成交并保留原仓位或现金，不得事后“向未来寻找开盘日”。
3. **截面最小资产门槛**：
   - 当日有效通过门槛的资产数若不足 6 只，全截面标记为“样本不足”，A/B/C 三者同步执行空仓（100% 现金）规则，严禁人为放宽门槛。
