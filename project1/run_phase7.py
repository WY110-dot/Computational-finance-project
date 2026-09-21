# -*- coding: utf-8 -*-
"""
Phase 7: Strategy Optimization and Out-of-Sample Validation
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys
import os
from datetime import datetime

sys.path.append('src')

from optimization.strategy_optimizer import StrategyOptimizer

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

def split_data(df, split_date='2026-01-01'):
    """Split in-sample and out-of-sample data"""
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    
    in_sample = df[df['trade_date'] < split_date].copy()
    out_sample = df[df['trade_date'] >= split_date].copy()
    
    print(f"In-sample: {in_sample['trade_date'].min()} to {in_sample['trade_date'].max()}")
    print(f"  Total {len(in_sample)} trading days")
    print(f"\nOut-of-sample: {out_sample['trade_date'].min()} to {out_sample['trade_date'].max()}")
    print(f"  Total {len(out_sample)} trading days")
    
    return in_sample, out_sample

def print_strategy_comparison(results_df, title="Strategy Comparison"):
    """Print strategy comparison table"""
    print(f"\n{'='*100}")
    print(f"{title:^100}")
    print(f"{'='*100}")
    
    # Check available columns and use them
    display_cols = ['strategy_name']
    available_metrics = []
    
    metric_mappings = [
        ('total_return', 'Total Return'),
        ('annualized_return', 'Annual Return'),
        ('sharpe_ratio', 'Sharpe'),
        ('max_drawdown', 'Max DD'),
        ('volatility', 'Volatility'),
        ('total_trades', 'Trades')
    ]
    
    for col, label in metric_mappings:
        if col in results_df.columns:
            display_cols.append(col)
            available_metrics.append((col, label))
    
    display_df = results_df[display_cols].copy()
    
    # Format values
    for col, label in available_metrics:
        if col in ['total_return', 'annualized_return', 'max_drawdown', 'volatility']:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        elif col == 'sharpe_ratio':
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "N/A")
        elif col == 'total_trades':
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"{int(x)}" if pd.notna(x) else "N/A")
    
    # Rename columns
    rename_map = {'strategy_name': 'Strategy'}
    for col, label in available_metrics:
        if col in display_df.columns:
            rename_map[col] = label
    
    display_df = display_df.rename(columns=rename_map)
    
    print(display_df.to_string(index=False))
    print(f"{'='*100}\n")

def save_results(results_df, optimizer, period_name, output_dir='outputs'):
    """Save results"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    csv_path = f"{output_dir}/tables/strategy_comparison_{period_name}_{timestamp}.csv"
    results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Results saved to: {csv_path}")
    
    best_strategy = results_df.iloc[0]['strategy_name']
    best_data = optimizer.results[best_strategy]['data']
    best_csv_path = f"{output_dir}/tables/best_strategy_{period_name}_{timestamp}.csv"
    best_data.to_csv(best_csv_path, index=False, encoding='utf-8-sig')
    print(f"Best strategy details saved to: {best_csv_path}")
    
    return csv_path, best_csv_path

