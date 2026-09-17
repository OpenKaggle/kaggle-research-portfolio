from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker, LGBMRegressor
from sklearn.model_selection import GroupKFold


sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_rogii_structured_selector as structured  # noqa: E402
import generate_rogii_candidate_paths as candgen  # noqa: E402


REPORT_DIR = Path("reports")


def quantile_bin(values: pd.Series, bins: int = 3) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if values.notna().sum() == 0 or values.nunique(dropna=True) <= 1:
        return pd.Series(np.zeros(len(values), dtype=int), index=values.index)
    q = min(bins, values.nunique(dropna=True))
    return (
        pd.qcut(values.rank(method="first"), q=q, labels=False, duplicates="drop")
        .fillna(0)
        .astype(int)
    )


def diagnostic_well_frame(features: pd.DataFrame, diagnostic_path: Path) -> pd.DataFrame:
    frame = (
        features.groupby("well", sort=False)
        .agg(
            hidden_rows=("hidden_rows", "max"),
            eval_z_min=("segment_z", "min"),
            eval_z_max=("segment_z", "max"),
            overall_azimuth_sin=("overall_azimuth_sin", "first"),
            overall_azimuth_cos=("overall_azimuth_cos", "first"),
            prefix_c_slope_200=("prefix_c_slope_200", "first"),
            unc_segment_grid_std_mean=("unc_segment_grid_std_mean", "mean"),
        )
        .reset_index()
    )
    frame["eval_z_range"] = frame["eval_z_max"] - frame["eval_z_min"]
    frame["abs_prefix_c_slope_200"] = frame["prefix_c_slope_200"].abs()
    if diagnostic_path.exists():
        diagnostics = pd.read_csv(diagnostic_path)
        visible_cols = [
            "well",
            "hidden_rows",
            "eval_z_range",
            "azimuth",
            "abs_prefix_c_slope_200",
            "unc_segment_grid_std_mean_mean",
        ]
        diagnostics = diagnostics[[col for col in visible_cols if col in diagnostics.columns]]
        frame = frame.merge(diagnostics, on="well", how="left", suffixes=("", "_diag"))
        for col in ("hidden_rows", "eval_z_range", "abs_prefix_c_slope_200"):
            diag_col = f"{col}_diag"
            if diag_col in frame:
                frame[col] = frame[diag_col].combine_first(frame[col])
        if "unc_segment_grid_std_mean_mean" in frame:
            frame["unc_segment_grid_std_mean"] = frame[
                "unc_segment_grid_std_mean_mean"
            ].combine_first(frame["unc_segment_grid_std_mean"])
    if "azimuth" not in frame:
        frame["azimuth"] = np.degrees(
            np.arctan2(frame["overall_azimuth_sin"], frame["overall_azimuth_cos"])
        )
    return frame


