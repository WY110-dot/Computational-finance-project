from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from quantcf.recorder import (
    ExperimentRecorder,
    canonical_json,
    file_manifest,
    hash_files,
    hash_object,
    record_experiment,
    write_strict_json,
)


FIXED_TIME = datetime(2026, 9, 21, 5, 30, tzinfo=timezone.utc)


def test_canonical_config_hash_ignores_mapping_order_and_is_strict_json() -> None:
    left = {"b": [1, np.nan, np.inf], "a": {"x": 2}}
    right = {"a": {"x": 2}, "b": [1, float("nan"), float("inf")]}
    payload = canonical_json(left)
    assert hash_object(left) == hash_object(right)
    assert json.loads(payload) == {"a": {"x": 2}, "b": [1, None, None]}
    assert "NaN" not in payload and "Infinity" not in payload


def test_file_manifest_is_order_independent_and_content_sensitive(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text("x\n1\n", encoding="utf-8")
    second.write_text("x\n2\n", encoding="utf-8")
    manifest = file_manifest({"b.csv": second, "a.csv": first})
    assert [row["path"] for row in manifest] == ["a.csv", "b.csv"]
    baseline = hash_files({"a.csv": first, "b.csv": second})
    reordered = hash_files({"b.csv": second, "a.csv": first})
    assert baseline == reordered
    second.write_text("x\n3\n", encoding="utf-8")
    assert hash_files({"a.csv": first, "b.csv": second}) != baseline


def test_repeated_inputs_have_same_experiment_fingerprint(tmp_path: Path) -> None:
    data = tmp_path / "prices.csv"
    source = tmp_path / "engine.py"
    data.write_text("date,asset,open\n2024-01-01,A,10\n", encoding="utf-8")
    source.write_text("VALUE = 1\n", encoding="utf-8")
    config = {"execution": {"fee": 0.0003}, "seed": 42}
    environment = {"python": "test", "packages": {"pandas": "test"}}

    first = ExperimentRecorder(
        tmp_path / "runs-a",
        config,
        data_paths={"prices.csv": data},
        source_paths={"engine.py": source},
        environment=environment,
        clock=lambda: FIXED_TIME,
    ).start()
    first.finalize(metrics={"return": 0.1})
    second = ExperimentRecorder(
        tmp_path / "runs-b",
        {"seed": 42, "execution": {"fee": 0.0003}},
        data_paths={"prices.csv": data},
        source_paths={"engine.py": source},
        environment=environment,
        clock=lambda: FIXED_TIME,
    ).start()
    second.finalize(metrics={"return": 0.1})

    assert first.experiment_fingerprint == second.experiment_fingerprint
    assert first.run_id == second.run_id
    first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    for key in ("experiment_fingerprint", "hashes", "config", "data_files", "source_files", "environment"):
        assert first_manifest[key] == second_manifest[key]


def test_recorder_writes_artifact_hashes_and_null_for_nonfinite_metrics(tmp_path: Path) -> None:
    artifact = tmp_path / "diagnostics.csv"
    artifact.write_text("factor,ic\nmomentum,0.01\n", encoding="utf-8")
    ticks = iter(
        [
            FIXED_TIME,
            datetime(2026, 9, 21, 5, 30, 2, tzinfo=timezone.utc),
        ]
    )
    recorder = ExperimentRecorder(
        tmp_path / "runs",
        {"a": 1},
        environment={"python": "test"},
        clock=lambda: next(ticks),
    ).start()
    record = recorder.record_artifact(artifact, role="diagnostic", logical_name="tables/diagnostics.csv")
    recorder.finalize(metrics={"ic": np.nan, "turnover": np.inf, "valid_days": 10})

    assert record["sha256"] == file_manifest({"x": artifact})[0]["sha256"]
    manifest_text = recorder.manifest_path.read_text(encoding="utf-8")
    artifact_text = recorder.artifact_manifest_path.read_text(encoding="utf-8")
    metrics_text = recorder.metrics_path.read_text(encoding="utf-8")
    assert "NaN" not in manifest_text + artifact_text + metrics_text
    assert "Infinity" not in manifest_text + artifact_text + metrics_text
    assert json.loads(metrics_text) == {"ic": None, "turnover": None, "valid_days": 10}
    manifest = json.loads(manifest_text)
    assert manifest["status"] == "completed"
    assert manifest["duration_seconds"] == 2.0
    assert {item["path"] for item in manifest["artifacts"]} == {
        "metrics.json",
        "tables/diagnostics.csv",
    }


def test_record_experiment_helper_and_atomic_json(tmp_path: Path) -> None:
    artifact = tmp_path / "result.txt"
    artifact.write_text("audited", encoding="utf-8")
    recorder = record_experiment(
        tmp_path / "runs",
        {"name": "demo"},
        artifacts={"result.txt": artifact},
        metrics={"ok": True},
        environment={"python": "test"},
        clock=lambda: FIXED_TIME,
    )
    assert recorder.manifest_path.exists()
    assert json.loads(recorder.manifest_path.read_text(encoding="utf-8"))["status"] == "completed"

    target = tmp_path / "strict.json"
    write_strict_json(target, {"missing": float("nan"), "when": FIXED_TIME})
    assert json.loads(target.read_text(encoding="utf-8"))["missing"] is None

