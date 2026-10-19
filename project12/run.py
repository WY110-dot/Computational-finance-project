"""Offline reproducible research entry: uv run --frozen python run.py."""
import argparse, hashlib, json, platform, time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.data import load_panel,sha
from src.factors import calculate,as_long,forward_label,diagnose
from src.backtest import simulate,metrics,audit

ROOT=Path(__file__).resolve().parent
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def plots(out,results,ic,groups,factors,cfg):
    figdir=out/'figures';figdir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    colors=['#16697a','#df8b2c','#75815d','#9662a2','#c84d5d','#34495e']
    fig,ax=plt.subplots(figsize=(9,4))
    for (name,r),col in zip(results.items(),colors):ax.plot(r.date,r.nav,label=name,color=col,lw=1.1)
    ax.set(ylabel='Net NAV (initial = 1)',title='Next-open simulation after costs');ax.legend(fontsize=7,ncol=2);ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(figdir/'nav.png');plt.close(fig)
    fig,axs=plt.subplots(2,1,figsize=(9,5.5),sharex=True)
    for name,col in [('momentum_weekly',colors[0]),('momentum_monthly',colors[1]),('momentum_liquidity',colors[4])]:
        r=results[name];v=np.r_[1,r.nav];dd=1-v/np.maximum.accumulate(v)
        axs[0].plot(r.date,dd[1:],label=name,color=col,lw=.9)
        yearly=r.assign(year=r.date.dt.year).groupby('year').cost.sum()
        axs[1].plot(pd.to_datetime(yearly.index.astype(str)),yearly.values,label=name,color=col,marker='o')
    axs[0].set(ylabel='Drawdown');axs[0].invert_yaxis();axs[0].legend(fontsize=8)
    axs[1].set(ylabel='Annual costs (USD)');fig.tight_layout();fig.savefig(figdir/'risk_cost.png');plt.close(fig)
    fig,axs=plt.subplots(3,1,figsize=(9,6),sharex=True)
    for ax,(name,col) in zip(axs,zip(factors,colors)):
        ii=ic[ic.factor==name].set_index('date')
        ax.plot(ii.index,ii.rank_ic.rolling(60,min_periods=30).mean(),label='Rank IC (60-day mean)',color=col)
        ax.axhline(0,color='gray',lw=.7);ax.set_ylabel(name,fontsize=9);ax.grid(alpha=.15)
    axs[0].set_title('Cross-sectional rank correlation with next-open 5-day labels')
    fig.tight_layout();fig.savefig(figdir/'ic.png');plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(9,3.5))
    for (name,col) in zip(factors,colors):
        g=groups[groups.factor==name].groupby('group').mean_return.mean()
        axs[0].plot(g.index,g*100,marker='o',label=name,color=col)
        ff=factors[name];ff=ff.loc[(ff.index>=cfg['start'])&(ff.index<=cfg['end'])]
        ranked=ff.rank(axis=1,pct=True).to_numpy().ravel();ranked=ranked[np.isfinite(ranked)]
        axs[1].hist(ranked,bins=9,alpha=.35,label=name,color=col)
    axs[0].set(xlabel='Formation-time group (low to high)',ylabel='Mean 5-day label (%)',xticks=range(1,cfg['groups']+1))
    axs[0].legend(fontsize=8);axs[1].set(xlabel='Cross-sectional percentile rank',ylabel='Count')
    fig.tight_layout();fig.savefig(figdir/'groups.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,2.6));ax.axis('off')
    boxes=['Raw snapshot\nSHA-256','Validated panel\nNo zero filling','Factor registry\nClose t','Target weights\nTop 3','Cash ledger\nOpen t+1','Diagnostics\nAudit / report']
    for i,text in enumerate(boxes):
        x=.015+i*.166
        ax.text(x+.073,.5,text,ha='center',va='center',fontsize=8,bbox=dict(boxstyle='round,pad=.65',fc='#edf5f6',ec='#16697a'),transform=ax.transAxes)
        if i<5:ax.annotate('',xy=(x+.166,.5),xytext=(x+.15,.5),xycoords='axes fraction',arrowprops=dict(arrowstyle='->',color='#16697a'))
    fig.tight_layout();fig.savefig(figdir/'architecture.png');plt.close(fig)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='config.json');ap.add_argument('--out',default='outputs');args=ap.parse_args()
    cfg=json.loads((ROOT/args.config).read_text(encoding='utf-8'));out=ROOT/args.out;out.mkdir(parents=True,exist_ok=True);tic=time.perf_counter()
    panel,piv,quality=load_panel(ROOT,cfg)
    dump(out/'quality_report.json',quality);panel.to_csv(out/'clean_panel.csv',index=False,float_format='%.12g')
    factors=calculate(piv['close'],cfg['factor_windows']);as_long(factors).to_csv(out/'factors.csv',index=False,float_format='%.12g')
    labels=forward_label(piv['open'],cfg['label_horizon']);labels.to_csv(out/'forward_labels.csv',float_format='%.12g')
    ic,groups,fs=diagnose(factors,labels,cfg)
    ic.to_csv(out/'ic_timeseries.csv',index=False);groups.to_csv(out/'group_returns.csv',index=False);fs.to_csv(out/'factor_summary.csv',index=False)
    specs=[('momentum_weekly','momentum','weekly',False,False),('momentum_monthly','momentum','monthly',False,False),
           ('reversal_weekly','reversal','weekly',False,False),('low_vol_weekly','low_volatility','weekly',False,False),
           ('momentum_liquidity','momentum','weekly',True,False),('equal_weight_monthly','momentum','monthly',False,True)]
    results={};summary=[];audits={}
    for name,freq_factor,freq,limited,eq in specs:
        d,t,h=simulate(piv,factors[freq_factor],cfg,freq,limited,eq)
        audits[name]=audit(d,t,h,cfg);m=metrics(d,cfg)
        gcfg={**cfg,'buy_fee':0.,'sell_fee':0.}
        gd,gt,gh=simulate(piv,factors[freq_factor],gcfg,freq,limited,eq);audit(gd,gt,gh,gcfg)
        m.update(strategy=name,gross_rerun_total_return=metrics(gd,gcfg)['total_return'],
            net_gross_difference=metrics(gd,gcfg)['total_return']-m['total_return'],trade_count=int((t.executed_dollars.abs()>1e-7).sum()))
        summary.append(m);results[name]=d
        d.to_csv(out/f'{name}_daily.csv',index=False);t.to_csv(out/f'{name}_trades.csv',index=False);h.to_csv(out/f'{name}_holdings.csv',index=False)
        gd.to_csv(out/f'{name}_gross_daily.csv',index=False)
        print(name,round(m['total_return'],4),round(m['total_cost'],2),flush=True)
    sm=pd.DataFrame(summary);sm.to_csv(out/'strategy_summary.csv',index=False)
    dump(out/'audit.json',audits);plots(out,results,ic,groups,factors,cfg)
    codepaths=[ROOT/'run.py',ROOT/'download_data.py',ROOT/'config.json',ROOT/'pyproject.toml',ROOT/'uv.lock',ROOT/'RESEARCH_PROTOCOL.md']+list((ROOT/'src').glob('*.py'))
    provenance=dict(config=cfg,python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
        code_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in codepaths},source_manifest_sha256=sha(ROOT/'data/source_manifest.json'),
        research_days=len(results['momentum_weekly']),research_start=str(results['momentum_weekly'].date.iloc[0].date()),
        research_end=str(results['momentum_weekly'].date.iloc[-1].date()),runtime_seconds=time.perf_counter()-tic)
    dump(out/'run_manifest.json',provenance)
    print('COMPLETE',len(summary),'strategies; seconds',round(provenance['runtime_seconds'],2))

if __name__=='__main__':main()
