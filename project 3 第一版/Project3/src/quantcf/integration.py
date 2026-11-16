"""Unified two-universe experiments and corrected statistical diagnostics.

All position decisions use formation-date information. Research returns are
linear monthly price-return proxies; cash, financing and borrow assumptions
are disclosed explicitly. Reference factors are never inputs to ETF weights.
"""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .data import load_panel
from .tsmom import build_monthly_tsmom_dataset
from .research_backtest import run_research_backtest, calculate_monthly_metrics


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def monthly_metrics(s):
    m = calculate_monthly_metrics(s)
    return {k: m[k] for k in ('ann_mean','ann_vol','sharpe','cagr','max_drawdown','n_months')}


def panel_signals(panel, start, end):
    return build_monthly_tsmom_dataset(panel, evaluation_start=start,
        evaluation_end=end, min_vol_days=252, vol_ann_factor=261)['signals_df']


def portfolio_series(result):
    p = result.monthly_portfolio
    # Different exchanges have different final trading dates. Align economic
    # months rather than accidentally treating two month-ends as observations.
    index=pd.DatetimeIndex(pd.to_datetime(p.holding_end_date)).to_period('M').to_timestamp('M')
    return pd.Series(p.portfolio_return.to_numpy(), index=index)


def risk_scaled_series(close, weights, holding_index, target=.12, max_gross=6.):
    """Causal covariance normalization at formation close, before next returns.

    Cap is applied after targeting; realized volatility need not equal target.
    Input weights must have formation dates, not holding-end dates.
    """
    rets = close.pct_change(fill_method=None)
    cov = rets.ewm(com=60, adjust=True, min_periods=252).cov(bias=True)*261
    mp = close.groupby(close.index.to_period('M')).last()
    nextret = mp.pct_change(fill_method=None).shift(-1)
    values, records = [], []
    for date, row in weights.iterrows():
        v = row.reindex(close.columns).fillna(0.).to_numpy(float)
        c = cov.loc[date].reindex(index=close.columns, columns=close.columns).to_numpy(float)
        active = np.abs(v)>1e-16
        if active.any() and not np.isfinite(c[np.ix_(active,active)]).all():
            raise ValueError('Missing formation covariance for an active asset')
        c=np.nan_to_num(c)  # Ineligible ETFs have zero positions, not missing risk.
        variance = float(v @ c @ v)
        scale = target / np.sqrt(variance) if np.isfinite(variance) and variance > 1e-16 else 0.
        w = v*scale
        gross = np.abs(w).sum()
        capped = gross > max_gross
        if capped:
            w *= max_gross/gross
        y = nextret.loc[date.to_period('M')].to_numpy(float)
        active = np.abs(w)>1e-16
        if not np.isfinite(y[active]).all():
            raise ValueError('Missing holding return for a nonzero weight')
        values.append(float(w @ np.nan_to_num(y)))
        records.append({'formation_date':date, 'scale':scale,
            'ex_ante_vol_before':np.sqrt(variance) if np.isfinite(variance) else np.nan,
            'ex_ante_vol_after':float(np.sqrt(w @ c @ w)) if np.isfinite(c).all() else np.nan,
            'gross_after':np.abs(w).sum(), 'gross_capped':bool(capped)})
    return pd.Series(values,index=holding_index), pd.DataFrame(records)


