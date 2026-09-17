from __future__ import annotations

import argparse
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from scipy.signal import find_peaks
from sklearn.model_selection import GroupKFold


sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_rogii_candidate_paths as candgen  # noqa: E402


REPORT_DIR = Path("reports")
MYCARTA_Q3D = (
    REPORT_DIR
    / "agent_github_reuse_2026-06-06_raw"
    / "rogii-geosteering-toolkit"
    / "toolkit"
    / "wellbore_tortuosity.py"
)


def safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return math.nan
    aa = a[m] - float(np.mean(a[m]))
    bb = b[m] - float(np.mean(b[m]))
    denom = float(np.sqrt(np.sum(aa * aa) * np.sum(bb * bb)))
    if denom < 1e-12:
        return math.nan
    return float(np.sum(aa * bb) / denom)


def interp_typewell_gr(tw: pd.DataFrame, tvt: np.ndarray) -> np.ndarray:
    tvt_tw = tw["TVT"].to_numpy(float)
    gr_tw = tw["GR"].to_numpy(float)
    order = np.argsort(tvt_tw)
    tvt_tw = tvt_tw[order]
    gr_tw = gr_tw[order]
    return np.interp(tvt, tvt_tw, gr_tw, left=np.nan, right=np.nan)


def _finite_curve(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if finite.sum() < 3:
        return np.array([], dtype=float), np.array([], dtype=float)
    x = x[finite]
    y = y[finite]
    order = np.argsort(x)
    return x[order], y[order]


def q3d_curve_metrics(
    x: np.ndarray,
    y: np.ndarray,
    smooth_window: int,
) -> dict[str, float]:
    """Q-3D-inspired arc excess and deflection metrics for a 2D candidate path."""
    x, y = _finite_curve(x, y)
    if len(x) < 3:
        return {
            "tortuosity": 0.0,
            "deflection": 0.0,
            "tqg": 0.0,
            "extrema": 0.0,
            "arc_excess": 0.0,
            "resid_std": 0.0,
        }
    if len(x) > 1024:
        sample_idx = np.linspace(0, len(x) - 1, 1024).round().astype(int)
        x = x[sample_idx]
        y = y[sample_idx]
    if smooth_window > 1:
        y = (
            pd.Series(y)
            .rolling(smooth_window, center=True, min_periods=1)
            .median()
            .to_numpy(float)
        )

    x0 = x - float(np.mean(x))
    try:
        trend = np.polyval(np.polyfit(x0, y, 1), x0)
    except np.linalg.LinAlgError:
        trend = np.full_like(y, float(np.mean(y)))
    resid = y - trend
    prominence = max(0.02, 0.15 * float(np.nanstd(resid)))
    min_distance = max(2, smooth_window // 2)
    peaks, _ = find_peaks(resid, prominence=prominence, distance=min_distance)
    valleys, _ = find_peaks(-resid, prominence=prominence, distance=min_distance)
    extrema = np.sort(np.concatenate([peaks, valleys]))

    dx = np.diff(x)
    dy = np.diff(y)
    arc = np.concatenate([[0.0], np.cumsum(np.hypot(dx, dy))])
    breakpoints = [0]
    for left, right in zip(extrema[:-1], extrema[1:]):
        target = 0.5 * (arc[left] + arc[right])
        bp = int(left + np.argmin(np.abs(arc[left : right + 1] - target)))
        if bp != breakpoints[-1]:
            breakpoints.append(bp)
    if breakpoints[-1] != len(x) - 1:
        breakpoints.append(len(x) - 1)

    arc_lengths: list[float] = []
    chord_lengths: list[float] = []
    slopes: list[float] = []
    for left, right in zip(breakpoints[:-1], breakpoints[1:]):
        seg_arc = float(arc[right] - arc[left])
        seg_dx = float(x[right] - x[left])
        seg_dy = float(y[right] - y[left])
        arc_lengths.append(seg_arc)
        chord_lengths.append(float(np.hypot(seg_dx, seg_dy)))
        slopes.append(seg_dy / seg_dx if abs(seg_dx) > 1e-12 else np.sign(seg_dy) * 1e12)

    total_arc = float(sum(arc_lengths))
    total_chord = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))
    n_segments = len(arc_lengths)
    if total_arc < 1e-12:
        tortuosity = 0.0
    else:
        weighted_excess = sum(
            (seg_arc / chord - 1.0) * (seg_arc / total_arc)
            for seg_arc, chord in zip(arc_lengths, chord_lengths)
            if chord > 1e-9
        )
        tortuosity = float(n_segments * total_arc * weighted_excess)

    deflections = []
    for slope_a, slope_b in zip(slopes[:-1], slopes[1:]):
        denom = 1.0 + slope_a * slope_b
        tan_theta = (
            57.29
            if abs(denom) < 1e-12
            else min(abs(slope_b - slope_a) / abs(denom), 57.29)
        )
        deflections.append(tan_theta)
    deflection = float(total_arc * np.mean(deflections)) if deflections else 0.0
    return {
        "tortuosity": tortuosity,
        "deflection": deflection,
        "tqg": float(np.hypot(tortuosity, deflection)),
        "extrema": float(len(extrema)),
        "arc_excess": float(total_arc / max(total_chord, 1e-9) - 1.0),
        "resid_std": float(np.std(resid)),
    }


