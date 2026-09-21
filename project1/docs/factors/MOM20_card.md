# Factor Card: MOM20

- **factor_name**: MOM20
- **research_hypothesis**: 过去20天涨幅较大的资产，在短期内会继续维持强势（动量效应）。
- **economic_intuition**: 市场对信息的反应可能存在延迟，或者存在趋势跟踪资金推波助澜，导致近期表现好的资产持续上涨。
- **formula**: `close_adj_t / close_adj_(t-20) - 1`
- **input_fields**: close_adj
- **lookback_window**: 20 days
- **direction**: 1 (Higher is better)
- **expected_sign**: Positive
- **missing_value_policy**: Keep as NaN (is_valid=False), do not fill with 0
- **winsorize_policy**: None
- **standardization_policy**: Cross-sectional Rank (0 to 1) per day
- **failure_scenarios**: 均值回归极其强烈的震荡市、或者牛市突然转熊的断头铡刀行情。
- **data_version**: v1.1_cs_rank
