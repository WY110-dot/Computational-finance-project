"""Reference data loader and parser for Moskowitz, Ooi & Pedersen (2012).

Handles fetching, hashing, and parsing of:
1. Official AQR Time Series Momentum dataset (1985-01 to 2009-12).
2. Published paper metadata and reference performance metrics.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
import urllib.request

import numpy as np
import openpyxl
import pandas as pd


AQR_DATASET_URL = (
    "https://images.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
    "Time-Series-Momentum-Original-Paper-Data.xlsx"
)
PAPER_PDF_URL = "https://fairmodel.econ.yale.edu/ec439/jpde.pdf"
BACKUP_PAPER_PDF_URL = "https://docs.lhpedersen.com/TimeSeriesMomentum.pdf"

DEFAULT_AQR_FILE = Path("data/reference/Time-Series-Momentum-Original-Paper-Data.xlsx")
DEFAULT_PAPER_PDF = Path("references/Moskowitz_Ooi_Pedersen_2012_TSMOM.pdf")


def compute_sha256(filepath: Path) -> str:
    """Compute sha256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def fetch_project2_sources(
    root_dir: Optional[Path] = None,
    force_download: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Download and verify project2 reference files."""
    if root_dir is None:
        root_dir = Path(".")

    ref_dir = root_dir / "references"
    data_ref_dir = root_dir / "data" / "reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    data_ref_dir.mkdir(parents=True, exist_ok=True)

    aqr_path = data_ref_dir / "Time-Series-Momentum-Original-Paper-Data.xlsx"
    paper_path = ref_dir / "Moskowitz_Ooi_Pedersen_2012_TSMOM.pdf"

    results = {}

    # 1. AQR Excel
    if not aqr_path.exists() or force_download:
        req = urllib.request.Request(AQR_DATASET_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
            aqr_path.write_bytes(content)

    results["aqr_excel"] = {
        "path": str(aqr_path),
        "size_bytes": aqr_path.stat().st_size,
        "sha256": compute_sha256(aqr_path),
        "source_url": AQR_DATASET_URL,
    }

    # 2. Paper PDF
    if not paper_path.exists() or force_download:
        try:
            req = urllib.request.Request(PAPER_PDF_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read()
                paper_path.write_bytes(content)
        except Exception:
            req = urllib.request.Request(BACKUP_PAPER_PDF_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                content = resp.read()
                paper_path.write_bytes(content)

    results["paper_pdf"] = {
        "path": str(paper_path),
        "size_bytes": paper_path.stat().st_size,
        "sha256": compute_sha256(paper_path),
        "source_url": PAPER_PDF_URL,
    }

    return results


def load_aqr_reference_factors(excel_path: Optional[Path] = None) -> pd.DataFrame:
    """Load and parse AQR official paper monthly TSMOM factors.
    
    Returns a DataFrame with DatetimeIndex and columns:
    ['TSMOM', 'TSMOM_EQ', 'TSMOM_FX', 'TSMOM_FI', 'TSMOM_CM'].
    """
    if excel_path is None:
        excel_path = DEFAULT_AQR_FILE

    if not excel_path.exists():
        raise FileNotFoundError(f"AQR Excel not found at {excel_path}. Run prepare_project2_sources.py first.")

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    if "TSMOM factors" not in wb.sheetnames:
        raise ValueError(f"Expected sheet 'TSMOM factors' in {excel_path}, found {wb.sheetnames}")

    sheet = wb["TSMOM factors"]
    # Find header row with 'DATE'
    header_row = None
    for r in range(1, 25):
        val = sheet.cell(r, 1).value
        if val is not None and str(val).strip().upper() == "DATE":
            header_row = r
            break

    if header_row is None:
        raise ValueError(f"Header row with 'DATE' not found in {excel_path}")

    headers = [sheet.cell(header_row, c).value for c in range(1, 7)]
    # Standardize column names
    col_mapping = {
        "DATE": "date",
        "TSMOM": "TSMOM",
        "TSMOM^EQ": "TSMOM_EQ",
        "TSMOM^FX": "TSMOM_FX",
        "TSMOM^FI": "TSMOM_FI",
        "TSMOM^CM": "TSMOM_CM",
    }

    records = []
    for r in range(header_row + 1, sheet.max_row + 1):
        dt_val = sheet.cell(r, 1).value
        if dt_val is None:
            continue
        row_dict = {"date": pd.to_datetime(dt_val)}
        for c, h in enumerate(headers[1:], start=2):
            raw_h = str(h).strip()
            norm_col = col_mapping.get(raw_h, raw_h)
            val = sheet.cell(r, c).value
            row_dict[norm_col] = float(val) if val is not None else np.nan
        records.append(row_dict)

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["month"] = df["date"].dt.to_period("M")
    return df


def calculate_reference_metrics(series_or_df: pd.Series | pd.DataFrame) -> Dict[str, Any]:
    """Calculate standard monthly performance metrics for reference factor series."""
    if isinstance(series_or_df, pd.DataFrame):
        results = {}
        for col in series_or_df.columns:
            if col not in ("date", "month"):
                results[col] = calculate_reference_metrics(series_or_df[col])
        return results

    s = series_or_df.dropna()
    n_months = len(s)
    if n_months == 0:
        return {"n_months": 0}

    mean_m = float(s.mean())
    vol_m = float(s.std(ddof=1))
    ann_mean = mean_m * 12.0
    ann_vol = vol_m * np.sqrt(12.0)
    sharpe = ann_mean / ann_vol if ann_vol > 1e-8 else 0.0

    # Compounded cumulative wealth with initial capital 1.0 at index 0
    cum_wealth = np.insert(np.cumprod(1.0 + s.values), 0, 1.0)
    peak = np.maximum.accumulate(cum_wealth)
    drawdown = (cum_wealth - peak) / peak
    max_dd = float(np.min(drawdown))

    # CAGR if ending wealth > 0
    end_wealth = float(cum_wealth[-1])
    cagr = (end_wealth ** (12.0 / n_months)) - 1.0 if end_wealth > 0 else np.nan

    skew = float(s.skew())
    pos_ratio = float((s > 0).mean())

    return {
        "n_months": n_months,
        "mean_monthly": mean_m,
        "ann_mean": ann_mean,
        "vol_monthly": vol_m,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "skewness": skew,
        "positive_ratio": pos_ratio,
        "total_compound_return": end_wealth - 1.0,
    }

