"""Next-open, long-only, self-financing cash ledger in adjusted-price units."""
import numpy as np
import pandas as pd

def rebalance_dates(index,frequency):
    if frequency=='daily':return set(index)
    if frequency not in ('weekly','monthly'):raise ValueError('Unknown frequency')
    periods=index.to_period('W-FRI' if frequency=='weekly' else 'M')
    return set(index[np.r_[True,periods[1:]!=periods[:-1]]])

def allocate(demand,caps,cash,buy_fee,sell_fee):
    """Dollar orders, sales first then proportional buys; never borrow."""
    demand=np.asarray(demand,float);caps=np.asarray(caps,float)
    sell=np.minimum(np.maximum(-demand,0),caps)
    available=cash+sell.sum()*(1-sell_fee)
    buy=np.minimum(np.maximum(demand,0),caps)
    if buy.sum()*(1+buy_fee)>available:buy*=max(available,0)/(buy.sum()*(1+buy_fee))
    cost=buy.sum()*buy_fee+sell.sum()*sell_fee
    cash_end=cash+sell.sum()-buy.sum()-cost
    if cash_end < -1e-6:raise AssertionError('negative cash')
    return buy,sell,max(cash_end,0),cost

def simulate(pivots,scores,cfg,frequency='weekly',limited=False,equal_weight=False):
    op,cl,vol=pivots['open'],pivots['close'],pivots['volume']
    assets=list(op.columns);dates=op.index[(op.index>=cfg['start'])&(op.index<=cfg['end'])]
    when=rebalance_dates(dates,frequency)
    # Only lagged capacity, never the completed volume of the execution day.
    adv=(cl*vol).rolling(cfg['adv_window'],min_periods=cfg['adv_window']).mean().shift(1)
    cash=float(cfg['initial_cash']);q=np.zeros(len(assets));last=np.full(len(assets),np.nan);stale=np.zeros(len(assets),int)
    daily=[];trades=[];holdings=[];previous=cash
    # Initial stale mark can only come from the completed warmup history.
    hist=cl.loc[cl.index<dates[0]]
    if len(hist):last=hist.ffill().iloc[-1].to_numpy(float)
    for date in dates:
        i=op.index.get_loc(date);opening=op.loc[date].to_numpy(float);closing=cl.loc[date].to_numpy(float)
        can_trade=np.isfinite(opening)&(opening>0)
        mark=np.where(can_trade,opening,last)
        if np.any((q>1e-10)&~np.isfinite(mark)):raise ValueError('unmarkable holding')
        marked=q*np.nan_to_num(mark);pre=cash+marked.sum();b=s=cost=requested=unfilled=0.;reb=date in when
        if reb:
            signal=scores.iloc[i-1] if i else pd.Series(np.nan,index=assets)
            eligible=signal.dropna()
            if len(eligible)>=cfg['min_assets']:
                chosen=list(eligible.index) if equal_weight else sorted(eligible.index,key=lambda a:(-eligible[a],a))[:cfg['top_n']]
                target=np.array([cfg['invest_fraction']/len(chosen) if a in chosen else 0 for a in assets])*pre
                demand=target-marked
                caps=np.where(can_trade,np.inf,0.)
                if limited:caps=np.minimum(caps,np.nan_to_num(adv.loc[date].to_numpy(float),nan=0.)*cfg['participation'])
                buys,sells,cash,cost=allocate(demand,caps,cash,cfg['buy_fee'],cfg['sell_fee'])
                executed=buys-sells;q+=np.divide(executed,opening,out=np.zeros_like(q),where=can_trade)
                if q.min() < -1e-7:raise AssertionError('short holding')
                q=np.maximum(q,0);b=buys.sum();s=sells.sum();requested=np.abs(demand).sum();unfilled=np.abs(demand-executed).sum()
                for j,a in enumerate(assets):
                    if abs(demand[j])>1e-7:
                        trades.append(dict(date=date,signal_date=op.index[i-1],asset=a,requested_dollars=demand[j],
                            executed_dollars=executed[j],fee=buys[j]*cfg['buy_fee']+sells[j]*cfg['sell_fee'],
                            execution_price=opening[j],capacity=caps[j] if np.isfinite(caps[j]) else np.nan,
                            unfilled_dollars=abs(demand[j]-executed[j])))
        valid=np.isfinite(closing)&(closing>0);stale=np.where(valid,0,stale+1);last=np.where(valid,closing,last)
        if np.any((q>1e-10)&(stale>cfg['max_stale_days'])):raise ValueError('holding lacks price beyond stale limit')
        values=q*np.nan_to_num(last);wealth=cash+values.sum()
        if wealth<=0:raise AssertionError('nonpositive wealth')
        ret=wealth/previous-1
        daily.append(dict(date=date,pretrade_wealth=pre,wealth=wealth,nav=wealth/cfg['initial_cash'],daily_return=ret,
            buy=b,sell=s,cost=cost,turnover=(b+s)/pre,cash=cash,requested=requested,unfilled=unfilled,
            holdings=int((q>1e-8).sum()),max_weight=values.max()/wealth,stale_positions=int(((q>1e-8)&~valid).sum()),
            rebalance=reb))
        for j,a in enumerate(assets):holdings.append(dict(date=date,asset=a,adjusted_units=q[j],mark=last[j],value=values[j],weight=values[j]/wealth))
        previous=wealth
    return pd.DataFrame(daily),pd.DataFrame(trades),pd.DataFrame(holdings)