def paired_bootstrap(a, b, seed=20261029, repetitions=2000, block=6):
    """Paired circular moving-block bootstrap; preserves month pairing.

    Percentile intervals describe sampling uncertainty, not a pre-registered
    strategy selection test. Both series and all considered variants retained.
    """
    z = pd.concat([a.rename('a'),b.rename('b')],axis=1).dropna().to_numpy(float)
    n=len(z)
    if n < 12:
        raise ValueError('Need at least 12 paired months')
    rng=np.random.default_rng(seed)
    stats=[]
    def sr(v):
        return np.sqrt(12)*v.mean()/v.std(ddof=1)
    for _ in range(repetitions):
        starts=rng.integers(0,n,size=int(np.ceil(n/block)))
        indices=((starts[:,None]+np.arange(block))%n).ravel()[:n]
        x=z[indices]
        stats.append([12*(x[:,0]-x[:,1]).mean(),sr(x[:,0])-sr(x[:,1])])
    ci=np.quantile(np.asarray(stats),[.025,.975],axis=0)
    return {'n_months':n,'repetitions':repetitions,'block_months':block,
        'delta_ann_mean':12*(z[:,0]-z[:,1]).mean(),
        'delta_sharpe':sr(z[:,0])-sr(z[:,1]),
        'mean_ci_low':ci[0,0],'mean_ci_high':ci[1,0],
        'sharpe_ci_low':ci[0,1],'sharpe_ci_high':ci[1,1]}


def diagnostic_regressions(panel, start, end, universe):
    """Eq. (3)-style single-lag signs and a separate 12M cumulative extension.

    Month-clustered covariance addresses contemporaneous cross-asset dependence.
    It is not HAC over time. ETF returns are proxies, not futures excess returns.
    """
    close=panel.pivot(index='date',columns='asset',values='close_adj').sort_index()
    vol=close.pct_change(fill_method=None).ewm(com=60,adjust=True,min_periods=252).var(bias=True).mul(261).pow(.5)
    dates=close.index.to_series().groupby(close.index.to_period('M')).max()
    px=close.loc[dates]
    r=px.pct_change(fill_method=None)
    sigma=vol.loc[dates]
    # At formation t, y is next-month return / sigma_t.
    y=r.shift(-1)/sigma
    rows=[]
    for kind, horizons in [('paper_eq3_single_month_lag',range(1,25)),('cumulative_12m_extension',[12])]:
        for h in horizons:
            x=np.sign(r.shift(h-1)) if kind.startswith('paper') else np.sign(px/px.shift(h)-1)
            z=pd.concat([x.stack(future_stack=True).rename('x'),y.stack(future_stack=True).rename('y')],axis=1).dropna().reset_index()
            z.columns=['formation_date','asset','x','y']
            holding=z.formation_date.dt.to_period('M')+1
            z=z[(holding>=pd.Period(start,'M'))&(holding<=pd.Period(end,'M'))]
            if len(z)<10 or z.x.std()==0:
                continue
            fit=sm.OLS(z.y.to_numpy(),sm.add_constant(z.x.to_numpy())).fit(cov_type='cluster',cov_kwds={'groups':z.formation_date.astype(str).to_numpy()})
            rows.append({'universe':universe,'model':kind,'lag_months':h,'beta':fit.params[1],
                't_beta_month_cluster':fit.tvalues[1],'p_beta':fit.pvalues[1],
                'n_obs':len(z),'n_month_clusters':z.formation_date.nunique(),
                'dependent_variable':'next_month_price_return / formation_EWMA_annual_vol',
                'fixed_effects':False})
    return pd.DataFrame(rows)


