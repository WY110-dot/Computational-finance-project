"""Tushare data ingestion with explicit units, adjustment, and provenance.

The module deliberately separates immutable source snapshots from the derived
research panel.  Tushare ``fund_daily`` reports ``vol`` in hands (100 fund
units) and ``amount`` in thousands of CNY.  Both source values are retained
while canonical ``volume`` and ``amount`` are converted to fund units and CNY.

No price or adjustment-factor value is interpolated.  A missing observation is
information about tradability and must remain missing to the simulator.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PRICE_REQUIRED_COLUMNS = (
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
)
ADJUSTMENT_REQUIRED_COLUMNS = ("ts_code", "trade_date", "adj_factor")
RAW_OPTIONAL_NUMERIC_COLUMNS = ("pre_close", "change", "pct_chg")
ADJUSTED_OHLC_COLUMNS = ("open_adj", "high_adj", "low_adj", "close_adj")


class DataValidationError(ValueError):
    """Raised when a source snapshot violates the declared data contract."""


class ManifestError(ValueError):
    """Raised when an immutable source manifest cannot be verified."""


@dataclass(frozen=True)
class DataAudit:
    """Compact, JSON-serialisable summary of a validated market panel."""

    rows: int
    assets: int
    first_date: str
    last_date: str
    missing_grid_cells: int
    coverage_by_asset: dict[str, float]
    rows_by_asset: dict[str, int]
    units: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "assets": self.assets,
            "first_date": self.first_date,
            "last_date": self.last_date,
            "missing_grid_cells": self.missing_grid_cells,
            "coverage_by_asset": self.coverage_by_asset,
            "rows_by_asset": self.rows_by_asset,
            "units": self.units,
        }


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Return the SHA-256 digest of *path* without loading it all into memory."""

    digest = sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def _reject_secret_metadata(value: Any, trail: tuple[str, ...] = ()) -> None:
    """Prevent credentials from accidentally entering a shareable manifest."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in ("token", "secret", "password", "api_key")):
                raise ManifestError(
                    f"Sensitive metadata key is not allowed in a source manifest: "
                    f"{'.'.join((*trail, str(key)))}"
                )
            _reject_secret_metadata(item, (*trail, str(key)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_metadata(item, (*trail, str(index)))


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def create_source_manifest(
    files: Mapping[str, str | Path],
    manifest_path: str | Path,
    *,
    source: str = "Tushare Pro",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create an immutable, deterministic SHA-256 manifest.

    If the target already exists, this function succeeds only when its complete
    canonical contents are identical.  It never silently refreshes hashes: a new
    raw snapshot must use a new path or the old manifest must be deliberately
    removed by a human.
    """

    if not files:
        raise ManifestError("At least one source file is required.")
    manifest_path = Path(manifest_path)
    base = manifest_path.parent.resolve()
    records: list[dict[str, Any]] = []
    for logical_name, source_path in sorted(files.items()):
        path = Path(source_path).resolve()
        if not path.is_file():
            raise ManifestError(f"Source file does not exist: {path}")
        records.append(
            {
                "logical_name": str(logical_name),
                "path": os.path.relpath(path, base).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    clean_metadata = dict(metadata or {})
    _reject_secret_metadata(clean_metadata)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": source,
        "files": records,
        "metadata": clean_metadata,
    }
    encoded = _canonical_json(payload)
    if manifest_path.exists():
        if manifest_path.read_text(encoding="utf-8") != encoded:
            raise ManifestError(
                f"Refusing to overwrite immutable source manifest: {manifest_path}"
            )
        return payload

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8", newline="\n")
    temporary.replace(manifest_path)
    return payload


def verify_source_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Verify every byte count and digest declared by a source manifest."""

    manifest_path = Path(manifest_path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Cannot read source manifest: {manifest_path}") from exc

    if payload.get("schema_version") != 1 or not isinstance(payload.get("files"), list):
        raise ManifestError("Unsupported or malformed source manifest.")
    _reject_secret_metadata(payload.get("metadata", {}))
    base = manifest_path.parent.resolve()
    for record in payload["files"]:
        required = {"logical_name", "path", "bytes", "sha256"}
        if not required.issubset(record):
            raise ManifestError("Malformed file record in source manifest.")
        path = (base / record["path"]).resolve()
        if not path.is_file():
            raise ManifestError(f"Manifest source file is missing: {record['logical_name']}")
        if path.stat().st_size != int(record["bytes"]):
            raise ManifestError(f"Raw snapshot size mismatch: {record['logical_name']}")
        actual = sha256_file(path)
        if actual != record["sha256"]:
            raise ManifestError(f"Raw snapshot hash mismatch: {record['logical_name']}")
    return payload


def _read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    raise ValueError(f"Unsupported snapshot format: {path.suffix}")


def _parse_dates(values: pd.Series, column: str) -> pd.Series:
    text = values.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    compact = text.str.fullmatch(r"\d{8}", na=False)
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    parsed.loc[compact] = pd.to_datetime(
        text.loc[compact], format="%Y%m%d", errors="coerce"
    )
    parsed.loc[~compact] = pd.to_datetime(text.loc[~compact], errors="coerce")
    if parsed.isna().any():
        examples = text.loc[parsed.isna()].head(3).tolist()
        raise DataValidationError(f"Invalid {column} values: {examples}")
    if (parsed != parsed.dt.normalize()).any():
        raise DataValidationError(f"{column} must contain dates, not intraday timestamps.")
    return parsed.dt.normalize()


def _require_columns(frame: pd.DataFrame, required: Iterable[str], label: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise DataValidationError(f"{label} is missing required columns: {missing}")
    if frame.empty:
        raise DataValidationError(f"{label} is empty.")


def _numeric(frame: pd.DataFrame, columns: Iterable[str], label: str) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        try:
            result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"{label}.{column} is not numeric.") from exc
        values = result[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise DataValidationError(f"{label}.{column} contains missing or infinite values.")
    return result


def _coverage_report(prices: pd.DataFrame) -> DataAudit:
    calendar = pd.DatetimeIndex(sorted(prices["date"].unique()))
    rows_by_asset: dict[str, int] = {}
    coverage_by_asset: dict[str, float] = {}
    missing_grid_cells = 0
    for asset, group in prices.groupby("asset", sort=True):
        asset = str(asset)
        observed = pd.DatetimeIndex(group["date"].unique())
        active_calendar = calendar[(calendar >= observed.min()) & (calendar <= observed.max())]
        missing = len(active_calendar.difference(observed))
        rows_by_asset[asset] = len(observed)
        coverage_by_asset[asset] = (
            float(len(observed) / len(active_calendar)) if len(active_calendar) else 0.0
        )
        missing_grid_cells += len(calendar.difference(observed))
    return DataAudit(
        rows=len(prices),
        assets=prices["asset"].nunique(),
        first_date=str(prices["date"].min().date()),
        last_date=str(prices["date"].max().date()),
        missing_grid_cells=int(missing_grid_cells),
        coverage_by_asset=coverage_by_asset,
        rows_by_asset=rows_by_asset,
        units={
            "price": "CNY per fund unit",
            "vol_raw": "hands (100 fund units) as reported by Tushare fund_daily",
            "volume": "fund units",
            "amount_raw": "thousand CNY as reported by Tushare fund_daily",
            "amount": "CNY",
        },
    )


def validate_tushare_prices(
    raw: pd.DataFrame,
    *,
    expected_assets: Iterable[str] | None = None,
    min_active_coverage: float = 0.0,
    check_units: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate and normalise a Tushare ``fund_daily`` snapshot.

    Missing date/asset grid cells are reported, not filled.  Missing values
    inside an observed row, duplicate keys, malformed OHLC, and impossible units
    are rejected.
    """

    if not 0.0 <= min_active_coverage <= 1.0:
        raise ValueError("min_active_coverage must be between zero and one.")
    _require_columns(raw, PRICE_REQUIRED_COLUMNS, "fund_daily snapshot")
    result = raw.copy()
    result["asset"] = result["ts_code"].astype("string").str.strip()
    result["date"] = _parse_dates(result["trade_date"], "trade_date")
    if result["asset"].isna().any() or (result["asset"] == "").any():
        raise DataValidationError("fund_daily snapshot contains a missing asset code.")
    if result.duplicated(["date", "asset"]).any():
        sample = result.loc[
            result.duplicated(["date", "asset"], keep=False), ["date", "asset"]
        ].head(3)
        raise DataValidationError(f"Duplicate date x asset keys: {sample.to_dict('records')}")

    numeric_columns = ["open", "high", "low", "close", "vol", "amount"]
    numeric_columns += [c for c in RAW_OPTIONAL_NUMERIC_COLUMNS if c in result.columns]
    result = _numeric(result, numeric_columns, "fund_daily")
    if (result[["open", "high", "low", "close"]] <= 0).any(axis=None):
        raise DataValidationError("Prices must be finite and strictly positive.")
    if (result[["vol", "amount"]] < 0).any(axis=None):
        raise DataValidationError("Volume and amount cannot be negative.")
    if "pre_close" in result and (result["pre_close"] <= 0).any():
        raise DataValidationError("pre_close must be strictly positive.")

    tolerance = np.maximum(result["close"].abs() * 1e-8, 1e-10)
    row_max = result[["open", "close", "low"]].max(axis=1)
    row_min = result[["open", "close", "high"]].min(axis=1)
    invalid_ohlc = (result["high"] + tolerance < row_max) | (
        result["low"] - tolerance > row_min
    )
    if invalid_ohlc.any():
        raise DataValidationError(
            f"OHLC inconsistency in {int(invalid_ohlc.sum())} fund_daily rows."
        )

    if check_units:
        zero_vol = result["vol"] == 0
        if (zero_vol & (result["amount"].abs() > 1e-9)).any():
            raise DataValidationError("Non-zero amount with zero volume; units/data are inconsistent.")
        traded = ~zero_vol
        if traded.any():
            # fund_daily: amount * 1,000 CNY / (vol * 100 fund units)
            implied_vwap = result.loc[traded, "amount"] * 10.0 / result.loc[traded, "vol"]
            low = result.loc[traded, "low"]
            high = result.loc[traded, "high"]
            unit_bad = (implied_vwap < low * 0.99) | (implied_vwap > high * 1.01)
            if unit_bad.any():
                raise DataValidationError(
                    "Tushare vol/amount unit check failed: implied VWAP is outside OHLC. "
                    "Expected vol in hands and amount in thousand CNY."
                )

    if expected_assets is not None:
        expected = {str(asset) for asset in expected_assets}
        observed = set(result["asset"].astype(str))
        missing_assets = sorted(expected - observed)
        if missing_assets:
            raise DataValidationError(f"Configured assets absent from prices: {missing_assets}")
        result = result[result["asset"].astype(str).isin(expected)].copy()

    result = result.sort_values(["date", "asset"], kind="mergesort").reset_index(drop=True)
    audit = _coverage_report(result)
    below = {
        asset: value
        for asset, value in audit.coverage_by_asset.items()
        if value < min_active_coverage
    }
    if below:
        raise DataValidationError(
            f"Active-calendar coverage below {min_active_coverage:.1%}: {below}"
        )
    return result, audit.as_dict()


def validate_tushare_adjustments(
    raw: pd.DataFrame,
    *,
    expected_assets: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Validate and normalise a Tushare ``fund_adj`` snapshot."""

    _require_columns(raw, ADJUSTMENT_REQUIRED_COLUMNS, "fund_adj snapshot")
    result = raw.copy()
    result["asset"] = result["ts_code"].astype("string").str.strip()
    result["date"] = _parse_dates(result["trade_date"], "trade_date")
    if result["asset"].isna().any() or (result["asset"] == "").any():
        raise DataValidationError("fund_adj snapshot contains a missing asset code.")
    if result.duplicated(["date", "asset"]).any():
        raise DataValidationError("Duplicate date x asset keys in fund_adj snapshot.")
    result = _numeric(result, ["adj_factor"], "fund_adj")
    if (result["adj_factor"] <= 0).any():
        raise DataValidationError("Adjustment factors must be strictly positive.")
    if expected_assets is not None:
        expected = {str(asset) for asset in expected_assets}
        observed = set(result["asset"].astype(str))
        missing_assets = sorted(expected - observed)
        if missing_assets:
            raise DataValidationError(
                f"Configured assets absent from adjustment factors: {missing_assets}"
            )
        result = result[result["asset"].astype(str).isin(expected)].copy()
    return result.sort_values(["date", "asset"], kind="mergesort").reset_index(drop=True)


def _timestamp(value: str | pd.Timestamp, name: str) -> pd.Timestamp:
    parsed = _parse_dates(pd.Series([value]), name).iloc[0]
    return pd.Timestamp(parsed)


def build_adjusted_panel(
    prices_raw: pd.DataFrame,
    adjustments_raw: pd.DataFrame,
    *,
    reference_date: str | pd.Timestamp,
    assets: Iterable[str] | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    min_active_coverage: float = 0.0,
    check_units: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build a fixed-reference adjusted panel while retaining source fields.

    For each asset and OHLC field, ``P_adj(t) = P_raw(t) * a(t) / a(tau)``.
    Total returns are computed from ``close_raw * adj_factor`` before reference
    normalisation, making it explicit that no future value enters a return.
    ``reference_date`` must exist for every selected asset and is never inferred
    from the end of a mutable file.
    """

    selected_assets = None if assets is None else tuple(str(asset) for asset in assets)
    prices, price_audit = validate_tushare_prices(
        prices_raw,
        expected_assets=selected_assets,
        min_active_coverage=0.0,
        check_units=check_units,
    )
    adjustments = validate_tushare_adjustments(
        adjustments_raw, expected_assets=selected_assets
    )
    reference = _timestamp(reference_date, "reference_date")
    start_date = _timestamp(start, "start") if start is not None else None
    end_date = _timestamp(end, "end") if end is not None else None
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start must not be after end.")
    ref = adjustments.loc[
        adjustments["date"].eq(reference), ["asset", "adj_factor"]
    ].rename(columns={"adj_factor": "reference_adj_factor"})
    expected_ref_assets = sorted(prices["asset"].astype(str).unique())
    missing_ref = sorted(set(expected_ref_assets) - set(ref["asset"].astype(str)))
    if missing_ref:
        raise DataValidationError(
            f"Reference date {reference.date()} is absent for assets: {missing_ref}"
        )
    if ref.duplicated("asset").any():
        raise DataValidationError("Reference adjustment factor is not unique per asset.")

    panel = prices.merge(
        adjustments[["date", "asset", "adj_factor"]],
        on=["date", "asset"],
        how="left",
        validate="one_to_one",
    )
    if panel["adj_factor"].isna().any():
        missing = panel.loc[panel["adj_factor"].isna(), ["date", "asset"]].head(5)
        raise DataValidationError(
            f"Missing same-day adjustment factor; no fill is permitted: "
            f"{missing.to_dict('records')}"
        )
    panel = panel.merge(ref, on="asset", how="left", validate="many_to_one")

    # Explicit source-value preservation.
    for field in ("open", "high", "low", "close"):
        panel[f"{field}_raw"] = panel[field].astype(float)
    for field in RAW_OPTIONAL_NUMERIC_COLUMNS:
        if field in panel:
            panel[f"{field}_raw"] = panel[field].astype(float)
    panel["vol_raw"] = panel["vol"].astype(float)
    panel["amount_raw"] = panel["amount"].astype(float)
    panel["volume_lots"] = panel["vol_raw"]
    panel["volume"] = panel["vol_raw"] * 100.0
    panel["amount_thousand_cny"] = panel["amount_raw"]
    panel["amount"] = panel["amount_raw"] * 1000.0

    ratio = panel["adj_factor"] / panel["reference_adj_factor"]
    for field in ("open", "high", "low", "close"):
        panel[f"{field}_adj"] = panel[f"{field}_raw"] * ratio

    # The normalising reference factor cancels from adjacent returns.  Computing
    # on this unnormalised total-return index demonstrates prefix-safe causality.
    panel["total_return_index"] = panel["close_raw"] * panel["adj_factor"]
    panel["ret_total"] = panel.groupby("asset", sort=False)[
        "total_return_index"
    ].pct_change(fill_method=None)
    panel["adjustment_reference_date"] = reference
    panel["price_currency"] = "CNY"

    if start_date is not None:
        panel = panel[panel["date"] >= start_date]
    if end_date is not None:
        panel = panel[panel["date"] <= end_date]
    if panel.empty:
        raise DataValidationError("No observations remain after the requested date filter.")
    panel = panel.sort_values(["date", "asset"], kind="mergesort").reset_index(drop=True)

    filtered_audit = _coverage_report(panel)
    below = {
        asset: value
        for asset, value in filtered_audit.coverage_by_asset.items()
        if value < min_active_coverage
    }
    if below:
        raise DataValidationError(
            f"Active-calendar coverage below {min_active_coverage:.1%}: {below}"
        )

    output_columns = [
        "date",
        "asset",
        "ts_code",
        "trade_date",
        "open_raw",
        "high_raw",
        "low_raw",
        "close_raw",
    ]
    output_columns += [
        f"{name}_raw" for name in RAW_OPTIONAL_NUMERIC_COLUMNS if f"{name}_raw" in panel
    ]
    output_columns += [
        "vol_raw",
        "amount_raw",
        "volume_lots",
        "volume",
        "amount_thousand_cny",
        "amount",
        "adj_factor",
        "reference_adj_factor",
        "adjustment_reference_date",
        *ADJUSTED_OHLC_COLUMNS,
        "total_return_index",
        "ret_total",
        "price_currency",
    ]
    panel = panel[output_columns]
    quality = {
        **filtered_audit.as_dict(),
        "raw_snapshot_audit": price_audit,
        "reference_date": str(reference.date()),
        "adjustment_formula": "raw_price * adj_factor / reference_adj_factor",
        "return_formula": "pct_change(close_raw * adj_factor), grouped by asset",
        "missing_policy": "No interpolation, backfill, forward fill, or zero fill.",
    }
    return panel, quality


def load_tushare_snapshots(
    prices_path: str | Path,
    adjustments_path: str | Path,
    *,
    reference_date: str | pd.Timestamp,
    assets: Iterable[str] | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    manifest_path: str | Path | None = None,
    require_manifest: bool = True,
    min_active_coverage: float = 0.0,
    check_units: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Verify, load, validate, and adjust two immutable source snapshots."""

    if manifest_path is None and require_manifest:
        raise ManifestError("An immutable source manifest is required.")
    manifest = verify_source_manifest(manifest_path) if manifest_path is not None else None
    panel, quality = build_adjusted_panel(
        _read_table(prices_path),
        _read_table(adjustments_path),
        reference_date=reference_date,
        assets=assets,
        start=start,
        end=end,
        min_active_coverage=min_active_coverage,
        check_units=check_units,
    )
    quality["source_manifest"] = manifest
    return panel, quality


def panel_to_wide(
    panel: pd.DataFrame,
    columns: Iterable[str] = ("open_adj", "high_adj", "low_adj", "close_adj", "volume", "amount"),
) -> dict[str, pd.DataFrame]:
    """Create deterministic date x asset matrices without imputing missing cells."""

    if panel.duplicated(["date", "asset"]).any():
        raise DataValidationError("Duplicate date x asset keys in adjusted panel.")
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(panel["date"]).unique()), name="date")
    assets = sorted(panel["asset"].astype(str).unique())
    result: dict[str, pd.DataFrame] = {}
    for column in columns:
        if column not in panel:
            raise KeyError(f"Panel column not found: {column}")
        result[column] = (
            panel.pivot(index="date", columns="asset", values=column)
            .reindex(index=dates, columns=assets)
            .rename_axis(index="date", columns="asset")
        )
    return result


def load_panel(root: str | Path, cfg: Mapping[str, Any]):
    """Project-level compatibility loader inspired by Qlib's data-provider API.

    ``cfg`` may be the whole project configuration or its ``data`` section.  A
    fixed 120-calendar-day warm-up is retained before the declared study start.
    The return shape mirrors project2: ``(long_panel, wide_fields, audit)``.
    """

    root = Path(root)
    data_cfg = cfg.get("data", cfg)
    start = _timestamp(data_cfg["start"], "start")
    warmup_days = int(data_cfg.get("warmup_calendar_days", 120))
    prices_path = root / data_cfg.get("prices_snapshot", "data/raw/prices_raw.parquet")
    adjustment_path = root / data_cfg.get(
        "adjustment_snapshot", "data/raw/adjustment_raw.parquet"
    )
    manifest_path = root / data_cfg.get("manifest", "data/source_manifest.json")
    panel, quality = load_tushare_snapshots(
        prices_path,
        adjustment_path,
        reference_date=data_cfg["adjustment_reference_date"],
        assets=data_cfg.get("assets"),
        start=start - pd.Timedelta(days=warmup_days),
        end=data_cfg.get("end"),
        manifest_path=manifest_path,
        require_manifest=bool(data_cfg.get("require_manifest", True)),
        min_active_coverage=float(data_cfg.get("min_active_coverage", 0.95)),
        check_units=bool(data_cfg.get("check_units", True)),
    )
    quality["study_start"] = str(start.date())
    quality["warmup_calendar_days"] = warmup_days
    return panel, panel_to_wide(panel), quality


def make_shareable_sample(
    panel: pd.DataFrame,
    *,
    max_assets: int = 3,
    max_dates: int = 60,
) -> pd.DataFrame:
    """Return a small deterministic sample with enough history for MOM20."""

    if max_assets < 1 or max_dates < 1:
        raise ValueError("max_assets and max_dates must be positive.")
    assets = sorted(panel["asset"].astype(str).unique())[:max_assets]
    dates = sorted(pd.to_datetime(panel["date"]).unique())[:max_dates]
    sample = panel[
        panel["asset"].astype(str).isin(assets) & pd.to_datetime(panel["date"]).isin(dates)
    ].copy()
    return sample.sort_values(["date", "asset"], kind="mergesort").reset_index(drop=True)


def write_shareable_sample(
    panel: pd.DataFrame,
    path: str | Path,
    *,
    max_assets: int = 3,
    max_dates: int = 60,
) -> Path:
    """Write a deterministic, credential-free sample as CSV or Parquet."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sample = make_shareable_sample(panel, max_assets=max_assets, max_dates=max_dates)
    if path.suffix.lower() == ".csv":
        sample.to_csv(path, index=False, encoding="utf-8")
    elif path.suffix.lower() in {".parquet", ".pq"}:
        sample.to_parquet(path, index=False)
    else:
        raise ValueError("Shareable sample must use .csv or .parquet.")
    return path


def download_tushare_snapshots(
    assets: Iterable[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    output_dir: str | Path,
    *,
    token_env: str = "TUSHARE_TOKEN",
    manifest_path: str | Path | None = None,
) -> dict[str, Path]:
    """Download versioned raw snapshots using a token read only from the environment.

    Existing files are never overwritten.  The token is neither returned nor
    placed in metadata/logging.  Network access and Tushare permissions are the
    caller's responsibility.
    """

    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(f"Set the {token_env} environment variable before downloading.")
    try:
        import tushare as ts
    except ImportError as exc:  # pragma: no cover - optional network path
        raise RuntimeError("Install the optional Tushare dependency to download data.") from exc

    output_dir = Path(output_dir)
    price_path = output_dir / "prices_raw.parquet"
    adjustment_path = output_dir / "adjustment_raw.parquet"
    for target in (price_path, adjustment_path):
        if target.exists():
            raise FileExistsError(
                f"Immutable snapshot already exists: {target}. Use a new versioned directory."
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    start_text = _timestamp(start, "start").strftime("%Y%m%d")
    end_text = _timestamp(end, "end").strftime("%Y%m%d")
    if start_text > end_text:
        raise ValueError("start must not be after end.")

    client = ts.pro_api(token)
    prices: list[pd.DataFrame] = []
    adjustments: list[pd.DataFrame] = []
    clean_assets = sorted({str(asset) for asset in assets})
    if not clean_assets:
        raise ValueError("At least one asset is required.")
    for asset in clean_assets:  # pragma: no cover - optional network path
        daily = client.fund_daily(ts_code=asset, start_date=start_text, end_date=end_text)
        adj = client.fund_adj(ts_code=asset, start_date=start_text, end_date=end_text)
        if daily is None or daily.empty:
            raise DataValidationError(f"Tushare returned no fund_daily data for {asset}.")
        if adj is None or adj.empty:
            raise DataValidationError(f"Tushare returned no fund_adj data for {asset}.")
        prices.append(daily)
        adjustments.append(adj)

    price_frame, _ = validate_tushare_prices(
        pd.concat(prices, ignore_index=True), expected_assets=clean_assets
    )
    adjustment_frame = validate_tushare_adjustments(
        pd.concat(adjustments, ignore_index=True), expected_assets=clean_assets
    )
    # Persist the original Tushare schemas, deterministically ordered.
    price_columns = [column for column in prices[0].columns if column in price_frame.columns]
    adjustment_columns = [
        column for column in adjustments[0].columns if column in adjustment_frame.columns
    ]
    price_frame[price_columns].to_parquet(price_path, index=False)
    adjustment_frame[adjustment_columns].to_parquet(adjustment_path, index=False)
    target_manifest = Path(manifest_path) if manifest_path else output_dir.parent / "source_manifest.json"
    create_source_manifest(
        {"fund_daily": price_path, "fund_adj": adjustment_path},
        target_manifest,
        metadata={
            "api_names": ["fund_daily", "fund_adj"],
            "assets": clean_assets,
            "start": start_text,
            "end": end_text,
            "unit_convention": {
                "vol": "hands (100 fund units)",
                "amount": "thousand CNY",
            },
        },
    )
    return {
        "prices": price_path,
        "adjustments": adjustment_path,
        "manifest": target_manifest,
    }


# Short aliases for callers that do not need the more explicit source wording.
create_manifest = create_source_manifest
verify_manifest = verify_source_manifest


__all__ = [
    "ADJUSTED_OHLC_COLUMNS",
    "DataAudit",
    "DataValidationError",
    "ManifestError",
    "build_adjusted_panel",
    "create_manifest",
    "create_source_manifest",
    "download_tushare_snapshots",
    "load_panel",
    "load_tushare_snapshots",
    "make_shareable_sample",
    "panel_to_wide",
    "sha256_file",
    "validate_tushare_adjustments",
    "validate_tushare_prices",
    "verify_manifest",
    "verify_source_manifest",
    "write_shareable_sample",
]