def metrics(daily,cfg):
    r=daily.daily_return;wealth=np.r_[cfg['initial_cash'],daily.wealth.to_numpy()]
    excess=r-cfg['daily_risk_free'];n=len(r);A=cfg['annualization'];total=wealth[-1]/wealth[0]-1
    return dict(days=n,total_return=total,annual_return=(1+total)**(A/n)-1,annual_vol=float(r.std(ddof=1)*np.sqrt(A)),
        sharpe=float(np.sqrt(A)*excess.mean()/excess.std(ddof=1)) if excess.std(ddof=1)>0 else None,
        max_drawdown=float((1-wealth/np.maximum.accumulate(wealth)).max()),total_cost=float(daily.cost.sum()),
        annual_turnover=float(daily.turnover.sum()*A/n),total_turnover=float(daily.turnover.sum()),
        mean_holdings=float(daily.holdings.mean()),max_weight=float(daily.max_weight.max()),
        fill_ratio=float(1-daily.unfilled.sum()/daily.requested.sum()) if daily.requested.sum()>0 else 1.,
        terminal_wealth=float(wealth[-1]))

def audit(daily,trades,holdings,cfg):
    prev=np.r_[cfg['initial_cash'],daily.wealth.to_numpy()[:-1]]
    errors={
        'returns':float(np.max(abs(daily.wealth.to_numpy()/prev-1-daily.daily_return.to_numpy()))),
        'compound':abs(float(np.prod(1+daily.daily_return))-float(daily.nav.iloc[-1])),
        'valuation':float(abs(holdings.groupby('date').value.sum().to_numpy()+daily.cash.to_numpy()-daily.wealth.to_numpy()).max()),
        'cost':float(abs(daily.cost-cfg['buy_fee']*daily.buy-cfg['sell_fee']*daily.sell).max()),
        'cash_ledger':float(abs(daily.cash.to_numpy()-(cfg['initial_cash']+np.cumsum(daily.sell-daily.buy-daily.cost))).max())}
    if max(errors.values())>1e-5:raise AssertionError(errors)
    if (daily.cash < -1e-6).any() or (holdings.adjusted_units < -1e-8).any():raise AssertionError('cash/position')
    if len(trades):
        if not (pd.to_datetime(trades.signal_date)<pd.to_datetime(trades.date)).all():raise AssertionError('timing')
        if abs(trades.fee.sum()-daily.cost.sum())>1e-5:raise AssertionError('trade fee sum')
        limited=trades.capacity.notna()
        if (trades.loc[limited,'executed_dollars'].abs()>trades.loc[limited,'capacity']+1e-6).any():raise AssertionError('capacity')
        filled=trades[trades.executed_dollars.abs()>1e-8].copy()
        filled['units']=filled.executed_dollars/filled.execution_price
        observed=holdings.pivot(index='date',columns='asset',values='adjusted_units')
        changes=filled.pivot_table(index='date',columns='asset',values='units',aggfunc='sum').reindex(index=observed.index,columns=observed.columns).fillna(0)
        errors['position_ledger']=float(abs(observed-changes.cumsum()).to_numpy().max())
        errors['position_valuation']=float(abs(holdings.value-holdings.adjusted_units*holdings.mark).max())
        if max(errors.values())>1e-5:raise AssertionError(errors)
    return errors
