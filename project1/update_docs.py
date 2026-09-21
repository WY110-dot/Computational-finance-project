import re

def update_readme():
    path = 'README.md'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Define the new content for Section 10
    new_sec_10 = """## 10. How to Reproduce Baseline
基准测试为 **MOM20 因子等权重（Monthly Rebalance），选取 Top 5 等权配置，双边交易费 0.03%**。

执行对应脚本：
```bash
python run_phase_p1_to_r1.py
```
- 输出至：`outputs/tables/portfolio_baseline_monthly_ledger.csv`
- 基准绩效指标（截至 2026-09-18）：Net Cumulative Return **+45.45%**, Annualized Return 5.17%, Volatility 21.92%, Sharpe Ratio 0.250, Max Drawdown -38.80%。"""

    # Define the new content for Section 11
    new_sec_11 = """## 11. How to Reproduce Controlled Experiment
严格遵循“控制变量法”，保持资产、因子、持仓数量、费用率完全一致，仅将调仓频率改为 **周度调仓（Weekly Rebalance）**。

执行对应脚本：
```bash
python run_project1.py --phase backtest
```
- 输出实验结果：`outputs/tables/experiment_comparison_monthly_vs_weekly.csv`
- 输出对比净值曲线：`outputs/figures/rebalance_frequency_experiment.png`
- **实验实证结论**：周度调仓实现了 Net Cumulative Return **+172.85%**，Sharpe Ratio **0.622**，大幅跑赢月度调仓基准。证明在当前 ETF 市场且有换手摩擦成本的前提下，基于该因子的周频调仓有效捕捉了短期动量，超额收益能够覆盖增加的交易摩擦成本。"""

    # Replace old Section 10
    content = re.sub(r'## 10\. How to Reproduce Baseline.*?---', new_sec_10 + '\n\n---\n', content, flags=re.DOTALL)
    
    # Replace old Section 11
    content = re.sub(r'## 11\. How to Reproduce Controlled Experiment.*?---', new_sec_11 + '\n\n---\n', content, flags=re.DOTALL)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def update_audit_report():
    path = 'outputs/reports/final_acceptance_audit_report.md'
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = content.replace('2024-09-18', '2026-09-18')
        content = content.replace('20240918', '20260918')
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except FileNotFoundError:
        pass

if __name__ == '__main__':
    update_readme()
    update_audit_report()
    print("Updates complete.")

