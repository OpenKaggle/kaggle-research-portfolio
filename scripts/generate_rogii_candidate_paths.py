from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import math
import sys
from itertools import product
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from numba import njit


DATA = Path("data/raw/rogii-wellbore-geology-prediction")
TRAIN = DATA / "train"
TEST = DATA / "test"
REPORT_DIR = Path("reports")
MORINOKUMA_SRC = (
    REPORT_DIR
    / "agent_public_frontier_2026-06-06_raw"
    / "datasets"
    / "morinokuma3__rogii-src"
)


@njit(cache=True)
def seed_numba_random(seed: int) -> None:
    np.random.seed(seed)


def stable_well_seed(wid: str, base_seed: int) -> int:
    digest = hashlib.blake2b(wid.encode("utf-8"), digest_size=4).digest()
    return (int.from_bytes(digest, "little") ^ int(base_seed)) & 0x7FFFFFFF


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return math.nan
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hidden_context(hw: pd.DataFrame) -> dict[str, object] | None:
    tvt_input = hw["TVT_input"].to_numpy(float)
    known = np.isfinite(tvt_input)
    if known.sum() < 20 or known.all():
        return None
    ps = int(np.flatnonzero(known)[-1])
    hidden_idx = np.arange(ps + 1, len(hw), dtype=int)
    if len(hidden_idx) == 0:
        return None
    z = hw["Z"].to_numpy(float)
    md = hw["MD"].to_numpy(float)
    c_known = tvt_input[: ps + 1] + z[: ps + 1]
    dc_known = np.diff(c_known)
    dmd_known = np.diff(md[: ps + 1])
    return {
        "ps": ps,
        "hidden_idx": hidden_idx,
        "z": z,
        "md": md,
        "tvt_input": tvt_input,
        "last_tvt": float(tvt_input[ps]),
        "last_z": float(z[ps]),
        "last_c": float(tvt_input[ps] + z[ps]),
        "dc_known": dc_known[np.isfinite(dc_known)],
        "dmd_known": dmd_known[np.isfinite(dmd_known)],
    }


def linear_c_from_dc(
    ctx: dict[str, object],
    dc_per_row: float,
    name: str,
    family: str,
) -> tuple[str, str, np.ndarray]:
    hidden_idx = ctx["hidden_idx"]
    z = ctx["z"]
    ps = int(ctx["ps"])
    steps = hidden_idx - ps
    c = float(ctx["last_c"]) + dc_per_row * steps
    tvt = c - z[hidden_idx]
    return name, family, tvt.astype(float)


def linear_c_from_md_slope(
    ctx: dict[str, object],
    slope: float,
    name: str,
    family: str,
) -> tuple[str, str, np.ndarray]:
    hidden_idx = ctx["hidden_idx"]
    z = ctx["z"]
    md = ctx["md"]
    ps = int(ctx["ps"])
    c = float(ctx["last_c"]) + slope * (md[hidden_idx] - md[ps])
    tvt = c - z[hidden_idx]
    return name, family, tvt.astype(float)


def robust_slope(y: np.ndarray, x: np.ndarray) -> float:
    m = np.isfinite(y) & np.isfinite(x)
    if m.sum() < 3 or np.nanstd(x[m]) < 1e-9:
        return 0.0
    return float(np.polyfit(x[m], y[m], 1)[0])


