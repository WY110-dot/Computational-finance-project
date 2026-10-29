"""Compatibility wrapper for the single final report generator."""
from pathlib import Path
from .final_report import build_report

def generate_all_reports(out_dir="outputs"):
    return build_report(Path(__file__).resolve().parents[2], Path(out_dir))
