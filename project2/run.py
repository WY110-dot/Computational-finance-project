"""Project 2 reproduction entry point.

Run from this directory:
    python run.py
    python run.py --config config.json --out outputs

Everything is offline. The raw snapshot is hashed and validated before use.
"""
import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import load_panel, sha
from src import tsmom as ts
from src import stats
from src import plots
from src.backtest import simulate, audit, metrics, monthly_returns, subperiod_metrics

ROOT = Path(__file__).resolve().parent


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def equal_weight_weights(index, assets):
    return pd.DataFrame(1.0 / len(assets), index=pd.DatetimeIndex(index), columns=list(assets))


def diversified_weights(monthly_px, vol, cfg, cov=None, transform=None):
    """Average the 1-, 3- and 12-month TSMOM weight vectors (paper Table 2).

    transform optionally maps the sign signal (e.g. clip to a long-only leg);
    it is used only for diagnostic decompositions, never for the baseline.
    """
    parts = {}
    diags = {}
    for h in (1, 3, 12):
        sig = ts.sign_signal(monthly_px, h)
        if transform is not None:
            sig = transform(sig)
        w, d = ts.build_weights(sig, vol, cfg, cov)
        parts[h] = w
        diags[h] = d
    w = sum(parts.values()) / len(parts)
    d = pd.DataFrame(index=w.index)
    d['n_assets'] = diags[1]['n_assets']
    d['gross_exposure'] = w.abs().sum(axis=1)
    d['net_exposure'] = w.sum(axis=1)
    d['long_assets'] = (w > 0).sum(axis=1)
    d['short_assets'] = (w < 0).sum(axis=1)
    d['max_abs_weight'] = w.abs().max(axis=1)
    d['gross_capped'] = False
    if cov is not None:
        ex_vol = []
        for date in w.index:
            sigma_m = cov.loc[date].reindex(index=cfg['assets'], columns=cfg['assets'])
            if sigma_m.notna().all().all():
                vec = w.loc[date].to_numpy(float)
                ex_vol.append(float(np.sqrt(vec @ sigma_m.to_numpy() @ vec)))
            else:
                ex_vol.append(np.nan)
        d['ex_ante_portfolio_vol'] = ex_vol
    return w, d, parts


