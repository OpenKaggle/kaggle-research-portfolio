from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit


sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_rogii_candidate_paths as candgen  # noqa: E402


REPORT_DIR = Path("reports")
STRONG_FAMILIES = {
    "anchor",
    "offset_state",
    "segment_grid",
    "dwt_pf",
    "dwt_beam",
    "dwt_dense",
    "pf_frontier_seed",
    "pf_frontier_ensemble",
}


def weighted_rmse(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sqrt(np.average(np.asarray(values, float) ** 2, weights=weights)))


def candidate_functions(args: argparse.Namespace):
    fns = [lambda hw, tw, ctx, wid: candgen.simple_candidates(hw, ctx)]
    if args.include_segment_grid:
        fns.append(lambda hw, tw, ctx, wid: candgen.segment_grid_candidates(hw, ctx))
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
    if args.include_dwt_bundle:
        dwt_bundle = candgen.DwtBundleGenerator(args.split, args.seed)
        fns.append(lambda hw, tw, ctx, wid: dwt_bundle(hw, tw, ctx, wid))
    return fns


def cache_path(args: argparse.Namespace, wid: str) -> Path:
    tag = (
        f"{args.split}_seg{int(args.include_segment_grid)}"
        f"_dwt{int(args.include_dwt_bundle)}"
        f"_pff{int(args.include_pf_frontier)}"
        f"_p{args.pf_particles}_s{args.pf_frontier_seeds}"
        f"_seed{args.seed}"
    )
    return args.cache_dir / tag / f"{wid}.npz"


def generate_or_load_candidates(
    args: argparse.Namespace,
    wid: str,
    hw: pd.DataFrame,
    tw: pd.DataFrame,
    ctx: dict[str, object],
    fns,
) -> tuple[list[str], list[str], np.ndarray]:
    path = cache_path(args, wid)
    if path.exists() and not args.refresh_cache:
        with np.load(path, allow_pickle=True) as data:
            return (
                data["names"].astype(str).tolist(),
                data["families"].astype(str).tolist(),
                data["tvt"].astype(np.float64),
            )

    candidates = []
    for fn in fns:
        candidates.extend(fn(hw, tw, ctx, wid))
    names: list[str] = []
    families: list[str] = []
    paths: list[np.ndarray] = []
    seen: set[bytes] = set()
    for name, family, pred in candidates:
        pred = np.asarray(pred, dtype=np.float64)
        if pred.shape != (len(ctx["hidden_idx"]),) or not np.isfinite(pred).all():
            continue
        key = np.round(pred, 5).astype(np.float32).tobytes()
        if key in seen:
            continue
        seen.add(key)
        names.append(str(name))
        families.append(str(family))
        paths.append(pred)
    tvt = np.stack(paths, axis=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        names=np.asarray(names, dtype=object),
        families=np.asarray(families, dtype=object),
        tvt=tvt.astype(np.float32),
    )
    return names, families, tvt


def segment_oracle(
    tvt: np.ndarray,
    y: np.ndarray,
    segment_length: int,
) -> tuple[np.ndarray, int]:
    pred = np.empty_like(y)
    selected: list[int] = []
    for start in range(0, len(y), segment_length):
        end = min(len(y), start + segment_length)
        mse = np.mean((tvt[:, start:end] - y[None, start:end]) ** 2, axis=1)
        best = int(np.argmin(mse))
        pred[start:end] = tvt[best, start:end]
        selected.append(best)
    switches = int(np.sum(np.diff(selected) != 0)) if len(selected) > 1 else 0
    return pred, switches


def nearest_distances(grid: np.ndarray, values: np.ndarray) -> np.ndarray:
    values = np.sort(np.asarray(values, dtype=float))
    if len(values) == 0:
        return np.full(len(grid), np.inf, dtype=float)
    pos = np.searchsorted(values, grid)
    left = values[np.clip(pos - 1, 0, len(values) - 1)]
    right = values[np.clip(pos, 0, len(values) - 1)]
    return np.minimum(np.abs(grid - left), np.abs(grid - right))


