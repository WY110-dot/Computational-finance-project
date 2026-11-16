"""Deterministic experiment recording inspired by Qlib's recorder layer.

The recorder separates a stable *experiment fingerprint* from a human-friendly
``run_id``.  Configuration, input data, source files and the software
environment are hashed independently, making it possible to explain exactly
why two runs do or do not match.  JSON is always written with
``allow_nan=False``; non-finite numerical results are represented by JSON
``null`` rather than the non-standard ``NaN``/``Infinity`` tokens.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
import hashlib
from importlib import metadata as importlib_metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


SCHEMA_VERSION = 1
DEFAULT_PACKAGES: tuple[str, ...] = (
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "pyarrow",
    "tushare",
    "python-dotenv",
    "reportlab",
)


def to_json_safe(value: Any) -> Any:
    """Recursively convert common scientific-Python values to strict JSON.

    Non-finite floats and pandas missing sentinels become ``None``.  Mapping
    keys become strings, timestamps use ISO-8601, and unordered sets are sorted
    by their canonical JSON representation.
    """

    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if is_dataclass(value):
        return to_json_safe(asdict(value))
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (datetime, pd.Timestamp)):
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            return timestamp.isoformat()
        return timestamp.tz_convert("UTC").isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, np.generic):
        return to_json_safe(value.item())
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, pd.DataFrame):
        return to_json_safe(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        if value.index.is_unique:
            return to_json_safe(value.to_dict())
        return to_json_safe(value.tolist())
    if isinstance(value, Mapping):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        converted = [to_json_safe(item) for item in value]
        return sorted(converted, key=lambda item: canonical_json(item))
    if isinstance(value, (list, tuple, np.ndarray, pd.Index)):
        return [to_json_safe(item) for item in list(value)]
    if hasattr(value, "tolist"):
        return to_json_safe(value.tolist())
    raise TypeError(f"cannot serialise {type(value).__name__} to JSON")


def canonical_json(value: Any) -> str:
    """Return deterministic, standards-compliant JSON text."""

    return json.dumps(
        to_json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def hash_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"not a file: {source}")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_file_inputs(
    paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None,
) -> list[tuple[str, Path]]:
    if paths is None:
        return []
    if isinstance(paths, Mapping):
        top_level = [(str(label), Path(path)) for label, path in paths.items()]
    elif isinstance(paths, (str, Path)):
        path = Path(paths)
        top_level = [(path.name, path)]
    else:
        top_level = [(Path(path).name, Path(path)) for path in paths]

    files: list[tuple[str, Path]] = []
    for label, path in top_level:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_file():
            files.append((label.replace("\\", "/"), path))
        elif path.is_dir():
            for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
                child_label = f"{label.rstrip('/')}/{child.relative_to(path).as_posix()}"
                files.append((child_label, child))
        else:
            raise ValueError(f"unsupported input path: {path}")
    labels = [label for label, _ in files]
    if len(labels) != len(set(labels)):
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        raise ValueError(f"duplicate logical file names: {duplicates}")
    return sorted(files, key=lambda item: item[0])


def file_manifest(
    paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None,
) -> list[dict[str, Any]]:
    """Return a portable, ordered SHA-256 manifest for files/directories."""

    result: list[dict[str, Any]] = []
    for label, path in _normalise_file_inputs(paths):
        stat = path.stat()
        result.append(
            {
                "path": label,
                "sha256": sha256_file(path),
                "size_bytes": int(stat.st_size),
            }
        )
    return result


def hash_files(
    paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None,
) -> str:
    return hash_object(file_manifest(paths))


def capture_environment(packages: Sequence[str] = DEFAULT_PACKAGES) -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for package in sorted(set(packages)):
        try:
            versions[package] = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable_name": Path(sys.executable).name,
        "platform": platform.platform(),
        "packages": versions,
    }


def write_strict_json(path: str | Path, value: Any, *, indent: int = 2) -> Path:
    """Atomically write UTF-8 JSON and reject all non-standard constants."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        to_json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        allow_nan=False,
    ) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug[:48] or "run"


