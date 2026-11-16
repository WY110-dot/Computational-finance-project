# CF2026 Project 3 因子卡 (Factor Cards)

- **编制日期**：2026-11-16
- **项目模块**：`quantcf.project3_factors`
- **输出格式**：标准长表（Long Panel: `date, asset, factor, value`）

---

## 1. 因子定义总览

| 标识 | 因子名称 | 类别 | 计算公式 | 预期方向 | 作用说明 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **A0** | `tsmom12_sign` | P2追溯基准 | $\text{sign}(m_{12}(i,t))$ | 正向 | P2 原始二值/三值符号信号，用于完整性追溯 |
| **A** | `mom12_continuous_z` | 经典基准 | $z_{\text{cs}}(\text{winsor}_{3\sigma}(m_{12}(i,t)))$ | 正向 | 经典 12M 连续动量基准 |
| **B (F1)**| `mom12_er63_z` | 主新因子 | $z_{\text{cs}}(\text{winsor}_{3\sigma}(m_{12}(i,t) \times ER_{63}(i,t)))$ | 正向 | 动量与 63 日路径效率交互主因子 |
| **F2** | `mom12_er126_z` | 窗口变体 | $z_{\text{cs}}(\text{winsor}_{3\sigma}(m_{12}(i,t) \times ER_{126}(i,t)))$ | 正向 | 中期约半年（126 日）路径效率变体 |
| **F3** | `mom12_noise63_z` | 反向对照 | $z_{\text{cs}}(\text{winsor}_{3\sigma}(m_{12}(i,t) \times (1 - ER_{63}(i,t))))$ | 正/负向 | 强调噪声路径的反向机制对照 |
| **C** | `combo_mom_er63_z`| 等权合成 | $z_{\text{cs}}(0.5 A + 0.5 B)$ | 正向 | 经典基准 A 与新因子 B 的等权标准化合成 |

---

## 2. 核心数学公式与边界规范

### 2.1 12 个月连续动量与 P2 符号
- 形成日 $t$ 为月末交易日，取一致复权收盘价 $P(i,t)$。
- 记 $t$ 之前第 12 个历史月末收盘价为 $P(i, t-12\text{M})$。
- 连续动量原始分数：
  $$m_{12}(i,t) = \frac{P(i,t)}{P(i, t-12\text{M})} - 1$$
- 追溯基准：
  $$A_0(i,t) = \begin{cases} +1, & m_{12}(i,t) > 0 \\ 0, & m_{12}(i,t) = 0 \\ -1, & m_{12}(i,t) < 0 \end{cases}$$

### 2.2 路径效率比率 (Efficiency Ratio, ER)
- 截至形成日 $t$（含当日收盘），取资产 $i$ 过去连续 $L$ 个有效交易日的复权收盘价序列 $\{P_0, P_1, \dots, P_L\}$（共 $L+1$ 个价格点）。
- 日度对数收益率：$r_{\log, k} = \ln(P_k / P_{k-1}), \quad k = 1, \dots, L$。
- 净位移量：$\Delta_{\text{net}} = \left|\sum_{k=1}^L r_{\log, k}\right| = |\ln(P_L / P_0)|$。
- 累计路径长度：$\Lambda_{\text{total}} = \sum_{k=1}^L |r_{\log, k}|$。
- 效率比率：
  $$ER_L(i,t) = \frac{\Delta_{\text{net}}}{\Lambda_{\text{total}}}$$
- **边界与异常值处理**：
  1. **平价/无波动路径 (Flat Path)**：若 $\Lambda_{\text{total}} = 0$（即价格完全未变），定义 $ER_L(i,t) = 0$，并在日志中记录 `flat_path`，绝不产生除以零异常或 $\text{Inf}$。
  2. **数值浮点容差**：由于浮点运算误差，理论上 $ER \in [0, 1]$。若计算值落入 $[-10^{-12}, 0)$，截断为 0；若落入 $(1, 1 + 10^{-12}]$，截断为 1。若超出该容差范围，立即报错中断。
  3. **数据缺失/停牌断裂**：若历史有效交易日不足 $L$ 天，或出现连续价格缺失，标记该资产在当日 $ER$ 为 `NaN`，不静默填补。

### 2.3 截面标准化流程 (Common Preprocessing)
对于任意原始连续分数向量 $\mathbf{x}_t = [x_{1,t}, x_{2,t}, \dots, x_{N,t}]$（仅在当日通过共同资格检验的资产集上）：
1. **$3\sigma$ 截断 (Winsorization)**：
   $$\mu_t = \frac{1}{N} \sum_{i=1}^N x_{i,t}, \quad \sigma_t = \sqrt{\frac{1}{N} \sum_{i=1}^N (x_{i,t} - \mu_t)^2} \quad (\text{ddof}=0)$$
   $$x_{i,t}^{\text{win}} = \min\left(\max(x_{i,t}, \mu_t - 3\sigma_t), \mu_t + 3\sigma_t\right)$$
2. **截面标准化 (Cross-Sectional Z-Score)**：
   重新计算截断后序列的均值 $\mu_t^{\text{win}}$ 与标准差 $\sigma_t^{\text{win}}$（$\text{ddof}=0$）：
   $$z_i = \begin{cases} \frac{x_{i,t}^{\text{win}} - \mu_t^{\text{win}}}{\sigma_t^{\text{win}}}, & \sigma_t^{\text{win}} > 10^{-12} \\ \text{NaN}, & \sigma_t^{\text{win}} \le 10^{-12} \end{cases}$$
   若截面标准差低于 $10^{-12}$（截面退化），当日所有资产标准分设为 `NaN` 并记录原因，不进行跨期伪填补。
