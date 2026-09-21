> **Historical / Deprecated**
> 
> This report is retained for historical development tracking only and does not define the final Project 1 method, results, or submission requirements.

# Phase 7: Strategy Optimization and Out-of-Sample Validation Report

## Executive Summary

- Test Date: 2026-09-17 15:01:35
- In-Sample Period: 2020-01-02 to 2025-12-31 (1455 trading days)
- Out-of-Sample Period: 2026-01-05 to 2026-09-16 (172 trading days)
- Number of Strategies Tested: 8

## Best Strategy

- Strategy Name: **BB_20_2**
- Parameters: {'period': 20, 'num_std': 2}

## In-Sample Performance (2020-2025)

- Total Return: 15.92%
- Annual Return: 2.59%
- Sharpe Ratio: 0.2694
- Max Drawdown: -25.91%
- Volatility: 12.29%

## Out-of-Sample Performance (2026)

- Total Return: 9.08%
- Annual Return: 13.58%
- Sharpe Ratio: 1.1436
- Max Drawdown: -9.53%
- Volatility: 11.74%

## Key Findings

### In-Sample Top 3 Strategies:
1. **BB_20_2**: Annual Return 2.59%, Sharpe 0.2694
2. **MA10_50**: Annual Return 1.47%, Sharpe 0.1799
3. **MA10_30**: Annual Return 1.09%, Sharpe 0.1487

### In-Sample vs Benchmark:
- Benchmark Return (Buy & Hold): 0.78%
- Best Strategy Return: 15.92%
- Excess Return: 15.14%

### Out-of-Sample vs Benchmark:
- Benchmark Return (Buy & Hold): -6.11%
- Best Strategy Return: 9.08%
- Excess Return: 15.20%

## Conclusion

✅ **GOOD**: Strategy maintains positive Sharpe Ratio out-of-sample, good generalization.

---
Report Generated: 2026-09-17 15:01:35