"""
Master Execution Script for Sections 25 to 30:
- Section 25 (Phase P1: Target Portfolio)
- Section 26 (Phase B1: Configurable Backtest)
- Section 27 (Benchmark Integration)
- Section 28 (Phase M1: Performance Metrics)
- Section 29 (Phase E1: Controlled Experiment - Monthly vs Weekly)
- Section 30 (Phase R1: Reproducibility Logging)
"""
import os
import sys
import yaml
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.portfolio.target_portfolio import TargetPortfolioGenerator
from src.backtest.portfolio_engine import PortfolioBacktestEngine
from src.metrics.portfolio_metrics import PortfolioPerformanceMetrics
from src.utils.reproducibility import ReproducibilityLogger

def run_pipeline():
    print("=" * 75)
    print("Executing MA216 Project 1: Portfolio, Backtest, Experiment & Reproducibility")
    print("Sections 25 -> 30")
    print("=" * 75)
    
    # 0. 载入核心数据
    price_path = 'data/processed/prices_daily.parquet'
    factor_path = 'data/processed/factors/core_factors_long.parquet'
    
    if not os.path.exists(price_path) or not os.path.exists(factor_path):
        print("Error: Missing processed data. Please run run_phase_d1.py and run_phase_f1.py first.")
        return
        
    print("\n[Step 0] Loading Panel Prices and Alpha Factors...")
    prices_df = pd.read_parquet(price_path)
    factors_df = pd.read_parquet(factor_path)
    universe_dates = sorted(prices_df['date'].astype(str).unique().tolist())
    print(f"   Loaded {len(prices_df)} price rows, {len(factors_df)} factor rows across {len(universe_dates)} trading days.")
    
    os.makedirs('outputs/tables', exist_ok=True)
    os.makedirs('outputs/figures', exist_ok=True)
    os.makedirs('outputs/manifests', exist_ok=True)
    
    pm = PortfolioPerformanceMetrics(risk_free_rate=0.02)
    
    # =========================================================================
    # 1. Baseline Run (Section 25, 26, 27, 28) - Monthly Rebalancing
    # =========================================================================
    print("\n" + "-" * 60)
    print("[Step 1] Running Baseline (Monthly Rebalancing - Section 26)...")
    baseline_cfg_path = 'config/project1_baseline.yaml'
    with open(baseline_cfg_path, 'r', encoding='utf-8') as f:
        baseline_cfg = yaml.safe_load(f)
        
    start_time_base = datetime.now()
    
    # P1: 生成月度 Top N 目标持仓
    gen_base = TargetPortfolioGenerator(
        holding_count=baseline_cfg['holding_count'],
        rebalance_frequency=baseline_cfg['rebalance_frequency'],
        missing_policy=baseline_cfg['missing_policy']
    )
    weights_base = gen_base.generate_target_weights(
        factor_df=factors_df,
        factor_name=baseline_cfg['factor'],
        universe_dates=universe_dates
    )
    print(f"   Generated {len(weights_base)} target position records across rebalance dates.")
    
    # B1 & Benchmark: 运行组合回测
    engine_base = PortfolioBacktestEngine(baseline_cfg)
    ledger_base, holdings_base = engine_base.run_backtest(prices_df, weights_base)
    
    # M1: 计算绩效指标
    metrics_base = pm.calculate_metrics(ledger_base)
    end_time_base = datetime.now()
    
    # R1: 记录复现日志
    repro_base = ReproducibilityLogger.record_experiment_run(
        run_name="baseline_monthly",
        config=baseline_cfg,
        data_filepath=price_path,
        start_time=start_time_base,
        end_time=end_time_base,
        metrics_summary=metrics_base
    )
    
    # 保存结果
    ledger_base.to_csv('outputs/tables/portfolio_baseline_monthly_ledger.csv', index=False)
    holdings_base.to_csv('outputs/tables/portfolio_baseline_monthly_holdings.csv', index=False)
    pd.DataFrame([metrics_base]).to_csv('outputs/tables/portfolio_baseline_metrics.csv', index=False)
    print("   [OK] Baseline completed and saved.")
    
    # =========================================================================
    # 2. Controlled Experiment (Section 29 - Phase E1) - Weekly Rebalancing
    # =========================================================================
    print("\n" + "-" * 60)
    print("[Step 2] Running Controlled Experiment (Weekly Rebalancing - Section 29)...")
    exp_cfg_path = 'config/project1_experiment_weekly.yaml'
    with open(exp_cfg_path, 'r', encoding='utf-8') as f:
        exp_cfg = yaml.safe_load(f)
        
    start_time_exp = datetime.now()
    
    # P1: 生成周度 Top N 目标持仓
    gen_exp = TargetPortfolioGenerator(
        holding_count=exp_cfg['holding_count'],
        rebalance_frequency=exp_cfg['rebalance_frequency'],
        missing_policy=exp_cfg['missing_policy']
    )
    weights_exp = gen_exp.generate_target_weights(
        factor_df=factors_df,
        factor_name=exp_cfg['factor'],
        universe_dates=universe_dates
    )
    print(f"   Generated {len(weights_exp)} target position records across rebalance dates.")
    
    # B1: 运行周度组合回测
    engine_exp = PortfolioBacktestEngine(exp_cfg)
    ledger_exp, holdings_exp = engine_exp.run_backtest(prices_df, weights_exp)
    
    # M1: 计算绩效指标
    metrics_exp = pm.calculate_metrics(ledger_exp)
    end_time_exp = datetime.now()
    
    # R1: 记录复现日志
    repro_exp = ReproducibilityLogger.record_experiment_run(
        run_name="experiment_weekly",
        config=exp_cfg,
        data_filepath=price_path,
        start_time=start_time_exp,
        end_time=end_time_exp,
        metrics_summary=metrics_exp
    )
    
    # 保存结果
    ledger_exp.to_csv('outputs/tables/portfolio_experiment_weekly_ledger.csv', index=False)
    holdings_exp.to_csv('outputs/tables/portfolio_experiment_weekly_holdings.csv', index=False)
    pd.DataFrame([metrics_exp]).to_csv('outputs/tables/portfolio_experiment_metrics.csv', index=False)
    print("   [OK] Controlled experiment completed and saved.")
    
    # =========================================================================
    # 3. 对比分析表与图表生成 (Section 28 & 29)
    # =========================================================================
    print("\n" + "-" * 60)
    print("[Step 3] Generating Comparative Report & Equity Curve Plot...")
    
    # 对比表
    compare_df = pd.DataFrame([
        {"Metric": k, "Baseline (Monthly)": metrics_base[k], "Experiment (Weekly)": metrics_exp[k]}
        for k in metrics_base.keys()
    ])
    compare_df.to_csv('outputs/tables/experiment_comparison_monthly_vs_weekly.csv', index=False)
    
    print("\n--- Strategy Performance Comparison (Section 28 & 29) ---")
    print(compare_df.to_string(index=False))
    
    # 绘制净值对比曲线
    plt.figure(figsize=(14, 7))
    plt.plot(pd.to_datetime(ledger_base['date']), ledger_base['equity'] / 10000.0, 
             label=f"Baseline: Monthly Rebalance (MOM20, Top 5)", color='crimson', linewidth=2.0)
    plt.plot(pd.to_datetime(ledger_exp['date']), ledger_exp['equity'] / 10000.0, 
             label=f"Experiment: Weekly Rebalance (MOM20, Top 5)", color='darkorange', linewidth=1.5, linestyle='--')
    plt.plot(pd.to_datetime(ledger_base['date']), ledger_base['benchmark_equity'] / 10000.0, 
             label=f"Benchmark: 510050.SH Buy & Hold", color='navy', linewidth=1.5, alpha=0.8)
             
    plt.title("MA216 Project 1 Controlled Experiment: Monthly vs Weekly Rebalancing (Net Equity)", fontsize=14, fontweight='bold')
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Equity (x 10,000 RMB)", fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(fontsize=11, loc='upper left')
    plt.tight_layout()
    
    fig_path = 'outputs/figures/rebalance_frequency_experiment.png'
    plt.savefig(fig_path, dpi=300)
    plt.close()
    print(f"\n   [OK] Equity curve comparison plot saved to: {fig_path}")
    
    print("\n" + "=" * 75)
    print("All tasks for Sections 22 through 30 completed successfully!")
    print("=" * 75)

if __name__ == "__main__":
    run_pipeline()

