"""Immutable raw CSV -> validated adjusted-price panel.

Reused from Project 1 (`project12/src/data.py`) with one change: the warm-up
start is an explicit config value, so a 12-month signal and a 60-day EWMA
volatility estimate are fully seeded before the research sample begins.

The source CSV files are already-adjusted OHLC. No original price, adjustment
factor or dividend cash flow is fabricated. Missing cells are never filled
with zero and extreme returns are never dropped.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):
    """SHA-256 with CRLF -> LF canonicalization.

    The upstream manifest was produced from LF files. Windows checkouts with
    core.autocrlf=true otherwise change only the line endings and break a
    byte-for-byte comparison, so hashes are computed on canonical LF bytes.
    """
    data = Path(path).read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def load_panel(root, cfg):
    """Validate the fixed snapshot and return (long panel, pivots, quality)."""
    root = Path(root)
    manifest = json.loads((root / 'data/source_manifest.json').read_text(encoding='utf-8'))
    expected = {x['asset']: x['sha256'] for x in manifest['files']}
    warm_start = pd.Timestamp(cfg.get('warmup_start', cfg['start']))
    end = pd.Timestamp(cfg['end'])

    panels, audits = [], []
    for asset in cfg['assets']:
        path = root / f'data/raw/{asset}.csv'
        if not path.exists():
            raise FileNotFoundError(f'Missing raw snapshot: {asset}')
        if sha(path) != expected[asset]:
            raise ValueError(f'Raw snapshot hash mismatch: {asset}')

        raw = pd.read_csv(path)
        required = {'Date', 'Open', 'High', 'Low', 'Close', 'Volume'}
        if not required.issubset(raw.columns):
            raise ValueError(f'Missing columns: {asset}')

        d = pd.DataFrame({
            'date': pd.to_datetime(raw.Date.astype(str).str[:10], errors='raise'),
            'asset': asset,
        })
        if d.date.duplicated().any():
            raise ValueError(f'Duplicate keys: {asset}')

        was_sorted = d.date.is_monotonic_increasing
        for dest, src in [('open', 'Open'), ('high', 'High'), ('low', 'Low'),
                          ('close', 'Close'), ('volume', 'Volume')]:
            d[dest] = pd.to_numeric(raw[src], errors='raise')
        for c in ['open', 'high', 'low', 'close', 'volume']:
            if np.isinf(d[c]).any():
                raise ValueError(f'Infinite value: {asset}{c}')
        if (d[['open', 'high', 'low', 'close']] <= 0).any().any() or (d.volume < 0).any():
            raise ValueError(f'Invalid price/volume: {asset}')

        tol = d.close.abs() * 1e-6
        invalid = ((d.high + tol < d[['open', 'close', 'low']].max(axis=1)) |
                   (d.low - tol > d[['open', 'close', 'high']].min(axis=1)))
        if invalid.any():
            raise ValueError(f'OHLC inconsistency: {asset}')

        d = d.sort_values('date').reset_index(drop=True)
        d = d[(d.date >= warm_start) & (d.date <= end)]
        if len(d) == 0:
            raise ValueError(f'No rows in declared window: {asset}')
        if d.date.min() > warm_start + pd.Timedelta(days=10):
            raise ValueError(f'Insufficient warm-up history for {asset}: starts {d.date.min()}')

        audits.append(dict(
            asset=asset, raw_rows=len(raw), retained_rows=len(d),
            duplicate_keys=0, original_sorted=bool(was_sorted),
            missing_cells=int(d.isna().sum().sum()), invalid_rows=0,
            zero_volume=int((d.volume == 0).sum()),
            first=str(d.date.min().date()), last=str(d.date.max().date()),
            missing_adjustment_factor=True,
        ))
        panels.append(d)

    panel = pd.concat(panels).sort_values(['date', 'asset']).reset_index(drop=True)
    calendar = pd.DatetimeIndex(sorted(panel.date.unique()))
    pivots = {
        c: panel.pivot(index='date', columns='asset', values=c)
        .reindex(index=calendar, columns=cfg['assets'])
        for c in ['open', 'high', 'low', 'close', 'volume']
    }
    # Project 2 needs a complete 12-month monthly panel; fail loudly rather
    # than silently using stale month-end values.
    if pivots['close'].isna().any().any():
        missing = int(pivots['close'].isna().sum().sum())
        raise ValueError(f'Missing close cells in fixed grid: {missing}')

    quality = dict(
        assets=len(cfg['assets']),
        raw_rows=sum(x['raw_rows'] for x in audits),
        clean_rows=len(panel),
        calendar_days=len(calendar),
        missing_grid_cells=int(pivots['close'].isna().sum().sum()),
        by_asset=audits,
        cleaning=('Sort dates and restrict to the pre-declared warm-up/sample window. '
                  'No interpolation, zero fill, return-based filtering or survivorship edits.'),
        calendar=('Union of trading dates observed in the fixed nine-ETF universe; '
                  'not an independently supplied exchange holiday calendar.'),
        price_basis=('Source already-adjusted OHLC, inferred from the upstream repository '
                     'and the absence of an Adj Close column. No independent original quotes/factors.'),
        adjustment_limitation=('Snapshot is not point-in-time. The ledger uses adjusted-price units '
                               'and adds no dividend cash; it is a total-return price proxy, '
                               'not a broker share/dividend ledger.'),
        warmup_start=str(warm_start.date()),
        sample_start=str(cfg['start']),
        sample_end=str(cfg['end']),
    )
    return panel, pivots, quality