def simple_candidates(hw: pd.DataFrame, ctx: dict[str, object]) -> list[tuple[str, str, np.ndarray]]:
    hidden_idx = ctx["hidden_idx"]
    z = ctx["z"]
    md = ctx["md"]
    ps = int(ctx["ps"])
    tvt_input = ctx["tvt_input"]
    dc_known = ctx["dc_known"]

    out: list[tuple[str, str, np.ndarray]] = []
    last = np.full(len(hidden_idx), float(ctx["last_tvt"]), dtype=float)
    out.append(("last_tvt", "anchor", last))
    out.append(("constant_C", "offset_state", float(ctx["last_c"]) - z[hidden_idx]))

    if len(dc_known):
        out.append(
            linear_c_from_dc(
                ctx,
                float(np.nanmedian(dc_known)),
                "prefix_dc_all_median",
                "offset_state",
            )
        )
        for w in (50, 200, 500):
            tail = dc_known[-min(w, len(dc_known)) :]
            out.append(
                linear_c_from_dc(
                    ctx,
                    float(np.nanmedian(tail)),
                    f"prefix_dc_tail{w}_median",
                    "offset_state",
                )
            )

    c_known = tvt_input[: ps + 1] + z[: ps + 1]
    for w in (100, 500, 1000):
        start = max(0, ps + 1 - w)
        slope = robust_slope(c_known[start : ps + 1], md[start : ps + 1])
        out.append(linear_c_from_md_slope(ctx, slope, f"prefix_C_md_slope{w}", "offset_state"))

    grid = np.unique(
        np.round(
            np.r_[
                np.arange(-1.2, 1.201, 0.20),
                np.arange(-0.16, 0.161, 0.02),
            ],
            2,
        )
    )
    for dc in grid:
        dc = 0.0 if abs(float(dc)) < 1e-12 else float(dc)
        out.append(linear_c_from_dc(ctx, float(dc), f"grid_dc_{dc:+.2f}", "offset_grid"))

    # A few segment-damped priors: keep prefix/tail dC near the heel, then shrink to flat.
    if len(dc_known):
        base = float(np.nanmedian(dc_known[-min(500, len(dc_known)) :]))
        steps = hidden_idx - ps
        for half_life in (500.0, 1500.0, 3000.0):
            damp = np.exp(-steps / half_life)
            c = float(ctx["last_c"]) + np.cumsum(base * damp)
            out.append(
                (
                    f"damped_tail500_hl{int(half_life)}",
                    "offset_state",
                    (c - z[hidden_idx]).astype(float),
                )
            )

    return out


def segment_grid_candidates(
    hw: pd.DataFrame,
    ctx: dict[str, object],
    *,
    levels: tuple[float, ...] = (-0.06, -0.03, 0.0, 0.03, 0.06),
) -> list[tuple[str, str, np.ndarray]]:
    hidden_idx = ctx["hidden_idx"]
    z = ctx["z"]
    n = len(hidden_idx)
    out: list[tuple[str, str, np.ndarray]] = []
    templates = {
        "k2_q25": (int(n * 0.25),),
        "k2_q50": (int(n * 0.50),),
        "k2_q75": (int(n * 0.75),),
        "k3_even": (int(n / 3), int(2 * n / 3)),
        "k3_front": (int(n * 0.20), int(n * 0.50)),
        "k3_back": (int(n * 0.50), int(n * 0.80)),
    }
    for template_name, cuts in templates.items():
        cuts = tuple(c for c in cuts if 0 < c < n)
        k = len(cuts) + 1
        combos = product(levels, repeat=k)
        boundaries = (0, *cuts, n)
        for combo in combos:
            dc = np.empty(n, dtype=float)
            for s in range(k):
                dc[boundaries[s] : boundaries[s + 1]] = combo[s]
            c_path = float(ctx["last_c"]) + np.cumsum(dc)
            name = f"{template_name}_" + "_".join(f"{x:+.2f}" for x in combo)
            out.append((name, "segment_grid", (c_path - z[hidden_idx]).astype(float)))
    return out


class DenseAnccGenerator:
    def __init__(self, split: str) -> None:
        mod = load_module("morinokuma_dense_spatial_ancc", MORINOKUMA_SRC / "dense_spatial_ancc.py")
        train_paths = sorted(TRAIN.glob("*__horizontal_well.csv"))
        self.mod = mod
        self.row_imputer = mod.RowKNN(train_paths)
        self.is_train = split == "train"

    def __call__(
        self, hw: pd.DataFrame, tw: pd.DataFrame, ctx: dict[str, object], wid: str
    ) -> list[tuple[str, str, np.ndarray]]:
        pred = self.mod.predict_well(
            hw,
            wid,
            self.row_imputer,
            is_train=self.is_train,
            k=self.mod.ROW_K,
            workers=4,
        )
        if pred is None or len(pred) == 0:
            return []
        hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
        by_row = pred.set_index("row_index")["spatial_pred"]
        tvt = by_row.reindex(hidden_idx).to_numpy(float)
        return [("dense_ancc_k20", "dense_ancc", tvt)]


