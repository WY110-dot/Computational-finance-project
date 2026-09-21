"""
ETF Price Adjustment Module (Phase C1)
Handles ETF dividend/split adjustment factor integration,
calculates forward-adjusted OHLC prices, and generates
clean, ex-dividend corrected total return series.
"""

from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np


class ETFAdjuster:
    """
    Adjusts raw ETF market data using official cumulative adjustment factors (fund_adj).
    
    Adheres to Project 1 C1 price convention:
    - raw price: used for real execution, transaction notional, and accounting ledger.
    - adjusted price: used for technical factors (momentum, volatility) and signals.
    - total return (ret_total): used for strategy return, benchmark, and evaluation.
    """

    STANDARD_COLUMNS = [
        "date",
        "asset",
        "open_raw",
        "high_raw",
        "low_raw",
        "close_raw",
        "volume",
        "amount",
        "adj_factor",
        "adjustment_reference_date",
        "open_adj",
        "high_adj",
        "low_adj",
        "close_adj",
        "ret_total",
    ]

    def __init__(self, reference_date: Optional[str] = None):
        """
        Initialize ETF adjuster.
        
        Args:
            reference_date (str, optional): Fixed reference date tau (YYYYMMDD) for forward adjustment.
                                           If None, will default to the latest date in the dataset.
        """
        self.reference_date = str(reference_date) if reference_date else None

    def merge_raw_and_adj(
        self,
        df_price: pd.DataFrame,
        df_adj: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge raw daily prices with adjustment factors on (trade_date, ts_code).
        
        Args:
            df_price: DataFrame containing raw price data
            df_adj: DataFrame containing adj_factor data
            
        Returns:
            pd.DataFrame: Merged and validated dataframe sorted chronologically
        """
        if df_price.empty:
            raise ValueError("Price dataframe is empty.")
        if df_adj.empty:
            raise ValueError("Adjustment factor dataframe is empty.")

        # Standardize column naming for merge
        p = df_price.copy()
        a = df_adj.copy()

        # Format dates as strings
        p["trade_date"] = p["trade_date"].astype(str)
        a["trade_date"] = a["trade_date"].astype(str)

        # Ensure required columns
        for col in ["open", "high", "low", "close"]:
            if col not in p.columns:
                raise KeyError(f"Price dataframe missing required price column: {col}")

        if "adj_factor" not in a.columns:
            raise KeyError("Adjustment dataframe missing 'adj_factor' column.")

        # Keep only necessary columns from adj dataframe
        adj_cols = ["trade_date", "adj_factor"]
        if "ts_code" in a.columns and "ts_code" in p.columns:
            adj_cols.append("ts_code")
            merged = pd.merge(p, a[adj_cols], on=["ts_code", "trade_date"], how="left")
        else:
            merged = pd.merge(p, a[["trade_date", "adj_factor"]], on="trade_date", how="left")

        # Sort chronologically
        merged = merged.sort_values("trade_date").reset_index(drop=True)

        # Forward fill adjustment factors if missing on non-dividend days
        merged["adj_factor"] = merged["adj_factor"].ffill().bfill()

        # Validate adjustment factor
        if (merged["adj_factor"] <= 0).any():
            raise ValueError("Found non-positive adjustment factor in data, which is invalid.")

        return merged

    def compute_forward_adjustment(
        self,
        df: pd.DataFrame,
        reference_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Computes forward-adjusted OHLC prices and total return.
        
        Formula:
            P_adj(t) = P_raw(t) * [ a(t) / a(tau) ]
            ret_total(t) = close_adj(t) / close_adj(t-1) - 1
            
        Args:
            df: Merged dataframe with raw OHLC and adj_factor
            reference_date: Reference date tau. Defaults to self.reference_date or max(date).
            
        Returns:
            pd.DataFrame: Processed DataFrame containing standard C1 columns and legacy aliases.
        """
        result = df.copy()

        # Determine reference date tau
        if reference_date is not None:
            tau = str(reference_date)
        elif self.reference_date is not None:
            tau = self.reference_date
        else:
            tau = str(result["trade_date"].max())

        # Find adj_factor at tau
        tau_rows = result[result["trade_date"] == tau]
        if tau_rows.empty:
            raise ValueError(f"Reference date {tau} not found in the dataset.")
        a_tau = float(tau_rows["adj_factor"].iloc[0])

        if a_tau <= 0:
            raise ValueError(f"Adjustment factor at reference date {tau} is non-positive: {a_tau}")

        # Preserve raw prices explicitly
        result["open_raw"] = result["open"].astype(float)
        result["high_raw"] = result["high"].astype(float)
        result["low_raw"] = result["low"].astype(float)
        result["close_raw"] = result["close"].astype(float)

        # Normalize volume and amount
        vol_col = "vol" if "vol" in result.columns else "volume"
        result["volume"] = result[vol_col].astype(float) if vol_col in result.columns else 0.0
        result["amount"] = result["amount"].astype(float) if "amount" in result.columns else 0.0

        # Identifiers
        result["date"] = result["trade_date"].astype(str)
        result["asset"] = result["ts_code"].astype(str) if "ts_code" in result.columns else "UNKNOWN"
        result["adjustment_reference_date"] = tau

        # Compute forward adjustment ratio: a(t) / a(tau)
        ratio = result["adj_factor"] / a_tau

        result["open_adj"] = result["open_raw"] * ratio
        result["high_adj"] = result["high_raw"] * ratio
        result["low_adj"] = result["low_raw"] * ratio
        result["close_adj"] = result["close_raw"] * ratio

        # Compute total return based on close_adj
        result["ret_total"] = result["close_adj"].pct_change().fillna(0.0)

        # Backward compatibility aliases:
        # Keep 'close', 'open', 'high', 'low' aligned with adjusted prices for factor calculations,
        # or preserve raw depending on workflow. By C1 spec, we keep raw and adj distinct,
        # and set 'close' as alias to 'close_adj' for existing strategy compatibility.
        result["close"] = result["close_adj"]
        result["open"] = result["open_adj"]
        result["high"] = result["high_adj"]
        result["low"] = result["low_adj"]

        return result

    def validate_adjustment_vs_pct_chg(
        self,
        df: pd.DataFrame,
        tolerance: float = 1e-4
    ) -> Dict:
        """
        Validates computed ret_total against Tushare's official pct_chg.
        
        Args:
            df: DataFrame containing 'ret_total' and 'pct_chg'
            tolerance: Maximum tolerated absolute percentage error (default 0.01%)
            
        Returns:
            Dict: Diagnostic summary of the validation
        """
        if "pct_chg" not in df.columns:
            return {
                "status": "SKIPPED",
                "message": "'pct_chg' column not found in dataframe for comparison."
            }

        # Tushare's pct_chg is in percent (e.g. 1.1578 means +1.1578%)
        # ret_total is decimal (e.g. 0.011578)
        ret_calc_pct = df["ret_total"] * 100.0
        ret_ref_pct = df["pct_chg"]

        # Ignore row 0 (initial condition)
        diff = (ret_calc_pct.iloc[1:] - ret_ref_pct.iloc[1:]).abs()

        max_diff = float(diff.max())
        mean_diff = float(diff.mean())
        mismatches = int((diff > tolerance * 100).sum())

        passed = mismatches == 0

        return {
            "status": "PASS" if passed else "FAIL",
            "records_checked": len(diff),
            "max_abs_diff_pct": max_diff,
            "mean_abs_diff_pct": mean_diff,
            "mismatch_count": mismatches,
            "tolerance_pct": tolerance * 100,
        }

    def process_and_standardize(
        self,
        df_price: pd.DataFrame,
        df_adj: pd.DataFrame,
        reference_date: Optional[str] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Complete pipeline: merges raw data and factors, computes forward adjustment,
        and validates against official pct_chg.
        
        Returns:
            Tuple[pd.DataFrame, Dict]: (Adjusted DataFrame, Validation Results)
        """
        merged = self.merge_raw_and_adj(df_price, df_adj)
        adjusted = self.compute_forward_adjustment(merged, reference_date=reference_date)
        diagnostics = self.validate_adjustment_vs_pct_chg(adjusted)
        return adjusted, diagnostics