def diagnostic_stratified_splits(
    features: pd.DataFrame,
    n_splits: int,
    seed: int,
    diagnostic_path: Path,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], pd.DataFrame]:
    well_frame = diagnostic_well_frame(features, diagnostic_path)
    well_frame["length_bin"] = quantile_bin(well_frame["hidden_rows"], 3)
    well_frame["z_range_bin"] = quantile_bin(well_frame["eval_z_range"], 3)
    well_frame["uncertainty_bin"] = quantile_bin(well_frame["unc_segment_grid_std_mean"], 3)
    well_frame["azimuth_sign"] = (well_frame["azimuth"] >= 0).astype(int)
    well_frame["c_slope_sign"] = (well_frame["prefix_c_slope_200"] >= 0).astype(int)
    well_frame["stratum"] = (
        well_frame["length_bin"].astype(str)
        + "_"
        + well_frame["z_range_bin"].astype(str)
        + "_"
        + well_frame["azimuth_sign"].astype(str)
        + "_"
        + well_frame["c_slope_sign"].astype(str)
    )

    rng = np.random.default_rng(seed)
    shuffled = well_frame.assign(_jitter=rng.random(len(well_frame))).sort_values(
        ["hidden_rows", "_jitter"], ascending=[False, True]
    )
    fold_weights = np.zeros(n_splits, dtype=float)
    fold_strata: list[dict[str, int]] = [dict() for _ in range(n_splits)]
    assignments: dict[str, int] = {}

    # Seed each fold with one large well so no fold starts empty.
    for fold, (_, row) in enumerate(shuffled.head(n_splits).iterrows()):
        well = str(row["well"])
        stratum = str(row["stratum"])
        weight = float(row["hidden_rows"])
        assignments[well] = fold
        fold_weights[fold] += weight
        fold_strata[fold][stratum] = fold_strata[fold].get(stratum, 0) + 1

    remaining = shuffled.iloc[n_splits:].copy()
    remaining = remaining.sort_values(["stratum", "hidden_rows", "_jitter"], ascending=[True, False, True])
    target_weight = max(float(well_frame["hidden_rows"].sum()) / n_splits, 1.0)
    for _, row in remaining.iterrows():
        well = str(row["well"])
        stratum = str(row["stratum"])
        weight = float(row["hidden_rows"])
        scores = []
        for fold in range(n_splits):
            stratum_count = fold_strata[fold].get(stratum, 0)
            weight_after = (fold_weights[fold] + weight) / target_weight
            scores.append(weight_after + 0.35 * stratum_count + 1e-6 * rng.random())
        fold = int(np.argmin(scores))
        assignments[well] = fold
        fold_weights[fold] += weight
        fold_strata[fold][stratum] = fold_strata[fold].get(stratum, 0) + 1

    well_frame["fold"] = well_frame["well"].map(assignments).astype(int) + 1
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    wells_by_fold = {
        fold: set(well_frame.loc[well_frame["fold"] == fold + 1, "well"].astype(str))
        for fold in range(n_splits)
    }
    all_index = np.arange(len(features))
    feature_wells = features["well"].astype(str).to_numpy()
    for fold in range(n_splits):
        valid_mask = np.isin(feature_wells, list(wells_by_fold[fold]))
        splits.append((all_index[~valid_mask], all_index[valid_mask]))
    return splits, well_frame


def safe_corr_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_centered = a - np.nanmean(a, axis=1, keepdims=True)
    b_centered = b - np.nanmean(b, axis=1, keepdims=True)
    numerator = np.nansum(a_centered * b_centered, axis=1)
    denominator = np.sqrt(
        np.nansum(a_centered**2, axis=1) * np.nansum(b_centered**2, axis=1)
    )
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator, dtype=float),
        where=denominator > 1e-9,
    )


def family_median_paths(c_paths: np.ndarray, families: np.ndarray) -> dict[str, np.ndarray]:
    return {
        family: np.nanmedian(c_paths[families == family], axis=0)
        for family in sorted(set(families))
    }


def robust_slope(y: np.ndarray, x: np.ndarray) -> float:
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    finite = np.isfinite(y) & np.isfinite(x)
    if finite.sum() < 3 or np.std(x[finite]) < 1e-9:
        return 0.0
    return float(np.polyfit(x[finite], y[finite], 1)[0])


