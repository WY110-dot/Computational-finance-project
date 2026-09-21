# Factor Card: REV5

- **factor_name**: REV5
- **research_hypothesis**: 过去5天跌幅较大的资产，在接下来的极短期内存在反弹需求（反转效应）。
- **economic_intuition**: 市场情绪在短期内容易过度反应，导致超卖，从而带来修正性的均值回归机会。
- **formula**: `-(close_adj_t / close_adj_(t-5) - 1)`
- **input_fields**: close_adj
- **lookback_window**: 5 days
- **direction**: 1 (Higher is better)
- **expected_sign**: Positive
- **missing_value_policy**: Keep as NaN (is_valid=False), do not fill with 0
- **winsorize_policy**: None
- **standardization_policy**: Cross-sectional Rank (0 to 1) per day
- **failure_scenarios**: 流动性危机导致的连续跌停、或者基本面彻底恶化导致的单边杀跌。
- **data_version**: v1.1_cs_rank
