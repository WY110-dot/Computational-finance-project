# CF2026 Project 1 - 最终版量化投研框架

这是一个以 Tushare 日频 ETF 数据为基础、强调正确性与复现性的课程项目。系统覆盖：不可变数据快照、复权与质量检查、三个因子、Alphalens 风格诊断、目标组合、下一开盘成交、现金与持仓账本、交易成本、流动性约束、受控实验、运行记录和自动报告。

设计优先级：

> 正确性 > 可复现性 > 可解释性 > 可扩展性 > 表面复杂度

## 设计来源

- 从 `project1` 吸收：Tushare 数据、原始价/复权因子分离、模块化目录、因子注册器。
- 从 `project2` 吸收：下一开盘成交、严格现金账本、实际成交计费、部分成交、独立毛收益重跑、锁定依赖、自动验证与报告。
- 借鉴 Alphalens：标准因子表、前向收益、IC/Rank IC、分组收益、因子换手。
- 借鉴 Qlib：数据、信号、策略、执行、分析、Recorder 松耦合，配置驱动实验。
- 借鉴 Backtrader：Strategy/Broker/Analyzer 分离，订单、成交和费用进入独立执行层。

本项目没有复制上述仓库源码，也不要求安装这三套大型框架。

## 快速开始

需要 Python 3.11+ 和 `uv`：

```powershell
uv sync --locked
uv run --locked python -m pytest
uv run --locked python run.py --config config/default.json --out outputs
uv run --locked python verify.py --config config/default.json --out outputs --rerun
uv run --locked python build_report.py --out outputs
```

默认运行使用随项目保存的 Tushare 原始快照，不需要联网或 Token。顶层启动脚本特意避免 Windows 中文路径下 editable install 的兼容问题；不要把 `src` 目录手工复制到环境中。

## 刷新 Tushare 数据

把 `.env.example` 复制为 `.env`，在本机填写：

```ini
TUSHARE_TOKEN=your_token_here
```

然后执行：

```powershell
uv run --locked python download_data.py --config config/default.json --snapshot-dir data/raw_YYYYMMDD
```

这里需要的是 Tushare API Token，不是账号 ID。Token 不会被打印，也不应提交到版本控制。下载器默认拒绝静默覆盖既有快照；需要更新时应创建新快照并记录哈希。

## 主要研究约定

- 形成日收盘后计算因子，下一交易日开盘执行目标权重。
- 主策略为 MOM20、Top 5 等权、月度调仓。
- 对照实验只将月度调仓改为周度调仓。
- 相同资产池月度等权组合作为基准。
- 买卖费用按实际成交额扣除；未成交不收费。
- 缺失开盘价不可交易，不能用向前填充价格伪造成交。
- 毛收益由相同成交规则的零费率回测独立重跑。
- 五日重叠标签只用于因子诊断，不连续复利为策略净值。

完整预设见 `RESEARCH_PROTOCOL.md`。

## 输出

一次完整运行将产生：

```text
outputs/
├── data/             # 清洗面板与可分享样本
├── factors/          # 因子长表和前向标签
├── diagnostics/      # IC、Rank IC、分组、覆盖率与换手
├── backtests/        # 每个方案的净/毛账本、订单、成交和持仓
├── figures/          # 报告图表
├── runs/             # Qlib 风格的每次实验记录与文件哈希
├── strategy_summary.csv
├── run_manifest.json
└── verification.json # 数据哈希、独立账本审计和重复运行结果

output/pdf/
└── CF2026_Project1_Final_Report.pdf
```

最终 PDF 默认位于 `output/pdf/CF2026_Project1_Final_Report.pdf`。`outputs` 中的所有绩效数字均由流水线生成，PDF 不保存手填示例数字。

## 当前固定快照的验收状态

- 21 只 ETF，2019-01-02 至 2026-09-18，共 38,407 条清洗记录。
- 6 个净值方案及各自的独立零费率重跑，共 12 套账本审计全部通过。
- 信号日/成交日、缺失开盘、容量上限和拒单收费违规均为 0。
- 完整流水线临时目录重跑与正式输出逐项一致。
- `pytest` 共 40 项测试通过；最终数字以 `outputs/verification.json` 和报告为准。

## 安全与解释边界

该项目是课程研究，不构成投资建议。固定 ETF 名单不等同于无幸存者偏差的历史全市场；交易费用、开盘成交和流动性参与率均为明确披露的研究假设。已经查看过的历史结果不会被描述为完全未见样本外结果。

## AI 与学术诚信

AI 参与了需求拆解、代码与测试草拟、错误排查、文档组织和报告排版；数据不是由 AI 生成，实证数字来自固定快照和可运行代码。详细边界见 `AI_ASSISTANCE.md`。提交者必须亲自复跑、理解并按课程最新规则披露，不能把自动验证冒充个人已经完成的审查。