def build_emission(
    c_paths: np.ndarray,
    families: list[str],
    z: np.ndarray,
    gr: np.ndarray,
    tw: pd.DataFrame,
    grid: np.ndarray,
    support_sigma: float,
    gr_weight: float,
) -> np.ndarray:
    family_indices = {
        family: np.flatnonzero(np.asarray(families) == family)
        for family in sorted(set(families) & STRONG_FAMILIES)
    }
    family_indices = {family: idx for family, idx in family_indices.items() if len(idx)}
    emission = np.empty((c_paths.shape[1], len(grid)), dtype=np.float32)

    tw_tvt = tw["TVT"].to_numpy(float)
    tw_gr = tw["GR"].to_numpy(float)
    order = np.argsort(tw_tvt)
    tw_tvt = tw_tvt[order]
    tw_gr = tw_gr[order]
    gr_center = float(np.nanmedian(tw_gr))
    gr_scale = max(10.0, 1.4826 * float(np.nanmedian(np.abs(tw_gr - gr_center))))

    for row in range(c_paths.shape[1]):
        support = np.zeros(len(grid), dtype=float)
        for idx in family_indices.values():
            dist = nearest_distances(grid, c_paths[idx, row])
            support += np.exp(-0.5 * (dist / support_sigma) ** 2)
        support_cost = -np.log(support + 0.05)

        if np.isfinite(gr[row]) and gr_weight > 0:
            tvt_grid = grid - z[row]
            expected_gr = np.interp(tvt_grid, tw_tvt, tw_gr, left=np.nan, right=np.nan)
            gr_cost = ((gr[row] - expected_gr) / gr_scale) ** 2
            gr_cost[~np.isfinite(gr_cost)] = 9.0
        else:
            gr_cost = 0.0
        emission[row] = (support_cost + gr_weight * gr_cost).astype(np.float32)
    return emission


@njit(cache=True)
def viterbi_grid(
    emission: np.ndarray,
    start_state: int,
    start_weight: float,
    transition_weight: float,
    max_step: int,
) -> np.ndarray:
    n_rows, n_states = emission.shape
    previous = emission[0].astype(np.float64).copy()
    for state in range(n_states):
        previous[state] += start_weight * abs(state - start_state)
    back = np.zeros((n_rows, n_states), dtype=np.int16)

    for row in range(1, n_rows):
        current = np.empty(n_states, dtype=np.float64)
        for state in range(n_states):
            lo = max(0, state - max_step)
            hi = min(n_states, state + max_step + 1)
            best_cost = 1e300
            best_prev = state
            for prev_state in range(lo, hi):
                cost = previous[prev_state] + transition_weight * abs(state - prev_state)
                if cost < best_cost:
                    best_cost = cost
                    best_prev = prev_state
            current[state] = best_cost + emission[row, state]
            back[row, state] = best_prev
        previous = current

    states = np.empty(n_rows, dtype=np.int32)
    states[-1] = int(np.argmin(previous))
    for row in range(n_rows - 1, 0, -1):
        states[row - 1] = back[row, states[row]]
    return states


def evaluate_well(
    args: argparse.Namespace,
    wid: str,
    hw: pd.DataFrame,
    tw: pd.DataFrame,
    ctx: dict[str, object],
    fns,
) -> list[dict[str, object]]:
    names, families, tvt = generate_or_load_candidates(args, wid, hw, tw, ctx, fns)
    hidden_idx = np.asarray(ctx["hidden_idx"], dtype=int)
    y = hw["TVT"].to_numpy(float)[hidden_idx]
    z = hw["Z"].to_numpy(float)[hidden_idx]
    gr = hw["GR"].to_numpy(float)[hidden_idx]
    c_paths = tvt + z[None, :]
    rows: list[dict[str, object]] = []

    path_mse = np.mean((tvt - y[None, :]) ** 2, axis=1)
    best_path = int(np.argmin(path_mse))
    rows.append(
        {
            "well": wid,
            "method": "path_oracle",
            "rmse": float(np.sqrt(path_mse[best_path])),
            "hidden_rows": len(y),
            "candidate_count": len(names),
            "switches": 0,
            "detail": names[best_path],
        }
    )

    local_pred = tvt[np.argmin(np.abs(tvt - y[None, :]), axis=0), np.arange(len(y))]
    rows.append(
        {
            "well": wid,
            "method": "row_candidate_oracle",
            "rmse": candgen.rmse(local_pred, y),
            "hidden_rows": len(y),
            "candidate_count": len(names),
            "switches": int(np.sum(np.diff(np.argmin(np.abs(tvt - y[None, :]), axis=0)) != 0)),
            "detail": "",
        }
    )
    for length in args.segment_lengths:
        pred, switches = segment_oracle(tvt, y, length)
        rows.append(
            {
                "well": wid,
                "method": f"segment_oracle_{length}",
                "rmse": candgen.rmse(pred, y),
                "hidden_rows": len(y),
                "candidate_count": len(names),
                "switches": switches,
                "detail": "",
            }
        )

    strong = np.flatnonzero(np.isin(np.asarray(families), list(STRONG_FAMILIES)))
    strong_c = c_paths[strong]
    c_min = math.floor(float(np.nanmin(strong_c)) - args.grid_margin)
    c_max = math.ceil(float(np.nanmax(strong_c)) + args.grid_margin)
    grid = np.arange(c_min, c_max + args.grid_step / 2, args.grid_step, dtype=float)

    for support_sigma, gr_weight, transition_weight in args.dp_configs:
        emission = build_emission(
            strong_c,
            [families[i] for i in strong],
            z,
            gr,
            tw,
            grid,
            support_sigma,
            gr_weight,
        )
        start_state = int(np.argmin(np.abs(grid - float(ctx["last_c"]))))
        states = viterbi_grid(
            emission,
            start_state,
            args.start_weight,
            transition_weight,
            args.max_step,
        )
        pred = grid[states] - z
        rows.append(
            {
                "well": wid,
                "method": (
                    f"cgrid_s{support_sigma:g}_g{gr_weight:g}"
                    f"_t{transition_weight:g}"
                ),
                "rmse": candgen.rmse(pred, y),
                "hidden_rows": len(y),
                "candidate_count": len(names),
                "switches": int(np.sum(np.diff(states) != 0)),
                "detail": f"states={len(grid)}",
            }
        )
    return rows