class ExperimentRecorder:
    """Record one reproducible research run in a self-contained directory."""

    def __init__(
        self,
        runs_root: str | Path,
        config: Mapping[str, Any],
        *,
        data_paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None = None,
        source_paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None = None,
        environment: Mapping[str, Any] | None = None,
        packages: Sequence[str] = DEFAULT_PACKAGES,
        run_name: str = "research",
        run_id: str | None = None,
        clock: Callable[[], datetime] | None = None,
        overwrite: bool = False,
    ) -> None:
        self.runs_root = Path(runs_root)
        self.config = to_json_safe(dict(config))
        self.data_files = file_manifest(data_paths)
        self.source_files = file_manifest(source_paths)
        self.environment = to_json_safe(environment or capture_environment(packages))
        self.hashes = {
            "config_sha256": hash_object(self.config),
            "data_sha256": hash_object(self.data_files),
            "source_sha256": hash_object(self.source_files),
            "environment_sha256": hash_object(self.environment),
        }
        self.experiment_fingerprint = hash_object(self.hashes)
        self._clock = clock or _utc_now
        self._started = _as_utc(self._clock())
        generated = (
            f"{_slug(run_name)}-{self._started.strftime('%Y%m%dT%H%M%S%fZ')}-"
            f"{self.experiment_fingerprint[:12]}"
        )
        self.run_id = run_id or generated
        if self.run_id in {"", ".", ".."} or Path(self.run_id).name != self.run_id:
            raise ValueError("run_id must be a single safe path component")
        self.run_directory = self.runs_root / self.run_id
        self.manifest_path = self.run_directory / "run_manifest.json"
        self.artifact_manifest_path = self.run_directory / "artifact_manifest.json"
        self.metrics_path = self.run_directory / "metrics.json"
        self.overwrite = overwrite
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._manifest: dict[str, Any] | None = None
        self._finalised = False

    @property
    def manifest(self) -> dict[str, Any]:
        if self._manifest is None:
            raise RuntimeError("recorder has not been started")
        return dict(self._manifest)

    def start(self) -> "ExperimentRecorder":
        if self._manifest is not None:
            return self
        if self.run_directory.exists() and not self.overwrite:
            raise FileExistsError(f"run directory already exists: {self.run_directory}")
        self.run_directory.mkdir(parents=True, exist_ok=True)
        self._manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "run_name": self.run_id.split("-", 1)[0],
            "status": "running",
            "started_at": self._started.isoformat().replace("+00:00", "Z"),
            "completed_at": None,
            "experiment_fingerprint": self.experiment_fingerprint,
            "hashes": self.hashes,
            "config": self.config,
            "data_files": self.data_files,
            "source_files": self.source_files,
            "environment": self.environment,
            "artifacts": [],
            "metrics_file": None,
        }
        self._write_manifests()
        return self

    def _require_active(self) -> None:
        if self._manifest is None:
            raise RuntimeError("call start() before recording outputs")
        if self._finalised:
            raise RuntimeError("the run has already been finalised")

    def _portable_artifact_name(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return resolved.relative_to(self.run_directory.resolve()).as_posix()
        except ValueError:
            return path.name

    def record_artifact(
        self,
        path: str | Path,
        *,
        role: str = "output",
        logical_name: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_active()
        artifact_path = Path(path)
        if not artifact_path.is_file():
            raise FileNotFoundError(f"artifact is not a file: {artifact_path}")
        name = (logical_name or self._portable_artifact_name(artifact_path)).replace("\\", "/")
        record = {
            "path": name,
            "role": str(role),
            "sha256": sha256_file(artifact_path),
            "size_bytes": int(artifact_path.stat().st_size),
            "metadata": to_json_safe(dict(metadata or {})),
        }
        self._artifacts[name] = record
        self._write_manifests()
        return dict(record)

    def record_metrics(self, metrics: Mapping[str, Any]) -> Path:
        self._require_active()
        write_strict_json(self.metrics_path, dict(metrics))
        self.record_artifact(self.metrics_path, role="metrics", logical_name="metrics.json")
        assert self._manifest is not None
        self._manifest["metrics_file"] = "metrics.json"
        self._write_manifests()
        return self.metrics_path

    def add_metadata(self, **values: Any) -> None:
        self._require_active()
        assert self._manifest is not None
        metadata = dict(self._manifest.get("metadata") or {})
        metadata.update(to_json_safe(values))
        self._manifest["metadata"] = metadata
        self._write_manifests()

    def _write_manifests(self) -> None:
        if self._manifest is None:
            return
        artifacts = [self._artifacts[key] for key in sorted(self._artifacts)]
        self._manifest["artifacts"] = artifacts
        write_strict_json(
            self.artifact_manifest_path,
            {"schema_version": SCHEMA_VERSION, "run_id": self.run_id, "artifacts": artifacts},
        )
        write_strict_json(self.manifest_path, self._manifest)

    def finalize(
        self,
        *,
        status: str = "completed",
        metrics: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        self._require_active()
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("status must be completed, failed or cancelled")
        if metrics is not None:
            self.record_metrics(metrics)
        if metadata:
            self.add_metadata(**dict(metadata))
        assert self._manifest is not None
        self._manifest["status"] = status
        completed = _as_utc(self._clock())
        self._manifest["completed_at"] = completed.isoformat().replace("+00:00", "Z")
        self._manifest["duration_seconds"] = max(0.0, (completed - self._started).total_seconds())
        self._write_manifests()
        self._finalised = True
        return self.manifest_path

    def __enter__(self) -> "ExperimentRecorder":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if not self._finalised:
            if exc is None:
                self.finalize(status="completed")
            else:
                self.finalize(
                    status="failed",
                    metadata={"error_type": exc_type.__name__ if exc_type else None, "error": str(exc)},
                )
        return False


def record_experiment(
    runs_root: str | Path,
    config: Mapping[str, Any],
    *,
    data_paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None = None,
    source_paths: Mapping[str, str | Path] | Iterable[str | Path] | str | Path | None = None,
    artifacts: Mapping[str, str | Path] | Iterable[str | Path] | None = None,
    metrics: Mapping[str, Any] | None = None,
    **recorder_options: Any,
) -> ExperimentRecorder:
    """Convenience helper for a completed one-shot experiment record."""

    recorder = ExperimentRecorder(
        runs_root,
        config,
        data_paths=data_paths,
        source_paths=source_paths,
        **recorder_options,
    ).start()
    if isinstance(artifacts, Mapping):
        for logical_name, path in artifacts.items():
            recorder.record_artifact(path, logical_name=str(logical_name))
    elif artifacts is not None:
        for path in artifacts:
            recorder.record_artifact(path)
    recorder.finalize(metrics=metrics)
    return recorder


__all__ = [
    "DEFAULT_PACKAGES",
    "ExperimentRecorder",
    "SCHEMA_VERSION",
    "canonical_json",
    "capture_environment",
    "file_manifest",
    "hash_files",
    "hash_object",
    "record_experiment",
    "sha256_file",
    "to_json_safe",
    "write_strict_json",
]
