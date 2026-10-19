"""Immutable raw CSV -> validated adjusted-price panel. No fill-zero cleaning."""
import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_panel(root, cfg):
    manifest=json.loads((root/'data/source_manifest.json').read_text())
    expected={x['asset']:x['sha256'] for x in manifest['files']}
    panels=[]; audits=[]
    # Warm-up is fixed, independent of results; only completed observations are used.
    warm_start=pd.Timestamp(cfg['start'])-pd.Timedelta(days=100)
    for asset in cfg['assets']:
        path=root/f'data/raw/{asset}.csv'
        if sha(path)!=expected[asset]: raise ValueError('Raw snapshot hash mismatch: '+asset)
        raw=pd.read_csv(path)
        required={'Date','Open','High','Low','Close','Volume'}
        if not required.issubset(raw):raise ValueError('Missing columns: '+asset)
        d=pd.DataFrame({'date':pd.to_datetime(raw.Date.astype(str).str[:10],errors='raise'),'asset':asset})
        if d.date.duplicated().any():raise ValueError('Duplicate keys: '+asset)
        was_sorted=d.date.is_monotonic_increasing
        for dest,src in [('open','Open'),('high','High'),('low','Low'),('close','Close'),('volume','Volume')]:
            d[dest]=pd.to_numeric(raw[src],errors='raise')
        for c in ['open','high','low','close','volume']:
            if np.isinf(d[c]).any():raise ValueError('Infinite value: '+asset+c)
        if (d[['open','high','low','close']]<=0).any().any() or (d.volume<0).any():raise ValueError('Invalid price/volume: '+asset)
        tol=d.close.abs()*1e-6
        invalid=(d.high+tol<d[['open','close','low']].max(axis=1))|(d.low-tol>d[['open','close','high']].min(axis=1))
        if invalid.any():raise ValueError('OHLC inconsistency: '+asset)
        # Source is already adjusted; keep no fictional raw price or adjustment factor.
        d=d.sort_values('date').reset_index(drop=True)
        d=d[(d.date>=warm_start)&(d.date<=cfg['end'])]
        audits.append(dict(asset=asset,raw_rows=len(raw),retained_rows=len(d),duplicate_keys=0,
            original_sorted=bool(was_sorted),missing_cells=int(d.isna().sum().sum()),invalid_rows=0,
            zero_volume=int((d.volume==0).sum()),first=str(d.date.min().date()),last=str(d.date.max().date()),
            missing_adjustment_factor=True))
        panels.append(d)
    panel=pd.concat(panels).sort_values(['date','asset']).reset_index(drop=True)
    calendar=pd.DatetimeIndex(sorted(panel.date.unique()))
    pivots={c:panel.pivot(index='date',columns='asset',values=c).reindex(index=calendar,columns=cfg['assets'])
            for c in ['open','high','low','close','volume']}
    quality=dict(assets=len(cfg['assets']),raw_rows=sum(x['raw_rows'] for x in audits),clean_rows=len(panel),
        calendar_days=len(calendar),missing_grid_cells=int(pivots['close'].isna().sum().sum()),by_asset=audits,
        cleaning='Sort dates; retain declared sample + 100 calendar warmup days. No interpolation, zero fill or return-based filtering.',
        calendar='Union of dates observed in the fixed ETF universe; not an independently supplied exchange holiday calendar.',
        price_basis='Source already-adjusted OHLC, inferred from repository stock.history default and absence of Adj Close. No independent original quotes/factors.',
        adjustment_limitation='Snapshot is not point-in-time; use adjusted units, no additional dividend cash. ADV uses adjusted-price times volume as a liquidity proxy, not certified dollar turnover.')
    return panel,pivots,quality