def parse_config(value: str) -> tuple[float, float, float]:
    parts = [float(part) for part in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("DP config must be support_sigma,gr_weight,transition_weight")
    return parts[0], parts[1], parts[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["train", "test"], default="train")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--include-segment-grid", action="store_true")
    parser.add_argument("--include-dwt-bundle", action="store_true")
    parser.add_argument("--include-pf-frontier", action="store_true")
    parser.add_argument("--pf-particles", type=int, default=100)
    parser.add_argument("--pf-frontier-seeds", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260606)
    parser.add_argument("--segment-lengths", type=int, nargs="+", default=[64, 128, 256, 512])
    parser.add_argument("--grid-step", type=float, default=1.0)
    parser.add_argument("--grid-margin", type=float, default=5.0)
    parser.add_argument("--start-weight", type=float, default=1.0)
    parser.add_argument("--max-step", type=int, default=1)
    parser.add_argument(
        "--dp-config",
        action="append",
        type=parse_config,
        dest="dp_configs",
        help="support_sigma,gr_weight,transition_weight",
    )
    parser.add_argument("--cache-dir", type=Path, default=REPORT_DIR / "rogii_candidate_cache")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument(
        "--by-well-out",
        type=Path,
        default=REPORT_DIR / "rogii_structured_selector_by_well20.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=REPORT_DIR / "rogii_structured_selector_summary20.csv",
    )
    args = parser.parse_args()
    if not args.dp_configs:
        args.dp_configs = [
            (1.5, 0.0, 0.02),
            (1.5, 0.05, 0.02),
            (1.5, 0.2, 0.02),
            (3.0, 0.05, 0.02),
            (3.0, 0.2, 0.05),
        ]

    folder = candgen.TRAIN if args.split == "train" else candgen.TEST
    wids = candgen.list_wells(folder)
    if args.limit:
        wids = wids[: args.limit]
    fns = candidate_functions(args)
    rows: list[dict[str, object]] = []
    for number, wid in enumerate(wids, start=1):
        hw, tw = candgen.load_well(folder, wid)
        ctx = candgen.hidden_context(hw)
        if ctx is None:
            continue
        rows.extend(evaluate_well(args, wid, hw, tw, ctx, fns))
        print(f"processed {number}/{len(wids)} wells", flush=True)

    by_well = pd.DataFrame(rows)
    args.by_well_out.parent.mkdir(parents=True, exist_ok=True)
    by_well.to_csv(args.by_well_out, index=False)
    summary_rows = []
    for method, group in by_well.groupby("method", sort=False):
        values = group["rmse"].to_numpy(float)
        weights = group["hidden_rows"].to_numpy(float)
        summary_rows.append(
            {
                "method": method,
                "weighted_rmse": weighted_rmse(values, weights),
                "mean_well_rmse": float(np.mean(values)),
                "median_well_rmse": float(np.median(values)),
                "mean_switches": float(group["switches"].mean()),
                "wells": len(group),
            }
        )
    summary = pd.DataFrame(summary_rows).sort_values("weighted_rmse")
    summary.to_csv(args.summary_out, index=False)
    metadata_path = args.summary_out.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "grid_step": args.grid_step,
                "strong_families": sorted(STRONG_FAMILIES),
                "dp_configs": args.dp_configs,
            },
            indent=2,
        )
        + "\n"
    )
    print(summary.to_string(index=False))
    print(f"wrote {args.by_well_out}")
    print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()
