# Factor Card: LOWVOL20

- **factor_name**: LOWVOL20
- **research_hypothesis**: 过去20天波动率较小的资产，其风险调整后收益更高（低波动异象）。
- **economic_intuition**: 投资者往往偏好高波动、具有“彩票特征”的资产，导致高波动资产被高估，低波动资产被低估。
- **formula**: `-std(ret_total_t, window=20, ddof=1)`
- **input_fields**: ret_total
- **lookback_window**: 20 days
- **direction**: 1 (Higher is better)
- **expected_sign**: Positive
- **missing_value_policy**: Keep as NaN (is_valid=False), do not fill with 0
- **winsorize_policy**: None
- **standardization_policy**: Cross-sectional Rank (0 to 1) per day
- **failure_scenarios**: 市场极度追求成长性与高弹性的狂热期。
- **data_version**: v1.1_cs_rank
