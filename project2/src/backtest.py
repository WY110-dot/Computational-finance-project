"""Daily mark-to-market ledger for signed target weights.

This is a Project 2 extension of the Project 1 cash-ledger idea. Project 1 was
long-only and self-financing; TSMOM needs short positions and signed weights,
so the ledger here allows negative units and negative cash. No financing,
borrow fee, margin constraint or short-sale locate is modelled. The ledger is a
research total-return proxy, not a broker account.

Timing contract:
  * signal is formed at a month-end close t;
  * the target weight is executed at the next trading day's open t+1;
  * the position is marked at every close through the next rebalance.
"""
import numpy as np
import pandas as pd

from .tsmom import execution_map


def simulate(pivots, weights, cfg):
    """Run the signed-weight ledger. Returns (daily, trades)."""
    op, cl = pivots['open'], pivots['close']
    assets = list(op.columns)
    dates = op.index[(op.index >= pd.Timestamp(cfg['start'])) & (op.index <= pd.Timestamp(cfg['end']))]
    if len(dates) == 0:
        raise ValueError('Empty backtest window')
    execs = execution_map(weights.index, op.index, cfg['start'], cfg['end'])

    cash = float(cfg['initial_cash'])
    q = np.zeros(len(assets))
    last = np.full(len(assets), np.nan)
    hist = cl.loc[cl.index < dates[0]]
    if len(hist):
        last = hist.ffill().iloc[-1].to_numpy(float)
    stale = np.zeros(len(assets), int)
    prev_wealth = cash
    daily_rows, trade_rows = [], []

    for date in dates:
        o = op.loc[date].to_numpy(float)
        c = cl.loc[date].to_numpy(float)
        can_trade = np.isfinite(o) & (o > 0)
        mark_open = np.where(can_trade, o, last)
        if np.any((np.abs(q) > 1e-10) & ~np.isfinite(mark_open)):
            raise ValueError(f'Unmarkable holding on {date.date()}')
        nav_pre = cash + float(np.nansum(q * mark_open))
        if not (nav_pre > 0):
            raise AssertionError(f'Nonpositive pre-trade NAV on {date.date()}')

        cost = gross_traded = turnover = 0.0
        rebalance = date in execs
        if rebalance:
            signal_date = execs[date]
            w = np.nan_to_num(weights.loc[signal_date].reindex(assets).to_numpy(float), nan=0.0)
            target = w * nav_pre
            current = q * np.where(can_trade, o, 0.0)
            delta = np.where(can_trade, target - current, 0.0)
            fee = np.where(delta > 0, cfg['buy_fee'], cfg['sell_fee']) * np.abs(delta)
            cash -= float(delta.sum()) + float(fee.sum())
            q = q + np.divide(delta, o, out=np.zeros_like(q), where=can_trade)
            cost = float(fee.sum())
            gross_traded = float(np.abs(delta).sum())
            turnover = gross_traded / nav_pre
            for j, a in enumerate(assets):
                if abs(delta[j]) > 1e-9:
                    trade_rows.append(dict(
                        date=date, signal_date=signal_date, asset=a,
                        target_weight=float(w[j]), target_dollars=float(target[j]),
                        current_dollars=float(current[j]) if can_trade[j] else np.nan,
                        trade_dollars=float(delta[j]), fee=float(fee[j]),
                        execution_price=float(o[j]), units=float(delta[j] / o[j]),
                    ))

        valid = np.isfinite(c) & (c > 0)
        stale = np.where(valid, 0, stale + 1)
        last = np.where(valid, c, last)
        if np.any((np.abs(q) > 1e-10) & (stale > cfg['max_stale_days'])):
            raise ValueError(f'Stale price beyond limit on {date.date()}')
        values = q * np.nan_to_num(last)
        wealth = cash + float(values.sum())
        if not (wealth > 0):
            raise AssertionError(f'Nonpositive wealth on {date.date()}')
        daily_rows.append(dict(
            date=date, pretrade_wealth=nav_pre, wealth=wealth,
            nav=wealth / cfg['initial_cash'], daily_return=wealth / prev_wealth - 1,
            cost=cost, gross_traded=gross_traded, turnover=turnover,
            cash=cash, gross_exposure=float(np.abs(values).sum() / wealth),
            net_exposure=float(values.sum() / wealth),
            n_long=int((q > 1e-10).sum()), n_short=int((q < -1e-10).sum()),
            rebalance=rebalance, signal_date=execs.get(date),
        ))
        prev_wealth = wealth

    return pd.DataFrame(daily_rows), pd.DataFrame(trade_rows)


