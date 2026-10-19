# 提交前核对

| 课程要求 | 对应成果 |
|---|---|
| 数据来源、固定版本、哈希与字段口径 | data/source_manifest.json、data/DATA_DICTIONARY.md、FILE_MANIFEST.json |
| 数据质量检查 | src/data.py、outputs/quality_report.json |
| 三个不同因子、统一接口与因子卡 | src/factors.py、报告第3页、outputs/factors.csv |
| 无未来信息的信号和成交顺序 | src/backtest.py、tests/test_research.py |
| 实际成交计费、现金与持仓账本 | outputs/*_daily.csv、*_trades.csv、*_holdings.csv |
| IC、Rank IC、形成日分组 | outputs/factor_summary.csv 及因子诊断明细 |
| 收益、波动、Sharpe、回撤与双边换手 | outputs/strategy_summary.csv |
| 单变量对照、事先预期、负结果 | RESEARCH_PROTOCOL.md、报告第7页 |
| 自主扩展及退化检验 | 流动性预算与部分成交；测试包含无限容量退化 |
| 可复现代码、配置、锁定依赖 | README.md、config.json、pyproject.toml、uv.lock |
| 验证与复现 | verify.py、outputs/verification.json、outputs/test_log.txt |
| 6—10页报告 | output/pdf/CF2026_Project1_Report.pdf，共8页 |
| 演示与问答 | DEMO.md |

提交者需要理解并能解释代码、复跑结果，按课程实际要求补充个人信息并披露AI辅助；本包不虚构个人身份或人工完成声明。数据快照的复权口径与容量代理限制见数据字典及报告。
