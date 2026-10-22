# CF2026 Project 2: Time Series Momentum Replication & Multi-Horizon Extension

**Author**: Siyang Yuan (袁思扬) | Student ID: 12411852  
**Course**: Computational Finance (CF2026)  
**Reference Paper**: Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). *Time series momentum*. Journal of Financial Economics, 104(2), 228–250. [DOI: 10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003)  
**Workspace**: `project2 ysy` (Project 1 `final_project` strictly untouched)  

---

## 1. Project Overview

This repository implements an end-to-end empirical replication and autonomous signal extension of Moskowitz, Ooi & Pedersen (2012) on an exchange-traded fund (ETF) dataset comprising 21 Chinese and cross-border ETFs over the period 2019–2026 (formal evaluation: 2020-02 to 2026-08, 79 calendar months).

### Core Research Tasks:
1. **Methodology Replication**:
   - 12-month time series momentum signal: $s^{(12)}_{i,m} = \operatorname{sign}(P^{adj}_{i,m} / P^{adj}_{i,m-12} - 1)$
   - Ex-ante finite-history EWMA volatility scaling: daily decay $\lambda = 60/61$, annualization 261.
   - Replication of published Fig. 2 (upper) single-asset Sharpe distribution and Fig. 3 cumulative wealth dynamics.
   - Benchmark verification against official AQR original paper factor data (O1).
2. **Autonomous Extension**:
   - Multi-horizon trend combination: $a_{i,m} = \frac{1}{3} [s^{(3)}_{i,m} + s^{(6)}_{i,m} + s^{(12)}_{i,m}]$
   - Evaluated under both theoretical research mode (R4) and realistic execution mode (T2).
3. **Controlled Attribution Experiments**:
   - 7 single-factor controlled experiments: Volatility Scaling (0.40/$\sigma$ vs $s/N$), Shorting Restrictions (Bridge vs R1), Volatility Estimators (EWMA vs Rolling Sample Std), Subperiod Stability (2020-2022 vs 2023-2026), Asset Universe Composition (Broad-market core vs All 21 ETFs), Transaction Costs (0, 3, 10 bps), and Multi-Horizon Extension Trade-offs.

---

## 2. Directory Structure

```text
references/                       # Published paper PDF and extracted original benchmark figures
data/
  manifests/                      # Source data SHA-256 manifests
  raw/                            # Local Parquet snapshots (prices & adjustment factors)
  reference/                      # Official AQR 1985-2009 paper dataset Excel
docs/project2/
  protocol.md                     # Frozen research protocol, targets, and hypotheses
  method_mapping.md               # Paper sections/equations to implementation function mapping
  platform_changes.md             # Project 1 reuse vs Project 2 new components
  data_dictionary.md              # 21-ETF universe definitions and variable dictionary
  method_checks.md                # Independent analytical hand-calculation audit trail
outputs_p2/
  resolved_config.json            # Exact configuration used for runs
  strategy_summary.csv            # Comprehensive metrics across all 18 strategy configurations
  original_vs_replication.csv     # Side-by-side comparison with original paper figures & tables
  difference_experiments.csv      # 7 single-factor controlled attribution experiments
  report_en.md                    # Full English research report in Markdown
  report_en.html                  # Styled self-contained HTML report
  report_en.pdf                   # Publication-ready PDF report with embedded figures
  summary_zh.md                   # Concise Chinese executive summary
  figures/                        # High-resolution charts (Fig 2, Fig 3, Multi-horizon, Exec, Exposures)
  research/                       # Monthly portfolio returns, weights, and contributions for R1-R4
  backtests/                      # Daily ledgers, orders, fills, and holdings for T1-T3
  reference/                      # AQR official factor recalculations
  runs/                           # Exact experiment fingerprints, source hashes, and run manifests
PROJECT_LOG.md                    # Chronological step-by-step modification and verification log
DEMO_P2.md                        # Presentation guide and script
README_PROJECT2.md                # This file
```

