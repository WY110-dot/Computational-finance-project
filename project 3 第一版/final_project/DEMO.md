# 演示提纲

1. 用一张架构图说明数据、因子、目标组合、成交与分析的边界。
2. 展示原始 Tushare 快照、固定参考日复权及数据质量报告。
3. 手算一个动量值和一个下一开盘前向标签，证明时间顺序。
4. 展示三个因子的 IC、Rank IC、分组收益和因子换手。
5. 展示一笔调仓的 signal date、execution date、成交额、费用和现金变化。
6. 展示月度与周度控制实验，强调只改变调仓频率。
7. 展示流动性限制导致的部分成交，以及未成交不收费。
8. 运行验证命令，展示账本误差、哈希和重复运行差异。
9. 说明固定资产池、费用模型、样本已见和统计显著性等局限。

推荐现场命令：

```powershell
uv run --locked python verify.py --out outputs --rerun
```

推荐依次打开 `outputs/verification.json`、`outputs/backtests/momentum_monthly/net/orders.csv`、`outputs/strategy_summary.csv` 和 `output/pdf/CF2026_Project1_Final_Report.pdf`。