def candidate_structure_features(
    md: np.ndarray,
    c: np.ndarray,
    prefix_md: np.ndarray,
    prefix_c: np.ndarray,
    prefix_metrics_by_window: dict[int, dict[str, float]] | None = None,
) -> dict[str, float]:
    rows: dict[str, float] = {}
    for window in (1, 11, 51):
        suffix = "raw" if window == 1 else f"sm{window}"
        candidate_metrics = q3d_curve_metrics(md, c, window)
        prefix_metrics = (
            prefix_metrics_by_window[window]
            if prefix_metrics_by_window is not None
            else q3d_curve_metrics(prefix_md, prefix_c, window)
        )
        for metric, value in candidate_metrics.items():
            rows[f"c_q3d_{metric}_{suffix}"] = value
            rows[f"prefix_c_q3d_{metric}_{suffix}"] = prefix_metrics[metric]
            rows[f"c_prefix_q3d_{metric}_delta_{suffix}"] = value - prefix_metrics[metric]
    return rows


@lru_cache(maxsize=1)
def load_mycarta_q3d():
    if not MYCARTA_Q3D.exists():
        return None
    return candgen.load_module("mycarta_wellbore_tortuosity", MYCARTA_Q3D)


def well_trajectory_q3d_features(
    hw: pd.DataFrame,
    ctx: dict[str, object],
) -> dict[str, float]:
    module = load_mycarta_q3d()
    if module is None:
        return {}
    sample_idx = np.arange(0, len(hw), 50, dtype=int)
    if len(sample_idx) == 0 or sample_idx[-1] != len(hw) - 1:
        sample_idx = np.append(sample_idx, len(hw) - 1)
    try:
        results, _, _ = module.compute_tortuosity_from_xyz(
            hw["MD"].to_numpy(float)[sample_idx],
            hw["X"].to_numpy(float)[sample_idx],
            hw["Y"].to_numpy(float)[sample_idx],
            hw["Z"].to_numpy(float)[sample_idx],
            portion_length=328.0,
            prominence=0.1,
            min_peak_distance=2,
            x_axis="east",
            y_axis="north",
            z_axis="up",
        )
    except Exception:
        return {}
    if results.empty:
        return {}

    hidden_start_md = float(np.asarray(ctx["md"], dtype=float)[int(ctx["ps"]) + 1])
    hidden = results[results["portion_end_md"] >= hidden_start_md]
    if hidden.empty:
        hidden = results
    rows: dict[str, float] = {}
    for col in ("TQG_Q3D", "TQG_incline", "TQG_azimuth"):
        values = hidden[col].to_numpy(float)
        key = col.lower()
        rows[f"well_q3d_{key}_mean"] = float(np.nanmean(values))
        rows[f"well_q3d_{key}_std"] = float(np.nanstd(values))
        rows[f"well_q3d_{key}_max"] = float(np.nanmax(values))
    return rows


