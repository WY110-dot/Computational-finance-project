import re
import os

def fix_readme():
    path = "README.md"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Replace badges and counts
    content = content.replace("25 passed", "26 passed")
    content = content.replace("1387 个交易日", "1,873 个交易日")
    content = content.replace("28,201 条日线行情", "38,407 条记录")
    content = content.replace("28201", "38407") # Just in case it's written differently
    content = content.replace("1387", "1873")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def fix_methodology():
    path = "docs/methodology.md"
    if os.path.exists(path):
        new_content = """# Methodology

## 1. 资产池 (Universe)
本项目选取 21 只 A 股核心高流动性 ETF，涵盖大盘宽基（50/300/500）、行业主题（芯片/医药/新能源）、海外（互联/纳指）以及国债 ETF。这种多资产设定能够保证策略在不同市场环境下的横截面选择空间。

## 2. 因子定义 (Factors)
项目构建并诊断了三大核心因子：
1. **MOM20** (20 日动量)：反映资产近期的价格趋势。
2. **REV5** (5 日反转)：捕捉资产的短期均值回归效应。
3. **LOWVOL20** (20 日低波动)：基于低波动率异象，预期低波动资产拥有更高的风险调整后收益。

## 3. 组合构建 (Portfolio Construction)
不再是单资产的择时，而是纯粹的多资产横截面组合：
- **目标权重**：在每个调仓日（形成日），在剔除缺失/停牌资产后，选取因子得分最高的 Top 5 资产。
- **等权重分配**：入选的 5 只资产采用等权重（Equal Weight）分配，每只占比约 20%。
- **调仓频率**：基准为月度调仓（Monthly Rebalance），实验组为周度调仓（Weekly Rebalance）。

## 4. 回测与交易摩擦 (Backtest & Friction)
引入了真实的交易摩擦模型：
- **买入费率**：0.03%
- **卖出费率**：0.03%
- **缺失值策略**：遇到资产停牌或数据缺失时禁止交易该资产，并沿用其上一有效价格进行组合估值。
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

def fix_assumptions():
    path = "docs/assumptions.md"
    if os.path.exists(path):
        new_content = """# Data & Assumptions

## 1. 数据对齐与缺失值假设 (Data Alignment & Missing Values)
- 所有数据基于交易日历进行面板对齐 (Date x Asset Panel)。
- 如果某资产在交易日无报价（如停牌或未上市），回测时使用上一交易日的有效价格进行估值（Forward Fill）。
- 缺失标签（如无未来收益）的资产将被剔除出形成日的横截面排序，但不影响历史已经持仓的估值。

## 2. 交易假设 (Trading Assumptions)
- **Top 5 多资产等权组合**：每次调仓选取因子值最高的 5 只资产，按 20% 的等权重分配资金。
- **交易费率**：买入 0.03%，卖出 0.03%。
- **无做空机制**：A 股 ETF 默认只进行多头操作，禁止做空，权重不得为负。
- **不考虑滑点**：暂不考虑市场冲击成本。
- **无未来函数**：交易发生日（T 日）的调仓目标只依赖 T-1 日及之前的数据，以 T 日的收盘价成交。

## 3. 资金与账本恒等式 (Ledger Identity)
- 初始资金：1,000,000 RMB。
- 现金和资产总值在扣除双边交易费用后，严格遵守会计账本恒等式：`Equity_t = Cash_t + HoldingsValue_t`。
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

def fix_audit_report():
    path = "outputs/reports/final_acceptance_audit_report.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace outdated numbers
        content = re.sub(r"99\.6%[-\~]99\.9%", "97.35%-97.59%", content)
        content = re.sub(r"5 assets [x×] 60 days", "4 只资产 × 60 天", content)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def fix_data_quality_report():
    path = "outputs/quality/data_quality_report.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace 100% coverage with explicit definitions
        old_cov_str = "- **Coverage**: 100.00%"
        new_cov_str = "- **observed-row field completeness**: 100.00%\n- **date × asset panel coverage**: ≈ 97.65%"
        content = content.replace(old_cov_str, new_cov_str)
        # Handle variations
        content = content.replace("coverage: 100%", "observed-row field completeness: 100%, date x asset panel coverage ≈ 97.65%")
        
        # Alternatively, aggressively find and replace
        if "100.00%" in content and "observed-row" not in content:
            content = content.replace("100.00%", "100.00% (observed-row field completeness), date x asset panel coverage ≈ 97.65%")
            
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

def create_pytest_ini():
    content = "[pytest]\ntestpaths = tests\n"
    with open("pytest.ini", "w", encoding="utf-8") as f:
        f.write(content)

def update_requirements():
    path = "requirements.txt"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "scipy" not in content.lower():
            with open(path, "a", encoding="utf-8") as f:
                f.write("\nscipy\n")

if __name__ == "__main__":
    fix_readme()
    fix_methodology()
    fix_assumptions()
    fix_audit_report()
    fix_data_quality_report()
    create_pytest_ini()
    update_requirements()
    print("Round 2 Document fixes completed.")

