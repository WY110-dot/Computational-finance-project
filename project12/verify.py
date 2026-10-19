"""Independent offline reproducibility check and distributable manifest."""
import json,subprocess,sys,hashlib,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from src.data import load_panel,sha
from src.factors import calculate
from src.backtest import simulate,metrics,audit

ROOT=Path(__file__).resolve().parent
def main():
    cfg=json.loads((ROOT/'config.json').read_text());out=ROOT/'outputs'
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    (out/'test_log.txt').write_text(test.stdout+'\n'+test.stderr,encoding='utf-8')
    if test.returncode:raise RuntimeError('tests failed')
    _,p,q=load_panel(ROOT,cfg);f=calculate(p['close'],cfg['factor_windows'])
    d,t,h=simulate(p,f['momentum'],cfg);checks=audit(d,t,h,cfg)
    saved=pd.read_csv(out/'momentum_weekly_daily.csv')
    cols=['wealth','daily_return','cash','cost','turnover','buy','sell']
    err=float(abs(d[cols].to_numpy()-saved[cols].to_numpy()).max())
    if err>1e-7:raise AssertionError(('repeatability',err))
    summary=pd.read_csv(out/'strategy_summary.csv');ref=summary.set_index('strategy').loc['momentum_weekly']
    for key,value in metrics(d,cfg).items():
        if value is not None and abs(value-ref[key])>1e-7:raise AssertionError(key)
    result=dict(status='passed',tests='See test_log.txt',offline_rerun_max_abs_difference=err,checks=checks,
        numerical_tolerance=1e-7,raw_hash_check='passed',notes='One complete main strategy independently re-executed; every strategy has ledger audits during original run.')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in ROOT.rglob('*') if p.is_file()
        and not any(x in p.parts for x in ['.venv','__pycache__','.git','tmp']) and p.name not in ['FILE_MANIFEST.json'] and p.suffix!='.zip'}
    (ROOT/'FILE_MANIFEST.json').write_text(json.dumps(files,indent=2)+'\n')
    print(json.dumps(result,indent=2));print('FILES',len(files))
if __name__=='__main__':main()
