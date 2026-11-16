"""Numerical invariants for integrated research components."""
import numpy as np
import pandas as pd
from quantcf.integration import paired_bootstrap, risk_scaled_series, monthly_metrics, portfolio_series

def test_identical_strategies_have_zero_paired_bootstrap_difference():
    s=pd.Series(np.sin(np.arange(60))*.03+.004,index=pd.date_range('2000-01-31',periods=60,freq='ME'))
    r=paired_bootstrap(s,s,repetitions=100)
    for key in ['delta_ann_mean','delta_sharpe','mean_ci_low','mean_ci_high','sharpe_ci_low','sharpe_ci_high']:
        assert abs(r[key])<1e-14

def test_risk_budget_is_causal_and_hits_target_before_cap():
    dates=pd.bdate_range('2018-01-01','2022-01-31')
    rng=np.random.default_rng(7)
    close=pd.DataFrame(100*np.exp(np.cumsum(rng.normal(.0002,.01,(len(dates),2)),axis=0)),index=dates,columns=['A','B'])
    formation=pd.Timestamp('2020-12-31')
    weights=pd.DataFrame([[.5,.5]],index=[formation],columns=close.columns)
    holding=pd.DatetimeIndex(['2021-01-31'])
    _,before=risk_scaled_series(close,weights,holding,target=.12)
    altered=close.copy(); altered.loc[altered.index>formation]*=2
    _,after=risk_scaled_series(altered,weights,holding,target=.12)
    assert abs(before.ex_ante_vol_after.iloc[0]-.12)<1e-12
    assert before.scale.iloc[0]==after.scale.iloc[0]
    _,capped=risk_scaled_series(close,weights,holding,target=10,max_gross=1)
    assert capped.gross_capped.iloc[0]
    assert abs(capped.gross_after.iloc[0]-1)<1e-12

def test_monthly_drawdown_includes_initial_capital():
    s=pd.Series([-.20,.10],index=pd.to_datetime(['2020-01-31','2020-02-29']))
    m=monthly_metrics(s)
    assert abs(m['max_drawdown']+.20)<1e-12
    assert m['cagr']<0

def test_exchange_month_ends_align_to_same_economic_month():
    from types import SimpleNamespace
    a=SimpleNamespace(monthly_portfolio=pd.DataFrame({'portfolio_return':[.01], 'holding_end_date':['2020-02-28']}))
    b=SimpleNamespace(monthly_portfolio=pd.DataFrame({'portfolio_return':[.02], 'holding_end_date':['2020-02-29']}))
    merged=pd.concat([portfolio_series(a),portfolio_series(b)],axis=1)
    assert len(merged)==1 and not merged.isna().any().any()
