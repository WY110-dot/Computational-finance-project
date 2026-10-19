"""Reproducibility gate for Project 2.

Steps
  1. run the unit-test suite;
  2. rerun the full pipeline into outputs_verify/ with the same config;
  3. compare every CSV and JSON output against outputs/ within tolerance;
  4. recheck the raw-data SHA-256 hashes and the ledger audit;
  5. write outputs/verification.json and exit nonzero on any failure.

Usage (from project2/):
    python verify.py
"""
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import sha

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
VERIFY_OUT = ROOT / 'outputs_verify'
RTOL, ATOL = 1e-6, 1e-9

CSV_FILES = sorted(p.name for p in OUT.glob('*.csv'))
JSON_FILES = ['quality_report.json', 'diagnostics.json', 'audit.json']
FIGURE_FILES = sorted(p.name for p in (OUT / 'figures').glob('*.png'))


def run(cmd):
    tic = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        'command': ' '.join(str(c) for c in cmd),
        'returncode': proc.returncode,
        'seconds': round(time.perf_counter() - tic, 3),
        'stdout_tail': proc.stdout.strip().splitlines()[-12:],
        'stderr_tail': proc.stderr.strip().splitlines()[-12:],
    }


def compare_csv(a, b):
    da, db = pd.read_csv(a), pd.read_csv(b)
    if da.shape != db.shape:
        return {'ok': False, 'error': f'shape {da.shape} != {db.shape}',
                'rows': int(len(da))}
    max_diff = 0.0
    bad_columns = []
    for col in da.columns:
        x, y = da[col], db[col]
        if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
            xx, yy = x.to_numpy(float), y.to_numpy(float)
            both_nan = np.isnan(xx) & np.isnan(yy)
            if not np.array_equal(np.isnan(xx), np.isnan(yy)):
                bad_columns.append(col)
                continue
            diff = np.abs(xx[~both_nan] - yy[~both_nan])
            if len(diff):
                max_diff = max(max_diff, float(diff.max()))
            if not np.allclose(xx, yy, rtol=RTOL, atol=ATOL, equal_nan=True):
                bad_columns.append(col)
        else:
            if not (x.fillna('') == y.fillna('')).all():
                bad_columns.append(col)
    ok = not bad_columns
    return {'ok': ok, 'rows': int(len(da)), 'columns': int(da.shape[1]),
            'max_abs_diff': max_diff, 'bad_columns': bad_columns,
            'error': None if ok else 'values differ beyond tolerance'}


def compare_json(a, b):
    da = json.loads(a.read_text(encoding='utf-8'))
    db = json.loads(b.read_text(encoding='utf-8'))
    problems = []
    max_diff = [0.0]

    def walk(x, y, path=''):
        if isinstance(x, dict) and isinstance(y, dict):
            if set(x) != set(y):
                problems.append(f'{path}: keys {sorted(set(x) ^ set(y))}')
                return
            for k in x:
                walk(x[k], y[k], f'{path}/{k}')
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                problems.append(f'{path}: length {len(x)} != {len(y)}')
                return
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, f'{path}/{i}')
        elif isinstance(x, (int, float)) and isinstance(y, (int, float)):
            d = abs(float(x) - float(y))
            max_diff[0] = max(max_diff[0], d)
            if d > ATOL + RTOL * max(abs(float(x)), abs(float(y)), 1.0):
                problems.append(f'{path}: {x} != {y}')
        elif x != y:
            problems.append(f'{path}: {x!r} != {y!r}')

    walk(da, db)
    return {'ok': not problems, 'max_abs_diff': max_diff[0],
            'problems': problems[:10]}


def check_data_hashes():
    manifest = json.loads((ROOT / 'data/source_manifest.json').read_text(encoding='utf-8'))
    rows = []
    for f in manifest['files']:
        path = ROOT / 'data/raw' / f"{f['asset']}.csv"
        actual = sha(path) if path.exists() else None
        rows.append({'asset': f['asset'], 'ok': actual == f['sha256'],
                     'expected': f['sha256'], 'actual': actual})
    return {'ok': all(r['ok'] for r in rows), 'files': rows}


