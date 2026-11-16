"""Project 3 Pipeline: Data loading, label alignment, portfolio targets, and broker ledger execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from quantcf.data import load_panel, sha256_file
from quantcf.backtest import run_backtest, audit_backtest, BacktestConfig
from quantcf.tsmom import (
    LAMBDA_DEFAULT,
    ANN_FACTOR_VOL,
    calculate_ewma_volatility,
    extract_continuous_daily_returns_before_date,
    get_market_month_ends,
)


def load_universe_data(root: Path, cfg: Dict[str, Any], max_date: str = "2024-12-31") -> Dict[str, pd.DataFrame]:
    """Load both CN21 and US9 panels with strict checksum validation and P5 quarantine truncation."""
    root = Path(root)
    cutoff_dt = pd.Timestamp(max_date)
    
    # 1. Load CN21 panel
    # We load with full start/end from data config
    cn_cfg = {
        "source": "tushare",
        "start": "2019-01-01",
        "end": "2026-09-18",
        "evaluation_start": "2020-01-01",
        "evaluation_end": "2026-08-31",
        "holding_start": "2020-02-01",
        "holding_end": "2026-08-31",
        "adjustment_reference_date": "2026-09-18",
        "prices_snapshot": cfg["data"]["cn_prices_raw"],
        "adjustment_snapshot": cfg["data"]["cn_adjustments_raw"],
        "manifest": cfg["data"]["cn_source_manifest"],
        "require_manifest": True,
        "min_active_coverage": 0.95,
        "warmup_calendar_days": 420,
        "calendar": "union",
    }
    cn_panel, _, _ = load_panel(root, cn_cfg)
    cn_panel["date"] = pd.to_datetime(cn_panel["date"])
    cn_panel = cn_panel.sort_values(["date", "asset"]).reset_index(drop=True)
    
    # Check original span and apply strict P5 quarantine truncation
    cn_orig_max = cn_panel["date"].max()
    cn_panel = cn_panel[cn_panel["date"] <= cutoff_dt].copy().reset_index(drop=True)
    assert cn_panel["date"].max() <= cutoff_dt, f"CN21 panel max date {cn_panel['date'].max()} exceeds {cutoff_dt}"
    print(f"[DATA LOAD] CN21: Original snapshot max date {cn_orig_max.date()}, truncated to {cn_panel['date'].max().date()} (P5 strictly quarantined).")
    
    # 2. Load US9 panel
    us_manifest_path = root / cfg["data"]["us_source_manifest"]
    us_manifest = json.loads(us_manifest_path.read_text(encoding="utf-8"))
    
    us_list = []
    for item in us_manifest["files"]:
        asset_name = item["asset"]
        fpath = root / cfg["data"]["us_sector_dir"] / f"{asset_name}.csv"
        calc_sha = sha256_file(fpath)
        if calc_sha != item["sha256"]:
            raise ValueError(f"US9 checksum mismatch for {fpath.name}: expected {item['sha256']}, got {calc_sha}")
        
        p = pd.read_csv(fpath)
        # Dates are YYYY-MM-DD
        dt_col = pd.to_datetime(p["Date"].astype(str).str[:10])
        sub = pd.DataFrame({
            "date": dt_col,
            "asset": asset_name,
            "open_adj": p["Open"].astype(float),
            "close_adj": p["Close"].astype(float),
            "high_adj": p["High"].astype(float),
            "low_adj": p["Low"].astype(float),
            "volume": p["Volume"].astype(float),
        })
        # Calculate daily return
        sub["ret_total"] = sub["close_adj"].pct_change(fill_method=None)
        us_list.append(sub)
        
    us_panel = pd.concat(us_list, ignore_index=True).sort_values(["date", "asset"]).reset_index(drop=True)
    us_orig_max = us_panel["date"].max()
    us_panel = us_panel[us_panel["date"] <= cutoff_dt].copy().reset_index(drop=True)
    assert us_panel["date"].max() <= cutoff_dt, f"US9 panel max date {us_panel['date'].max()} exceeds {cutoff_dt}"
    print(f"[DATA LOAD] US9: Original snapshot max date {us_orig_max.date()}, truncated to {us_panel['date'].max().date()} (P5 strictly quarantined).")
    
    return {"CN21": cn_panel, "US9": us_panel}


def get_holding_periods(
    calendar_dates: List[pd.Timestamp],
    month_ends: List[pd.Timestamp],
    split_start: pd.Timestamp | str,
    split_end: pd.Timestamp | str,
) -> List[Dict[str, pd.Timestamp]]:
    """Determine non-overlapping monthly holding intervals strictly contained in [split_start, split_end].
    
    A holding period is defined by:
    - formation_date: month-end t
    - entry_date: first trading day strictly after t
    - exit_date: first trading day strictly after t+1
    
    The condition is:
    entry_date >= split_start and exit_date <= split_end.
    """
    cal_dates = sorted(set(pd.to_datetime(calendar_dates)))
    m_ends = sorted(set(pd.to_datetime(month_ends)))
    s_start = pd.to_datetime(split_start)
    s_end = pd.to_datetime(split_end)
    
    periods = []
    for i, t in enumerate(m_ends):
        if i + 1 >= len(m_ends):
            break
        next_m = m_ends[i + 1]
        
        # entry date
        entries = [d for d in cal_dates if d > t]
        if not entries:
            continue
        entry_d = entries[0]
        
        # exit date
        exits = [d for d in cal_dates if d > next_m]
        if not exits:
            continue
        exit_d = exits[0]
        
        if entry_d >= s_start and exit_d <= s_end:
            periods.append({
                "formation_date": t,
                "entry_date": entry_d,
                "next_formation_date": next_m,
                "exit_date": exit_d,
            })
            
    return periods


def compute_holding_labels(
    panel: pd.DataFrame,
    periods: List[Dict[str, pd.Timestamp]],
) -> pd.DataFrame:
    """Compute open-to-open holding labels: y(i, t) = open(exit) / open(entry) - 1."""
    piv_open = panel.pivot(index="date", columns="asset", values="open_adj").sort_index()
    
    records = []
    for p in periods:
        t = p["formation_date"]
        entry = p["entry_date"]
        exit_d = p["exit_date"]
        
        if entry not in piv_open.index or exit_d not in piv_open.index:
            continue
        
        row_entry = piv_open.loc[entry]
        row_exit = piv_open.loc[exit_d]
        
        for asset in piv_open.columns:
            p_en = row_entry.get(asset, np.nan)
            p_ex = row_exit.get(asset, np.nan)
            if not np.isnan(p_en) and not np.isnan(p_ex) and p_en > 0 and p_ex > 0:
                ret = float(p_ex / p_en - 1.0)
                records.append({
                    "formation_date": t,
                    "entry_date": entry,
                    "exit_date": exit_d,
                    "asset": asset,
                    "holding_return": ret,
                })
                
    return pd.DataFrame(records)


def assign_tercile_memberships(scores: pd.Series) -> Dict[str, Tuple[float, float, float]]:
    """Assign fractional memberships in [Bottom T1, Middle T2, Top T3] with exact tie-handling.
    
    Returns a dict mapping asset -> (m_T1, m_T2, m_T3) each in [0, 1].
    The sum of memberships for each group across all assets is exactly N/3.
    """
    valid = scores.dropna()
    N = len(valid)
    if N == 0:
        return {}
    
    mass_per_group = N / 3.0
    # Group intervals in continuous rank space [0, N]:
    # T1: [0, N/3]
    # T2: [N/3, 2N/3]
    # T3: [2N/3, N]
    
    # Sort assets by score ascending
    # Group assets by unique score to handle ties exactly
    unique_scores = sorted(valid.unique())
    
    # Track current cumulative mass
    cum = 0.0
    memberships = {}
    
    for val in unique_scores:
        ties = valid[valid == val].index.tolist()
        k = len(ties)
        start_rank = cum
        end_rank = cum + k
        cum = end_rank
        
        # Overlaps with T1, T2, T3
        # T1: [0, N/3]
        o_t1 = max(0.0, min(end_rank, mass_per_group) - max(start_rank, 0.0))
        # T2: [N/3, 2N/3]
        o_t2 = max(0.0, min(end_rank, 2.0 * mass_per_group) - max(start_rank, mass_per_group))
        # T3: [2N/3, N]
        o_t3 = max(0.0, min(end_rank, N) - max(start_rank, 2.0 * mass_per_group))
        
        # Per asset membership
        m1 = o_t1 / k
        m2 = o_t2 / k
        m3 = o_t3 / k
        
        for asset in ties:
            memberships[asset] = (m1, m2, m3)
            
    return memberships


def generate_portfolio_target_weights(
    df_factors: pd.DataFrame,
    periods: List[Dict[str, pd.Timestamp]],
    daily_panel: pd.DataFrame,
    calendar_dates: List[pd.Timestamp],
    strategy_mode: str,
    budget: float = 0.99,
    min_assets: int = 6,
    vol_decay: float = LAMBDA_DEFAULT,
    vol_ann_factor: float = ANN_FACTOR_VOL,
    min_vol_days: int = 252,
) -> pd.DataFrame:
    """Generate target portfolio weights for each formation date / entry date.
    
    Strategy modes:
    - 'A': Top tercile of factor A, weighted by inverse EWMA vol
    - 'B': Top tercile of factor B (F1), weighted by inverse EWMA vol
    - 'C': Top tercile of factor C (Combo), weighted by inverse EWMA vol
    - 'F2': Top tercile of factor F2, weighted by inverse EWMA vol
    - 'F3': Top tercile of factor F3, weighted by inverse EWMA vol
    - 'A0': Positive momentum sign assets from A0, weighted by inverse EWMA vol
    - 'passive_equal': Equal weight among all qualified assets (budget 0.99)
    - 'passive_inv_vol': Inverse volatility weight among all qualified assets (budget 0.99)
    """
    piv_ret = daily_panel.pivot(index="date", columns="asset", values="ret_total").sort_index()
    
    targets = []
    
    for p in periods:
        t = p["formation_date"]
        entry = p["entry_date"]
        period_added = False
        
        sub_factors = df_factors[df_factors["formation_date"] == t].set_index("asset")
        if len(sub_factors) < min_assets:
            # Insufficient qualified assets -> rebalance to 100% cash
            fallback_asset = piv_ret.columns[0]
            targets.append({
                "signal_date": t,
                "execution_date": entry,
                "asset": fallback_asset,
                "target_weight": 0.0,
            })
            continue
        
        qual_assets = sub_factors.index.tolist()
        
        # Compute EWMA volatilities at date t
        vols = {}
        for asset in qual_assets:
            if asset not in piv_ret.columns:
                continue
            s_ret = piv_ret[asset].loc[:t].dropna()
            continuous_rets = extract_continuous_daily_returns_before_date(s_ret, t, max_days=min_vol_days)
            if len(continuous_rets) < min_vol_days:
                continue
            vol = calculate_ewma_volatility(continuous_rets, decay=vol_decay, min_days=min_vol_days, ann_factor=vol_ann_factor)
            if not np.isnan(vol) and vol > 1e-6:
                vols[asset] = vol
                
        # Eligible assets must have valid volatility
        valid_assets = [a for a in qual_assets if a in vols]
        if len(valid_assets) < min_assets:
            # Insufficient assets with valid volatility -> rebalance to 100% cash
            fallback_asset = qual_assets[0] if qual_assets else piv_ret.columns[0]
            targets.append({
                "signal_date": t,
                "execution_date": entry,
                "asset": fallback_asset,
                "target_weight": 0.0,
            })
            continue
        
        # Determine strategy weights
        if strategy_mode in ["A", "B", "C", "F2", "F3"]:
            scores = sub_factors.loc[valid_assets, strategy_mode]
            if not scores.isna().all():
                memberships = assign_tercile_memberships(scores)
                
                # Group 3 is Top Tercile
                raw_weights = {}
                for asset in valid_assets:
                    m_top = memberships[asset][2]
                    if m_top > 0:
                        raw_weights[asset] = m_top / vols[asset]
                        
                tot = sum(raw_weights.values())
                if tot > 0:
                    for asset, rw in raw_weights.items():
                        targets.append({
                            "signal_date": t,
                            "execution_date": entry,
                            "asset": asset,
                            "target_weight": float((rw / tot) * budget),
                        })
                    period_added = True
                        
        elif strategy_mode == "A0":
            # P2 exact Long/Cash mapping: allocate inverse-vol budget over ALL qualified assets,
            # then multiply by positive sign max(s, 0). Negative signals remain unallocated in cash.
            inv_vols = {a: 1.0 / vols[a] for a in valid_assets}
            tot = sum(inv_vols.values())
            budgets = {a: budget * (iv / tot) for a, iv in inv_vols.items()} if tot > 0 else {}
            raw_signs = sub_factors.loc[valid_assets, "a0_raw"]
            for a in valid_assets:
                s = float(raw_signs.get(a, 0.0))
                if s > 0:
                    targets.append({
                        "signal_date": t,
                        "execution_date": entry,
                        "asset": a,
                        "target_weight": float(budgets[a]),
                    })
                    period_added = True
                    
        elif strategy_mode == "passive_equal":
            n_val = len(valid_assets)
            for a in valid_assets:
                targets.append({
                    "signal_date": t,
                    "execution_date": entry,
                    "asset": a,
                    "target_weight": float(budget / n_val),
                })
            period_added = True
                
        elif strategy_mode == "passive_inv_vol":
            inv_vols = {a: 1.0 / vols[a] for a in valid_assets}
            tot = sum(inv_vols.values())
            for a, iv in inv_vols.items():
                targets.append({
                    "signal_date": t,
                    "execution_date": entry,
                    "asset": a,
                    "target_weight": float((iv / tot) * budget),
                })
            period_added = True
        else:
            raise ValueError(f"Unknown strategy mode: {strategy_mode}")
            
        if not period_added:
            # If strategy produces no positive allocations (e.g. A0 in bear regime), actively rebalance to 0 (100% cash)
            fallback_asset = valid_assets[0] if valid_assets else piv_ret.columns[0]
            targets.append({
                "signal_date": t,
                "execution_date": entry,
                "asset": fallback_asset,
                "target_weight": 0.0,
            })
            
    df_targets = pd.DataFrame(targets)
    if df_targets.empty:
        return pd.DataFrame(columns=["signal_date", "execution_date", "asset", "target_weight"])
    return df_targets.sort_values(["execution_date", "asset"]).reset_index(drop=True)


def execute_broker_simulation(
    panel: pd.DataFrame,
    targets: pd.DataFrame,
    periods: List[Dict[str, pd.Timestamp]],
    calendar_dates: List[pd.Timestamp],
    cost_bps: float = 3.0,
    initial_cash: float = 1_000_000.0,
) -> Dict[str, Any]:
    """Execute target weights at next-open using shared P1 broker engine quantcf.backtest.run_backtest.
    
    Generates orders, fills, holdings, ledger, and monthly returns with exact open-to-open
    telescoping compounding and non-overlapping fee attribution.
    """
    if not periods:
        raise ValueError("No holding periods provided for backtest")
        
    fee_rate = cost_bps / 10_000.0
    start_date = periods[0]["entry_date"]
    end_date = periods[-1]["exit_date"]
    
    # Configure backtest using official P1 BacktestConfig
    cfg = BacktestConfig(
        initial_cash=initial_cash,
        buy_fee=fee_rate,
        sell_fee=fee_rate,
        slippage_bps=0.0,
        allow_fractional_units=True,
        capacity_limited=False,
        start=start_date,
        end=end_date,
    )
    
    # Execute through shared quantcf.backtest broker engine
    bt_res = run_backtest(
        prices=panel,
        targets=targets,
        config=cfg,
        run_audit=True,
    )
    
    df_ledger = bt_res.ledger.copy()
    df_orders = bt_res.orders.copy()
    df_fills = bt_res.fills.copy()
    df_holdings = bt_res.holdings.copy()
    audit_report = bt_res.audit
    
    if not audit_report.get("passed", False):
        raise AssertionError(f"P1 Broker backtest audit failed: {audit_report.get('max_errors')}")
        
    # Reconstruct exact open-to-open monthly holding period returns and non-overlapping fees
    ledger_by_date = df_ledger.set_index("date")
    monthly_ret_records = []
    
    for p in periods:
        en = p["entry_date"]
        ex = p["exit_date"]
        
        if en in ledger_by_date.index and ex in ledger_by_date.index:
            # Pre-rebalance equity at entry date open: W(T_k^-)
            w_entry_minus = float(ledger_by_date.loc[en, "pretrade_equity"])
            # Post-trade equity at entry date open: W(T_k^+)
            w_entry_post = float(ledger_by_date.loc[en, "posttrade_equity_at_open"])
            # Pre-rebalance equity at exit date open: W(T_{k+1}^-)
            w_exit_minus = float(ledger_by_date.loc[ex, "pretrade_equity"])
            
            # Net monthly holding period return: W(T_{k+1}^-) / W(T_k^-) - 1
            net_return = float(w_exit_minus / w_entry_minus - 1.0) if w_entry_minus > 0 else 0.0
            
            # Fee uniquely attributed to period k: incurred on entry date en (no overlap with ex)
            period_fee = float(ledger_by_date.loc[en, "transaction_cost"])
            period_turnover = float(ledger_by_date.loc[en, "turnover"])
            period_turnover_notional = float(ledger_by_date.loc[en, "turnover_notional"])
            
            monthly_ret_records.append({
                "formation_date": p["formation_date"],
                "entry_date": en,
                "exit_date": ex,
                "net_return": net_return,
                "turnover": period_turnover,
                "turnover_notional": period_turnover_notional,
                "fees": period_fee,
                "w_entry_pretrade": w_entry_minus,
                "w_entry_posttrade": w_entry_post,
                "w_exit_pretrade": w_exit_minus,
            })
            
    df_monthly_returns = pd.DataFrame(monthly_ret_records)
    
    # Assertions for reconciliation
    if not df_monthly_returns.empty:
        total_monthly_fees = float(df_monthly_returns["fees"].sum())
        total_ledger_fees = float(df_ledger["transaction_cost"].sum())
        total_fills_fees = float(df_fills["fee"].sum()) if not df_fills.empty else 0.0
        
        # 1. Non-overlapping fee attribution assertion
        assert np.isclose(total_monthly_fees, total_ledger_fees, atol=1e-4), (
            f"Monthly fees sum {total_monthly_fees} != ledger fees sum {total_ledger_fees}"
        )
        assert np.isclose(total_monthly_fees, total_fills_fees, atol=1e-4), (
            f"Monthly fees sum {total_monthly_fees} != fills fees sum {total_fills_fees}"
        )
        
        # 2. Telescoping compounding assertion
        compounded_prod = float(np.prod(1.0 + df_monthly_returns["net_return"].values))
        w_start = float(df_monthly_returns["w_entry_pretrade"].iloc[0])
        w_end = float(df_monthly_returns["w_exit_pretrade"].iloc[-1])
        nav_ratio = float(w_end / w_start)
        assert np.isclose(compounded_prod, nav_ratio, atol=1e-7), (
            f"Telescoping product {compounded_prod} != NAV ratio {nav_ratio}"
        )
        
        # Performance summary metrics
        r_series = df_monthly_returns["net_return"]
        n_m = len(r_series)
        ann_mean_arithmetic = float(r_series.mean() * 12.0)
        ann_vol = float(r_series.std(ddof=1) * np.sqrt(12.0)) if n_m > 1 else 0.0
        sharpe = float(ann_mean_arithmetic / ann_vol) if ann_vol > 1e-6 else np.nan
        
        # Monthly cumulative wealth and drawdown (strictly including initial NAV 1.0)
        cum_wealth_monthly = np.cumprod(np.insert(1.0 + r_series.values, 0, 1.0))
        cagr = float((cum_wealth_monthly[-1] ** (12.0 / n_m)) - 1.0) if n_m > 0 and cum_wealth_monthly[-1] > 0 else np.nan
        running_peak_monthly = np.maximum.accumulate(cum_wealth_monthly)
        dd_monthly = (cum_wealth_monthly - running_peak_monthly) / running_peak_monthly
        max_dd_monthly = float(np.min(dd_monthly)) if len(dd_monthly) > 0 else 0.0
        
        # Daily cumulative wealth and drawdown strictly bounded at final exit open
        ex_final = periods[-1]["exit_date"]
        pre_exit_ledger = df_ledger[df_ledger["date"] < ex_final]
        daily_equities = list(pre_exit_ledger["equity"].values)
        daily_equities.append(w_end)
        daily_nav_seq = np.insert(np.array(daily_equities, dtype=float) / initial_cash, 0, 1.0)
        running_peak_daily = np.maximum.accumulate(daily_nav_seq)
        dd_daily = (daily_nav_seq - running_peak_daily) / running_peak_daily
        max_dd_daily = float(np.min(dd_daily)) if len(dd_daily) > 0 else 0.0
        
        calmar = float(ann_mean_arithmetic / abs(max_dd_monthly)) if abs(max_dd_monthly) > 1e-6 else np.nan
        win_rate = float((r_series > 0).mean())
        
        summary_metrics = {
            "n_months": n_m,
            "ann_mean": ann_mean_arithmetic,
            "cagr": cagr,
            "ann_vol": ann_vol,
            "sharpe": sharpe,
            "max_drawdown": max_dd_monthly,
            "max_drawdown_daily": max_dd_daily,
            "calmar": calmar,
            "win_rate": win_rate,
            "total_turnover": float(df_monthly_returns["turnover"].sum()),
            "total_fees": total_monthly_fees,
            "w_start_open": w_start,
            "w_end_open": w_end,
            "cum_return": nav_ratio - 1.0,
            "cost_bps": cost_bps,
        }
    else:
        summary_metrics = {}
        
    return {
        "orders": df_orders,
        "fills": df_fills,
        "holdings": df_holdings,
        "ledger": df_ledger,
        "monthly_returns": df_monthly_returns,
        "audit": audit_report,
        "summary": summary_metrics,
    }
