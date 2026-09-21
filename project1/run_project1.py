"""
MA216 Project 1: Unified CLI Entrypoint (Section 36)
AI-Assisted Quantitative Research Framework
提供全自动化、模块化运行入口。
"""
import os
import sys
import argparse
import subprocess

def run_step(step_name: str, script_path: str):
    print("\n" + "="*70)
    print(f">> EXECUTING: {step_name} ({script_path})")
    print("="*70)
    python_exe = sys.executable
    cmd = [python_exe, script_path]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"\n[ERROR] Step {step_name} failed with exit code {res.returncode}")
        sys.exit(res.returncode)
    print(f"\n[OK] Step {step_name} completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="MA216 Project 1 Unified Execution Entrypoint")
    parser.add_argument(
        "--phase", 
        choices=["all", "data", "factors", "diagnostics", "backtest", "test"],
        default="all",
        help="Pipeline phase to execute (default: all)"
    )
    args = parser.parse_args()

    print("\n" + "#"*70)
    print("# MA216 Project 1 -- AI-Assisted Quantitative Research Framework")
    print(f"# Target Phase: {args.phase.upper()}")
    print("#"*70)

    if args.phase in ["all", "data"]:
        run_step("Data Layer (Phase D1)", "run_phase_d1.py")

    if args.phase in ["all", "factors"]:
        run_step("Factors Calculation (Phase F1)", "run_phase_f1.py")

    if args.phase in ["all", "diagnostics"]:
        run_step("Factor Diagnostics (Phase A1 / Sec 22-24)", "run_phase_a1.py")

    if args.phase in ["all", "backtest"]:
        run_step("Portfolio, Backtest, Experiment & Reproducibility (Sec 25-30)", "run_phase_p1_to_r1.py")

    if args.phase in ["all", "test"]:
        print("\n" + "="*70)
        print(">> RUNNING FULL TEST SUITE (pytest tests/)")
        print("="*70)
        cmd = [sys.executable, "-m", "pytest", "tests/"]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print("\n[ERROR] Test suite failed!")
            sys.exit(res.returncode)
        print("\n[OK] All test cases passed with 100% success.")

    print("\n" + "#"*70)
    print("# PROJECT 1 PIPELINE EXECUTION FINISHED SUCCESSFULLY!")
    print("# All reports, figures, manifests and tables are generated in outputs/")
    print("#"*70 + "\n")

if __name__ == "__main__":
    main()
