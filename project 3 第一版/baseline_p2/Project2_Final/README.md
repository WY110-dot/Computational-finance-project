# CF2026 Project 2 | 时间序列动量：ETF 方法复现与受控扩展

**小组：杨皓博、袁思扬、缪梓航**。整合提交版，2026-10-29。

先阅读 `outputs/report/Project2_Final_Report.pdf`。这是原论文核心方法在两个 ETF 替代样本上的复现与边界检验，不是原始 58 个全球期货的数值重建。

## 快速运行

建议 Python 3.11（本次验收 3.11.9）。在解压后的本目录运行：

```powershell
uv sync --locked
uv run --locked python run_final.py
uv run --locked python verify_final.py --rerun
```

不使用 uv 时：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements.lock
.venv/Scripts/python.exe run_final.py
.venv/Scripts/python.exe verify_final.py --rerun
```

macOS/Linux 将 `.venv/Scripts/python.exe` 换为 `.venv/bin/python`。首次安装依赖需要网络，实验与报告生成使用本地固定快照，不访问外部数据服务，不需要 Tushare Token。若 uv 缓存目录权限受限，可将 `UV_CACHE_DIR` 设为本地可写目录。PDF 在 Windows 尝试嵌入微软雅黑，其他平台回退到 ReportLab 中文字体；数值输出应一致，分页可能不同。

`run_final.py` 为唯一正式入口，启动后自动定位项目根目录。`--out <目录>` 支持独立输出；`--no-report` 用于数值复验；`--analysis-only` 仅供已有同版本执行结果上的开发重建，正式复现不要使用。

## 交付索引

| 内容 | 路径 |
|---|---|
| 最终中文报告 / 同源 Markdown | `outputs/report/` |
| 统一两资产池、共同区间与风险对齐 | `outputs/integration/unified_summary.csv` |
| 配对 bootstrap 全部 3/6/12 月块长 | `outputs/integration/paired_bootstrap.csv` |
| 理论到执行逐步桥接 | `outputs/integration/bridge_summary.csv` |
| 修正预测回归 / alpha | `outputs/integration/predictive_regressions.csv`, `benchmark_alpha.csv` |
| 原始研究结果 / 贡献与移除归因 | `outputs/research/`, `outputs/experiments/` |
| 日频现金 / 持仓 / 订单 / 成交与审计 | `outputs/backtests/` |
| 真实测试、审计与干净目录重跑 | `outputs/verification.json`, `tests.xml` |
| 数据、代码、配置与环境指纹 | `outputs/run_manifest_final.json` |
| 文件完整性索引 | `FILE_MANIFEST.json` |
| 原论文及目标图 | `references/` |
| 方法、协议、数据与贡献说明 | `docs/` |
| 演示顺序 | `DEMO.md` |

## 研究要点

- 主基线是 12 个月回看、持有 1 个月；3/6/12 月平均是自主扩展。
- CN21：2020-02 至 2026-08，79 月；US9：2000-01 至 2024-12，300 月；共同区间为 2020-02 至 2024-12，59 月。
- ETF 价格收益与期货超额收益不同。AQR 参考因子只用于独立复算，不用于信号或权重。
- 理论多空组合可能使用杠杆；Long/Cash 执行层遵守非负持仓和现金。不能混同其 Sharpe、日/月回撤或风险预算。
- 本研究是回顾性分析，未声称预注册或完全未见样本外。保留多期限扩展的负结果，不按最高历史收益筛选提交方案。

原始组员目录和远端仓库未被覆盖。完整历史可追溯至仓库 main `294ca84` 与 ysy_proj2 `163e50a`。本包的旧 P1 功能源码保留用于复用与测试，正式研究仅以本 README、`run_final.py` 和最终报告为准。