def main():
    failures = []
    report = {'started_utc': datetime.now(timezone.utc).isoformat()}

    print('[1/4] unit tests')
    tests = run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    report['tests'] = tests
    if tests['returncode'] != 0:
        failures.append('unit tests failed')

    print('[2/4] full rerun -> outputs_verify/')
    if VERIFY_OUT.exists():
        shutil.rmtree(VERIFY_OUT)
    rerun = run([sys.executable, 'run.py', '--config', 'config.json',
                 '--out', 'outputs_verify'])
    report['rerun'] = rerun
    if rerun['returncode'] != 0:
        failures.append('pipeline rerun failed')

    print('[3/4] compare outputs')
    csv_results = {}
    for name in CSV_FILES:
        a, b = OUT / name, VERIFY_OUT / name
        if not b.exists():
            csv_results[name] = {'ok': False, 'error': 'missing in outputs_verify'}
        else:
            csv_results[name] = compare_csv(a, b)
        if not csv_results[name]['ok']:
            failures.append(f'CSV mismatch: {name}')
    report['csv'] = csv_results

    json_results = {}
    for name in JSON_FILES:
        a, b = OUT / name, VERIFY_OUT / name
        if not b.exists():
            json_results[name] = {'ok': False, 'problems': ['missing']}
        else:
            json_results[name] = compare_json(a, b)
        if not json_results[name]['ok']:
            failures.append(f'JSON mismatch: {name}')

    # run_manifest differs by design in runtime and command; compare provenance.
    manifest_compare = compare_json(OUT / 'run_manifest.json', VERIFY_OUT / 'run_manifest.json')
    if not manifest_compare['ok']:
        da = json.loads((OUT / 'run_manifest.json').read_text(encoding='utf-8'))
        db = json.loads((VERIFY_OUT / 'run_manifest.json').read_text(encoding='utf-8'))
        keys = set(da) | set(db)
        diff = [k for k in keys if k not in ('runtime_seconds', 'command') and da.get(k) != db.get(k)]
        manifest_compare = {'ok': not diff, 'differing_keys': diff}
    json_results['run_manifest.json'] = manifest_compare
    if not manifest_compare['ok']:
        failures.append('run_manifest provenance mismatch')
    report['json'] = json_results

    figures = {name: (OUT / 'figures' / name).exists()
               and (VERIFY_OUT / 'figures' / name).exists() for name in FIGURE_FILES}
    report['figures'] = {'ok': all(figures.values()), 'present': figures}
    if not figures or not all(figures.values()):
        failures.append('figures missing')

    print('[4/4] data hashes and ledger audit')
    data = check_data_hashes()
    report['data_hashes'] = data
    if not data['ok']:
        failures.append('raw data hash mismatch')

    audit = json.loads((OUT / 'audit.json').read_text(encoding='utf-8'))
    worst = max(max(errors.values()) for errors in audit.values())
    report['audit'] = {'ok': worst < 1e-5, 'max_error': worst,
                       'threshold': 1e-5, 'strategies': len(audit)}
    if worst >= 1e-5:
        failures.append('ledger audit above tolerance')

    report['status'] = 'PASS' if not failures else 'FAIL'
    report['failures'] = failures
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    OUT.mkdir(exist_ok=True)
    (OUT / 'verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')

    print('\n' + '=' * 60)
    print(f"STATUS: {report['status']}")
    if failures:
        for f in failures:
            print(' -', f)
    else:
        print('  unit tests: PASS')
        print(f"  CSV files compared: {len(csv_results)}")
        print(f"  max CSV diff: {max((v.get('max_abs_diff', 0) for v in csv_results.values()), default=0):.3e}")
        print(f"  data hashes: {sum(r['ok'] for r in data['files'])}/{len(data['files'])}")
        print(f"  ledger max error: {worst:.3e}")
    print(f"  report: outputs/verification.json")
    print('=' * 60)
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