def run_integration(root, out):
    root,out=Path(root),Path(out)
    dst=out/'integration'; dst.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((root/'config/project2_tsmom.json').read_text(encoding='utf-8'))
    settings=json.loads((root/'config/integration.json').read_text(encoding='utf-8'))
    cn,_,_=load_panel(root,cfg['data'])
    cn['date']=pd.to_datetime(cn.date)
    manifest=json.loads((root/'data/us_sector/source_manifest.json').read_text())
    us=[]
    for item in manifest['files']:
        f=root/'data/us_sector'/f"{item['asset']}.csv"
        if digest(f)!=item['sha256']:
            raise ValueError(f'Snapshot checksum mismatch: {f.name}')
        p=pd.read_csv(f)
        us.append(pd.DataFrame({'date':pd.to_datetime(p.Date.str[:10]),'asset':item['asset'],
            'close_adj':p.Close,'open_adj':p.Open,'ret_total':p.Close.pct_change(fill_method=None)}))
    us=pd.concat(us,ignore_index=True).sort_values(['date','asset'])
    us=us[us.date<='2024-12-31']
    datasets={'CN21':cn,'US9':us}
    summary=[]; diagnostics=[]; all_returns={}; all_results={}
    for name,panel in datasets.items():
        start=settings['samples'][name]['start']; end=settings['samples'][name]['end']
        sig=panel_signals(panel,start,end)
        # Formation-date interval for the declared holding-period interval.
        lo=(pd.Timestamp(start).to_period('M')-1).start_time
        hi=(pd.Timestamp(end).to_period('M')-1).end_time
        res={}
        for mode in ['tsmom12','passive_long','multi_horizon','long_only_bridge']:
            result=run_research_backtest(sig,strategy_mode=mode,evaluation_start=lo,evaluation_end=hi)
            s=portfolio_series(result)
            if s.isna().any():
                raise AssertionError(f'{name}: missing portfolio return')
            res[mode]=result; all_returns[f'{name}_{mode}']=s
            row={'universe':name,'strategy':mode,'sample':'full',**monthly_metrics(s),
                'mean_gross':result.summary_metrics['mean_gross_exposure']}
            summary.append(row)
            common=s.loc[settings['common_start']:settings['common_end']]
            summary.append({'universe':name,'strategy':mode,'sample':'common',**monthly_metrics(common),
                'mean_gross':np.nan})
            result.monthly_weights.to_csv(dst/f'{name}_{mode}_weights.csv',index=False)
        all_results[name]=res
        close=panel.pivot(index='date',columns='asset',values='close_adj').sort_index()
        for mode in ['tsmom12','multi_horizon']:
            result=res[mode]
            weights=result.monthly_weights.pivot(index='formation_date',columns='asset',values='weight').fillna(0.)
            risk, record=risk_scaled_series(close,weights,portfolio_series(result).index,
                settings['portfolio_vol_target'],settings['max_gross'])
            all_returns[f'{name}_{mode}_risk12']=risk
            record.to_csv(dst/f'{name}_{mode}_risk12_diagnostics.csv',index=False)
            summary.append({'universe':name,'strategy':mode+'_risk12','sample':'full',**monthly_metrics(risk),
                'mean_gross':record.gross_after.mean()})
        diagnostics.append(diagnostic_regressions(panel,start,end,name))
    # Independent vectorized reconstruction must agree with the primary pipeline.
    saved=pd.read_csv(out/'research/R1_tsmom12_monthly_portfolio.csv')
    original=pd.Series(saved.portfolio_return.to_numpy(),index=pd.to_datetime(saved.holding_end_date))
    assert np.allclose(original,all_returns['CN21_tsmom12'],rtol=0,atol=1e-12)
    pd.DataFrame(summary).to_csv(dst/'unified_summary.csv',index=False)
    pd.concat(diagnostics).to_csv(dst/'predictive_regressions.csv',index=False)
    pd.concat(all_returns,axis=1).rename_axis('date').to_csv(dst/'monthly_returns.csv')
    bootstrap=[]
    for universe in datasets:
        for suffix in ['', '_risk12']:
            for block in settings['bootstrap_blocks']:
                b=paired_bootstrap(all_returns[f'{universe}_multi_horizon{suffix}'],all_returns[f'{universe}_tsmom12{suffix}'],
                    seed=settings['seed'],repetitions=settings['bootstrap_repetitions'],block=block)
                bootstrap.append({'universe':universe,'comparison':'multi_minus_12m'+suffix,**b})
    # Execution series compared at the same monthly observation frequency.
    execution={}
    for label in ['T1_base_3bps','T1_zero_0bps','T2_base_3bps','T3_base_3bps']:
        ledger=pd.read_csv(out/f'backtests/{label}_ledger.csv')
        date=pd.to_datetime(ledger.date)
        r=ledger.daily_return
        monthly=pd.Series(r.to_numpy(),index=date).groupby(date.dt.to_period('M').to_numpy()).apply(lambda s:(1+s).prod()-1)
        monthly.index=monthly.index.to_timestamp('M')
        execution[label]=monthly
    for block in settings['bootstrap_blocks']:
        bootstrap.append({'universe':'CN21','comparison':'execution_T2_minus_T1',**paired_bootstrap(
            execution['T2_base_3bps'],execution['T1_base_3bps'],seed=settings['seed'],
            repetitions=settings['bootstrap_repetitions'],block=block)})
    pd.DataFrame(bootstrap).to_csv(dst/'paired_bootstrap.csv',index=False)
    pd.concat(execution,axis=1).rename_axis('date').to_csv(dst/'execution_monthly_returns.csv')
    # Controlled bridge: research close-to-close -> next-open broker -> fees.
    result=all_results['CN21']['long_only_bridge']
    weights=result.monthly_weights
    sig=pd.read_csv(out/'signals/tsmom_monthly_signals.csv')
    sig['date']=pd.to_datetime(sig.date)
    normal=[]
    for date,g in weights.groupby('formation_date'):
        eligible=sig[(sig.date==date)&sig.formation_eligible]
        denominator=(1/eligible.sigma_ewma).sum()
        factor=.99/(.40*denominator/len(eligible))
        normal.append({'holding_end_date':g.holding_end_date.iloc[0],'factor':factor,
            'formation_date':date})
    scale=pd.DataFrame(normal)
    sr=portfolio_series(result)
    normalized=pd.Series(sr.to_numpy()*scale.factor.to_numpy(),index=sr.index)
    stages={'B0_research_long_short':all_returns['CN21_tsmom12'],
        'B1_remove_short':sr,'B2_normalize_budget_099':normalized,
        'B3_next_open_0bps':execution['T1_zero_0bps'],
        'B4_next_open_3bps':execution['T1_base_3bps']}
    pd.concat(stages,axis=1).rename_axis('date').to_csv(dst/'bridge_returns.csv')
    pd.DataFrame([{'stage':k,**monthly_metrics(v)} for k,v in stages.items()]).to_csv(dst/'bridge_summary.csv',index=False)
    finance=[]
    for rate in settings['funding_rates']:
        p=all_results['CN21']['tsmom12'].monthly_portfolio
        # Proxy only: negative net cash financing, no short proceeds haircut.
        borrow=np.maximum(p.net_exposure.to_numpy()-1,0)
        r=all_returns['CN21_tsmom12']-borrow*rate/12
        finance.append({'funding_rate':rate,'assumption':'charge max(net_exposure-1,0); no rebate/borrow fee',**monthly_metrics(r)})
    pd.DataFrame(finance).to_csv(dst/'funding_sensitivity.csv',index=False)
    alphas=[]; quarterly=[]
    for name in datasets:
        s=all_returns[f'{name}_tsmom12']; b=all_returns[f'{name}_passive_long']
        fit=sm.OLS(s.to_numpy(),sm.add_constant(b.to_numpy())).fit(cov_type='HAC',cov_kwds={'maxlags':6})
        alphas.append({'universe':name,'alpha_ann':fit.params[0]*12,'t_alpha_HAC6':fit.tvalues[0],
            'beta':fit.params[1],'n_months':len(s),'benchmark':'same risk-budget passive long; not original multi-factor alpha'})
        # Use complete, non-overlapping calendar quarters only.
        z=pd.concat([s.rename('strategy'),b.rename('market_proxy')],axis=1)
        q=z.groupby(z.index.to_period('Q')).agg(lambda x:(1+x).prod()-1)
        counts=z.groupby(z.index.to_period('Q')).size()
        q=q[counts==3]
        q['universe']=name; q['quarter']=q.index.astype(str)
        quarterly.append(q.reset_index(drop=True))
    pd.DataFrame(alphas).to_csv(dst/'benchmark_alpha.csv',index=False)
    q=pd.concat(quarterly); q.to_csv(dst/'quarterly_smile_proxy.csv',index=False)
    make_figures(out,all_returns,pd.DataFrame(summary),pd.DataFrame(bootstrap),q)
    return {'summary':summary,'bootstrap':bootstrap}


