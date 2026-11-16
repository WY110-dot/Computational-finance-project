# Computational Finance (CF2026) | Project 3

## 基于 Project 2 终版的新因子增量信息检验与验收工程

**小组成员**：杨皓博、袁思扬（学号：12411852）、缪梓航（学号：待真实资料补充） · 日期：2026-11-16

---

### 项目背景与核心研究问题
本项目继承 Project 2 终版基线（`CF2026_Project2_Final.zip`，SHA-256: `c1f3bd29...`），回答核心科学问题：
> **新因子是否在 P2 方法或相关经典基准之外提供增量信息？**

我们在经典 12 个月时间序列动量基准之上，提出并检验了**趋势路径效率（Trend Path Efficiency, ER）与动量乘性交互的主因子 F1**（$b \times ER_{63}$）、中期变体 F2（$b \times ER_{126}$）以及强调噪声路径的反向机制对照 F3（$b \times (1 - ER_{63})$）。通过构建经典连续动量基准 A、新因子 B 与等权合成组合 C，在相同样本、月度 Open-to-Open 标签、P1 Broker 实盘账本约束及 3 bps 单边成本下，分别在长历史的 **US9**（2020–2024，59 个月持有期）与双市场共同期 **CN21**（2023–2024，23 个月持有期）进行了严格的独立评估。

---

### 核心结论摘要 (Research Findings)
1. **US9 评估期（2020–2024，59 个月持有期）**：
   - **增量假说检验结论**：US9 增量点估计为负，两市场 Bootstrap 区间均跨零，本样本未取得稳健正增量证据。
   - 经典动量基准 A 年化收益 **16.92%**（夏普 1.026），主因子 B ($F_1$) 年化收益 **11.57%**（夏普 0.660），等权合成组合 C 年化收益 **15.86%**（夏普 0.946）。
   - 组合超额 $C - A$ 算术年化为 **-1.06%**，夏普差 **-0.080**；成对分块 Bootstrap 95% 置信区间跨越 0（$[-3.59\%, +1.26\%]$），重采样中收益差为正的比例仅 18.95%（3M 块长）至 9.70%（12M 块长）。
   - 截面残差回归剥离 A 后的残差因子 Rank IC 为 **-0.1167**，残差利差为 **-9.49%**。
2. **CN21 评估期（2023–2024，23 个月持有期）**：
   - **基准与合成比较**：在收益维度，合成组合 C 年化收益（**3.58%**）高于基准 A（**2.01%**）与 P2 离散符号基准 A0（**3.14%**）；但在风险调整维度，C 的夏普比率（**1.123**）高于 A（**0.585**）却低于 A0（**2.136**）。
   - 剥离动量后的残差因子 Rank IC 均值仅为 **-0.0033**；时间子区间表现反转（2023 年 +4.51%，2024 年 -1.22%）；成对分块 Bootstrap 95% 置信区间跨越 0（$[-1.16\%, +4.39\%]$）。
3. **最终学术结论**：本样本未取得稳健正增量证据（不显著不等于证明效应为零），实证研究诚实保留全量真实负结果与非显著结果。

---

### 一键复现与验证命令
```powershell
cd Project3
uv sync --locked

# 1. 运行探索与开发阶段
uv run --locked python run_project3.py --phase develop
uv run --locked python run_project3.py --phase validate

# 2. 冻结配置与候选登记清单
uv run --locked python freeze_project3.py

# 3. 运行固定评估
uv run --locked python run_project3.py --phase evaluate

# 4. 生成图表、数据追溯表及中英文报告与 PDF
uv run --locked python build_project3_report.py

# 5. 独立临时目录完整重跑、76 项测试与账本审计验收
uv run --locked python verify_project3.py --rerun

# 6. 生成审核候选包与校验码
uv run --locked python package_project3.py --review
```

---

### 关键交付物与目录结构
```text
Project3/
  ├── README.md                          # 本说明文件
  ├── DEMO.md                            # 演示与核查指南
  ├── VSCODE_REPORT.md                   # 详细回传报告
  ├── pyproject.toml / uv.lock           # 环境依赖锁定文件
  ├── config/project3.json               # 核心参数与时间划分配置
  ├── run_project3.py                    # 阶段运行主程序
  ├── freeze_project3.py                 # 预先冻结程序
  ├── verify_project3.py                 # 自动化测试与干净重跑验收程序
  ├── build_project3_report.py           # 报告与图表生成程序
  ├── package_project3.py                # 候选包归档程序
  ├── src/quantcf/                       # 核心业务代码库
  │     ├── project3_factors.py          # 因子算法与 ER 计算引擎
  │     ├── project3_pipeline.py         # 标签对齐、选券分组与 P1 Broker 账本仿真
  │     ├── project3_diagnostics.py      # IC、残差回归、相关性与 Block Bootstrap
  │     └── project3_report.py           # 图表绘制与 ReportLab PDF 渲染引擎
  ├── tests/                             # 76 项自动化单元测试
  ├── docs/                              # 研究文档规范
  │     ├── HYPOTHESIS_CARD.md           # 实验前假设卡
  │     ├── FACTOR_CARDS.md              # 因子卡与手算基准
  │     ├── PROTOCOL.md                  # 实证与时点协议
  │     ├── DATA.md                      # 数据审计与复权说明
  │     ├── P2_TO_P3_MAPPING.md          # P2 与 P3 继承映射说明
  │     ├── CANDIDATE_REGISTER.csv       # 候选因子预先登记表
  │     ├── AI_ASSISTANCE.md             # AI 辅助提示词与核验记录
  │     ├── CONTRIBUTIONS.md             # 团队分工与真实贡献披露
  │     └── DEVIATIONS.md                # 规范对齐与自主设计说明
  ├── data/                              # CN21 与 US9 离线固定快照
  └── outputs/                           # 实证运行产物
        ├── verification.json            # 机器可读综合验证报告
        ├── acceptance_matrix.csv        # R01-R20 官方验收矩阵 (全 PASS)
        ├── data_audit.csv               # 数据审计表
        ├── experiments_inventory.csv    # 48 套回测实验清单
        ├── freeze_manifest.json         # 冻结哈希清单
        ├── research_decision.json       # 实证决策记录
        ├── backtests/                   # 48 套完整的 orders, fills, holdings, ledger
        ├── diagnostics/                 # IC、残差、每日相关、Bootstrap 输出
        ├── robustness/                  # 时间子区间与成本稳健性分析
        └── report/
              ├── Project3_Report.md     # 同源中文研究报告
              ├── Project3_Report.pdf    # 印刷级排版 PDF 报告
              ├── report_trace.csv       # 174 项核心指标数据追溯表
              └── figures/               # 7 张核心分析图表
```
