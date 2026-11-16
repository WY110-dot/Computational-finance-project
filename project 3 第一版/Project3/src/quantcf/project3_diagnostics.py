"""Project 3 Diagnostics: Factor IC, terciles, correlations, residuals, and block bootstrap."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from quantcf.project3_pipeline import assign_tercile_memberships


def compute_factor_ic_series(
    df_factors: pd.DataFrame,
    df_labels: pd.DataFrame,
    factor_names: List[str] = ["A", "B", "C", "F2", "F3", "A0"],
    min_assets: int = 6,
) -> pd.DataFrame:
    """Compute Pearson IC and Spearman Rank IC for each factor on each formation date."""
    df_f = df_factors.copy()
    if "date" in df_f.columns and "formation_date" not in df_f.columns:
        df_f = df_f.rename(columns={"date": "formation_date"})
    merged = pd.merge(df_f, df_labels, on=["formation_date", "asset"], how="inner")
    if merged.empty:
        return pd.DataFrame(columns=["formation_date", "factor", "pearson_ic", "rank_ic", "n_assets"])
    
    records = []
    for (t, factor), grp in merged.groupby(["formation_date", "factor"]):
        sub = grp.dropna(subset=["value", "holding_return"])
        if len(sub) < min_assets:
            continue
        
        # Check standard deviations
        std_val = sub["value"].std(ddof=0)
        std_ret = sub["holding_return"].std(ddof=0)
        if std_val < 1e-12 or std_ret < 1e-12:
            records.append({
                "formation_date": t,
                "factor": factor,
                "pearson_ic": np.nan,
                "rank_ic": np.nan,
                "n_assets": len(sub),
                "is_degenerate": True,
            })
            continue
            
        p_ic, _ = stats.pearsonr(sub["value"], sub["holding_return"])
        r_ic, _ = stats.spearmanr(sub["value"], sub["holding_return"])
        
        records.append({
            "formation_date": t,
            "factor": factor,
            "pearson_ic": float(p_ic),
            "rank_ic": float(r_ic),
            "n_assets": len(sub),
            "is_degenerate": False,
        })
        
    return pd.DataFrame(records)


def summarize_ic_series(df_ic: pd.DataFrame) -> pd.DataFrame:
    """Summarize IC metrics across dates for each factor."""
    summary_rows = []
    for factor, grp in df_ic.groupby("factor"):
        valid_rank = grp["rank_ic"].dropna()
        valid_pearson = grp["pearson_ic"].dropna()
        n_dates = len(valid_rank)
        
        if n_dates > 0:
            r_mean = float(valid_rank.mean())
            r_std = float(valid_rank.std(ddof=1)) if n_dates > 1 else 0.0
            r_icir = float(r_mean / r_std) if r_std > 1e-8 else np.nan
            r_pos = float((valid_rank > 0).mean())
            r_t = float(r_mean / (r_std / np.sqrt(n_dates))) if (r_std > 1e-8 and n_dates > 1) else np.nan
            
            p_mean = float(valid_pearson.mean())
            p_std = float(valid_pearson.std(ddof=1)) if n_dates > 1 else 0.0
            p_icir = float(p_mean / p_std) if p_std > 1e-8 else np.nan
            p_pos = float((valid_pearson > 0).mean())
            p_t = float(p_mean / (p_std / np.sqrt(n_dates))) if (p_std > 1e-8 and n_dates > 1) else np.nan
            
            summary_rows.append({
                "factor": factor,
                "n_dates": n_dates,
                "rank_ic_mean": r_mean,
                "rank_ic_std": r_std,
                "rank_icir": r_icir,
                "rank_ic_tstat": r_t,
                "rank_ic_pos_ratio": r_pos,
                "pearson_ic_mean": p_mean,
                "pearson_ic_std": p_std,
                "pearson_icir": p_icir,
                "pearson_ic_tstat": p_t,
                "pearson_ic_pos_ratio": p_pos,
            })
        else:
            summary_rows.append({
                "factor": factor,
                "n_dates": 0,
                "rank_ic_mean": np.nan,
                "rank_ic_std": np.nan,
                "rank_icir": np.nan,
                "rank_ic_tstat": np.nan,
                "rank_ic_pos_ratio": np.nan,
                "pearson_ic_mean": np.nan,
                "pearson_ic_std": np.nan,
                "pearson_icir": np.nan,
                "pearson_ic_tstat": np.nan,
                "pearson_ic_pos_ratio": np.nan,
            })
            
    return pd.DataFrame(summary_rows).sort_values("factor").reset_index(drop=True)


def compute_tercile_returns_series(
    df_factors_wide: pd.DataFrame,
    df_labels: pd.DataFrame,
    factor_names: List[str] = ["A", "B", "C", "F2", "F3"],
    min_assets: int = 6,
) -> pd.DataFrame:
    """Compute equal-weighted forward returns for each tercile (T1 Bottom, T2 Mid, T3 Top) and Spread."""
    merged = pd.merge(df_factors_wide, df_labels, on=["formation_date", "asset"], how="inner")
    if merged.empty:
        return pd.DataFrame()
    
    records = []
    for t, grp in merged.groupby("formation_date"):
        sub = grp.set_index("asset")
        if len(sub) < min_assets:
            continue
        
        rets = sub["holding_return"]
        
        for factor in factor_names:
            if factor not in sub.columns:
                continue
            scores = sub[factor].dropna()
            if len(scores) < min_assets:
                continue
            
            memberships = assign_tercile_memberships(scores)
            
            # Compute weighted returns
            # T1, T2, T3
            m_t1 = np.array([memberships[a][0] for a in scores.index])
            m_t2 = np.array([memberships[a][1] for a in scores.index])
            m_t3 = np.array([memberships[a][2] for a in scores.index])
            y = np.array([rets.loc[a] for a in scores.index])
            
            sum_m1 = np.sum(m_t1)
            sum_m2 = np.sum(m_t2)
            sum_m3 = np.sum(m_t3)
            
            r_t1 = float(np.sum(m_t1 * y) / sum_m1) if sum_m1 > 0 else np.nan
            r_t2 = float(np.sum(m_t2 * y) / sum_m2) if sum_m2 > 0 else np.nan
            r_t3 = float(np.sum(m_t3 * y) / sum_m3) if sum_m3 > 0 else np.nan
            spread = float(r_t3 - r_t1) if (not np.isnan(r_t3) and not np.isnan(r_t1)) else np.nan
            
            records.append({
                "formation_date": t,
                "factor": factor,
                "t1_return": r_t1,
                "t2_return": r_t2,
                "t3_return": r_t3,
                "spread_t3_minus_t1": spread,
            })
            
    return pd.DataFrame(records)


def compute_cross_sectional_residual_factor(
    df_factors_wide: pd.DataFrame,
    df_labels: pd.DataFrame,
    min_assets: int = 6,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Perform cross-sectional regression: B = alpha_t + beta_t * A + epsilon_t.
    
    Evaluates Rank IC and tercile returns of the residual factor epsilon_t.
    """
    merged = pd.merge(df_factors_wide, df_labels, on=["formation_date", "asset"], how="inner")
    
    residual_records = []
    regression_stats = []
    
    for t, grp in merged.groupby("formation_date"):
        sub = grp.dropna(subset=["A", "B", "holding_return"])
        if len(sub) < min_assets:
            continue
        
        x = sub["A"].to_numpy(dtype=float)
        y = sub["B"].to_numpy(dtype=float)
        
        # Cross-sectional OLS with intercept
        # B = alpha + beta * A + epsilon
        x_mat = np.column_stack([np.ones_like(x), x])
        try:
            # Solve OLS
            coeffs, residuals_sum, rank, s = np.linalg.lstsq(x_mat, y, rcond=1e-12)
            alpha, beta = float(coeffs[0]), float(coeffs[1])
            fit = x_mat @ coeffs
            epsilon = y - fit
            
            # Check orthogonality: dot(epsilon, ones) approx 0, dot(epsilon, x) approx 0
            ortho_mean = abs(float(np.mean(epsilon)))
            ortho_cov = abs(float(np.dot(epsilon, x)))
            
            r2 = 1.0 - float(np.var(epsilon) / np.var(y)) if np.var(y) > 1e-12 else np.nan
            
            regression_stats.append({
                "formation_date": t,
                "alpha": alpha,
                "beta": beta,
                "r2": r2,
                "ortho_mean_abs": ortho_mean,
                "ortho_cov_abs": ortho_cov,
                "n_assets": len(sub),
            })
            
            # Compute Rank IC of epsilon against holding_return
            f_ret = sub["holding_return"].to_numpy(dtype=float)
            r_ic, _ = stats.spearmanr(epsilon, f_ret)
            p_ic, _ = stats.pearsonr(epsilon, f_ret)
            
            # Terciles of epsilon
            eps_series = pd.Series(epsilon, index=sub["asset"])
            memberships = assign_tercile_memberships(eps_series)
            m_t1 = np.array([memberships[a][0] for a in sub["asset"]])
            m_t3 = np.array([memberships[a][2] for a in sub["asset"]])
            ret_t1 = float(np.sum(m_t1 * f_ret) / np.sum(m_t1))
            ret_t3 = float(np.sum(m_t3 * f_ret) / np.sum(m_t3))
            
            residual_records.append({
                "formation_date": t,
                "rank_ic": float(r_ic),
                "pearson_ic": float(p_ic),
                "t1_return": ret_t1,
                "t3_return": ret_t3,
                "spread_t3_minus_t1": ret_t3 - ret_t1,
                "alpha": alpha,
                "beta": beta,
                "r2": r2,
                "ortho_mean_abs": ortho_mean,
                "ortho_cov_abs": ortho_cov,
                "n_assets": len(sub),
            })
        except Exception:
            continue
            
    df_res = pd.DataFrame(residual_records)
    df_reg = pd.DataFrame(regression_stats)
    
    if not df_res.empty:
        r_mean = float(df_res["rank_ic"].mean())
        r_std = float(df_res["rank_ic"].std(ddof=1)) if len(df_res) > 1 else 0.0
        r_icir = float(r_mean / r_std) if r_std > 1e-8 else np.nan
        r_pos = float((df_res["rank_ic"] > 0).mean())
        
        summary = {
            "n_dates": len(df_res),
            "residual_rank_ic_mean": r_mean,
            "residual_rank_ic_std": r_std,
            "residual_rank_icir": r_icir,
            "residual_rank_ic_pos_ratio": r_pos,
            "residual_spread_ann": float(df_res["spread_t3_minus_t1"].mean() * 12.0),
            "mean_beta_on_A": float(df_res["beta"].mean()) if not df_res.empty else np.nan,
            "mean_r2": float(df_res["r2"].mean()) if not df_res.empty else np.nan,
            "max_ortho_mean_abs": float(df_res["ortho_mean_abs"].max()) if not df_res.empty else 0.0,
            "max_ortho_cov_abs": float(df_res["ortho_cov_abs"].max()) if not df_res.empty else 0.0,
            "orthogonality_verified": bool((df_res["ortho_mean_abs"].max() < 1e-8) and (df_res["ortho_cov_abs"].max() < 1e-8)),
        }
    else:
        summary = {"n_dates": 0}
        
    return df_res, summary


