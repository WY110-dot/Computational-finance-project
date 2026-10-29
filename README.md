# Computational Finance | CF2026

## Project 2 最终整合提交版

**小组：杨皓博、袁思扬、缪梓航** · 更新日期：2026-10-29

时间序列动量在 ETF 替代样本中的复现：统一两个资产池，检验资产结构、交易约束与多期限信号的影响。

- **[下载最终提交 ZIP](https://github.com/WY110-dot/Computational-finance-project/raw/refs/heads/main/CF2026_Project2_Final.zip)**（约 20.8 MB）
- **[阅读 12 页中文报告](Project2_Final/outputs/report/Project2_Final_Report.pdf)**
- **[查看完整源码与运行说明](Project2_Final/README.md)**
- [查看测试与独立重跑证据](Project2_Final/outputs/verification.json)
- [演示顺序与答辩准备](Project2_Final/DEMO.md)
- [团队贡献和 AI 辅助披露](Project2_Final/docs/CONTRIBUTIONS.md)
- [ZIP SHA-256](CF2026_Project2_Final.sha256.txt)

### 已完成的核验

64 项测试全部通过，0 项跳过；8 套执行账本审计通过；独立输出目录重跑比较 104 张结果与明细表，数值最大绝对偏差为 0。ZIP 已通过完整性、逐文件哈希检查及解压后测试。

本研究实现了原文 12 个月回看、1 个月持有的核心方法；ETF 替代样本未稳定重现相对同风险预算被动多头的优势。多期限设计的负结果、融资敏感性与统计不确定性均保留在报告中。

### 运行

```powershell
cd Project2_Final
uv sync --locked
uv run --locked python run_final.py
uv run --locked python verify_final.py --rerun
```

首次安装依赖需要网络；后续研究使用随包固定快照离线运行，不需要 API Token。完整依赖、数据来源和指标定义见提交版 README 与 docs。

### 历史版本

正式提交以 `Project2_Final/` 与上述 ZIP 为准。原有 `project1/`、`project12/`、`project2/`、`final_project/` 以及 `ysy_proj2` 分支保留用于贡献追溯；它们不代表当前整合提交入口。
