from pathlib import Path

content = Path("docs/AI_ASSISTANCE.md").read_text(encoding="utf-8")

v3_section = '''
---

## 5. 第二轮独立复核意见及工程修复闭环 (v2 $\\to$ v3 Repair Log)

- **复核输入**：第二轮候选包提交后，经 ChatGPT 深入复核（`Project3 v2 复核结论与 v3 修复执行指令`）查出以下遗留与深层工程漏洞：
  1. **干净重跑空目录报错**：`run_project3.py` 缺少 `--freeze-manifest` 参数，在全新空输出目录直接运行时找不到冻结文件；
  2. **验收表字段与源码不一致**：R01 与 R02 因键名不对（`baseline_tests` vs `tests`，`baseline_zip_sha256_match`）被判为 FAIL；
  3. **验证器深度防伪漏检**：
     - `report_trace.csv` 仅检查了 `source_file` 存在，未校验 `raw_value` 与底层产物过滤单元值是否一致；
     - `reconciliation.csv` 仅检查了布尔列，篡改费用至 10 亿只要保留布尔值仍能漏检；
     - `check_p5_quarantine` 限制了 `nrows=50000` 且用 `except Exception: continue` 静默吞掉异常；
  4. **A0 偏离 P2 原规则**：在 6 资产（3 正 3 负）算例中，v2 错误地重归一化至 99%，而 P2 原始规则是将负信号预算留存现金（总仓位严格为 49.5%）；
  5. **报告生成与绘图丢期**：`factor_ic_series.csv` 缺少 `universe` 列导致绘图报 KeyError；CN21 柱状图因过滤条件遗漏了 9 个有效月份；
  6. **PDF 报告格式与严谨性**：ReportLab Paragraph 无法渲染原生 LaTeX 数学符号（需转为规范 Unicode/HTML）、ER 公式需写为对数价格定义、动态提取每日截面相关系数均值、明确教学零滑点假设与复利连乘定义；
  7. **日度风险跨越终局边界**：`execute_broker_simulation` 日账本计算最大回撤时包含了期末退出日收盘暴跌，应严格终止于 $T_{K+1}^-$ 开盘前净值；
  8. **阶段数据视图与覆盖率**：因子与相关性计算严格限制于阶段视图 $t \\le \\text{split\\_end}$，`coverage.csv` 补充 warmup 与 evaluate 分期及因子覆盖。

- **修复与采纳行动（v3 闭环）**：
  1. **参数化冻结文件与自闭环**：`run_project3.py` 增加 `--freeze-manifest` 参数，支持自动从 outputs 继承并持久化至全新目标目录；
  2. **统一验收键名与真实验证**：`verify_project3.py` 统一支持 `tests` / `baseline_tests` 与 `zip_sha256` 直接哈希核验，确保 R01 和 R02 真实输出 PASS；
  3. **全域深度防伪与负面注入测试**：彻底重构 `check_report_trace`（逐行底层值比对）、`check_reconciliation`（重算 fills/ledger/monthly 费用与连乘复利）、`check_p5_quarantine`（分块全量遍历无行数限制，严查损坏日期格式），并编写 7 项针对性负面注入单元测试；
  4. **严格对齐 P2 A0 资金逻辑**：`project3_pipeline.py` 恢复 P2 原始 A0 逻辑（负信号预算留在现金不重归一化），并通过 6 资产等权重测试验证总仓位 49.5%；
  5. **字段补齐与全样本绘图**：`run_project3.py` 补充 `universe` 与 `split` 列，绘图代码绘制全量 23 期 CN21 Rank IC；
  6. **规范 PDF 排版与真实学术披露**：`project3_report.py` 修复 ReportLab 标签、对数价格 ER 公式、动态提取相关系数均值、明确零滑点与净值比说明；
  7. **日度风险严格开盘截断**：`execute_broker_simulation` 严格截断至 $T_{K+1}^-$ 开盘前净值；
  8. **数据视图隔离与阶段标记**：全流程阶段限制视图与 `coverage.csv` 分期字段齐备；R20 稳健保持 `PENDING_HUMAN_REVIEW` 等待人类签字。
'''

content += v3_section
Path("docs/AI_ASSISTANCE.md").write_text(content, encoding="utf-8")
print("Updated docs/AI_ASSISTANCE.md successfully!")
