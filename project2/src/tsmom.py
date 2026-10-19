"""Signal construction for Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum".

Paper specification reproduced here:
  signal_t       = sign(r_{t-h, t})                     (h = 1, 3, 12 months)
  position_t     = (1 / N_t) * (0.40 / sigma_t) * signal_t
  sigma_t        = annualized EWMA daily volatility, center of mass = 60 days
  rebalance      = monthly, signal formed at month-end close, applied to the
                   following month

The 40% per-asset volatility target and the 1/N averaging are the paper's
construction. The baseline deliberately does *not* rescale the portfolio to a
fixed ex-ante volatility; the paper's diversified futures portfolio happens to
realize roughly 12% annualized volatility through diversification. A portfolio
rescale is available only as a diagnostic variant.

No future price enters a signal or a weight. The caller executes the weights at
the next trading day's open.
"""
import numpy as np
import pandas as pd


def month_end_dates(index):
    """Last observed trading date of each calendar month."""
    idx = pd.DatetimeIndex(index)
    s = pd.Series(idx, index=idx)
    return pd.DatetimeIndex(s.groupby(idx.to_period('M')).max().to_numpy())


def monthly_close(close):
    """Month-end close on the last observed trading day (data are complete)."""
    return close.loc[month_end_dates(close.index)]


def monthly_returns(close):
    return monthly_close(close).pct_change(fill_method=None)


def daily_returns(close):
    return close.pct_change(fill_method=None)


def ewma_vol(returns, com=60, min_periods=40, annualization=252):
    """Annualized EWMA volatility, center of mass = com days (delta = com/(1+com)).

    bias=True returns the normalized weighted population variance, close to the
    paper's formula sigma^2 = A * sum_j (1-delta) delta^j (r_{t-1-j} - mean)^2.
    """
    var = returns.ewm(com=com, min_periods=min_periods, adjust=True).var(bias=True)
    return np.sqrt(var * annualization)


def ewma_cov(returns, com=60, min_periods=40, annualization=252):
    """Annualized pairwise EWMA covariance panel indexed by (date, asset)."""
    return returns.ewm(com=com, min_periods=min_periods, adjust=True).cov(bias=True) * annualization


def trailing_return(monthly_px, months, skip=0):
    """P_{t-skip} / P_{t-months-skip} - 1.

    skip=0 is the paper's 12-month signal. skip=1 is the "12-1" variant:
    twelve monthly returns ending one month before the formation date.
    """
    end = monthly_px.shift(skip)
    start = monthly_px.shift(months + skip)
    return end / start - 1


def sign_signal(monthly_px, months, skip=0):
    return np.sign(trailing_return(monthly_px, months, skip))


def multihorizon_signal(monthly_px, months_list):
    """Average of the signs at several horizons; lies in [-1, 1]."""
    signs = [np.sign(trailing_return(monthly_px, h)) for h in months_list]
    return sum(signs) / len(signs)


def execution_map(signal_index, daily_index, start, end):
    """Map each month-end signal date to the next trading date (execution)."""
    daily_index = pd.DatetimeIndex(daily_index)
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    out = {}
    for t in pd.DatetimeIndex(signal_index):
        pos = daily_index.searchsorted(t, side='right')
        if pos >= len(daily_index):
            continue
        d = daily_index[pos]
        if start <= d <= end:
            out[d] = t
    return out


def build_weights(signal, vol, cfg, cov=None):
    """Turn signals and volatility into signed target weights (fraction of NAV).

    w_raw[i] = signal[i] * (vol_target / sigma[i]) / N_t
    If portfolio_rescale is true, w = w_raw * portfolio_vol_target / sqrt(w_raw' Sigma w_raw).
    Gross exposure is capped at cfg['max_gross_exposure']; binding dates are counted.
    """
    signal = signal.reindex(columns=cfg['assets'])
    vol = vol.reindex(index=signal.index, columns=cfg['assets'])
    vol_target = float(cfg['vol_target'])
    max_gross = float(cfg.get('max_gross_exposure', np.inf))
    rescale = bool(cfg.get('portfolio_rescale', False))
    pvol_target = float(cfg.get('portfolio_vol_target', vol_target))

    weights = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    rows = []
    for date in signal.index:
        s = signal.loc[date]
        sigma = vol.loc[date]
        usable = s.notna() & sigma.notna() & (sigma > 0)
        n = int(usable.sum())
        if n < int(cfg.get('min_assets', 1)):
            w = pd.Series(0.0, index=signal.columns)
            scale = 1.0
            var = np.nan
            capped = False
        else:
            w = pd.Series(0.0, index=signal.columns)
            w.loc[usable] = s.loc[usable] * (vol_target / sigma.loc[usable]) / n
            scale = 1.0
            var = np.nan
            # Always report ex-ante portfolio variance when a covariance panel
            # is supplied. Rescaling is a separate, opt-in decision.
            if cov is not None:
                sigma_m = cov.loc[date].reindex(index=cfg['assets'], columns=cfg['assets'])
                if sigma_m.notna().all().all():
                    var = float(w.to_numpy() @ sigma_m.to_numpy() @ w.to_numpy())
                    if rescale and np.isfinite(var) and var > 0:
                        scale = pvol_target / np.sqrt(var)
                        w = w * scale
            gross0 = float(w.abs().sum())
            capped = gross0 > max_gross
            if capped and gross0 > 0:
                w = w * (max_gross / gross0)
        gross = float(w.abs().sum())
        net = float(w.sum())
        weights.loc[date] = w
        rows.append(dict(
            date=date, n_assets=n, scale=scale, ex_ante_portfolio_vol=np.sqrt(var) if np.isfinite(var) else np.nan,
            gross_exposure=gross, net_exposure=net, gross_capped=capped,
            max_abs_weight=float(w.abs().max()) if len(w) else np.nan,
            long_assets=int((w > 0).sum()), short_assets=int((w < 0).sum()),
        ))

    diagnostics = pd.DataFrame(rows).set_index('date')
    diagnostics.index.name = 'date'
    return weights, diagnostics