class FarDriftGenerator:
    def __init__(self, split: str, *, poly: bool = False) -> None:
        mod = load_module("morinokuma_spatial_far_kriging", MORINOKUMA_SRC / "spatial_far_kriging.py")
        self.mod = mod
        self.db = mod.build_drift_db(TRAIN, poly=poly)
        self.is_train = split == "train"
        self.poly = poly

    def __call__(
        self, hw: pd.DataFrame, tw: pd.DataFrame, ctx: dict[str, object], wid: str
    ) -> list[tuple[str, str, np.ndarray]]:
        rows: list[tuple[str, str, np.ndarray]] = []
        for krige in (False, True):
            pred = self.mod.predict_well_drift(
                hw,
                wid,
                self.db,
                is_train=self.is_train,
                k=self.mod.K_WELLS,
                power=self.mod.IDW_POWER,
                krige=krige,
            )
            if pred is None or len(pred) == 0:
                continue
            hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
            by_row = pred.set_index("row_index")["spatial_far_pred"]
            tvt = by_row.reindex(hidden_idx).to_numpy(float)
            prefix = "far_poly" if self.poly else "far_idw"
            suffix = "krige" if krige else "mean"
            rows.append((f"{prefix}_{suffix}_k{self.mod.K_WELLS}", "far_drift", tvt))
        return rows


class DwtBundleGenerator:
    def __init__(self, split: str, seed: int = 20260606) -> None:
        src = str(MORINOKUMA_SRC.resolve())
        if src not in sys.path:
            sys.path.insert(0, src)
        mod = importlib.import_module("dwt_features")
        train_ids = list_wells(TRAIN)
        self.mod = mod
        self.fi = mod.FormationPlaneKNN(train_ids, TRAIN)
        self.di = mod.DenseANCCImputer(train_ids, TRAIN)
        self.folder = TRAIN if split == "train" else TEST
        self.is_train = split == "train"
        self.seed = int(seed)

    @staticmethod
    def family_for(col: str) -> str:
        if col.startswith("pf_"):
            return "dwt_pf"
        if col.startswith("beam_"):
            return "dwt_beam"
        if col.startswith("sc") or col.startswith("hyb_"):
            return "dwt_ncc"
        if col.startswith("tvtF") or col.startswith("form_"):
            return "dwt_form"
        if col.startswith("tvt_dense"):
            return "dwt_dense"
        if col.startswith("dtw_"):
            return "dwt_dtw"
        if col.startswith("slp_"):
            return "dwt_slope"
        return "dwt_bundle"

    @staticmethod
    def candidate_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
        actual = [
            c
            for c in df.columns
            if c in {"pf_ancc", "pf_z"}
            or c.startswith("tvtF_")
            or c.startswith("tvtFw_")
            or c.startswith("tvtF50_")
        ]
        delta = [
            c
            for c in (
                "beam_cons_d",
                "beam_loose_d",
                "beam_vcons_d",
                "beam_sm5_d",
                "beam_vloose_d",
                "beam_mid_d",
                "beam_stiff_d",
                "beam_mean_d",
                "beam_med_d",
                "sc8_d",
                "sc15_d",
                "sc25_d",
                "sc_cons_d",
                "sc_ens_d",
                "hyb_d",
                "tvt_dense_d",
                "tvt_densew_d",
                "tvt_dense50_d",
                "dtw_ens_d",
                "dtw_stoch_mean_d",
                "dtw_r20_d",
                "dtw_r50_d",
                "dtw_r100_d",
                "dtw_r200_d",
                "slp_b_d_all",
                "slp_b_d_50",
                "form_mean_d",
                "sig_mean_d",
            )
            if c in df.columns
        ]
        return sorted(set(actual)), sorted(set(delta))

    def __call__(
        self, hw: pd.DataFrame, tw: pd.DataFrame, ctx: dict[str, object], wid: str
    ) -> list[tuple[str, str, np.ndarray]]:
        well_seed = stable_well_seed(wid, self.seed)
        np.random.seed(well_seed)
        seed_numba_random(well_seed)
        df = self.mod.build_well(
            self.folder / f"{wid}__horizontal_well.csv",
            self.folder / f"{wid}__typewell.csv",
            self.is_train,
            self.fi,
            self.di,
        )
        if df is None or len(df) == 0:
            return []
        last = df["last_known_tvt"].to_numpy(float)
        rows: list[tuple[str, str, np.ndarray]] = []
        actual_cols, delta_cols = self.candidate_columns(df)
        for col in actual_cols:
            pred = df[col].to_numpy(float)
            if np.isfinite(pred).any():
                rows.append((f"dwt_{col}", self.family_for(col), pred))
        for col in delta_cols:
            pred = last + df[col].to_numpy(float)
            if np.isfinite(pred).any():
                rows.append((f"dwt_{col}", self.family_for(col), pred))
        return rows


