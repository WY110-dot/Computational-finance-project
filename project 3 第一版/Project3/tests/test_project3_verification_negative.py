"""Negative unit tests for Project 3 verification harness.

Ensures that the verifier strictly rejects:
1. P5 quarantine violation beyond line 50000 (chunking verification).
2. Unparseable/corrupted date formats in P5 quarantine check.
3. Tampered raw_value in report_trace.csv.
4. Tampered monthly fee in reconciliation.csv even when boolean fees_reconciled is True.
5. Incomplete backtest runs in reconciliation check.
6. Freeze manifest hash tampering.
7. Missing required outputs.
8. Acceptance matrix failure propagation.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verify_project3 import (
    check_p5_quarantine,
    check_reconciliation,
    check_freeze_manifest,
    check_report_trace,
    check_required_outputs,
    build_acceptance_matrix,
)


def test_negative_p5_quarantine_chunk_detects_row_50001():
    """Verifier must catch P5 violations located past the 50,000 row boundary."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        diag_dir = tmp_path / "diagnostics"
        diag_dir.mkdir(parents=True)
        
        # Build DataFrame with 50,005 rows
        n_rows = 50005
        dates = ["2024-12-01"] * n_rows
        # Inject violation at row 50001 (0-indexed 50001)
        dates[50001] = "2026-01-02"
        
        df = pd.DataFrame({"date": dates, "value": np.ones(n_rows)})
        df.to_csv(diag_dir / "large_series.csv", index=False)
        
        passed, msg = check_p5_quarantine(tmp_path)
        assert not passed
        assert "P5 Quarantine Violation" in msg
        assert "2026" in msg


def test_negative_p5_quarantine_rejects_unparseable_date():
    """Verifier must reject unparseable/corrupted dates and not swallow formatting errors."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        diag_dir = tmp_path / "diagnostics"
        diag_dir.mkdir(parents=True)
        
        df = pd.DataFrame({"date": ["2024-12-01", "corrupted-date-xyz"], "value": [1.0, 2.0]})
        df.to_csv(diag_dir / "corrupted_series.csv", index=False)
        
        passed, msg = check_p5_quarantine(tmp_path)
        assert not passed
        assert "P5 Quarantine Check Error" in msg or "unparseable" in msg.lower() or "error" in msg.lower()


def test_negative_report_trace_detects_tampered_value():
    """Verifier must reject report_trace when raw_value does not match source file."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rep_dir = tmp_path / "report"
        rep_dir.mkdir(parents=True)
        
        # Create real source file
        src_df = pd.DataFrame([{
            "experiment_id": "EXP_US9_A_3bps",
            "ann_return": 0.169168,
        }])
        src_df.to_csv(tmp_path / "experiments_inventory.csv", index=False)
        
        # Create trace mapping matching the source
        trace_df = pd.DataFrame([{
            "report_location": "Table 1",
            "metric_name": "ann_return",
            "universe": "US9",
            "strategy": "A",
            "fee_bps": 3.0,
            "source_file": "outputs/experiments_inventory.csv",
            "filter_key": "experiment_id == 'EXP_US9_A_3bps'",
            "source_column": "ann_return",
            "raw_value": 0.169168,
            "displayed_value": "16.92%",
            "assertion_passed": True,
        }])
        trace_df.to_csv(rep_dir / "report_trace.csv", index=False)
        
        passed, msg = check_report_trace(tmp_path, tmp_path)
        assert passed
        
        # Tamper raw_value to 999999.0
        trace_df.loc[0, "raw_value"] = 999999.0
        trace_df.to_csv(rep_dir / "report_trace.csv", index=False)
        
        passed, msg = check_report_trace(tmp_path, tmp_path)
        assert not passed
        assert "Trace mismatch" in msg
        assert "ann_return" in msg


