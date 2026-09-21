"""
Unit Tests for Phase P1, B1, M1 (Sections 25-28)
"""
import pytest
import pandas as pd
import numpy as np
from src.portfolio.target_portfolio import TargetPortfolioGenerator
from src.backtest.portfolio_engine import PortfolioBacktestEngine
from src.metrics.portfolio_metrics import PortfolioPerformanceMetrics

def test_target_portfolio_generator_no_lookahead():
    """测试组合生成器：Top N 筛选、等权分配与严格 t->t+1 生效日对齐"""
    dates = ['20240102', '20240103', '20240131', '20240201']
    assets = ['A', 'B', 'C', 'D', 'E', 'F']
    
    factor_records = []
    # 20240131 是月末调仓信号日
    scores = {'A': 0.9, 'B': 0.8, 'C': 0.7, 'D': 0.6, 'E': 0.5, 'F': 0.1}
    for a in assets:
        factor_records.append({
            'date': '20240131',
            'asset': a,
            'factor': 'MOM20',
            'value': scores[a],
            'is_valid': True
        })
        
    factor_df = pd.DataFrame(factor_records)
    gen = TargetPortfolioGenerator(holding_count=3, rebalance_frequency='M')
    weights_df = gen.generate_target_weights(factor_df, factor_name='MOM20', universe_dates=dates)
    
    # 验证筛选出的 Top 3 为 A, B, C
    assert not weights_df.empty
    selected_assets = set(weights_df['asset'].tolist())
    assert selected_assets == {'A', 'B', 'C'}
    
    # 验证等权 1/3
    for w in weights_df['target_weight']:
        assert np.isclose(w, 1.0 / 3.0)
        
    # 验证无前视偏差：20240131 生成的信号，生效日在 20240201
    assert weights_df['signal_date'].iloc[0] == '20240131'
    assert weights_df['effective_date'].iloc[0] == '20240201'

def test_portfolio_engine_accounting_identity_and_fees():
    """测试组合回测引擎：全流程资金恒等式与手续费扣减精确性"""
    # 构造极简的2只资产、3个交易日场景
    dates = ['20240102', '20240103', '20240104']
    prices_data = [
        # Date 1: 现金未买入
        {'date': '20240102', 'asset': 'A', 'close_adj': 10.0},
        {'date': '20240102', 'asset': 'B', 'close_adj': 20.0},
        # Date 2: 调仓执行日，买入 A 和 B 各 50%
        {'date': '20240103', 'asset': 'A', 'close_adj': 10.0},
        {'date': '20240103', 'asset': 'B', 'close_adj': 20.0},
        # Date 3: 持仓持有日，价格上涨
        {'date': '20240104', 'asset': 'A', 'close_adj': 11.0},
        {'date': '20240104', 'asset': 'B', 'close_adj': 22.0},
    ]
    prices_df = pd.DataFrame(prices_data)
    
    # Target weights effective on 20240103
    weights_df = pd.DataFrame([
        {'signal_date': '20240102', 'effective_date': '20240103', 'asset': 'A', 'target_weight': 0.5},
        {'signal_date': '20240102', 'effective_date': '20240103', 'asset': 'B', 'target_weight': 0.5},
    ])
    
    config = {
        'initial_cash': 100000.0,
        'buy_fee_rate': 0.001, # 10 bps
        'sell_fee_rate': 0.001,
        'benchmark_asset': 'A'
    }
    
    engine = PortfolioBacktestEngine(config)
    ledger, holdings = engine.run_backtest(prices_df, weights_df)
    
    # 1. 恒等式核验: Equity == Cash + Holdings Value 在每一天都必须成立
    for _, row in ledger.iterrows():
        assert np.isclose(row['equity'], row['cash'] + row['holdings_value'], atol=1e-4)
        
    # 2. 手续费扣减核验
    day2 = ledger[ledger['date'] == '20240103'].iloc[0]
    # 买入名义本金总和
    expected_fee = day2['turnover'] * 0.001
    assert np.isclose(day2['daily_cost'], expected_fee, atol=1e-4)
    # 净值在调仓日因手续费而略低于初始 100000
    assert day2['equity'] < 100000.0
    
    # 3. 绩效指标核验
    pm = PortfolioPerformanceMetrics()
    metrics = pm.calculate_metrics(ledger)
    assert metrics['Gross Cumulative Return (%)'] > metrics['Net Cumulative Return (%)']
    assert metrics['Total Trade Count'] == 2

