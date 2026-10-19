"""Download an immutable public educational snapshot, never silently refresh it."""
import argparse, base64, hashlib, json, datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent

def download(no_proxy=False):
    cfg = json.loads((ROOT/'config.json').read_text())
    out = ROOT/'data/raw'; out.mkdir(parents=True, exist_ok=True)
    repo, commit = cfg['source_repo'], cfg['source_commit']
    def one(asset):
        filename = f'data/etfs/{asset}.csv'
        url = f'https://api.github.com/repos/{repo}/contents/{filename}?ref={commit}'
        s = requests.Session(); s.trust_env = not no_proxy
        errors=[]
        for attempt in range(2):
            try:
                r=s.get(url, timeout=(10,30)); r.raise_for_status(); j=r.json()
                if j.get('encoding')!='base64': raise ValueError('expected small base64 file')
                raw=base64.b64decode(j['content']); path=out/f'{asset}.csv'
                if path.exists() and path.read_bytes()!=raw: raise ValueError('existing raw snapshot differs')
                path.write_bytes(raw)
                return dict(asset=asset,url=url,blob_sha=j['sha'],sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
            except (requests.RequestException,ValueError) as e: errors.append(str(e))
        raise RuntimeError((asset,errors))
    with ThreadPoolExecutor(max_workers=3) as pool:
        files=list(pool.map(one,cfg['assets']))
    manifest=dict(provider='Public repository snapshot; repository documents Yahoo Finance-format ETF prices',
        repository=repo,commit=commit,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=files,
        limitation='Third-party archived vendor data, not exchange-certified or point-in-time corporate-action data. Educational personal use; no claim to redistribution rights.')
    (ROOT/'data/source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for f in files: print(f['asset'],f['bytes'],f['sha256'][:12],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--no-proxy',action='store_true');args=p.parse_args();download(args.no_proxy)
