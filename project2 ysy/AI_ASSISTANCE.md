# AI 辅助使用情况披露 (AI Assistance Disclosure)

**项目名称**: Computational Finance (CF2026) Project 1 & Project 2  
**作者/学生**: 袁思扬 (学号: 12411852)  
**辅助工具**: 
- **ChatGPT**: 用于前期研究方案构思、论文研究协议解读及外部代码复核意见的整理与排查。
- **Google DeepMind Antigravity (Gemini 3.8 Flash High)**: 用于脚手架代码生成、全流程管线编排、PyMuPDF 裁切集成、Matplotlib 图表排版及 ReportLab PDF 编译。
- **VSCode + Codex / Copilot**: 用于本地开发环境下的代码补全、函数签名对齐、Docstring 维护及测试用例调试。
**更新日期**: 2026-10-22  

---

## 1. Project 2 阶段 AI 使用具体说明

在 Project 2 开发与复核过程中，AI 辅助工具具体用于以下环节：
1. **前期方案与复核讨论 (ChatGPT)**:
   - 梳理 Moskowitz, Ooi & Pedersen (2012) 原论文的核心图表（Fig. 2 上部、Fig. 3）与公式映射。
   - 协助分析代码复核中关于执行区间截断、时序资格解耦、滚动方差估计器与回撤高水位的数学边界反例。
2. **工程架构与代码生成 (Antigravity / Gemini & VSCode + Codex)**:
   - 辅助编写数据提取与自然月末对齐逻辑 (`src/quantcf/tsmom.py`)。
   - 辅助实现 AQR 官方 Excel 数据解析与因子复算 (`src/quantcf/reference_data.py`)。
   - 辅助实现全流程管线编排与 CLI 接口 (`src/quantcf/pipeline_p2.py`, `run_project2.py`, `build_report_project2.py`)。
   - 辅助编写 PyMuPDF 裁切脚本提取原论文 Fig. 2 与 Fig. 3 矢量图。
   - 辅助编写 Matplotlib 出版级图表绘制代码及 ReportLab PDF 跨平台中英文字体排版 (`src/quantcf/report_p2.py`)。
3. **测试用例与手算核验辅助**:
   - 协助将解析手算期望值（如衰减 $\lambda=0.5$ 时的方差 $3/17500$、756 日滚动样本方差反例、`[-10%, +1%]` 回撤高水位反例、`[-10%, -10%]` 负 Calmar 反例）组织为 Pytest 单元测试与真实函数集成测试 (`tests/test_tsmom.py`, `tests/test_portfolio_tsmom.py`)。

---

## 2. 人工学术责任与数据真实性声明

1. **真实数据与实证计算**: 所有回测指标、绩效数字、图表数据均严格由本地 `data/raw/` 快照及 `data/reference/` AQR 官方数据通过 Python 代码独立计算产生。**绝不存在任何由 AI 编造假数据或伪造收益率的行为**。
2. **方法与公式核查**: 论文 Moskowitz et al. (2012) 第 2.4 节公式 (1) 及第 4.1 节公式 (5) 的数学逻辑、符号映射、年化口径（EWMA 波动率 261、月度 12、日度 252）均由作者本人亲自复核并独立推导。
3. **客观保留未达到预期的实验结果**: 实证中发现被动做多（R2）在当前 ETF 样本中的夏普比率高于时序动量（R1），以及宽基股指单独跑动量效果极差（夏普 0.052），均如实完整保留并进行归因分析，绝未通过调参、删改资产强行追求虚假最优。
4. **独立复核承诺**: 本人已实际复核全部代码、测试套件、实证报表及中英文报告，对提交成果的准确性与合规性承担全部学术责任。
5. **代码库隔离保障**: 所有 Project 2 改动均严格局限在 `project2 ysy` 目录内，未改动 `final_project` 原版仓库。