def run_strategy(name, weights, cfg, pivots, save_daily=True, out=None):
    daily, trades = simulate(
        {'open': pivots['open'], 'close': pivots['close']}, weights, cfg)
    checks = audit(daily, trades, cfg)
    m = metrics(daily, cfg)
    m['strategy'] = name
    if save_daily and out is not None:
        daily.to_csv(out / f'{name}_daily.csv', index=False, float_format='%.12g')
        trades.to_csv(out / f'{name}_trades.csv', index=False, float_format='%.12g')
    return daily, trades, m, checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='config.json')
    ap.add_argument('--out', default='outputs')
    args = ap.parse_args()

    cfg = json.loads((ROOT / args.config).read_text(encoding='utf-8'))
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / 'figures').mkdir(exist_ok=True)
    tic = time.perf_counter()

    panel, pivots, quality = load_panel(ROOT, cfg)
    dump(out / 'quality_report.json', quality)
    panel.to_csv(out / 'clean_panel.csv', index=False, float_format='%.12g')

    close = pivots['close']
    mpx = ts.monthly_close(close)
    mret = mpx.pct_change(fill_method=None)
    dret = ts.daily_returns(close)
    vol = ts.ewma_vol(dret, cfg['vol_com'], cfg['vol_min_periods'], cfg['annualization'])
    cov = ts.ewma_cov(dret, cfg['vol_com'], cfg['vol_min_periods'], cfg['annualization'])

    # Signals and baseline weights.
    signals = {h: ts.sign_signal(mpx, h) for h in cfg['sensitivity']['lookbacks']}
    signal_rows = []
    for h, frame in signals.items():
        long = frame.stack(future_stack=True).rename('signal').reset_index()
        long.columns = ['date', 'asset', 'signal']
        long['horizon_months'] = h
        signal_rows.append(long[['date', 'asset', 'horizon_months', 'signal']])
    pd.concat(signal_rows, ignore_index=True).to_csv(
        out / 'signals.csv', index=False, float_format='%.12g')

    w_div, d_div, w_parts = diversified_weights(mpx, vol, cfg, cov)
    w_long, d_long, _ = diversified_weights(
        mpx, vol, cfg, cov, transform=lambda s: s.clip(lower=0))
    w_short, d_short, _ = diversified_weights(
        mpx, vol, cfg, cov, transform=lambda s: s.clip(upper=0))
    weight_rows = []
    for h, w in w_parts.items():
        for date in w.index:
            for a in w.columns:
                weight_rows.append(dict(date=date, portfolio=f'tsmom_{h}m', asset=a, weight=w.loc[date, a]))
    for date in w_div.index:
        for a in w_div.columns:
            weight_rows.append(dict(date=date, portfolio='tsmom_diversified', asset=a, weight=w_div.loc[date, a]))
    pd.DataFrame(weight_rows).to_csv(out / 'weights.csv', index=False, float_format='%.12g')
    d_div.to_csv(out / 'weight_diagnostics.csv', float_format='%.12g')
    d_long.to_csv(out / 'weight_diagnostics_longonly.csv', float_format='%.12g')
    d_short.to_csv(out / 'weight_diagnostics_shortonly.csv', float_format='%.12g')

    # Main strategies.
    strategies = {}
    summaries = []
    audits = {}
    specifications = [
        ('tsmom_12m', '12-month TSMOM, net 10 bp', w_parts[12], cfg),
        ('tsmom_diversified', 'Diversified 1/3/12-month TSMOM, net 10 bp', w_div, cfg),
        ('tsmom_diversified_gross', 'Diversified TSMOM, zero fees', w_div,
         {**cfg, 'buy_fee': 0.0, 'sell_fee': 0.0}),
        ('benchmark_ew', 'Equal-weight nine ETFs, monthly, net 10 bp',
         equal_weight_weights(mpx.index, cfg['assets']), cfg),
        ('tsmom_diversified_longonly', 'Diagnostic: long leg only, net 10 bp', w_long, cfg),
        ('tsmom_diversified_shortonly', 'Diagnostic: short leg only, net 10 bp', w_short, cfg),
    ]
    for name, desc, w, c in specifications:
        daily, trades, m, checks = run_strategy(name, w, c, pivots, True, out)
        m['description'] = desc
        summaries.append(m)
        strategies[name] = daily
        audits[name] = checks

    # Pre-specified extensions: change one design element at a time.
    ext = cfg['extension']
    w_multi, d_multi = ts.build_weights(ts.multihorizon_signal(mpx, ext['multihorizon_months']), vol, cfg)
    w_skip, d_skip = ts.build_weights(ts.sign_signal(mpx, cfg['lookback_months'], skip=ext['skip_month']), vol, cfg)
    for name, desc, w in [
        ('tsmom_multihorizon', 'Extension: average sign at 1/3/6/12 months, net 10 bp', w_multi),
        ('tsmom_12_1', 'Extension: 12-month signal skipping the latest month, net 10 bp', w_skip),
    ]:
        daily, trades, m, checks = run_strategy(name, w, cfg, pivots, True, out)
        m['description'] = desc
        summaries.append(m)
        strategies[name] = daily
        audits[name] = checks

    # Portfolio-rescale diagnostic (not the paper's baseline).
    rescale_cfg = {**cfg, 'portfolio_rescale': True, 'portfolio_vol_target': 0.12}
    w_rescale, d_rescale, _ = diversified_weights(mpx, vol, rescale_cfg, cov)
    daily, trades, m, checks = run_strategy(
        'tsmom_diversified_volscale12', w_rescale, rescale_cfg, pivots, False, out)
    m['description'] = 'Diagnostic: diversified TSMOM rescaled to 12% ex-ante vol'
    summaries.append(m)
    audits['tsmom_diversified_volscale12'] = checks
    d_rescale.to_csv(out / 'weight_diagnostics_volscale12.csv', float_format='%.12g')

    summary = pd.DataFrame(summaries)
    cols = ['strategy', 'description', 'annual_return', 'annual_vol', 'sharpe',
            'sharpe_monthly', 'monthly_ann_return', 'monthly_ann_vol', 'max_drawdown',
            'calmar', 'worst_month', 'hit_rate_monthly', 'total_cost', 'cost_drag_annual',
            'annual_turnover', 'avg_gross_exposure', 'avg_net_exposure',
            'avg_long_assets', 'avg_short_assets', 'rebalance_days', 'terminal_nav', 'days']
    summary = summary[cols].sort_values('sharpe', ascending=False)
    summary.to_csv(out / 'strategy_summary.csv', index=False, float_format='%.12g')
    dump(out / 'audit.json', audits)

    # Predictability regressions (asset-level and pooled fixed effects).
    pred = stats.predictive_table(mret, mpx, [1, 3, 6, 12, 24], cfg)
    pred.to_csv(out / 'predictive_regressions.csv', index=False, float_format='%.12g')

    # Monthly returns for inference.
    mret_strategy = {name: monthly_returns(daily) for name, daily in strategies.items()}
    market_monthly = mret.mean(axis=1)
    monthly_table = pd.DataFrame(mret_strategy)
    monthly_table['market_ew'] = market_monthly
    monthly_table.to_csv(out / 'monthly_returns.csv', float_format='%.12g')

    # Alpha vs equal-weight benchmark; HAC.
    alpha_rows = []
    for name in ['tsmom_diversified', 'tsmom_diversified_gross', 'tsmom_12m',
                 'tsmom_multihorizon', 'tsmom_12_1', 'tsmom_diversified_longonly',
                 'tsmom_diversified_shortonly']:
        if name not in mret_strategy:
            continue
        a = stats.alpha_regression(mret_strategy[name], mret_strategy['benchmark_ew'], cfg['nw_lags'])
        a.update(strategy=name)
        alpha_rows.append(a)
    pd.DataFrame(alpha_rows).to_csv(out / 'alpha_tests.csv', index=False, float_format='%.12g')

    # Extreme market months.
    extreme = stats.extreme_table(mret_strategy['tsmom_diversified'], market_monthly, cfg['nw_lags'])
    extreme.to_csv(out / 'extreme_months.csv', index=False, float_format='%.12g')

    # Signal diagnostics: how often is the strategy long, and is the next-month
    # return actually higher after a positive signal? This separates a timing
    # edge from passive equity exposure.
    diag_rows = []
    first_signal_date = pd.Timestamp(cfg['start']) - pd.offsets.MonthEnd(1)
    for h in [1, 3, 6, 12, 24]:
        sig = np.sign(mpx / mpx.shift(h) - 1)
        y_next = mret.shift(-1)
        long = pd.concat([
            sig.stack(future_stack=True).rename('signal'),
            y_next.stack(future_stack=True).rename('ret'),
        ], axis=1).dropna().reset_index()
        long.columns = ['date', 'asset', 'signal', 'ret']
        long = long[long.date >= first_signal_date]
        pos = long.loc[long.signal > 0, 'ret']
        neg = long.loc[long.signal < 0, 'ret']
        res = stats.nw_regression(long.ret, long.signal, cfg['nw_lags'])
        diag_rows.append(dict(
            horizon_months=h,
            share_positive=float((long.signal > 0).mean()),
            share_negative=float((long.signal < 0).mean()),
            share_zero=float((long.signal == 0).mean()),
            n_pos=int(len(pos)), n_neg=int(len(neg)),
            mean_next_ret_pos=float(pos.mean()),
            mean_next_ret_neg=float(neg.mean()),
            difference=float(pos.mean() - neg.mean()),
            t_difference=float(res['t_beta']),
            n=int(len(long)),
        ))
    signal_diag = pd.DataFrame(diag_rows)
    signal_diag.to_csv(out / 'signal_diagnostics.csv', index=False, float_format='%.12g')

    # Correlation and market diagnostics used in the difference attribution.
    corr_d = dret.corr().to_numpy(float)
    corr_m = mret.corr().to_numpy(float)
    iu = np.triu_indices(len(cfg['assets']), 1)
    market_research = market_monthly.loc[pd.Timestamp(cfg['start']):]
    mkt = stats.mean_tstat(market_research, cfg['nw_lags'])
    mkt_sharpe = stats.sharpe(market_research, rf_annual=0.0, periods=12)
    diagnostics = dict(
        average_pairwise_correlation_daily=float(corr_d[iu].mean()),
        average_pairwise_correlation_monthly=float(corr_m[iu].mean()),
        min_pairwise_correlation_monthly=float(corr_m[iu].min()),
        market_equal_weight=dict(
            mean_monthly=mkt['mean'], t_mean=mkt['t'], n=int(mkt['n']),
            ann_return_arith=mkt_sharpe['ann_return'], ann_vol=mkt_sharpe['ann_vol'],
            sharpe_monthly=mkt_sharpe['sharpe'],
        ),
        signal_long_bias={int(r.horizon_months): float(r.share_positive)
                          for r in signal_diag.itertuples()},
        ex_ante_portfolio_vol=dict(
            mean=float(d_div.ex_ante_portfolio_vol.mean()),
            min=float(d_div.ex_ante_portfolio_vol.min()),
            max=float(d_div.ex_ante_portfolio_vol.max()),
            realized_monthly_ann_vol=float(monthly_table['tsmom_diversified'].std(ddof=1) * np.sqrt(12)),
        ),
        note=('Correlations and the equal-weight market use the same fixed nine-ETF '
              'snapshot. Long bias is the share of asset-month observations with a '
              'positive trailing-return sign.'),
    )
    dump(out / 'diagnostics.json', diagnostics)

    # Look-back sensitivity.
    look_rows = []
    for h in cfg['sensitivity']['lookbacks']:
        w = w_parts[h] if h in w_parts else ts.build_weights(signals[h], vol, cfg)[0]
        daily, _, m, _ = run_strategy(f'lookback_{h}m', w, cfg, pivots, False, out)
        g = {**cfg, 'buy_fee': 0.0, 'sell_fee': 0.0}
        daily_g, _, m_g, _ = run_strategy(f'lookback_{h}m_gross', w, g, pivots, False, out)
        look_rows.append(dict(lookback_months=h, ann_return=m['annual_return'], ann_vol=m['annual_vol'],
                              net_sharpe=m['sharpe'], gross_sharpe=m_g['sharpe'],
                              max_drawdown=m['max_drawdown'], annual_turnover=m['annual_turnover'],
                              avg_gross_exposure=m['avg_gross_exposure']))
    look = pd.DataFrame(look_rows)
    look.to_csv(out / 'sensitivity_lookback.csv', index=False, float_format='%.12g')

    # Cost sensitivity (same weights, different fees).
    cost_rows = []
    for bp in cfg['sensitivity']['cost_bps']:
        c = {**cfg, 'buy_fee': bp / 1e4, 'sell_fee': bp / 1e4}
        daily, _, m, _ = run_strategy(f'cost_{bp}bp', w_div, c, pivots, False, out)
        cost_rows.append(dict(cost_bps=bp, ann_return=m['annual_return'], ann_vol=m['annual_vol'],
                              sharpe=m['sharpe'], total_cost=m['total_cost'],
                              annual_turnover=m['annual_turnover']))
    cost = pd.DataFrame(cost_rows)
    cost.to_csv(out / 'sensitivity_cost.csv', index=False, float_format='%.12g')

    # Volatility-target sensitivity.
    vol_rows = []
    for vt in cfg['sensitivity']['vol_targets']:
        c = {**cfg, 'vol_target': vt}
        w, _, _ = diversified_weights(mpx, vol, c)
        daily, _, m, _ = run_strategy(f'voltarget_{vt}', w, c, pivots, False, out)
        vol_rows.append(dict(vol_target=vt, ann_return=m['annual_return'], ann_vol=m['annual_vol'],
                             sharpe=m['sharpe'], max_drawdown=m['max_drawdown'],
                             avg_gross_exposure=m['avg_gross_exposure']))
    voldf = pd.DataFrame(vol_rows)
    voldf.to_csv(out / 'sensitivity_vol_target.csv', index=False, float_format='%.12g')

    # Subperiod stability.
    sub_rows = []
    for start, end in cfg['sensitivity']['subperiods']:
        m = subperiod_metrics(strategies['tsmom_diversified'], start, end, cfg)
        m.update(period=f'{start}..{end}')
        sub_rows.append(m)
    subs = pd.DataFrame(sub_rows)
    subs.to_csv(out / 'sensitivity_subperiods.csv', index=False, float_format='%.12g')

    # Risk-free sensitivity for the Sharpe ratio.
    rf_rows = []
    for rf in cfg['sensitivity']['risk_free_annual']:
        s = stats.sharpe(mret_strategy['tsmom_diversified'], rf_annual=rf, periods=12)
        s.update(strategy='tsmom_diversified', risk_free_annual=rf)
        rf_rows.append(s)
    pd.DataFrame(rf_rows).to_csv(out / 'sensitivity_risk_free.csv', index=False, float_format='%.12g')

    # Figures.
    fig = out / 'figures'
    plot_series = {
        'Diversified TSMOM (net)': (strategies['tsmom_diversified'].date,
                                    strategies['tsmom_diversified'].nav, plots.BLUE),
        '12-month TSMOM (net)': (strategies['tsmom_12m'].date,
                                 strategies['tsmom_12m'].nav, plots.ORANGE),
        'Equal-weight benchmark': (strategies['benchmark_ew'].date,
                                   strategies['benchmark_ew'].nav, plots.AQUA),
        'Multi-horizon extension': (strategies['tsmom_multihorizon'].date,
                                    strategies['tsmom_multihorizon'].nav, plots.YELLOW),
    }
    plots.nav_plot(plot_series, fig)
    plots.gross_net_plot(strategies['tsmom_diversified'], strategies['tsmom_diversified_gross'], fig)
    plots.predictability_plot(pred, fig, horizon=12)
    plots.extreme_plot(extreme, fig)
    plots.lookback_plot(look, fig)
    plots.cost_plot(cost, fig)
    plots.exposure_plot(strategies['tsmom_diversified'], fig)
    plots.architecture_plot(fig)

    # Provenance.
    codepaths = [ROOT / 'run.py', ROOT / 'config.json', ROOT / 'pyproject.toml',
                 ROOT / 'RESEARCH_PROTOCOL.md', ROOT / 'PAPER.md'] + list((ROOT / 'src').glob('*.py'))
    provenance = dict(
        config=cfg, python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
        code_sha256={str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in codepaths if p.exists()},
        source_manifest_sha256=sha(ROOT / 'data/source_manifest.json'),
        research_days=len(strategies['tsmom_diversified']),
        research_start=str(strategies['tsmom_diversified'].date.iloc[0].date()),
        research_end=str(strategies['tsmom_diversified'].date.iloc[-1].date()),
        runtime_seconds=time.perf_counter() - tic,
        command=f'python run.py --config {args.config} --out {args.out}',
    )
    dump(out / 'run_manifest.json', provenance)

    print(summary.to_string(index=False))
    print(f'\nCOMPLETE {len(summary)} strategies; {provenance["runtime_seconds"]:.2f}s')


if __name__ == '__main__':
    main()