def compute_pairwise_difference_table(
    monthly_ret_C: pd.DataFrame,
    monthly_ret_A: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute paired return difference statistics: C - A."""
    merged = pd.merge(
        monthly_ret_C[["formation_date", "net_return", "turnover", "fees"]],
        monthly_ret_A[["formation_date", "net_return", "turnover", "fees"]],
        on="formation_date",
        suffixes=("_C", "_A"),
        how="inner",
    ).sort_values("formation_date")
    
    if merged.empty:
        return {}
    
    diff = merged["net_return_C"] - merged["net_return_A"]
    n_m = len(diff)
    
    mean_diff = float(diff.mean())
    ann_mean_diff = float(mean_diff * 12.0)
    std_diff = float(diff.std(ddof=1)) if n_m > 1 else 0.0
    tracking_error = float(std_diff * np.sqrt(12.0)) if n_m > 1 else 0.0
    info_ratio = float(ann_mean_diff / tracking_error) if tracking_error > 1e-8 else np.nan
    t_stat = float(mean_diff / (std_diff / np.sqrt(n_m))) if (std_diff > 1e-8 and n_m > 1) else np.nan
    win_rate = float((diff > 0).mean())
    
    # CAGR and Sharpe for C and A
    ann_mean_C = float(merged["net_return_C"].mean() * 12.0)
    ann_vol_C = float(merged["net_return_C"].std(ddof=1) * np.sqrt(12.0)) if n_m > 1 else 0.0
    sharpe_C = float(ann_mean_C / ann_vol_C) if ann_vol_C > 1e-8 else np.nan
    
    ann_mean_A = float(merged["net_return_A"].mean() * 12.0)
    ann_vol_A = float(merged["net_return_A"].std(ddof=1) * np.sqrt(12.0)) if n_m > 1 else 0.0
    sharpe_A = float(ann_mean_A / ann_vol_A) if ann_vol_A > 1e-8 else np.nan
    sharpe_diff = float(sharpe_C - sharpe_A)
    
    turnover_diff = float(merged["turnover_C"].mean() - merged["turnover_A"].mean())
    fee_diff_ann = float((merged["fees_C"].sum() - merged["fees_A"].sum()) / (n_m / 12.0)) if n_m > 0 else 0.0
    
    return {
        "n_months": n_m,
        "ann_mean_diff": ann_mean_diff,
        "tracking_error": tracking_error,
        "information_ratio": info_ratio,
        "t_stat": t_stat,
        "win_rate": win_rate,
        "sharpe_C": sharpe_C,
        "sharpe_A": sharpe_A,
        "sharpe_diff": sharpe_diff,
        "mean_turnover_diff": turnover_diff,
        "annual_fee_diff": fee_diff_ann,
        "paired_series": merged,
    }


def circular_block_bootstrap_pairwise(
    monthly_ret_C: pd.DataFrame,
    monthly_ret_A: pd.DataFrame,
    block_size: int = 3,
    n_reps: int = 2000,
    seed: int = 20261116,
) -> Dict[str, Any]:
    """Perform circular moving block bootstrap on paired monthly returns (R_C, R_A).
    
    Preserves time-series autocorrelation and cross-sectional dependence by sampling paired months.
    """
    merged = pd.merge(
        monthly_ret_C[["formation_date", "net_return"]],
        monthly_ret_A[["formation_date", "net_return"]],
        on="formation_date",
        suffixes=("_C", "_A"),
        how="inner",
    ).sort_values("formation_date")
    
    if merged.empty:
        return {}
    
    r_c = merged["net_return_C"].to_numpy(dtype=float)
    r_a = merged["net_return_A"].to_numpy(dtype=float)
    T = len(r_c)
    
    if T < 4:
        return {"error": f"Sample size T={T} too small for bootstrap"}
    
    rng = np.random.default_rng(seed)
    
    diff_ann_list = []
    sharpe_diff_list = []
    failed_reps = 0
    
    n_blocks = int(np.ceil(T / block_size))
    
    for _ in range(n_reps):
        # Draw random block starting positions from [0, T-1]
        start_indices = rng.integers(0, T, size=n_blocks)
        sample_indices = []
        for s in start_indices:
            for b in range(block_size):
                sample_indices.append((s + b) % T)
                
        # Truncate to exact length T
        idx = sample_indices[:T]
        sub_c = r_c[idx]
        sub_a = r_a[idx]
        
        ann_c = float(np.mean(sub_c) * 12.0)
        ann_a = float(np.mean(sub_a) * 12.0)
        delta_ann = ann_c - ann_a
        
        vol_c = float(np.std(sub_c, ddof=1) * np.sqrt(12.0))
        vol_a = float(np.std(sub_a, ddof=1) * np.sqrt(12.0))
        
        if vol_c < 1e-8 or vol_a < 1e-8:
            failed_reps += 1
            continue
            
        sh_c = ann_c / vol_c
        sh_a = ann_a / vol_a
        delta_sh = sh_c - sh_a
        
        diff_ann_list.append(delta_ann)
        sharpe_diff_list.append(delta_sh)
        
    diff_ann_arr = np.array(diff_ann_list)
    sharpe_diff_arr = np.array(sharpe_diff_list)
    
    ci_ann_lower = float(np.percentile(diff_ann_arr, 2.5))
    ci_ann_upper = float(np.percentile(diff_ann_arr, 97.5))
    ci_sh_lower = float(np.percentile(sharpe_diff_arr, 2.5))
    ci_sh_upper = float(np.percentile(sharpe_diff_arr, 97.5))
    
    return {
        "block_size": block_size,
        "n_reps": n_reps,
        "valid_reps": len(diff_ann_list),
        "failed_reps": failed_reps,
        "delta_ann_mean": float(np.mean(diff_ann_arr)),
        "delta_ann_ci_95": [ci_ann_lower, ci_ann_upper],
        "delta_ann_pos_pct": float(np.mean(diff_ann_arr > 0)),
        "delta_sharpe_mean": float(np.mean(sharpe_diff_arr)),
        "delta_sharpe_ci_95": [ci_sh_lower, ci_sh_upper],
        "delta_sharpe_pos_pct": float(np.mean(sharpe_diff_arr > 0)),
    }