def build_segment_rows(
    wid: str,
    hw: pd.DataFrame,
    tw: pd.DataFrame,
    ctx: dict[str, object],
    names: list[str],
    families: list[str],
    tvt: np.ndarray,
    segment_length: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
    y = hw["TVT"].to_numpy(float)[hidden_idx]
    z = hw["Z"].to_numpy(float)[hidden_idx]
    md = hw["MD"].to_numpy(float)[hidden_idx]
    x = hw["X"].to_numpy(float)[hidden_idx]
    y_coord = hw["Y"].to_numpy(float)[hidden_idx]
    gr = hw["GR"].to_numpy(float)[hidden_idx]
    c_paths = tvt + z[None, :]
    family_arr = np.asarray(families)
    family_medians = family_median_paths(c_paths, family_arr)
    uncertainty_groups = {
        "pf_seed": np.flatnonzero(family_arr == "pf_frontier_seed"),
        "pf_ensemble": np.flatnonzero(family_arr == "pf_frontier_ensemble"),
        "beam": np.flatnonzero(family_arr == "dwt_beam"),
        "formation": np.flatnonzero(family_arr == "dwt_form"),
        "segment_grid": np.flatnonzero(family_arr == "segment_grid"),
    }
    uncertainty_paths = {}
    for label, idx in uncertainty_groups.items():
        if len(idx) < 2:
            continue
        group_paths = c_paths[idx]
        uncertainty_paths[label] = (
            np.nanmedian(group_paths, axis=0),
            np.nanstd(group_paths, axis=0),
            np.nanpercentile(group_paths, 75, axis=0)
            - np.nanpercentile(group_paths, 25, axis=0),
        )
    ps = int(ctx["ps"])
    full_md = hw["MD"].to_numpy(float)
    full_x = hw["X"].to_numpy(float)
    full_y = hw["Y"].to_numpy(float)
    full_z = hw["Z"].to_numpy(float)
    full_tvt_input = hw["TVT_input"].to_numpy(float)
    known_c = full_tvt_input[: ps + 1] + full_z[: ps + 1]
    prefix_c_slopes = {
        window: robust_slope(
            known_c[max(0, ps + 1 - window) : ps + 1],
            full_md[max(0, ps + 1 - window) : ps + 1],
        )
        for window in (50, 200, 500, 1000)
    }
    known_z_slope = robust_slope(
        full_z[max(0, ps - 499) : ps + 1],
        full_md[max(0, ps - 499) : ps + 1],
    )
    anchor_md = float(full_md[ps])
    anchor_x = float(full_x[ps])
    anchor_y = float(full_y[ps])
    anchor_z = float(full_z[ps])
    overall_dx = float(full_x[-1] - anchor_x)
    overall_dy = float(full_y[-1] - anchor_y)
    overall_azimuth = math.atan2(overall_dy, overall_dx)

    tw_tvt = tw["TVT"].to_numpy(float)
    tw_gr = tw["GR"].to_numpy(float)
    order = np.argsort(tw_tvt)
    tw_tvt = tw_tvt[order]
    tw_gr = tw_gr[order]

    rows: list[pd.DataFrame] = []
    segments: list[tuple[int, int]] = []
    for segment_id, start in enumerate(range(0, len(y), segment_length)):
        end = min(len(y), start + segment_length)
        segments.append((start, end))
        seg_tvt = tvt[:, start:end]
        seg_c = c_paths[:, start:end]
        seg_y = y[start:end]
        seg_gr = gr[start:end]
        seg_md = md[start:end]
        seg_x = x[start:end]
        seg_y_coord = y_coord[start:end]
        seg_z = z[start:end]
        length = end - start
        md_span = float(seg_md[-1] - seg_md[0]) if length > 1 else 0.0
        local_dx = float(seg_x[-1] - seg_x[0]) if length > 1 else 0.0
        local_dy = float(seg_y_coord[-1] - seg_y_coord[0]) if length > 1 else 0.0
        local_dz = float(seg_z[-1] - seg_z[0]) if length > 1 else 0.0
        local_azimuth = math.atan2(local_dy, local_dx)
        local_horizontal = float(np.hypot(local_dx, local_dy))
        local_inclination = math.atan2(local_horizontal, abs(local_dz) + 1e-9)
        gr_finite = seg_gr[np.isfinite(seg_gr)]
        gr_mean = float(np.mean(gr_finite)) if len(gr_finite) else 0.0
        gr_std = float(np.std(gr_finite)) if len(gr_finite) else 0.0
        gr_q25 = float(np.percentile(gr_finite, 25)) if len(gr_finite) else 0.0
        gr_q75 = float(np.percentile(gr_finite, 75)) if len(gr_finite) else 0.0
        gr_slope = robust_slope(seg_gr, seg_md)
        gr_diff = np.diff(seg_gr)
        gr_diff = gr_diff[np.isfinite(gr_diff)]
        mean_abs_dgr = float(np.mean(np.abs(gr_diff))) if len(gr_diff) else 0.0
        p95_abs_dgr = float(np.percentile(np.abs(gr_diff), 95)) if len(gr_diff) else 0.0

        expected_gr = np.interp(
            seg_tvt.reshape(-1),
            tw_tvt,
            tw_gr,
            left=np.nan,
            right=np.nan,
        ).reshape(seg_tvt.shape)
        residual = expected_gr - seg_gr[None, :]
        coverage = np.mean(np.isfinite(expected_gr), axis=1)
        gr_rmse = np.sqrt(np.nanmean(residual**2, axis=1))
        gr_mae = np.nanmean(np.abs(residual), axis=1)
        gr_bias = np.nanmean(residual, axis=1)
        gr_corr = safe_corr_rows(
            np.broadcast_to(seg_gr[None, :], expected_gr.shape),
            expected_gr,
        )

        dc = np.diff(seg_c, axis=1)
        d2c = np.diff(dc, axis=1)
        consensus = np.nanmedian(seg_c, axis=0)
        consensus_rmse = np.sqrt(np.mean((seg_c - consensus[None, :]) ** 2, axis=1))
        q25 = np.nanpercentile(seg_c, 25, axis=0)
        q75 = np.nanpercentile(seg_c, 75, axis=0)
        consensus_iqr_frac = np.mean((seg_c >= q25) & (seg_c <= q75), axis=1)

        target_rmse = np.sqrt(np.mean((seg_tvt - seg_y[None, :]) ** 2, axis=1))
        target_min = float(np.min(target_rmse))
        target_rank = pd.Series(target_rmse).rank(pct=True, method="average").to_numpy(float)
        frame = pd.DataFrame(
            {
                "well": wid,
                "segment_id": segment_id,
                "candidate_idx": np.arange(len(names), dtype=int),
                "candidate": names,
                "family": families,
                "segment_start": start,
                "segment_end": end,
                "segment_rows": length,
                "segment_frac": start / max(len(y) - 1, 1),
                "hidden_rows": len(y),
                "md_span": md_span,
                "md_from_anchor_start": float(seg_md[0] - anchor_md),
                "md_from_anchor_end": float(seg_md[-1] - anchor_md),
                "anchor_x": anchor_x,
                "anchor_y": anchor_y,
                "anchor_z": anchor_z,
                "segment_x": float(np.mean(seg_x)),
                "segment_y": float(np.mean(seg_y_coord)),
                "segment_z": float(np.mean(seg_z)),
                "segment_dx": local_dx,
                "segment_dy": local_dy,
                "segment_dz": local_dz,
                "segment_dz_dmd": local_dz / max(md_span, 1e-6),
                "segment_dxy_dmd": local_horizontal / max(md_span, 1e-6),
                "segment_azimuth_sin": math.sin(local_azimuth),
                "segment_azimuth_cos": math.cos(local_azimuth),
                "segment_inclination_sin": math.sin(local_inclination),
                "segment_inclination_cos": math.cos(local_inclination),
                "overall_azimuth_sin": math.sin(overall_azimuth),
                "overall_azimuth_cos": math.cos(overall_azimuth),
                "known_z_slope": known_z_slope,
                "gr_segment_mean": gr_mean,
                "gr_segment_std": gr_std,
                "gr_segment_iqr": gr_q75 - gr_q25,
                "gr_segment_slope": gr_slope,
                "gr_segment_mean_abs_diff": mean_abs_dgr,
                "gr_segment_p95_abs_diff": p95_abs_dgr,
                "pred_start": seg_tvt[:, 0],
                "pred_end": seg_tvt[:, -1],
                "pred_delta": seg_tvt[:, -1] - seg_tvt[:, 0],
                "c_start": seg_c[:, 0],
                "c_end": seg_c[:, -1],
                "c_delta": seg_c[:, -1] - seg_c[:, 0],
                "c_slope_md": (
                    (seg_c[:, -1] - seg_c[:, 0]) / max(md_span, 1e-6)
                ),
                "c_mean": np.mean(seg_c, axis=1),
                "c_std": np.std(seg_c, axis=1),
                "c_range": np.ptp(seg_c, axis=1),
                "mean_abs_dc": np.mean(np.abs(dc), axis=1) if dc.shape[1] else 0.0,
                "p95_abs_dc": (
                    np.percentile(np.abs(dc), 95, axis=1) if dc.shape[1] else 0.0
                ),
                "mean_abs_d2c": (
                    np.mean(np.abs(d2c), axis=1) if d2c.shape[1] else 0.0
                ),
                "gr_rmse": gr_rmse,
                "gr_mae": gr_mae,
                "gr_bias": gr_bias,
                "gr_corr": gr_corr,
                "gr_coverage": coverage,
                "consensus_c_rmse": consensus_rmse,
                "consensus_c_iqr_frac": consensus_iqr_frac,
                "start_from_anchor": seg_c[:, 0] - float(ctx["last_c"]),
                "target_rmse": target_rmse,
                "target_relative_rmse": target_rmse - target_min,
                "target_rank": target_rank,
            }
        )
        for window, prefix_slope in prefix_c_slopes.items():
            expected_start = float(ctx["last_c"]) + prefix_slope * (seg_md[0] - anchor_md)
            expected_end = float(ctx["last_c"]) + prefix_slope * (seg_md[-1] - anchor_md)
            frame[f"prefix_c_slope_{window}"] = prefix_slope
            frame[f"c_slope_minus_prefix_{window}"] = frame["c_slope_md"] - prefix_slope
            frame[f"c_start_minus_prefix_{window}"] = frame["c_start"] - expected_start
            frame[f"c_end_minus_prefix_{window}"] = frame["c_end"] - expected_end
        for label, (center_path, std_path, iqr_path) in uncertainty_paths.items():
            center = center_path[start:end]
            std = std_path[start:end]
            iqr = iqr_path[start:end]
            deviation = np.abs(seg_c - center[None, :])
            scaled = deviation / np.maximum(std[None, :], 0.25)
            frame[f"unc_{label}_std_mean"] = float(np.mean(std))
            frame[f"unc_{label}_std_p90"] = float(np.percentile(std, 90))
            frame[f"unc_{label}_iqr_mean"] = float(np.mean(iqr))
            frame[f"dist_to_{label}_center_mae"] = np.mean(deviation, axis=1)
            frame[f"dist_to_{label}_center_rmse"] = np.sqrt(np.mean(deviation**2, axis=1))
            frame[f"dist_to_{label}_center_zmean"] = np.mean(scaled, axis=1)
            frame[f"frac_inside_{label}_1std"] = np.mean(deviation <= std[None, :], axis=1)
        for family, median_path in family_medians.items():
            family_seg = median_path[start:end]
            frame[f"dist_to_{family}_c_rmse"] = np.sqrt(
                np.mean((seg_c - family_seg[None, :]) ** 2, axis=1)
            )
        rows.append(frame)

    return pd.concat(rows, ignore_index=True), {
        "names": names,
        "families": families,
        "tvt": tvt,
        "c": c_paths,
        "y": y,
        "z": z,
        "segments": segments,
    }


def add_segment_relative_features(features: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [
        "gr_rmse",
        "gr_mae",
        "gr_corr",
        "gr_coverage",
        "consensus_c_rmse",
        "consensus_c_iqr_frac",
        "mean_abs_dc",
        "mean_abs_d2c",
        "c_slope_md",
        "c_delta",
        "c_range",
        "start_from_anchor",
    ]
    feature_cols.extend(
        col for col in features.columns if col.startswith("dist_to_") and col.endswith("_c_rmse")
    )
    feature_cols.extend(
        col
        for col in features.columns
        if col.startswith(("c_slope_minus_prefix_", "c_start_minus_prefix_", "c_end_minus_prefix_"))
    )
    feature_cols.extend(
        col
        for col in features.columns
        if col.startswith(("dist_to_pf_", "dist_to_beam_", "dist_to_formation_", "frac_inside_"))
    )
    feature_cols = list(dict.fromkeys(feature_cols))
    group = features.groupby(["well", "segment_id"], sort=False)
    relative: dict[str, pd.Series] = {}
    for col in feature_cols:
        values = features[col].replace([np.inf, -np.inf], np.nan)
        minimum = group[col].transform("min")
        maximum = group[col].transform("max")
        median = group[col].transform("median")
        q25 = group[col].transform(lambda x: np.nanpercentile(x, 25))
        q75 = group[col].transform(lambda x: np.nanpercentile(x, 75))
        span = (maximum - minimum).replace(0, np.nan)
        iqr = (q75 - q25).replace(0, np.nan)
        relative[f"{col}_min_delta"] = (values - minimum) / span
        relative[f"{col}_centered"] = (values - median) / iqr
        relative[f"{col}_rank"] = group[col].rank(pct=True, ascending=True)
    return pd.concat([features, pd.DataFrame(relative, index=features.index)], axis=1)


def design_matrix(
    features: pd.DataFrame,
    use_candidate_category: bool,
) -> tuple[pd.DataFrame, list[str]]:
    excluded = {
        "well",
        "segment_id",
        "candidate_idx",
        "candidate",
        "family",
        "target_rmse",
        "target_relative_rmse",
        "target_rank",
    }
    numeric = [
        col
        for col in features.columns
        if col not in excluded and np.issubdtype(features[col].dtype, np.number)
    ]
    matrix = features[numeric].replace([np.inf, -np.inf], np.nan).fillna(-999.0)
    categorical = ["family"]
    matrix["family"] = features["family"].astype("category")
    if use_candidate_category:
        matrix["candidate"] = features["candidate"].astype("category")
        categorical.append("candidate")
    return matrix, categorical


def regression_target(features: pd.DataFrame, target: str) -> np.ndarray:
    if target == "rank":
        return features["target_rank"].to_numpy(float)
    if target == "relative_rmse":
        return features["target_relative_rmse"].to_numpy(float)
    if target == "log_relative_rmse":
        return np.log1p(features["target_relative_rmse"].to_numpy(float))
    if target == "log_rmse":
        return np.log1p(features["target_rmse"].to_numpy(float))
    raise ValueError(target)


def ranking_target(features: pd.DataFrame, grades: int = 31) -> np.ndarray:
    rank = features["target_rank"].to_numpy(float)
    return np.clip(np.floor((1.0 - rank) * grades), 0, grades).astype(int)


def decode_independent(group: pd.DataFrame) -> list[int]:
    return (
        group.loc[group.groupby("segment_id")["pred_score"].idxmin()]
        .sort_values("segment_id")["candidate_idx"]
        .astype(int)
        .tolist()
    )


def decode_dp(
    group: pd.DataFrame,
    data: dict[str, object],
    top_k: int,
    jump_weight: float,
    slope_weight: float,
    switch_cost: float,
) -> list[int]:
    segment_groups = [part.sort_values("pred_score") for _, part in group.groupby("segment_id")]
    candidates = [part.head(top_k)["candidate_idx"].to_numpy(int) for part in segment_groups]
    scores = [part.head(top_k)["pred_score"].to_numpy(float) for part in segment_groups]
    c_paths = np.asarray(data["c"], dtype=float)
    segments = data["segments"]

    previous = scores[0].copy()
    back: list[np.ndarray] = [np.full(len(candidates[0]), -1, dtype=int)]
    for segment_id in range(1, len(candidates)):
        prev_idx = candidates[segment_id - 1]
        curr_idx = candidates[segment_id]
        boundary = segments[segment_id][0]
        prev_end = c_paths[prev_idx, boundary - 1]
        curr_start = c_paths[curr_idx, boundary]
        jump = np.abs(prev_end[:, None] - curr_start[None, :])

        prev_left = max(0, boundary - 8)
        curr_right = min(c_paths.shape[1] - 1, boundary + 7)
        prev_slope = (c_paths[prev_idx, boundary - 1] - c_paths[prev_idx, prev_left]) / max(
            boundary - 1 - prev_left, 1
        )
        curr_slope = (c_paths[curr_idx, curr_right] - c_paths[curr_idx, boundary]) / max(
            curr_right - boundary, 1
        )
        slope_gap = np.abs(prev_slope[:, None] - curr_slope[None, :])
        switched = prev_idx[:, None] != curr_idx[None, :]
        transition = (
            jump_weight * jump
            + slope_weight * slope_gap
            + switch_cost * switched.astype(float)
        )
        total = previous[:, None] + transition
        best_prev = np.argmin(total, axis=0)
        previous = scores[segment_id] + total[best_prev, np.arange(len(curr_idx))]
        back.append(best_prev)

    positions = [int(np.argmin(previous))]
    for segment_id in range(len(candidates) - 1, 0, -1):
        positions.append(int(back[segment_id][positions[-1]]))
    positions.reverse()
    return [int(candidates[i][positions[i]]) for i in range(len(candidates))]


def stitch_prediction(selected: list[int], data: dict[str, object]) -> np.ndarray:
    tvt = np.asarray(data["tvt"], dtype=float)
    pred = np.empty(tvt.shape[1], dtype=float)
    for candidate_idx, (start, end) in zip(selected, data["segments"]):
        pred[start:end] = tvt[candidate_idx, start:end]
    return pred


def summarize_methods(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    summary = []
    for method, group in frame.groupby("method", sort=False):
        rmse = group["rmse"].to_numpy(float)
        weights = group["hidden_rows"].to_numpy(float)
        summary.append(
            {
                "method": method,
                "weighted_rmse": float(np.sqrt(np.average(rmse**2, weights=weights))),
                "mean_well_rmse": float(np.mean(rmse)),
                "median_well_rmse": float(np.median(rmse)),
                "mean_switches": float(group["switches"].mean()),
                "wells": len(group),
            }
        )
    return pd.DataFrame(summary).sort_values("weighted_rmse")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--segment-length", type=int, default=128)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument(
        "--fold-strategy",
        choices=["group", "diagnostic-stratified"],
        default="group",
    )
    parser.add_argument(
        "--diagnostic-features",
        type=Path,
        default=REPORT_DIR / "rogii_well_diagnostic_features50.csv",
    )
    parser.add_argument("--top-k", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--n-estimators", type=int, default=350)
    parser.add_argument(
        "--target",
        choices=["rank", "relative_rmse", "log_relative_rmse", "log_rmse", "lambdarank"],
        default="rank",
    )
    parser.add_argument("--use-candidate-category", action="store_true")
    parser.add_argument("--features-in", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=REPORT_DIR / "rogii_candidate_cache")
    parser.add_argument(
        "--features-out",
        type=Path,
        default=REPORT_DIR / "rogii_segment_selector_features20.parquet",
    )
    parser.add_argument(
        "--oof-out",
        type=Path,
        default=REPORT_DIR / "rogii_segment_selector_oof20.parquet",
    )
    parser.add_argument(
        "--by-well-out",
        type=Path,
        default=REPORT_DIR / "rogii_segment_selector_by_well20.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=REPORT_DIR / "rogii_segment_selector_summary20.csv",
    )
    parser.add_argument(
        "--folds-out",
        type=Path,
        default=REPORT_DIR / "rogii_segment_selector_folds.csv",
    )
    args = parser.parse_args()

    structured_args = argparse.Namespace(
        split="train",
        include_segment_grid=True,
        include_dwt_bundle=True,
        include_pf_frontier=True,
        pf_particles=100,
        pf_frontier_seeds=4,
        seed=args.seed,
        cache_dir=args.cache_dir,
        refresh_cache=False,
    )
    fns = structured.candidate_functions(structured_args)
    wids = candgen.list_wells(candgen.TRAIN)[: args.limit]
    feature_parts: list[pd.DataFrame] = []
    well_data: dict[str, dict[str, object]] = {}
    if args.features_in:
        features = pd.read_parquet(args.features_in)
        wids = features["well"].drop_duplicates().tolist()
    else:
        for number, wid in enumerate(wids, start=1):
            hw, tw = candgen.load_well(candgen.TRAIN, wid)
            ctx = candgen.hidden_context(hw)
            if ctx is None:
                continue
            names, families, tvt = structured.generate_or_load_candidates(
                structured_args,
                wid,
                hw,
                tw,
                ctx,
                fns,
            )
            part, data = build_segment_rows(
                wid,
                hw,
                tw,
                ctx,
                names,
                families,
                tvt,
                args.segment_length,
            )
            feature_parts.append(part)
            well_data[wid] = data
            print(f"built segments {number}/{len(wids)}", flush=True)
        features = add_segment_relative_features(pd.concat(feature_parts, ignore_index=True))

    for wid in wids:
        hw, tw = candgen.load_well(candgen.TRAIN, wid)
        ctx = candgen.hidden_context(hw)
        names, families, tvt = structured.generate_or_load_candidates(
            structured_args,
            wid,
            hw,
            tw,
            ctx,
            fns,
        )
        hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
        well_data[wid] = {
            "names": names,
            "families": families,
            "tvt": tvt,
            "c": tvt + hw["Z"].to_numpy(float)[hidden_idx][None, :],
            "y": hw["TVT"].to_numpy(float)[hidden_idx],
            "z": hw["Z"].to_numpy(float)[hidden_idx],
            "segments": [
                (start, min(len(hidden_idx), start + args.segment_length))
                for start in range(0, len(hidden_idx), args.segment_length)
            ],
        }

    X, categorical_features = design_matrix(features, args.use_candidate_category)
    y = (
        ranking_target(features)
        if args.target == "lambdarank"
        else regression_target(features, args.target)
    )
    groups = features["well"].to_numpy(str)
    predictions = np.full(len(features), np.nan, dtype=float)
    n_splits = min(args.folds, len(well_data))
    if args.fold_strategy == "diagnostic-stratified":
        splits, fold_frame = diagnostic_stratified_splits(
            features,
            n_splits=n_splits,
            seed=args.seed,
            diagnostic_path=args.diagnostic_features,
        )
    else:
        gkf = GroupKFold(n_splits=n_splits)
        splits = list(gkf.split(X, y, groups))
        fold_frame = pd.DataFrame({"well": sorted(well_data), "fold": 0})
        for fold_number, (_, valid_idx) in enumerate(splits, start=1):
            valid_wells = sorted(set(groups[valid_idx]))
            fold_frame.loc[fold_frame["well"].isin(valid_wells), "fold"] = fold_number
    for fold, (train_idx, valid_idx) in enumerate(splits, start=1):
        common_params = dict(
            learning_rate=0.035,
            n_estimators=args.n_estimators,
            num_leaves=31,
            min_child_samples=30,
            subsample=0.9,
            colsample_bytree=0.85,
            random_state=args.seed + fold,
            verbose=-1,
        )
        if args.target == "lambdarank":
            train_order = np.lexsort(
                (
                    features.iloc[train_idx]["candidate_idx"].to_numpy(int),
                    features.iloc[train_idx]["segment_id"].to_numpy(int),
                    features.iloc[train_idx]["well"].to_numpy(str),
                )
            )
            valid_order = np.lexsort(
                (
                    features.iloc[valid_idx]["candidate_idx"].to_numpy(int),
                    features.iloc[valid_idx]["segment_id"].to_numpy(int),
                    features.iloc[valid_idx]["well"].to_numpy(str),
                )
            )
            tr = train_idx[train_order]
            va = valid_idx[valid_order]
            train_group = (
                features.iloc[tr]
                .groupby(["well", "segment_id"], sort=False)
                .size()
                .to_numpy(int)
            )
            model = LGBMRanker(
                objective="lambdarank",
                label_gain=list(range(32)),
                **common_params,
            )
            model.fit(
                X.iloc[tr],
                y[tr],
                group=train_group,
                categorical_feature=categorical_features,
            )
            predictions[va] = -model.predict(X.iloc[va])
        else:
            model = LGBMRegressor(objective="regression", **common_params)
            model.fit(
                X.iloc[train_idx],
                y[train_idx],
                sample_weight=features.iloc[train_idx]["segment_rows"].to_numpy(float),
                categorical_feature=categorical_features,
            )
            predictions[valid_idx] = model.predict(X.iloc[valid_idx])
        print(f"fold {fold}/{n_splits} done", flush=True)

    scored = features.copy()
    scored["pred_score"] = predictions
    result_rows: list[dict[str, object]] = []
    dp_configs = [
        (0.00, 0.00, 0.00),
        (0.02, 0.05, 0.02),
        (0.05, 0.10, 0.05),
        (0.10, 0.20, 0.10),
    ]
    for wid, group in scored.groupby("well", sort=False):
        data = well_data[wid]
        methods: list[tuple[str, list[int]]] = [("segment_independent", decode_independent(group))]
        for jump, slope, switch in dp_configs:
            selected = decode_dp(
                group,
                data,
                args.top_k,
                jump,
                slope,
                switch,
            )
            methods.append((f"segment_dp_j{jump:g}_s{slope:g}_x{switch:g}", selected))
        for method, selected in methods:
            pred = stitch_prediction(selected, data)
            result_rows.append(
                {
                    "well": wid,
                    "method": method,
                    "rmse": candgen.rmse(pred, np.asarray(data["y"], dtype=float)),
                    "hidden_rows": len(data["y"]),
                    "switches": int(np.sum(np.diff(selected) != 0)),
                }
            )

    args.features_out.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(args.features_out, index=False)
    scored.to_parquet(args.oof_out, index=False)
    by_well = pd.DataFrame(result_rows)
    by_well.to_csv(args.by_well_out, index=False)
    summary = summarize_methods(result_rows)
    summary.to_csv(args.summary_out, index=False)
    fold_frame.to_csv(args.folds_out, index=False)
    print(summary.to_string(index=False))
    print(f"wrote {args.features_out}")
    print(f"wrote {args.oof_out}")
    print(f"wrote {args.by_well_out}")
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.folds_out}")


if __name__ == "__main__":
    main()