def beam_candidates(hw: pd.DataFrame, tw: pd.DataFrame, ctx: dict[str, object]) -> list[tuple[str, str, np.ndarray]]:
    mod = load_module("morinokuma_pf_beam_selector", MORINOKUMA_SRC / "pf_beam_selector.py")
    pred_full = mod.run_beam_ensemble(hw, tw)
    return [("beam_ensemble", "beam", np.asarray(pred_full, dtype=float)[ctx["hidden_idx"]])]


def pf_candidates(
    hw: pd.DataFrame,
    tw: pd.DataFrame,
    ctx: dict[str, object],
    n_particles: int,
    n_seeds: int,
) -> list[tuple[str, str, np.ndarray]]:
    mod = load_module("morinokuma_pf_sequential", MORINOKUMA_SRC / "pf_sequential.py")
    out = mod.run_pf_lik_ensemble_scales(
        hw,
        tw,
        scales=(3.0, 5.0, 8.0, 12.0),
        n_particles=n_particles,
        n_seeds=n_seeds,
    )
    rows = []
    for name, pred_full in out.items():
        rows.append((f"pf_{name}", "pf", np.asarray(pred_full, dtype=float)[ctx["hidden_idx"]]))
    return rows


def pf_frontier_candidates(
    hw: pd.DataFrame,
    tw: pd.DataFrame,
    ctx: dict[str, object],
    n_particles: int,
    n_seeds: int,
) -> list[tuple[str, str, np.ndarray]]:
    mod = load_module("morinokuma_pf_sequential_frontier", MORINOKUMA_SRC / "pf_sequential.py")
    configs = {
        "wide": {"init_spread": 2.0},
        "narrow": {"init_spread": 0.5},
        "adaptive": {
            "init_spread": 2.0,
            "adaptive_gs": True,
            "gs_alpha": 1.0,
            "gs_beta": 0.95,
            "gs_cap": 3.0,
        },
        "diverse": {
            "init_spread": 2.0,
            "soft_resample_alpha": 0.9,
            "ess_temper": 2.0,
            "ess_temper_floor": 0.5,
        },
    }
    hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
    rows: list[tuple[str, str, np.ndarray]] = []
    for config_name, kwargs in configs.items():
        preds = []
        liks = []
        for seed in range(n_seeds):
            pred_full, log_lik = mod.run_particle_filter(
                hw,
                tw,
                n_particles=n_particles,
                seed=seed,
                **kwargs,
            )
            pred = np.asarray(pred_full, dtype=float)[hidden_idx]
            preds.append(pred)
            liks.append(float(log_lik))
            rows.append((f"pf_frontier_{config_name}_seed{seed}", "pf_frontier_seed", pred))

        arr = np.stack(preds, axis=0)
        liks_arr = np.asarray(liks, dtype=float)
        centered = liks_arr - float(np.max(liks_arr))
        for scale in (3.0, 5.0, 8.0, 12.0):
            weights = np.exp(centered / scale)
            weights /= weights.sum()
            mean_path = np.sum(weights[:, None] * arr, axis=0)
            rows.append(
                (
                    f"pf_frontier_{config_name}_scale{scale:g}",
                    "pf_frontier_ensemble",
                    mean_path,
                )
            )
        rows.append(
            (
                f"pf_frontier_{config_name}_mean",
                "pf_frontier_ensemble",
                arr.mean(axis=0),
            )
        )
    return rows


def list_wells(folder: Path) -> list[str]:
    return sorted(p.name.replace("__horizontal_well.csv", "") for p in folder.glob("*__horizontal_well.csv"))


def load_well(folder: Path, wid: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_csv(folder / f"{wid}__horizontal_well.csv"),
        pd.read_csv(folder / f"{wid}__typewell.csv"),
    )