def path_features(
    hw: pd.DataFrame,
    tw: pd.DataFrame,
    ctx: dict[str, object],
    candidate: str,
    family: str,
    pred: np.ndarray,
    y: np.ndarray | None,
    well: str,
) -> dict[str, object]:
    hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
    z = np.asarray(ctx["z"], dtype=float)[hidden_idx]
    md = np.asarray(ctx["md"], dtype=float)[hidden_idx]
    gr = hw["GR"].to_numpy(float)[hidden_idx]
    pred = np.asarray(pred, dtype=float)
    c = pred + z
    dc = np.diff(c)
    d2c = np.diff(dc)
    dtvt = np.diff(pred)
    dmd = np.diff(md)
    dz = np.diff(z)
    ps = int(ctx["ps"])
    prefix_start = max(0, ps + 1 - 1000)
    prefix_md = np.asarray(ctx["md"], dtype=float)[prefix_start : ps + 1]
    prefix_c = (
        np.asarray(ctx["tvt_input"], dtype=float)[prefix_start : ps + 1]
        + np.asarray(ctx["z"], dtype=float)[prefix_start : ps + 1]
    )
    prefix_metrics_by_window = ctx.get("_prefix_q3d_metrics")
    if prefix_metrics_by_window is None:
        prefix_metrics_by_window = {
            window: q3d_curve_metrics(prefix_md, prefix_c, window)
            for window in (1, 11, 51)
        }
        ctx["_prefix_q3d_metrics"] = prefix_metrics_by_window
    tw_gr = interp_typewell_gr(tw, pred)
    gr_res = gr - tw_gr
    in_typewell = np.isfinite(tw_gr)

    def nan_stat(fn, arr: np.ndarray, default: float = math.nan) -> float:
        arr = np.asarray(arr, dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) == 0:
            return default
        return float(fn(arr))

    rows = {
        "well": well,
        "candidate": candidate,
        "family": family,
        "hidden_rows": int(len(hidden_idx)),
        "hidden_md_span": float(md[-1] - md[0]) if len(md) > 1 else 0.0,
        "last_tvt": float(ctx["last_tvt"]),
        "last_c": float(ctx["last_c"]),
        "last_z": float(ctx["last_z"]),
        "pred_start": float(pred[0]),
        "pred_end": float(pred[-1]),
        "pred_mean": nan_stat(np.mean, pred),
        "pred_std": nan_stat(np.std, pred, 0.0),
        "pred_range": nan_stat(np.ptp, pred),
        "pred_delta": float(pred[-1] - pred[0]) if len(pred) else math.nan,
        "pred_end_minus_last": float(pred[-1] - float(ctx["last_tvt"])) if len(pred) else math.nan,
        "c_start": float(c[0]),
        "c_end": float(c[-1]),
        "c_mean": nan_stat(np.mean, c),
        "c_std": nan_stat(np.std, c, 0.0),
        "c_range": nan_stat(np.ptp, c),
        "c_delta": float(c[-1] - c[0]) if len(c) else math.nan,
        "mean_abs_dc": nan_stat(np.mean, np.abs(dc), 0.0),
        "p95_abs_dc": nan_stat(lambda x: np.percentile(x, 95), np.abs(dc), 0.0),
        "max_abs_dc": nan_stat(np.max, np.abs(dc), 0.0),
        "mean_abs_d2c": nan_stat(np.mean, np.abs(d2c), 0.0),
        "p95_abs_d2c": nan_stat(lambda x: np.percentile(x, 95), np.abs(d2c), 0.0),
        "mean_abs_dtvt": nan_stat(np.mean, np.abs(dtvt), 0.0),
        "mean_dz": nan_stat(np.mean, dz, 0.0),
        "std_dz": nan_stat(np.std, dz, 0.0),
        "mean_abs_dz": nan_stat(np.mean, np.abs(dz), 0.0),
        "mean_slope_c_md": nan_stat(np.mean, dc / np.maximum(np.abs(dmd), 1e-6), 0.0),
        "roughness_per_row": nan_stat(np.mean, np.abs(d2c), 0.0),
        "gr_rmse": float(np.sqrt(np.nanmean(gr_res**2))) if np.isfinite(gr_res).any() else math.nan,
        "gr_mae": nan_stat(np.mean, np.abs(gr_res)),
        "gr_bias": nan_stat(np.mean, gr_res),
        "gr_res_std": nan_stat(np.std, gr_res),
        "gr_corr": safe_corr(gr, tw_gr),
        "gr_coverage": float(np.mean(in_typewell)) if len(in_typewell) else 0.0,
        "prefix_dc_median": nan_stat(np.median, np.asarray(ctx["dc_known"], dtype=float), 0.0),
        "prefix_dc_std": nan_stat(np.std, np.asarray(ctx["dc_known"], dtype=float), 0.0),
    }
    rows.update(
        candidate_structure_features(
            md,
            c,
            prefix_md,
            prefix_c,
            prefix_metrics_by_window,
        )
    )
    if y is not None:
        rows["rmse"] = candgen.rmse(pred, y)
    return rows


