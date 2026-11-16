# CF2026 Project 3 演示与验收顺序 (Demo & Verification Guide)

- **编制日期**：2026-11-16
- **供复核人员（ChatGPT 或 助教/老师）快速重现与审计**

---

## 1. 快速检查 (Quick Inspection)

若仅需快速查验关键结果与验收证据，无需重跑回测，可直接查阅：
1. **研究报告**：
   - PDF 版本：`Project3/outputs/report/Project3_Report.pdf`（或工作区根目录下的 `Project3_Report.pdf`）
   - Markdown 版本：`Project3/outputs/report/Project3_Report.md`
2. **验收矩阵与机器可读核验**：
   - 官方验收矩阵：`Project3/outputs/acceptance_matrix.csv`（R01–R20 全 PASS）
   - 机器验证 JSON：`Project3/outputs/verification.json`
3. **数据追溯性表**：
   - `Project3/outputs/report/report_trace.csv`（报告中 174 个关键数字到源文件的精确映射）

---

## 2. 完整复现运行 (Full Replication Walkthrough)

### 步骤 1：同步依赖环境
```powershell
cd Project3
uv sync --locked
```
*预计耗时：< 5 秒。*

### 步骤 2：查看预置文档与数据审计
```powershell
uv run --locked python run_project3.py --phase develop
uv run --locked python run_project3.py --phase validate
```
*验证开发期与验证期数据无误，生成 `outputs/data_audit.csv`。*

### 步骤 3：核验冻结清单
```powershell
uv run --locked python freeze_project3.py
```
*计算 12 个预置文件的 SHA-256，生成 `outputs/freeze_manifest.json`。*

### 步骤 4：运行正式评估
```powershell
uv run --locked python run_project3.py --phase evaluate
```
*运行 US9 与 CN21 上的 48 组 Broker 仿真回测、因子 IC、残差回归、日频相关性与 2,000 次 Block Bootstrap。*

### 步骤 5：渲染图表与报告
```powershell
uv run --locked python build_project3_report.py
```
*绘制 7 张图表，生成 Markdown 报告与双页 ReportLab PDF。*

### 步骤 6：一键全套验收与独立目录重跑比对
```powershell
uv run --locked python verify_project3.py --rerun
```
*自动运行 76 项测试，审查 48 套回测账本，在系统临时目录全新独立重跑，比对 289 张表（数值误差严格为 0.0），输出 `outputs/verification.json` 与 `outputs/acceptance_matrix.csv`。*

### 步骤 7：候选包归档与校验
```powershell
uv run --locked python package_project3.py --review
```
*打包 `Project3_Review_Bundle.zip` 并输出 SHA-256 校验和。*