def audit(daily, trades, cfg):
    """Reconcile returns, cash, costs and timing; raise on any material error."""
    if len(daily) == 0:
        raise AssertionError('No daily rows')
    r = daily.daily_return.to_numpy(float)
    nav = daily.nav.to_numpy(float)
    prev = np.r_[1.0, nav[:-1]]
    errors = {
        'returns': float(np.max(np.abs(nav / prev - 1 - r))),
        'compound': abs(float(np.prod(1 + r)) - float(nav[-1])),
        'nav_definition': float(np.max(np.abs(nav - daily.wealth.to_numpy(float) / cfg['initial_cash']))),
        'cost_nonnegative': float(max(0.0, -daily.cost.min())),
        'turnover_definition': float(np.max(np.abs(
            daily.turnover.to_numpy(float)
            - np.divide(daily.gross_traded.to_numpy(float), daily.pretrade_wealth.to_numpy(float),
                        out=np.zeros(len(daily)), where=daily.pretrade_wealth.to_numpy(float) > 0)
        ))),
    }

    if len(trades):
        if not (pd.to_datetime(trades.signal_date) < pd.to_datetime(trades.date)).all():
            raise AssertionError('Signal/execution timing')
        t = trades.groupby('date').agg(delta=('trade_dollars', 'sum'), fee=('fee', 'sum'))
        t = t.reindex(daily.date).fillna(0.0)
        cash_recon = cfg['initial_cash'] - t.delta.cumsum() - t.fee.cumsum()
        errors['cash_ledger'] = float(np.max(np.abs(cash_recon.to_numpy(float) - daily.cash.to_numpy(float))))
        errors['fee_sum'] = abs(float(trades.fee.sum()) - float(daily.cost.sum()))

    if max(errors.values()) > 1e-5:
        raise AssertionError(errors)

    # The gross cap is a target-at-rebalance constraint; drift after execution
    # is allowed. Check only rebalance days.
    reb = daily[daily.rebalance]
    if len(reb):
        max_gross = float(cfg.get('max_gross_exposure', np.inf))
        if np.isfinite(max_gross) and (reb.gross_exposure > max_gross * 1.02 + 1e-9).any():
            raise AssertionError('Gross exposure cap breached')
    return errors


def monthly_returns(daily):
    """Compounded monthly strategy returns indexed by the last trading date."""
    tmp = daily[['date', 'daily_return']].copy()
    tmp['period'] = tmp.date.dt.to_period('M')
    g = tmp.groupby('period')
    vals = g.daily_return.apply(lambda x: float(np.prod(1 + x) - 1))
    idx = pd.DatetimeIndex(g.date.max().to_numpy())
    return pd.Series(vals.to_numpy(float), index=idx, name='return')


def metrics(daily, cfg):
    r = daily.daily_return.astype(float)
    n = len(r)
    A = float(cfg['annualization'])
    rf = float(cfg.get('daily_risk_free', 0.0))
    nav = daily.nav.astype(float)
    total = float(nav.iloc[-1] - 1)
    ann_return = float(nav.iloc[-1] ** (A / n) - 1) if nav.iloc[-1] > 0 else np.nan
    ann_vol = float(r.std(ddof=1) * np.sqrt(A)) if n > 1 else np.nan
    excess = r - rf
    sharpe = float(np.sqrt(A) * excess.mean() / excess.std(ddof=1)) if excess.std(ddof=1) > 0 else np.nan
    wealth = np.r_[1.0, nav.to_numpy(float)]
    drawdown = 1 - wealth / np.maximum.accumulate(wealth)
    max_dd = float(drawdown.max())
    monthly = monthly_returns(daily)
    # Monthly statistics are the like-for-like comparison with the paper,
    # which reports monthly Sharpe ratios and annualized monthly volatility.
    if len(monthly) > 1 and monthly.std(ddof=1) > 0:
        m_mean = float(monthly.mean())
        m_vol = float(monthly.std(ddof=1) * np.sqrt(12))
        m_sharpe = float(m_mean / monthly.std(ddof=1) * np.sqrt(12))
    else:
        m_mean = m_vol = m_sharpe = np.nan
    avg_wealth = float(daily.wealth.mean()) if n else np.nan
    years = n / A
    cost_drag = (float(daily.cost.sum()) / avg_wealth / years
                 if avg_wealth > 0 and years > 0 else np.nan)
    return dict(
        days=n, total_return=total, annual_return=ann_return, annual_vol=ann_vol,
        sharpe=sharpe, max_drawdown=max_dd,
        calmar=float(ann_return / abs(max_dd)) if max_dd > 0 else np.nan,
        monthly_ann_return=float(m_mean * 12) if np.isfinite(m_mean) else np.nan,
        monthly_ann_vol=m_vol, sharpe_monthly=m_sharpe,
        worst_month=float(monthly.min()) if len(monthly) else np.nan,
        best_month=float(monthly.max()) if len(monthly) else np.nan,
        hit_rate_monthly=float((monthly > 0).mean()) if len(monthly) else np.nan,
        total_cost=float(daily.cost.sum()),
        cost_drag_annual=float(cost_drag),
        annual_turnover=float(daily.turnover.sum() * A / n),
        total_turnover=float(daily.turnover.sum()),
        avg_gross_exposure=float(daily.gross_exposure.mean()),
        avg_net_exposure=float(daily.net_exposure.mean()),
        avg_long_assets=float(daily.n_long.mean()),
        avg_short_assets=float(daily.n_short.mean()),
        rebalance_days=int(daily.rebalance.sum()),
        terminal_nav=float(nav.iloc[-1]),
    )


def subperiod_metrics(daily, start, end, cfg):
    sub = daily[(daily.date >= pd.Timestamp(start)) & (daily.date <= pd.Timestamp(end))]
    # Rebase NAV to 1 at the start of the subperiod so drawdown is local.
    if len(sub) == 0:
        return dict(days=0)
    sub = sub.copy()
    sub['nav'] = (1 + sub.daily_return).cumprod()
    return metrics(sub, cfg)