def plot_strategy_comparison(optimizer, results_df, period_name, output_dir='outputs'):
    """Plot strategy comparison"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(f'Strategy Comparison - {period_name}', fontsize=16, fontweight='bold')
    
    # 1. Equity curves
    ax1 = axes[0, 0]
    for strategy_name in results_df['strategy_name'].head(5):
        df = optimizer.results[strategy_name]['data']
        ax1.plot(df['trade_date'], df['strategy_equity'], label=strategy_name, linewidth=1.5)
    
    benchmark_df = list(optimizer.results.values())[0]['data']
    ax1.plot(benchmark_df['trade_date'], benchmark_df['benchmark_equity'], 
            label='Buy & Hold', linestyle='--', color='black', linewidth=2)
    
    ax1.set_title('Equity Curves (Top 5)', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Equity')
    ax1.legend(loc='best', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # 2. Sharpe Ratio
    ax2 = axes[0, 1]
    strategies = results_df['strategy_name'].head(10)
    sharpe_ratios = results_df['sharpe_ratio'].head(10)
    colors = ['green' if x > 0 else 'red' for x in sharpe_ratios]
    
    ax2.barh(range(len(strategies)), sharpe_ratios, color=colors, alpha=0.7)
    ax2.set_yticks(range(len(strategies)))
    ax2.set_yticklabels(strategies, fontsize=9)
    ax2.set_xlabel('Sharpe Ratio')
    ax2.set_title('Sharpe Ratio Comparison', fontsize=12, fontweight='bold')
    ax2.axvline(x=0, color='black', linestyle='--', linewidth=1)
    ax2.grid(True, alpha=0.3, axis='x')
    
    # 3. Return vs Risk
    ax3 = axes[1, 0]
    scatter = ax3.scatter(results_df['volatility'], 
                         results_df['annualized_return'],
                         s=100, alpha=0.6, c=results_df['sharpe_ratio'],
                         cmap='RdYlGn', edgecolors='black', linewidth=1)
    
    for idx in range(min(3, len(results_df))):
        row = results_df.iloc[idx]
        ax3.annotate(row['strategy_name'], 
                    xy=(row['volatility'], row['annualized_return']),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=8, bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.5))
    
    ax3.set_xlabel('Annualized Volatility (%)')
    ax3.set_ylabel('Annualized Return (%)')
    ax3.set_title('Return-Risk Scatter', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax3, label='Sharpe Ratio')
    
    # 4. Max Drawdown
    ax4 = axes[1, 1]
    strategies = results_df['strategy_name'].head(10)
    drawdowns = results_df['max_drawdown'].head(10)
    
    ax4.barh(range(len(strategies)), drawdowns, color='darkred', alpha=0.7)
    ax4.set_yticks(range(len(strategies)))
    ax4.set_yticklabels(strategies, fontsize=9)
    ax4.set_xlabel('Max Drawdown (%)')
    ax4.set_title('Max Drawdown Comparison', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fig_path = f"{output_dir}/figures/strategy_comparison_{period_name}_{timestamp}.png"
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    print(f"Chart saved to: {fig_path}")
    plt.close()

def main():
    print("=" * 100)
    print(" " * 30 + "Phase 7: Strategy Optimization and Validation")
    print("=" * 100)
    
    print("\nLoading data...")
    data_path = 'data/raw/510050_SH_20200101_.csv'
    df = pd.read_csv(data_path)
    print(f"Data loaded: {len(df)} records")
    
    print("\n" + "=" * 100)
    print("Step 1: Data Split")
    print("=" * 100)
    in_sample, out_sample = split_data(df, '2026-01-01')
    
    print("\n" + "=" * 100)
    print("Step 2: In-Sample Optimization (2020-2025)")
    print("=" * 100)
    
    optimizer_in = StrategyOptimizer(in_sample)
    results_in = optimizer_in.run_all_strategies()
    
    print_strategy_comparison(results_in, "In-Sample Strategy Comparison (2020-2025)")
    
    save_results(results_in, optimizer_in, 'in_sample')
    plot_strategy_comparison(optimizer_in, results_in, 'In-Sample(2020-2025)')
    
    best_strategy_name = results_in.iloc[0]['strategy_name']
    best_params = results_in.iloc[0]['parameters']
    
    print(f"\n{'='*100}")
    print(f"Best Strategy: {best_strategy_name}")
    print(f"Parameters: {best_params}")
    print(f"In-Sample Performance:")
    print(f"  - Total Return: {results_in.iloc[0].get('total_return', 0):.2f}%")
    print(f"  - Annual Return: {results_in.iloc[0].get('annualized_return', 0):.2f}%")
    print(f"  - Sharpe Ratio: {results_in.iloc[0].get('sharpe_ratio', 0):.4f}")
    print(f"  - Max Drawdown: {results_in.iloc[0].get('max_drawdown', 0):.2f}%")
    print(f"{'='*100}\n")
    
    print("\n" + "=" * 100)
    print("Step 3: Out-of-Sample Validation (2026)")
    print("=" * 100)
    print("WARNING: Final validation, execute only once!")
    print("=" * 100)
    
    optimizer_out = StrategyOptimizer(out_sample)
    results_out = optimizer_out.run_all_strategies()
    
    print_strategy_comparison(results_out, "Out-of-Sample Strategy Comparison (2026)")
    
    save_results(results_out, optimizer_out, 'out_sample')
    plot_strategy_comparison(optimizer_out, results_out, 'Out-of-Sample(2026)')
    
    print("\n" + "=" * 100)
    print("Step 4: Best Strategy In-Sample vs Out-of-Sample")
    print("=" * 100)
    
    best_out = results_out[results_out['strategy_name'] == best_strategy_name]
    
    if len(best_out) > 0:
        print(f"\nStrategy: {best_strategy_name}")
        print(f"\n{'Metric':<20} {'In-Sample(2020-2025)':<25} {'Out-of-Sample(2026)':<25} {'Difference':<20}")
        print("-" * 90)
        
        metrics_to_compare = [
            ('total_return', 'Total Return', '%'),
            ('annualized_return', 'Annual Return', '%'),
            ('sharpe_ratio', 'Sharpe Ratio', 'float'),
            ('max_drawdown', 'Max Drawdown', '%'),
            ('volatility', 'Volatility', '%'),
            ('total_trades', 'Trades', 'int')
        ]
        
        for metric_key, metric_name, fmt in metrics_to_compare:
            in_val = results_in.iloc[0].get(metric_key, 0)
            out_val = best_out.iloc[0].get(metric_key, 0)
            
            if fmt == '%':
                diff = out_val - in_val
                print(f"{metric_name:<20} {in_val:>23.2f}% {out_val:>23.2f}% {diff:>18.2f}%")
            elif fmt == 'float':
                diff = out_val - in_val
                print(f"{metric_name:<20} {in_val:>23.4f} {out_val:>23.4f} {diff:>18.4f}")
            else:  # int
                diff = int(out_val - in_val) if pd.notna(out_val) and pd.notna(in_val) else 0
                print(f"{metric_name:<20} {int(in_val):>23} {int(out_val):>23} {diff:>18}")
    
    print("\n" + "=" * 100)
    print("Step 5: Generate Final Report")
    print("=" * 100)
    
    report = []
    report.append("# Phase 7: Strategy Optimization and Out-of-Sample Validation Report")
    report.append("")
    report.append("## Executive Summary")
    report.append("")
    report.append(f"- Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"- In-Sample Period: 2020-01-02 to 2025-12-31 ({len(in_sample)} trading days)")
    report.append(f"- Out-of-Sample Period: 2026-01-05 to 2026-09-16 ({len(out_sample)} trading days)")
    report.append(f"- Number of Strategies Tested: {len(results_in)}")
    report.append("")
    report.append("## Best Strategy")
    report.append("")
    report.append(f"- Strategy Name: **{best_strategy_name}**")
    report.append(f"- Parameters: {best_params}")
    report.append("")
    report.append("## In-Sample Performance (2020-2025)")
    report.append("")
    report.append(f"- Total Return: {results_in.iloc[0].get('total_return', 0):.2f}%")
    report.append(f"- Annual Return: {results_in.iloc[0].get('annualized_return', 0):.2f}%")
    report.append(f"- Sharpe Ratio: {results_in.iloc[0].get('sharpe_ratio', 0):.4f}")
    report.append(f"- Max Drawdown: {results_in.iloc[0].get('max_drawdown', 0):.2f}%")
    report.append(f"- Volatility: {results_in.iloc[0].get('volatility', 0):.2f}%")
    report.append("")
    
    if len(best_out) > 0:
        report.append("## Out-of-Sample Performance (2026)")
        report.append("")
        report.append(f"- Total Return: {best_out.iloc[0].get('total_return', 0):.2f}%")
        report.append(f"- Annual Return: {best_out.iloc[0].get('annualized_return', 0):.2f}%")
        report.append(f"- Sharpe Ratio: {best_out.iloc[0].get('sharpe_ratio', 0):.4f}")
        report.append(f"- Max Drawdown: {best_out.iloc[0].get('max_drawdown', 0):.2f}%")
        report.append(f"- Volatility: {best_out.iloc[0].get('volatility', 0):.2f}%")
        report.append("")
    
    report.append("## Key Findings")
    report.append("")
    
    report.append("### In-Sample Top 3 Strategies:")
    for i in range(min(3, len(results_in))):
        row = results_in.iloc[i]
        report.append(f"{i+1}. **{row['strategy_name']}**: Annual Return {row.get('annualized_return', 0):.2f}%, Sharpe {row.get('sharpe_ratio', 0):.4f}")
    report.append("")
    
    benchmark_return_in = results_in.iloc[0].get('total_return_benchmark', 0)
    strategy_return_in = results_in.iloc[0].get('total_return', 0)
    outperformance_in = strategy_return_in - benchmark_return_in
    
    report.append("### In-Sample vs Benchmark:")
    report.append(f"- Benchmark Return (Buy & Hold): {benchmark_return_in:.2f}%")
    report.append(f"- Best Strategy Return: {strategy_return_in:.2f}%")
    report.append(f"- Excess Return: {outperformance_in:.2f}%")
    report.append("")
    
    if len(best_out) > 0:
        benchmark_return_out = best_out.iloc[0].get('total_return_benchmark', 0)
        strategy_return_out = best_out.iloc[0].get('total_return', 0)
        outperformance_out = strategy_return_out - benchmark_return_out
        
        report.append("### Out-of-Sample vs Benchmark:")
        report.append(f"- Benchmark Return (Buy & Hold): {benchmark_return_out:.2f}%")
        report.append(f"- Best Strategy Return: {strategy_return_out:.2f}%")
        report.append(f"- Excess Return: {outperformance_out:.2f}%")
        report.append("")
    
    report.append("## Conclusion")
    report.append("")
    
    if len(best_out) > 0:
        sharpe_in = results_in.iloc[0].get('sharpe_ratio', 0)
        sharpe_out = best_out.iloc[0].get('sharpe_ratio', 0)
        sharpe_degradation = sharpe_in - sharpe_out
        
        return_in = results_in.iloc[0].get('annualized_return', 0)
        return_out = best_out.iloc[0].get('annualized_return', 0)
        return_degradation = return_in - return_out
        
        if sharpe_degradation > 0.5 or return_degradation > 10:
            report.append("⚠️ **WARNING**: Strategy performance significantly degraded out-of-sample, possible overfitting.")
        elif sharpe_out > 0:
            report.append("✅ **GOOD**: Strategy maintains positive Sharpe Ratio out-of-sample, good generalization.")
        else:
            report.append("⚠️ **NOTE**: Strategy has negative Sharpe Ratio out-of-sample, needs further optimization.")
    
    report.append("")
    report.append("---")
    report.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = f"docs/phase7_optimization_report_{timestamp}.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\nFinal report saved to: {report_path}")
    
    print("\n" + "=" * 100)
    print("Phase 7 Complete!")
    print("=" * 100)

if __name__ == '__main__':
    main()