def finite_rmse(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return math.nan
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def add_well_consensus_features(
    rows: list[dict[str, object]],
    pred_paths: list[np.ndarray],
    c_paths: list[np.ndarray],
) -> None:
    if not rows or not pred_paths:
        return
    pred_mat = np.vstack([np.asarray(p, dtype=float) for p in pred_paths])
    c_mat = np.vstack([np.asarray(p, dtype=float) for p in c_paths])
    pred_med = np.nanmedian(pred_mat, axis=0)
    c_med = np.nanmedian(c_mat, axis=0)
    c_q25 = np.nanpercentile(c_mat, 25, axis=0)
    c_q75 = np.nanpercentile(c_mat, 75, axis=0)
    pred_q25 = np.nanpercentile(pred_mat, 25, axis=0)
    pred_q75 = np.nanpercentile(pred_mat, 75, axis=0)

    family_medians: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for fam in sorted({str(r["family"]) for r in rows if r.get("family") != "error"}):
        idx = [i for i, r in enumerate(rows) if str(r.get("family")) == fam]
        if not idx:
            continue
        family_medians[fam] = (
            np.nanmedian(pred_mat[idx], axis=0),
            np.nanmedian(c_mat[idx], axis=0),
        )

    for row, pred, c in zip(rows, pred_paths, c_paths):
        row["consensus_tvt_rmse"] = finite_rmse(pred, pred_med)
        row["consensus_c_rmse"] = finite_rmse(c, c_med)
        row["consensus_tvt_mae"] = float(np.nanmean(np.abs(pred - pred_med)))
        row["consensus_c_mae"] = float(np.nanmean(np.abs(c - c_med)))
        row["consensus_tvt_iqr_frac"] = float(np.nanmean((pred >= pred_q25) & (pred <= pred_q75)))
        row["consensus_c_iqr_frac"] = float(np.nanmean((c >= c_q25) & (c <= c_q75)))
        row["consensus_c_signed_bias"] = float(np.nanmean(c - c_med))
        row["consensus_tvt_signed_bias"] = float(np.nanmean(pred - pred_med))
        for fam in ("anchor", "beam", "dense_ancc", "far_drift", "offset_state", "segment_grid"):
            if fam not in family_medians:
                row[f"dist_to_{fam}_tvt_rmse"] = math.nan
                row[f"dist_to_{fam}_c_rmse"] = math.nan
                continue
            pred_fam, c_fam = family_medians[fam]
            row[f"dist_to_{fam}_tvt_rmse"] = finite_rmse(pred, pred_fam)
            row[f"dist_to_{fam}_c_rmse"] = finite_rmse(c, c_fam)


def add_group_relative_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    feature_cols = [
        "gr_rmse",
        "gr_mae",
        "gr_res_std",
        "gr_corr",
        "gr_coverage",
        "mean_abs_dc",
        "p95_abs_dc",
        "mean_abs_d2c",
        "c_q3d_tqg_raw",
        "c_q3d_tqg_sm11",
        "c_q3d_tqg_sm51",
        "c_q3d_arc_excess_raw",
        "c_q3d_arc_excess_sm11",
        "c_q3d_arc_excess_sm51",
        "c_q3d_resid_std_raw",
        "c_prefix_q3d_tqg_delta_raw",
        "c_prefix_q3d_tqg_delta_sm11",
        "c_prefix_q3d_tqg_delta_sm51",
        "c_range",
        "c_delta",
        "pred_delta",
        "pred_end_minus_last",
        "consensus_tvt_rmse",
        "consensus_c_rmse",
        "consensus_tvt_mae",
        "consensus_c_mae",
        "consensus_tvt_iqr_frac",
        "consensus_c_iqr_frac",
        "dist_to_anchor_c_rmse",
        "dist_to_beam_c_rmse",
        "dist_to_dense_ancc_c_rmse",
        "dist_to_far_drift_c_rmse",
        "dist_to_offset_state_c_rmse",
        "dist_to_segment_grid_c_rmse",
    ]
    feature_cols = [c for c in feature_cols if c in df.columns]
    g = df.groupby("well", sort=False)
    relative: dict[str, pd.Series] = {}
    for col in feature_cols:
        vals = df[col].replace([np.inf, -np.inf], np.nan)
        med = g[col].transform("median")
        q25 = g[col].transform(lambda x: np.nanpercentile(x, 25))
        q75 = g[col].transform(lambda x: np.nanpercentile(x, 75))
        mn = g[col].transform("min")
        mx = g[col].transform("max")
        iqr = (q75 - q25).replace(0, np.nan)
        span = (mx - mn).replace(0, np.nan)
        relative[f"{col}_well_centered"] = (vals - med) / iqr
        relative[f"{col}_well_min_delta"] = (vals - mn) / span
        relative[f"{col}_rank_asc"] = g[col].rank(pct=True, ascending=True)
        relative[f"{col}_rank_desc"] = g[col].rank(pct=True, ascending=False)
    return pd.concat([df, pd.DataFrame(relative, index=df.index)], axis=1)


def candidate_functions(args: argparse.Namespace):
    fns = [lambda hw, tw, ctx, wid: candgen.simple_candidates(hw, ctx)]
    if args.include_segment_grid:
        fns.append(lambda hw, tw, ctx, wid: candgen.segment_grid_candidates(hw, ctx))
    if args.include_beam:
        fns.append(lambda hw, tw, ctx, wid: candgen.beam_candidates(hw, tw, ctx))
    if args.include_pf:
        fns.append(
            lambda hw, tw, ctx, wid: candgen.pf_candidates(
                hw,
                tw,
                ctx,
                args.pf_particles,
                args.pf_seeds,
            )
        )
    if args.include_pf_frontier:
        fns.append(
            lambda hw, tw, ctx, wid: candgen.pf_frontier_candidates(
                hw,
                tw,
                ctx,
                args.pf_particles,
                args.pf_frontier_seeds,
            )
        )
    if args.include_dense_ancc:
        dense_ancc = candgen.DenseAnccGenerator(args.split)
        fns.append(lambda hw, tw, ctx, wid: dense_ancc(hw, tw, ctx, wid))
    if args.include_far_drift:
        far_drift = candgen.FarDriftGenerator(args.split, poly=False)
        fns.append(lambda hw, tw, ctx, wid: far_drift(hw, tw, ctx, wid))
    if args.include_far_poly:
        far_poly = candgen.FarDriftGenerator(args.split, poly=True)
        fns.append(lambda hw, tw, ctx, wid: far_poly(hw, tw, ctx, wid))
    if args.include_dwt_bundle:
        dwt_bundle = candgen.DwtBundleGenerator(args.split, args.seed)
        fns.append(lambda hw, tw, ctx, wid: dwt_bundle(hw, tw, ctx, wid))
    return fns


def build_features(args: argparse.Namespace) -> pd.DataFrame:
    folder = candgen.TRAIN if args.split == "train" else candgen.TEST
    wids = candgen.list_wells(folder)
    if args.limit:
        wids = wids[: args.limit]
    fns = candidate_functions(args)
    rows: list[dict[str, object]] = []
    for n, wid in enumerate(wids, start=1):
        hw, tw = candgen.load_well(folder, wid)
        ctx = candgen.hidden_context(hw)
        if ctx is None:
            continue
        hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
        z_h = np.asarray(ctx["z"], dtype=float)[hidden_idx]
        y = hw["TVT"].to_numpy(float)[hidden_idx] if "TVT" in hw else None
        well_q3d = well_trajectory_q3d_features(hw, ctx)
        well_rows: list[dict[str, object]] = []
        pred_paths: list[np.ndarray] = []
        c_paths: list[np.ndarray] = []
        for fn in fns:
            try:
                generated = fn(hw, tw, ctx, wid)
            except Exception as e:
                well_rows.append(
                    {
                        "well": wid,
                        "candidate": getattr(fn, "__name__", "candidate_fn"),
                        "family": "error",
                        "hidden_rows": int(len(hidden_idx)),
                        "error": repr(e),
                    }
                )
                continue
            for candidate, family, pred in generated:
                pred = np.asarray(pred, dtype=float)
                row = path_features(hw, tw, ctx, candidate, family, pred, y, wid)
                row.update(well_q3d)
                row["error"] = ""
                well_rows.append(row)
                pred_paths.append(pred)
                c_paths.append(pred + z_h)
        non_error_rows = [r for r in well_rows if r.get("family") != "error"]
        if len(non_error_rows) == len(pred_paths):
            add_well_consensus_features(non_error_rows, pred_paths, c_paths)
        rows.extend(well_rows)
        if n % 25 == 0:
            print(f"built features for {n}/{len(wids)} wells", flush=True)
    return add_group_relative_features(pd.DataFrame(rows))


def weighted_rmse_from_rows(df: pd.DataFrame, rmse_col: str = "rmse") -> float:
    vals = df[rmse_col].to_numpy(float)
    weights = df["hidden_rows"].to_numpy(float)
    ok = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
    if not ok.any():
        return math.nan
    return float(np.sqrt(np.average(vals[ok] ** 2, weights=weights[ok])))


def train_oof(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    ok = features[np.isfinite(features["rmse"]) & (features["family"] != "error")].copy()
    wells = ok["well"].unique()
    if len(wells) < 3:
        raise RuntimeError("need at least 3 wells for grouped OOF reranking")

    cat_cols = ["family"]
    if args.use_candidate_dummies:
        cat_cols.append("candidate")
    cat = pd.get_dummies(ok[cat_cols].astype(str), dtype=float)
    num_cols = [
        c
        for c in ok.columns
        if c not in {"well", "candidate", "family", "error", "rmse"}
        and np.issubdtype(ok[c].dtype, np.number)
    ]
    X = pd.concat([ok[num_cols].replace([np.inf, -np.inf], np.nan), cat], axis=1).fillna(-999.0)
    if args.target == "rmse":
        y = ok["rmse"].to_numpy(float)
    elif args.target == "log_rmse":
        y = np.log1p(ok["rmse"].to_numpy(float))
    elif args.target == "relative_rmse":
        y = (
            ok["rmse"]
            - ok.groupby("well")["rmse"].transform("min")
        ).to_numpy(float)
    elif args.target == "rank":
        y = ok.groupby("well")["rmse"].rank(pct=True, ascending=True).to_numpy(float)
    else:
        raise ValueError(args.target)
    groups = ok["well"].to_numpy(str)
    preds = np.full(len(ok), np.nan, dtype=float)
    n_splits = min(args.folds, len(wells))
    gkf = GroupKFold(n_splits=n_splits)

    for fold, (tr, va) in enumerate(gkf.split(X, y, groups), start=1):
        model = LGBMRegressor(
            objective="regression",
            learning_rate=args.learning_rate,
            n_estimators=args.n_estimators,
            num_leaves=args.num_leaves,
            min_child_samples=args.min_child_samples,
            subsample=0.9,
            colsample_bytree=0.85,
            random_state=args.seed + fold,
            verbose=-1,
        )
        model.fit(X.iloc[tr], y[tr], sample_weight=ok.iloc[tr]["hidden_rows"].to_numpy(float))
        preds[va] = model.predict(X.iloc[va])
        print(f"fold {fold}/{n_splits} done", flush=True)

    scored = ok.copy()
    scored["pred_rmse"] = preds
    chosen = scored.loc[scored.groupby("well")["pred_rmse"].idxmin()].copy()
    oracle = scored.loc[scored.groupby("well")["rmse"].idxmin()].copy()
    best_single = (
        scored.groupby(["family", "candidate"], as_index=False)
        .apply(lambda g: pd.Series({"weighted_rmse": weighted_rmse_from_rows(g), "wells": len(g)}))
        .reset_index(drop=True)
        .sort_values("weighted_rmse")
        .head(1)
    )

    summary = pd.DataFrame(
        [
            {
                "wells": int(len(wells)),
                "candidates": int(len(scored)),
                "unique_candidates": int(scored["candidate"].nunique()),
                "weighted_oracle_rmse": weighted_rmse_from_rows(oracle),
                "weighted_oof_selected_rmse": weighted_rmse_from_rows(chosen),
                "mean_oof_selected_well_rmse": float(chosen["rmse"].mean()),
                "median_oof_selected_well_rmse": float(chosen["rmse"].median()),
                "pct_oof_wells_under_7": float(np.mean(chosen["rmse"].to_numpy(float) < 7.0)),
                "pct_oof_wells_under_5": float(np.mean(chosen["rmse"].to_numpy(float) < 5.0)),
                "best_single_family": str(best_single.iloc[0]["family"]) if len(best_single) else "",
                "best_single_candidate": str(best_single.iloc[0]["candidate"]) if len(best_single) else "",
                "best_single_weighted_rmse": float(best_single.iloc[0]["weighted_rmse"])
                if len(best_single)
                else math.nan,
            }
        ]
    )
    return scored, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["train", "test"], default="train")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--include-beam", action="store_true")
    parser.add_argument("--include-pf", action="store_true")
    parser.add_argument("--include-pf-frontier", action="store_true")
    parser.add_argument("--include-dense-ancc", action="store_true")
    parser.add_argument("--include-far-drift", action="store_true")
    parser.add_argument("--include-far-poly", action="store_true")
    parser.add_argument("--include-segment-grid", action="store_true")
    parser.add_argument("--include-dwt-bundle", action="store_true")
    parser.add_argument("--pf-particles", type=int, default=100)
    parser.add_argument("--pf-seeds", type=int, default=8)
    parser.add_argument("--pf-frontier-seeds", type=int, default=6)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--target", choices=["rmse", "log_rmse", "relative_rmse", "rank"], default="relative_rmse")
    parser.add_argument("--use-candidate-dummies", action="store_true")
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--n-estimators", type=int, default=350)
    parser.add_argument("--learning-rate", type=float, default=0.035)
    parser.add_argument("--num-leaves", type=int, default=31)
    parser.add_argument("--min-child-samples", type=int, default=20)
    parser.add_argument("--features-out", type=Path, default=REPORT_DIR / "rogii_candidate_reranker_features.csv")
    parser.add_argument("--oof-out", type=Path, default=REPORT_DIR / "rogii_candidate_reranker_oof.csv")
    parser.add_argument("--summary-out", type=Path, default=REPORT_DIR / "rogii_candidate_reranker_summary.csv")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    features = build_features(args)
    features.to_csv(args.features_out, index=False)
    print(f"wrote {args.features_out}")

    if args.split == "train":
        oof, summary = train_oof(features, args)
        oof.to_csv(args.oof_out, index=False)
        summary.to_csv(args.summary_out, index=False)
        print(summary.to_string(index=False))
        print(f"wrote {args.oof_out}")
        print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()