def evaluate_oracle(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty or "rmse" not in scores:
        return pd.DataFrame(
            columns=["well", "hidden_rows", "best_candidate", "best_family", "oracle_rmse"]
        )
    ok = scores[np.isfinite(scores["rmse"])]
    rows = []
    for well, g in ok.groupby("well"):
        best = g.loc[g["rmse"].idxmin()]
        rows.append(
            {
                "well": well,
                "hidden_rows": int(best["hidden_rows"]),
                "best_candidate": best["candidate"],
                "best_family": best["family"],
                "oracle_rmse": float(best["rmse"]),
            }
        )
    return pd.DataFrame(rows)


def summarize_scores(scores: pd.DataFrame, oracle: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cand_rows = []
    required_score_cols = {"family", "candidate", "rmse", "hidden_rows"}
    if required_score_cols.issubset(scores.columns):
        for (family, cand), g in scores.groupby(["family", "candidate"]):
            vals = g["rmse"].to_numpy(float)
            weights = g["hidden_rows"].to_numpy(float)
            ok = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
            if not ok.any():
                continue
            cand_rows.append(
                {
                    "family": family,
                    "candidate": cand,
                    "weighted_rmse": float(np.sqrt(np.average(vals[ok] ** 2, weights=weights[ok]))),
                    "mean_well_rmse": float(np.mean(vals[ok])),
                    "median_well_rmse": float(np.median(vals[ok])),
                    "wells": int(ok.sum()),
                }
            )

    oracle_summary = pd.DataFrame()
    if len(oracle):
        vals = oracle["oracle_rmse"].to_numpy(float)
        weights = oracle["hidden_rows"].to_numpy(float)
        oracle_summary = pd.DataFrame(
            [
                {
                    "candidate_count": int(scores["candidate"].nunique()),
                    "weighted_oracle_rmse": float(np.sqrt(np.average(vals**2, weights=weights))),
                    "mean_well_oracle_rmse": float(np.mean(vals)),
                    "median_well_oracle_rmse": float(np.median(vals)),
                    "wells": int(len(oracle)),
                    "pct_wells_under_7": float(np.mean(vals < 7.0)),
                    "pct_wells_under_5": float(np.mean(vals < 5.0)),
                }
            ]
        )
    cand_summary = pd.DataFrame(
        cand_rows,
        columns=[
            "family",
            "candidate",
            "weighted_rmse",
            "mean_well_rmse",
            "median_well_rmse",
            "wells",
        ],
    )
    if len(cand_summary):
        cand_summary = cand_summary.sort_values("weighted_rmse")
    return cand_summary, oracle_summary


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
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--summary-top", type=int, default=80)
    parser.add_argument("--write-predictions", action="store_true")
    parser.add_argument("--scores-out", type=Path, default=REPORT_DIR / "rogii_candidate_path_scores.csv")
    parser.add_argument("--oracle-out", type=Path, default=REPORT_DIR / "rogii_candidate_path_oracle.csv")
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=REPORT_DIR / "rogii_candidate_path_summary.csv",
    )
    parser.add_argument(
        "--predictions-out",
        type=Path,
        default=REPORT_DIR / "rogii_candidate_paths_long.csv",
    )
    args = parser.parse_args()

    folder = TRAIN if args.split == "train" else TEST
    wids = list_wells(folder)
    if args.limit:
        wids = wids[: args.limit]

    # Keep simple call signatures for older function bodies by wrapping them.
    candidate_fns: list[
        Callable[[pd.DataFrame, pd.DataFrame, dict[str, object], str], list[tuple[str, str, np.ndarray]]]
    ]
    candidate_fns = [lambda hw, tw, ctx, wid: simple_candidates(hw, ctx)]
    if args.include_segment_grid:
        candidate_fns.append(lambda hw, tw, ctx, wid: segment_grid_candidates(hw, ctx))
    if args.include_beam:
        candidate_fns.append(lambda hw, tw, ctx, wid: beam_candidates(hw, tw, ctx))
    if args.include_pf:
        candidate_fns.append(
            lambda hw, tw, ctx, wid: pf_candidates(hw, tw, ctx, args.pf_particles, args.pf_seeds)
        )
    if args.include_pf_frontier:
        candidate_fns.append(
            lambda hw, tw, ctx, wid: pf_frontier_candidates(
                hw,
                tw,
                ctx,
                args.pf_particles,
                args.pf_frontier_seeds,
            )
        )
    if args.include_dense_ancc:
        dense_ancc = DenseAnccGenerator(args.split)
        candidate_fns.append(lambda hw, tw, ctx, wid: dense_ancc(hw, tw, ctx, wid))
    if args.include_far_drift:
        far_drift = FarDriftGenerator(args.split, poly=False)
        candidate_fns.append(lambda hw, tw, ctx, wid: far_drift(hw, tw, ctx, wid))
    if args.include_far_poly:
        far_poly = FarDriftGenerator(args.split, poly=True)
        candidate_fns.append(lambda hw, tw, ctx, wid: far_poly(hw, tw, ctx, wid))
    if args.include_dwt_bundle:
        dwt_bundle = DwtBundleGenerator(args.split, args.seed)
        candidate_fns.append(lambda hw, tw, ctx, wid: dwt_bundle(hw, tw, ctx, wid))

    score_rows = []
    pred_rows = []
    for n, wid in enumerate(wids, start=1):
        hw, tw = load_well(folder, wid)
        ctx = hidden_context(hw)
        if ctx is None:
            continue
        hidden_idx = ctx["hidden_idx"]
        y = hw["TVT"].to_numpy(float)[hidden_idx] if "TVT" in hw else None
        z_h = ctx["z"][hidden_idx]
        candidates: list[tuple[str, str, np.ndarray]] = []
        for fn in candidate_fns:
            try:
                candidates.extend(fn(hw, tw, ctx, wid))
            except Exception as e:
                score_rows.append(
                    {
                        "well": wid,
                        "candidate": getattr(fn, "__name__", "candidate_fn"),
                        "family": "error",
                        "hidden_rows": int(len(hidden_idx)),
                        "rmse": math.nan,
                        "error": repr(e),
                    }
                )

        for cand, family, pred in candidates:
            pred = np.asarray(pred, dtype=float)
            if pred.shape != (len(hidden_idx),):
                score_rows.append(
                    {
                        "well": wid,
                        "candidate": cand,
                        "family": family,
                        "hidden_rows": int(len(hidden_idx)),
                        "rmse": math.nan,
                        "error": f"bad_prediction_shape={pred.shape}, expected={(len(hidden_idx),)}",
                    }
                )
                continue
            score_rows.append(
                {
                    "well": wid,
                    "candidate": cand,
                    "family": family,
                    "hidden_rows": int(len(hidden_idx)),
                    "rmse": rmse(pred, y) if y is not None else math.nan,
                    "error": "",
                }
            )
            if args.write_predictions:
                pred_rows.extend(
                    {
                        "well": wid,
                        "row_index": int(row_index),
                        "candidate": cand,
                        "family": family,
                        "tvt_pred": float(tvt_pred),
                        "c_pred": float(tvt_pred + z_val),
                    }
                    for row_index, tvt_pred, z_val in zip(hidden_idx, pred, z_h)
                )
        if n % 25 == 0:
            print(f"processed {n}/{len(wids)} wells", flush=True)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    scores = pd.DataFrame(score_rows)
    scores.to_csv(args.scores_out, index=False)

    oracle = evaluate_oracle(scores) if args.split == "train" else pd.DataFrame()
    oracle.to_csv(args.oracle_out, index=False)
    cand_summary, oracle_summary = summarize_scores(scores, oracle)
    if args.summary_top and len(cand_summary) > args.summary_top:
        cand_summary = cand_summary.head(args.summary_top)
    summary = pd.concat(
        [cand_summary.assign(section="candidate"), oracle_summary.assign(section="oracle")],
        ignore_index=True,
        sort=False,
    )
    summary.to_csv(args.summary_out, index=False)
    if args.write_predictions:
        pd.DataFrame(pred_rows).to_csv(args.predictions_out, index=False)

    print(summary.to_string(index=False))
    print(f"wrote {args.scores_out}")
    print(f"wrote {args.oracle_out}")
    print(f"wrote {args.summary_out}")
    if args.write_predictions:
        print(f"wrote {args.predictions_out}")


if __name__ == "__main__":
    main()