---

## 3. Quick Start & Execution Commands

### Prerequisites
- Python 3.11+
- Package manager: `uv`

### One-Click Execution
```powershell
# 1. Install locked dependencies
uv sync --locked

# 2. Run unit tests and independent mathematical hand-calculation checks
uv run --locked pytest

# 3. Prepare offline sources (Paper PDF and AQR official dataset)
uv run --locked python prepare_project2_sources.py --config config/project2_tsmom.json

# 4. Execute the complete Project 2 research pipeline
uv run --locked python run_project2.py --config config/project2_tsmom.json --out outputs_p2_fixed --offline

# 5. Rebuild reports and figures from saved outputs
uv run --locked python build_report_project2.py --out outputs_p2_fixed
```

---

## 4. Key Empirical Findings Summary

| Strategy ID | Mode | Description | Ann. Return | Ann. Vol | Sharpe | CAGR | Max DD | Win Rate |
|---|---|---|---|---|---|---|---|---|
| **R1_tsmom12** | Research | 12M TSMOM (0.40/$\sigma$ scaling) | **18.91%** | 23.88% | **0.792** | 16.97% | -35.73% | **72.15%** |
| **R2_passive_long** | Research | Passive Long Benchmark | 24.53% | 24.89% | 0.986 | 23.92% | -25.65% | 64.56% |
| **R3_equal_nominal** | Research | 12M TSMOM Equal Nominal ($s/N$) | 5.57% | 14.51% | 0.384 | 4.59% | -22.69% | 56.96% |
| **R4_multi_horizon** | Research | Multi-Horizon 3/6/12M Extension | 12.96% | **22.17%** | 0.584 | 10.80% | **-33.74%** | 68.35% |
| **Bridge_long_only** | Research | Long-Only Research Mode | 21.72% | 15.02% | **1.446** | 22.70% | **-12.10%** | 69.62% |
| **R1_sample_vol** | Research | TSMOM 252d Rolling Sample Vol | 17.01% | 23.30% | 0.730 | 14.98% | -34.37% | 72.15% |
| **R1_broad_market** | Research | Broad-Market Core (510050/300/500) | 2.22% | 42.41% | 0.052 | -9.86% | -79.80% | 56.96% |
| **T1_tsmom12_3bps** | Execution | 12M Long/Cash Exec (3 bps) | 5.18% | 3.98% | 1.303 | 5.24% | -4.25% | 55.85% |
| **T2_multi_horizon_3bps** | Execution | Multi-Horizon Long/Cash (3 bps) | 4.25% | **3.15%** | **1.350** | 4.29% | **-3.38%** | **57.22%** |
| **T3_passive_long_3bps** | Execution | Passive Long Exec (3 bps) | 6.32% | 5.34% | 1.184 | 6.38% | -6.56% | 52.78% |
| **O1_aqr_original_reference**| Reference | Official AQR Factor Recalculation | 17.08% | 12.33% | 1.385 | 17.60% | -15.23% | 67.33% |
| **O1_aqr_reference** | Reference | AQR Official Paper Factor (1985-2009)| 17.08% | 12.33% | 1.385 | 17.60% | -15.23% | 67.33% |

### Core Takeaways:
1. **Single-Asset Pervasiveness**: 17 of 21 ETFs (81.0%) demonstrate positive Sharpe ratios under 12M TSMOM, confirming Moskowitz et al.'s finding across an independent ETF asset class.
2. **Surrogate Universe Differences**: Bond and gold ETFs experienced a prolonged upward drift, which elevated passive long carry; whereas equity ETFs suffered from policy-driven sharp reversals where short positions generated negative carry.
3. **Multi-Horizon Improvement**: Under realistic execution constraints, the multi-horizon strategy achieved a higher Sharpe ratio (**1.332 vs 1.279**) and a lower maximum drawdown (**-3.38% vs -4.25%**) than the single 12-month lookback.

