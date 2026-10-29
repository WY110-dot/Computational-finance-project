"""Single offline entry point; works from any current directory."""
import argparse
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default='outputs')
    parser.add_argument('--analysis-only',action='store_true',help='Reuse existing P1 execution outputs')
    parser.add_argument('--no-report',action='store_true')
    args=parser.parse_args()
    os.chdir(ROOT)
    out=Path(args.out).resolve()
    from quantcf.pipeline_p2 import run_p2_pipeline
    from quantcf.integration import run_integration
    if not args.analysis_only:
        run_p2_pipeline(config_path=ROOT/'config/project2_tsmom.json',out_dir=out,offline=True,random_seed=20261029)
    run_integration(ROOT,out)
    if not args.no_report:
        from quantcf.final_report import build_report
        build_report(ROOT,out)
    print('Completed:',out)

if __name__=='__main__':
    main()