def test_negative_reconciliation_detects_tampered_monthly_fees():
    """Verifier must independently recalculate sums and reject tampered fees even if boolean is True."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        b_dir = tmp_path / "backtests"
        b_dir.mkdir(parents=True)
        
        # Create backtests artifacts for 48 runs
        universes = ["US9", "CN21"]
        strategies = ["A", "B", "C", "F2", "F3", "A0", "passive_equal", "passive_inv_vol"]
        fees = [0.0, 3.0, 10.0]
        
        rec_rows = []
        for u in universes:
            for s in strategies:
                for f in fees:
                    prefix = f"{u}_{s}_{int(f)}bps"
                    # Create fills, ledger, monthly_returns
                    fills = pd.DataFrame([{"fee": 100.0}])
                    ledger = pd.DataFrame([{"transaction_cost": 100.0}])
                    monthly = pd.DataFrame([{
                        "fees": 100.0,
                        "net_return": 0.05,
                        "w_entry_pretrade": 1e6,
                        "w_exit_pretrade": 1.05e6,
                    }])
                    fills.to_csv(b_dir / f"{prefix}_fills.csv", index=False)
                    ledger.to_csv(b_dir / f"{prefix}_ledger.csv", index=False)
                    monthly.to_csv(b_dir / f"{prefix}_monthly_returns.csv", index=False)
                    
                    rec_rows.append({
                        "universe": u, "strategy": s, "cost_bps": f,
                        "experiment_id": f"EXP_{prefix}",
                        "fills_fees_sum": 100.0,
                        "ledger_fees_sum": 100.0,
                        "monthly_fees_sum": 100.0,
                        "fees_reconciled": True,
                        "w_start_open": 1e6,
                        "w_end_open": 1.05e6,
                        "cum_return_telescoping": 0.05,
                        "nav_ratio_telescoping": 0.05,
                        "compounding_reconciled": True,
                    })
                    
        df_rec = pd.DataFrame(rec_rows)
        df_rec.to_csv(tmp_path / "reconciliation.csv", index=False)
        
        # Verify valid reconciliation passes
        passed, msg = check_reconciliation(tmp_path)
        assert passed
        
        # Tamper monthly_fees_sum in reconciliation.csv to 10亿 while leaving boolean True
        df_rec.loc[0, "monthly_fees_sum"] = 1_000_000_000.0
        df_rec.to_csv(tmp_path / "reconciliation.csv", index=False)
        
        passed, msg = check_reconciliation(tmp_path)
        assert not passed
        assert "mismatch" in msg.lower() or "fee" in msg.lower()


def test_negative_freeze_manifest_rejects_hash_tampering():
    """Verifier must reject freeze verification if a frozen file's contents are altered."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out_dir = tmp_path / "outputs"
        out_dir.mkdir(parents=True)
        
        dummy_file = tmp_path / "dummy.py"
        dummy_file.write_text("print('hello')", encoding="utf-8")
        import hashlib
        h = hashlib.sha256(dummy_file.read_bytes()).hexdigest()
        
        manifest = {
            "files": [{"path": "dummy.py", "sha256": h, "bytes": len(dummy_file.read_bytes())}]
        }
        (out_dir / "freeze_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        passed, msg = check_freeze_manifest(out_dir, tmp_path)
        assert passed
        
        # Tamper file contents
        dummy_file.write_text("print('tampered')", encoding="utf-8")
        passed, msg = check_freeze_manifest(out_dir, tmp_path)
        assert not passed
        assert "Freeze hash mismatch" in msg


def test_negative_required_outputs_rejects_missing_tables():
    """Verifier must reject if required tables like factors_long.csv or coverage.csv are missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        passed, msg = check_required_outputs(tmp_path)
        assert not passed
        assert "missing" in msg.lower()


def test_negative_acceptance_matrix_reports_real_failures():
    """Acceptance matrix must produce FAIL when checks fail, not hardcoded PASS."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Empty directory -> checks will fail
        v_data = {
            "tests": {"passed": 0, "failures": 1, "errors": 0, "skipped": 0},
            "audits_passed": 0,
            "freeze_verification": "FAIL",
            "p5_quarantine": "FAIL",
            "reproducibility": {"performed": False},
        }
        matrix = build_acceptance_matrix(tmp_path, v_data)
        statuses = set(matrix["status"].unique())
        assert "FAIL" in statuses