3. **合成规则 (Combination)**：
   $$C_{\text{raw}, i} = 0.5 \times A_i + 0.5 \times B_i$$
   $$C_i = z_{\text{cs}}(C_{\text{raw}, i})$$
   对等权平均后的连续分数进行二次截面标准化（保持相对排序完全不变，尺度统一为均值 0、方差 1）。

---

## 3. 信息切分与执行时点规范

- **信息截止时点 (Information Cutoff)**：形成日 $t$ 月末收盘时刻（$T_{\text{formation}}$）。仅使用截至 $t$ 已经确知并公告的复权价格数据。
- **调仓执行时点 (Execution Open)**：形成日 $t$ 之后的第 1 个交易日开盘时刻（$T_{\text{entry}}$）。买卖订单以该日复权开盘价成交。
- **退出时点 (Exit Open)**：下一形成日 $t+1$ 之后的第 1 个交易日开盘时刻（$T_{\text{exit}}$）。
- **预测收益率标签 (Open-to-Open Holding Label)**：
  $$y(i,t) = \frac{P_{\text{open\_adj}}(i, T_{\text{exit}})}{P_{\text{open\_adj}}(i, T_{\text{entry}})} - 1$$
  严格避免日历月收盘价（Close-to-Close）导致的次日开盘无法以收盘价成交的时点错位偏差。

---

## 4. 小样本手算基准例 (Synthetic Hand-Calculation Example)

为确保单元测试完全独立、可复核，设计以下 3 资产合成算例：

### 4.1 输入数据
- 资产 1 ($S_1$)：$P = [100.0, 110.0, 121.0]$，$L=2$。
  - $r_{\log} = [\ln(1.1), \ln(1.1)] \approx [0.095310, 0.095310]$。
  - 单向单调上升：$\Delta_{\text{net}} = 2 \times 0.095310$, $\Lambda_{\text{total}} = 2 \times 0.095310 \implies ER_2(S_1) = 1.0$。
  - 设其 12M 动量 $b_1 = 0.20$。
  - $F_{1,1} = 0.20 \times 1.0 = 0.20$。
- 资产 2 ($S_2$)：$P = [100.0, 110.0, 100.0]$，$L=2$。
  - $r_{\log} = [\ln(1.1), \ln(100/110)] \approx [0.095310, -0.095310]$。
  - 完美对称往返：$\Delta_{\text{net}} = 0.0$, $\Lambda_{\text{total}} \approx 0.190620 \implies ER_2(S_2) = 0.0$。
  - 设其 12M 动量 $b_2 = 0.10$。
  - $F_{1,2} = 0.10 \times 0.0 = 0.00$。
- 资产 3 ($S_3$)：$P = [100.0, 100.0, 100.0]$，$L=2$。
  - 平价无波动：$\Lambda_{\text{total}} = 0.0 \implies ER_2(S_3) = 0.0$ (`flat_path=True`)。
  - 设其 12M 动量 $b_3 = -0.05$。
  - $F_{1,3} = -0.05 \times 0.0 = 0.00$。

### 4.2 截面标准化手算
- **基准动量 $b = [0.20, 0.10, -0.05]$**：
  - $\mu = (0.20 + 0.10 - 0.05) / 3 = 0.0833333333$。
  - $\sigma = \sqrt{((0.20-0.08333)^2 + (0.10-0.08333)^2 + (-0.05-0.08333)^2)/3} \approx 0.1027402$。
  - 均在 $\pm 3\sigma$ 内，无截断。
  - $A_1 = (0.20 - 0.083333) / 0.1027402 \approx 1.135549$。
  - $A_2 = (0.10 - 0.083333) / 0.1027402 \approx 0.162221$。
  - $A_3 = (-0.05 - 0.083333) / 0.1027402 \approx -1.297771$。
- **新因子 $F_1 = [0.20, 0.00, 0.00]$**：
  - $\mu = 0.20 / 3 = 0.0666666667$。
  - $\sigma = \sqrt{((0.20-0.06667)^2 + 2 \times (0-0.06667)^2)/3} = 0.20 \times \sqrt{2/9} \approx 0.0942809$。
  - $B_1 = (0.20 - 0.066667) / 0.0942809 \approx \sqrt{2} \approx 1.414214$。
  - $B_2 = (0.00 - 0.066667) / 0.0942809 \approx -1/\sqrt{2} \approx -0.707107$。
  - $B_3 = (0.00 - 0.066667) / 0.0942809 \approx -1/\sqrt{2} \approx -0.707107$。
- **等权合成 $C_{\text{raw}} = 0.5 A + 0.5 B$**：
  - $C_{\text{raw}, 1} = 0.5 \times (1.135549 + 1.414214) \approx 1.274881$。
  - $C_{\text{raw}, 2} = 0.5 \times (0.162221 - 0.707107) \approx -0.272443$。
  - $C_{\text{raw}, 3} = 0.5 \times (-1.297771 - 0.707107) \approx -1.002439$。
  - 对 $C_{\text{raw}}$ 进行标准化得到 $C$（均值 0，方差 1）。

该基准算例作为固定数值测试固化在 `tests/test_project3_factors.py` 中。