def make_figures(out,returns,summary,bootstrap,quarters):
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,
        'axes.grid':True,'grid.alpha':.18,'savefig.dpi':180})
    fig,axs=plt.subplots(1,2,figsize=(11,3.8))
    for ax,name in zip(axs,['CN21','US9']):
        for mode,label in [('tsmom12','12M TSMOM'),('passive_long','Passive long'),('multi_horizon','3/6/12M')]:
            s=returns[f'{name}_{mode}']; ax.plot(s.index,(1+s).cumprod(),label=label,lw=1.7)
        ax.set_title(name+' | full sample'); ax.set_ylabel('Growth of 1'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out/'figures/unified_nav.png'); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,3.6))
    for ax,name in zip(axs,['CN21','US9']):
        sub=summary[(summary.universe==name)&(summary['sample']=='full')]
        labels=['tsmom12','multi_horizon','tsmom12_risk12','multi_horizon_risk12']
        v=sub.set_index('strategy').loc[labels]
        ax.bar(['12M','Multi','12M risk12','Multi risk12'],v.sharpe,color=['#165B72','#D29C49']*2)
        ax.set_title(name+' | risk normalization'); ax.set_ylabel('Monthly Sharpe (annualized)')
    fig.tight_layout(); fig.savefig(out/'figures/risk_normalized.png'); plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,3.4))
    for ax,name in zip(axs,['CN21','US9']):
        z=quarters[quarters.universe==name]
        ax.scatter(z.market_proxy*100,z.strategy*100,s=18,alpha=.7,color='#165B72')
        ax.axhline(0,color='#888',lw=.6); ax.axvline(0,color='#888',lw=.6)
        ax.set_title(name+' | complete quarters'); ax.set_xlabel('Passive proxy return (%)'); ax.set_ylabel('12M return (%)')
    fig.tight_layout(); fig.savefig(out/'figures/quarterly_proxy.png'); plt.close(fig)
    # Published targets and new results shown together, with distinct samples.
    root=Path(__file__).resolve().parents[2]
    fig,axes=plt.subplots(2,2,figsize=(11,7),gridspec_kw={'height_ratios':[1,1.1]})
    for ax,path,label in [(axes[0,0],root/'references/fig2_upper_original.png','Original Fig. 2 | 58 futures | 1985-2009'),
                           (axes[1,0],root/'references/fig3_original.png','Original Fig. 3 | published figure')]:
        ax.imshow(plt.imread(path)); ax.set_axis_off(); ax.set_title(label,fontsize=10)
    single=pd.read_csv(out/'research/R1_single_asset_metrics.csv').sort_values('asset')
    axes[0,1].bar(single.asset.str.replace('.SH','',regex=False),single.sharpe,color='#17677B')
    axes[0,1].axhline(0,color='#888',lw=.6); axes[0,1].tick_params(axis='x',rotation=90,labelsize=6)
    axes[0,1].set_title('Replication | CN21 individual strategies',fontsize=10)
    axes[0,1].set_ylabel('Annualized monthly Sharpe')
    for mode,label in [('tsmom12','12M TSMOM'),('passive_long','Passive long')]:
        s=returns[f'CN21_{mode}']; axes[1,1].plot(s.index,(1+s).cumprod(),label=label)
    axes[1,1].set_yscale('log'); axes[1,1].set_ylabel('Growth of 1 (log scale)')
    axes[1,1].set_title('Replication | CN21 | 2020-2026',fontsize=10); axes[1,1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out/'figures/original_replication_targets.png'); plt.close(fig)
