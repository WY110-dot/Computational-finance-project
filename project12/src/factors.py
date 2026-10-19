"""Registration keeps factor formulas outside the simulator."""
import numpy as np
import pandas as pd

REGISTRY={}
def register(name):
    def wrap(fn):REGISTRY[name]=fn;return fn
    return wrap

@register('momentum')
def momentum(close,window):return close/close.shift(window)-1

@register('reversal')
def reversal(close,window):return -(close/close.shift(window)-1)

@register('low_volatility')
def low_volatility(close,window):return -close.pct_change(fill_method=None).rolling(window,min_periods=window).std(ddof=1)

def calculate(close,windows):return {name:REGISTRY[name](close,w) for name,w in windows.items()}

def as_long(factors):
    rows=[]
    for name,f in factors.items():
        t=f.rename_axis(index='date',columns='asset').stack(future_stack=True).rename('value').reset_index()
        t['factor']=name;rows.append(t[['date','asset','factor','value']])
    return pd.concat(rows,ignore_index=True)

def forward_label(open_price,h):
    # signal t close -> entry open t+1 -> exit open t+1+h
    return open_price.shift(-(h+1))/open_price.shift(-1)-1

def groups_at_formation(scores,k,min_assets):
    v=scores.dropna()
    if len(v)<max(min_assets,k) or v.nunique()<2:return pd.Series(dtype=int)
    # Ties split deterministically by ticker, never by a future return.
    order=sorted(v.index,key=lambda a:(v[a],a))
    return pd.Series({a:1+int(i*k/len(order)) for i,a in enumerate(order)},dtype=int)

def diagnose(factors,labels,cfg):
    ic=[];group_rows=[];summary=[]
    valid_dates=labels.index[(labels.index>=cfg['start'])&(labels.index<=cfg['end'])]
    for name,f in factors.items():
        ff=f.loc[valid_dates]
        for date,scores in ff.iterrows():
            y=labels.loc[date];mask=scores.notna()&y.notna();xv=scores[mask];yv=y[mask]
            valid=len(xv)>=cfg['min_assets'] and xv.nunique()>1 and yv.nunique()>1
            ic.append(dict(date=date,factor=name,n_factor=int(scores.notna().sum()),n_label=int(mask.sum()),
                ic=float(xv.corr(yv)) if valid else np.nan,
                rank_ic=float(xv.rank(method='average').corr(yv.rank(method='average'))) if valid else np.nan))
            membership=groups_at_formation(scores,cfg['groups'],cfg['min_assets'])
            for k in range(1,cfg['groups']+1):
                assets=membership[membership==k].index;ys=y.reindex(assets).dropna()
                group_rows.append(dict(date=date,factor=name,group=k,n_formed=len(assets),n_valid=len(ys),
                    mean_return=float(ys.mean()) if len(ys) else np.nan))
        flat=ff.to_numpy().ravel();flat=flat[np.isfinite(flat)]
        summary.append(dict(factor=name,coverage=len(flat)/ff.size,mean=float(flat.mean()),std=float(flat.std(ddof=1)),
            p01=float(np.quantile(flat,.01)),p50=float(np.median(flat)),p99=float(np.quantile(flat,.99))))
    ic=pd.DataFrame(ic);groups=pd.DataFrame(group_rows);summ=pd.DataFrame(summary).set_index('factor')
    for name in factors:
        ii=ic[ic.factor==name]
        for c in ['ic','rank_ic']:
            summ.loc[name,c+'_mean']=ii[c].mean();summ.loc[name,c+'_std']=ii[c].std(ddof=1)
            summ.loc[name,c+'_days']=ii[c].count()
        summ.loc[name,'mean_effective_assets']=ii.n_label.mean()
    return ic,groups,summ.reset_index()
