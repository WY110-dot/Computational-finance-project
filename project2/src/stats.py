"""Inference for the reproduction: HAC regressions, alpha, extremes, sensitivity."""
import numpy as np
import pandas as pd
import statsmodels.api as sm


def nw_regression(y, x, lags=12):
    """OLS y = a + b x with Newey-West (HAC) standard errors."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    mask = np.isfinite(y) & np.isfinite(x)
    y, x = y[mask], x[mask]
    if len(y) < 3 or np.std(x) == 0:
        return dict(alpha=np.nan, beta=np.nan, t_alpha=np.nan, t_beta=np.nan,
                    r2=np.nan, n=int(len(y)))
    X = sm.add_constant(x, has_constant='add')
    fit = sm.OLS(y, X).fit(cov_type='HAC', cov_kwds={'maxlags': int(lags)})
    return dict(alpha=float(fit.params[0]), beta=float(fit.params[1]),
                t_alpha=float(fit.tvalues[0]), t_beta=float(fit.tvalues[1]),
                r2=float(fit.rsquared), n=int(len(y)))


def cluster_regression(y, x, groups, lags=12):
    """OLS with standard errors clustered by month (cross-sectional correlation)."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    mask = np.isfinite(y) & np.isfinite(x)
    y, x, groups = y[mask], x[mask], np.asarray(groups)[mask]
    if len(y) < 3 or np.std(x) == 0:
        return dict(alpha=np.nan, beta=np.nan, t_alpha=np.nan, t_beta=np.nan,
                    r2=np.nan, n=int(len(y)))
    X = sm.add_constant(x, has_constant='add')
    fit = sm.OLS(y, X).fit(cov_type='cluster', cov_kwds={'groups': groups})
    return dict(alpha=float(fit.params[0]), beta=float(fit.params[1]),
                t_alpha=float(fit.tvalues[0]), t_beta=float(fit.tvalues[1]),
                r2=float(fit.rsquared), n=int(len(y)))


def mean_tstat(series, lags=12):
    """HAC t-statistic for the mean of a monthly return series."""
    s = pd.Series(series).dropna().astype(float)
    if len(s) < 3:
        return dict(mean=np.nan, t=np.nan, n=len(s))
    fit = sm.OLS(s.to_numpy(), np.ones((len(s), 1))).fit(cov_type='HAC', cov_kwds={'maxlags': int(lags)})
    return dict(mean=float(fit.params[0]), t=float(fit.tvalues[0]), n=int(len(s)))


def sharpe(monthly, rf_annual=0.0, periods=12):
    s = pd.Series(monthly).dropna().astype(float) - rf_annual / periods
    if len(s) < 3 or s.std(ddof=1) == 0:
        return dict(sharpe=np.nan, ann_return=np.nan, ann_vol=np.nan, n=len(s))
    return dict(
        sharpe=float(s.mean() / s.std(ddof=1) * np.sqrt(periods)),
        ann_return=float(s.mean() * periods),
        ann_vol=float(s.std(ddof=1) * np.sqrt(periods)),
        n=int(len(s)),
    )


def alpha_regression(strategy_monthly, benchmark_monthly, lags=12):
    """Regress strategy monthly return on the equal-weight benchmark.

    alpha is annualized as 12 * intercept; t(alpha) uses HAC standard errors.
    This is an equity-sector alpha, not a Fama-French alpha (those factors are
    not part of the fixed offline snapshot).
    """
    df = pd.concat([pd.Series(strategy_monthly, name='strategy'),
                    pd.Series(benchmark_monthly, name='benchmark')], axis=1).dropna()
    if len(df) < 12:
        return dict(alpha_annual=np.nan, t_alpha=np.nan, beta=np.nan,
                    t_beta=np.nan, r2=np.nan, n=len(df))
    X = sm.add_constant(df.benchmark.to_numpy(float), has_constant='add')
    fit = sm.OLS(df.strategy.to_numpy(float), X).fit(
        cov_type='HAC', cov_kwds={'maxlags': int(lags)})
    return dict(alpha_annual=float(fit.params[0] * 12), t_alpha=float(fit.tvalues[0]),
                beta=float(fit.params[1]), t_beta=float(fit.tvalues[1]),
                r2=float(fit.rsquared), n=int(len(df)))


def predictive_table(monthly_ret, monthly_px, horizons, cfg):
    """Per-asset and pooled fixed-effects regressions of next-month return on sign signal.

    y_t+1 = a + b * sign(P_t / P_{t-h} - 1) + e
    Per-asset: HAC (maxlags = cfg['nw_lags']).
    Pooled: asset fixed effects (within transformation), SE clustered by month.
    """
    rows = []
    assets = list(monthly_ret.columns)
    # A signal formed on the last day of the previous month predicts the first
    # research month, so include that one formation date and no earlier ones.
    first_signal_date = pd.Timestamp(cfg['start']) - pd.offsets.MonthEnd(1)
    for h in horizons:
        sig = np.sign(monthly_px / monthly_px.shift(h) - 1)
        y_next = monthly_ret.shift(-1)
        for a in assets:
            mask = sig.index >= first_signal_date
            res = nw_regression(y_next.loc[mask, a], sig.loc[mask, a], cfg['nw_lags'])
            rows.append(dict(horizon_months=h, asset=a, scope='asset', **res))
        # Stack and demean within asset (fixed effects).
        long = pd.concat([
            sig.stack(future_stack=True).rename('signal'),
            y_next.stack(future_stack=True).rename('ret'),
        ], axis=1).dropna().reset_index()
        long.columns = ['date', 'asset', 'signal', 'ret']
        long = long[long.date >= first_signal_date]
        long['signal_dm'] = long.signal - long.groupby('asset').signal.transform('mean')
        long['ret_dm'] = long.ret - long.groupby('asset').ret.transform('mean')
        groups = long.date.astype('category').cat.codes.to_numpy()
        res = cluster_regression(long.ret_dm, long.signal_dm, groups, cfg['nw_lags'])
        rows.append(dict(horizon_months=h, asset='POOLED_FE', scope='pooled', **res))
    return pd.DataFrame(rows)


def extreme_table(strategy_monthly, market_monthly, lags=12):
    """Average strategy return in extreme market months (paper's Table 3 idea)."""
    df = pd.concat([pd.Series(strategy_monthly, name='strategy'),
                    pd.Series(market_monthly, name='market')], axis=1).dropna()
    out = []
    for label, lo, hi in [('bottom_10pct', 0.0, 0.10), ('middle_80pct', 0.10, 0.90),
                          ('top_10pct', 0.90, 1.0), ('bottom_20pct', 0.0, 0.20),
                          ('top_20pct', 0.80, 1.0)]:
        q_lo = df.market.quantile(lo)
        q_hi = df.market.quantile(hi)
        if label.startswith('bottom'):
            sub = df[df.market <= q_hi]
        elif label.startswith('top'):
            sub = df[df.market >= q_lo]
        else:
            sub = df[(df.market > q_lo) & (df.market < q_hi)]
        stats = mean_tstat(sub.strategy, lags)
        out.append(dict(bin=label, months=len(sub), mean_market=float(sub.market.mean()),
                        mean_tsmom=float(sub.strategy.mean()), t_tsmom=stats['t'],
                        hit_rate=float((sub.strategy > 0).mean()),
                        std_tsmom=float(sub.strategy.std(ddof=1)) if len(sub) > 1 else np.nan))
    return pd.DataFrame(out)


def information_ratio_vs_zero(monthly, lags=12):
    s = pd.Series(monthly).dropna()
    return mean_tstat(s, lags)
