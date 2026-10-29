"""Run tests, reconcile broker audits and compare a clean offline rerun."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def compare(a,b):
    x,y=pd.read_csv(a),pd.read_csv(b)
    if list(x.columns)!=list(y.columns) or x.shape!=y.shape:
        raise AssertionError(f'Table schema changed: {a.name}')
    largest=0.
    for col in x:
        if pd.api.types.is_numeric_dtype(x[col]) and pd.api.types.is_numeric_dtype(y[col]):
            v,w=x[col].to_numpy(float),y[col].to_numpy(float)
            if not np.allclose(v,w,rtol=1e-10,atol=1e-9,equal_nan=True):
                raise AssertionError(f'Numerical mismatch: {a.name}/{col}')
            delta=np.abs(v-w); finite=delta[np.isfinite(delta)]
            largest=max(largest,float(finite.max()) if len(finite) else 0.)
        else:
            left=x[col].fillna('<NA>'); right=y[col].fillna('<NA>')
            if col=='evidence_path':
                # The isolated rerun intentionally has a different output name.
                left=left.str.replace(a.parent.name+'/', '<OUT>/',regex=False)
                right=right.str.replace(b.parent.name+'/', '<OUT>/',regex=False)
            if not left.equals(right):
                raise AssertionError(f'Text mismatch: {a.name}/{col}')
    return largest

def main():
    p=argparse.ArgumentParser(); p.add_argument('--rerun',action='store_true'); args=p.parse_args()
    os.chdir(ROOT); out=ROOT/'outputs'; out.mkdir(exist_ok=True)
    run=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','--junitxml',str(out/'tests.xml')],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (out/'test_output.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode: raise RuntimeError(run.stdout+run.stderr)
    suites=ET.parse(out/'tests.xml').getroot()
    suite=suites if suites.tag=='testsuite' else suites.find('testsuite')
    counts={k:int(suite.attrib.get(k,0)) for k in ['tests','failures','errors','skipped']}
    tests={'passed':counts['tests']-counts['failures']-counts['errors']-counts['skipped'],**counts}
    if tests['skipped']: raise AssertionError('Release test suite must have no skips')
    audits=list((out/'backtests').glob('*_audit.json'))
    for path in audits:
        audit=json.loads(path.read_text())
        if not audit['passed'] or not all(audit['checks'].values()): raise AssertionError(path.name)
    reproduction={'performed':False,'tables_compared':0,'max_absolute_difference':0.,'tolerance':'rtol=1e-10, atol=1e-9'}
    if args.rerun:
        with tempfile.TemporaryDirectory(prefix='cf_p2_verify_') as temp:
            subprocess.run([sys.executable,'run_final.py','--out',temp,'--no-report'],check=True)
            rerun=Path(temp)
            paths=[]
            for directory in ['research','backtests','signals','integration','experiments','reference']:
                paths.extend((out/directory).glob('*.csv'))
            paths.extend(out/x for x in ['strategy_summary.csv','difference_experiments.csv','original_vs_replication.csv'])
            details={}
            for path in sorted(paths):
                relative=path.relative_to(out)
                details[relative.as_posix()]=compare(path,rerun/relative)
            reproduction.update(performed=True,tables_compared=len(details),max_absolute_difference=max(details.values()),tables=details)
    elif (out/'verification.json').exists():
        # A report-only rebuild must not erase an earlier successful rerun.
        reproduction=json.loads((out/'verification.json').read_text(encoding='utf-8'))['reproducibility']
    evidence={'status':'PASS','tests':tests,'audits_passed':len(audits),'reproducibility':reproduction}
    (out/'verification.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    import importlib.metadata
    packages={x:importlib.metadata.version(x) for x in ['numpy','pandas','scipy','statsmodels','matplotlib','pyarrow','reportlab','openpyxl','pytest','pymupdf']}
    folders=['src','tests','data/raw','data/reference','data/us_sector','references']
    files={str(path.relative_to(ROOT)).replace('\\','/'):sha(path) for folder in folders for path in (ROOT/folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts}
    additional=[ROOT/'data/manifests/source_manifest.json',ROOT/'config/project2_tsmom.json',ROOT/'config/integration.json']
    additional.extend((ROOT/'docs').glob('*.md'))
    for path in additional:
        files[path.relative_to(ROOT).as_posix()]=sha(path)
    for path in [ROOT/'run_final.py',ROOT/'verify_final.py',ROOT/'package_submission.py',ROOT/'pyproject.toml',ROOT/'uv.lock',ROOT/'requirements.lock']:
        files[path.name]=sha(path)
    manifest={'python':sys.version,'platform':platform.platform(),'packages':packages,'sha256':files,
        'seeds':{'integration':20261029},'input_repository_commits':['294ca84','163e50a']}
    (out/'run_manifest_final.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    sys.path.insert(0,str(ROOT/'src'))
    from quantcf.final_report import build_report
    build_report(ROOT,out)
    print(json.dumps({'tests':tests,'audits':len(audits),'tables_compared':reproduction['tables_compared'],'maximum_difference':reproduction['max_absolute_difference']},ensure_ascii=False))

if __name__=='__main__': main()
