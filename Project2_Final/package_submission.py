"""Build and verify a clean submission ZIP without environments or old bundles."""
from pathlib import Path
import hashlib
import json
import tempfile
import zipfile
import argparse

ROOT=Path(__file__).resolve().parent

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def selected(path):
    rel=path.relative_to(ROOT)
    if not path.is_file() or any(p in {'.venv','__pycache__','.pytest_cache','.git'} for p in rel.parts): return False
    if path.suffix.lower() in {'.pyc','.zip'}: return False
    if rel.parts[0]=='docs': return len(rel.parts)==2
    if rel.parts[0]=='config': return path.name in {'project2_tsmom.json','integration.json'}
    if rel.parts[0]=='data':
        return rel.parts[1] in {'raw','reference','us_sector'} or rel.as_posix()=='data/manifests/source_manifest.json'
    if len(rel.parts)>2 and rel.parts[:2]==('outputs','runs'):
        runs=sorted(p.name for p in (ROOT/'outputs/runs').iterdir() if p.is_dir())
        return rel.parts[2]==runs[-1]
    if rel.parts[0] in {'src','tests','references','outputs'}: return True
    return len(rel.parts)==1 and (path.suffix.lower() in {'.py','.md','.toml','.lock'} or path.name=='.python-version')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--out',default='../CF2026_Project2_Final.zip'); args=parser.parse_args()
    verification=json.loads((ROOT/'outputs/verification.json').read_text(encoding='utf-8'))
    assert verification['status']=='PASS' and verification['reproducibility']['performed']
    # Keep only the latest local P1 recorder run in the release; the final
    # run manifest records all integrated sources and dependency versions.
    paths=sorted(p for p in ROOT.rglob('*') if selected(p) and p.name!='FILE_MANIFEST.json')
    records={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths}
    manifest=ROOT/'FILE_MANIFEST.json'
    manifest.write_text(json.dumps({'format':1,'files':records},ensure_ascii=False,indent=2),encoding='utf-8')
    paths.append(manifest)
    target=(ROOT/args.out).resolve()
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in paths: z.write(path,'Project2_Final/'+path.relative_to(ROOT).as_posix())
    with tempfile.TemporaryDirectory(prefix='cf_p2_package_') as temporary:
        with zipfile.ZipFile(target) as z:
            assert z.testzip() is None
            z.extractall(temporary)
        unpacked=Path(temporary)/'Project2_Final'
        assert (unpacked/'outputs/report/Project2_Final_Report.pdf').exists()
        for name,item in records.items():
            assert sha(unpacked/name)==item['sha256'],name
    result={'zip':target.name,'bytes':target.stat().st_size,'files':len(paths),'sha256':sha(target),'archive_integrity':'PASS','extracted_file_hashes':'PASS'}
    (target.with_suffix('.sha256.txt')).write_text(result['sha256']+'  '+target.name+'\n',encoding='utf-8')
    (target.with_suffix('.verification.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
