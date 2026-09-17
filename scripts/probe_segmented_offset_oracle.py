from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


DATA = Path("data/raw/rogii-wellbore-geology-prediction")
TRAIN = DATA / "train"
REPORT_DIR = Path("reports")


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return math.nan
    return float(np.sqrt(np.mean((a[m] - b[m]) ** 2)))


def contiguous_segment_sse(
    target_dtvt: np.ndarray,
    dz: np.ndarray,
    start: int,
    end: int,
    z_sign: float,
) -> tuple[float, float]:
    residual = target_dtvt[start:end] - z_sign * dz[start:end]
    offset = float(np.nanmean(residual))
    err = residual - offset
    return float(np.nansum(err * err)), offset


def piecewise_offset_oracle(
    z: np.ndarray,
    tvt: np.ndarray,
    tvt_input: np.ndarray,
    ps: int,
    n_segments: int,
    z_sign: float = -1.0,
    min_steps: int = 32,
    boundary_step: int = 16,
) -> dict[str, object]:
    hidden_start = ps + 1
    if hidden_start >= len(z):
        return {"ok": False}

    y = tvt[hidden_start:]
    dz = np.diff(z[ps:])
    target_dtvt = np.diff(tvt[ps:])
    n = len(target_dtvt)
    if n <= 0:
        return {"ok": False}

    n_segments = max(1, min(n_segments, max(1, n // min_steps)))
    boundary_step = max(1, int(boundary_step))
    min_len = min_steps if n >= min_steps else 1

    positions = np.unique(
        np.r_[0, np.arange(boundary_step, n, boundary_step, dtype=int), n]
    ).astype(int)
    m = len(positions)
    residual = target_dtvt - z_sign * dz
    prefix = np.r_[0.0, np.cumsum(residual)]
    prefix2 = np.r_[0.0, np.cumsum(residual * residual)]

    starts = positions[:, None]
    ends = positions[None, :]
    lengths = ends - starts
    valid = lengths >= min_len
    sums = prefix[ends] - prefix[starts]
    sums2 = prefix2[ends] - prefix2[starts]
    with np.errstate(invalid="ignore", divide="ignore"):
        costs = sums2 - sums * sums / lengths
        offsets = sums / lengths
    costs[~valid] = np.inf
    offsets[~valid] = np.nan

    dp = np.full((n_segments + 1, m), np.inf, dtype=float)
    prev = np.full((n_segments + 1, m), -1, dtype=int)
    dp[0, 0] = 0.0
    for s in range(1, n_segments + 1):
        for end_idx in range(1, m):
            candidates = dp[s - 1, :end_idx] + costs[:end_idx, end_idx]
            best_mid = int(np.argmin(candidates))
            best_cost = float(candidates[best_mid])
            if math.isfinite(best_cost):
                dp[s, end_idx] = best_cost
                prev[s, end_idx] = best_mid

    usable = np.flatnonzero(np.isfinite(dp[1:, m - 1]))
    if len(usable) == 0:
        return {"ok": False}
    best_s = int(usable[np.argmin(dp[1:, m - 1][usable])] + 1)
    boundaries: list[tuple[int, int]] = []
    end_idx = m - 1
    for s in range(best_s, 0, -1):
        start_idx = int(prev[s, end_idx])
        if start_idx < 0:
            return {"ok": False}
        start = int(positions[start_idx])
        end = int(positions[end_idx]) - 1
        boundaries.append((start, end))
        end_idx = start_idx
    boundaries.reverse()

    pred_dtvt = np.empty(n, dtype=float)
    segment_offsets = []
    for start, end in boundaries:
        _, off = contiguous_segment_sse(target_dtvt, dz, start, end + 1, z_sign)
        pred_dtvt[start : end + 1] = z_sign * dz[start : end + 1] + off
        segment_offsets.append(off)
    pred = float(tvt_input[ps]) + np.cumsum(pred_dtvt)
    return {
        "ok": True,
        "segments_used": len(boundaries),
        "rmse": rmse(pred, y),
        "boundaries": boundaries,
        "offsets": segment_offsets,
        "boundary_step": boundary_step,
    }


def one_well(
    path: Path, max_segments: int, min_steps: int, boundary_step: int
) -> list[dict[str, object]]:
    well = path.name.replace("__horizontal_well.csv", "")
    df = pd.read_csv(path)
    known = df["TVT_input"].notna().to_numpy()
    if known.sum() < 20 or known.all():
        return [{"well": well, "status": "skip"}]
    ps = int(np.flatnonzero(known)[-1])
    z = df["Z"].to_numpy(float)
    tvt = df["TVT"].to_numpy(float)
    tvt_input = df["TVT_input"].to_numpy(float)
    rows: list[dict[str, object]] = []
    for k in range(1, max_segments + 1):
        out = piecewise_offset_oracle(
            z,
            tvt,
            tvt_input,
            ps,
            k,
            min_steps=min_steps,
            boundary_step=boundary_step,
        )
        rows.append(
            {
                "well": well,
                "status": "ok" if out.get("ok") else "skip",
                "hidden_rows": int(len(df) - ps - 1),
                "requested_segments": k,
                "segments_used": out.get("segments_used"),
                "boundary_step": out.get("boundary_step"),
                "rmse": out.get("rmse"),
                "offsets": "|".join(f"{x:.4f}" for x in out.get("offsets", [])),
                "boundaries": "|".join(f"{a}:{b}" for a, b in out.get("boundaries", [])),
            }
        )
    return rows


def weighted_rmse(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for k, g in df[df["status"].eq("ok")].groupby("requested_segments"):
        weights = g["hidden_rows"].to_numpy(float)
        vals = g["rmse"].to_numpy(float)
        rows.append(
            {
                "segments": int(k),
                "weighted_rmse": float(np.sqrt(np.average(vals * vals, weights=weights))),
                "mean_well_rmse": float(np.mean(vals)),
                "median_well_rmse": float(np.median(vals)),
                "wells": int(len(g)),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-segments", type=int, default=8)
    parser.add_argument("--min-steps", type=int, default=64)
    parser.add_argument("--boundary-step", type=int, default=16)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPORT_DIR / "rogii_segmented_offset_oracle_by_well.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=REPORT_DIR / "rogii_segmented_offset_oracle_summary.csv",
    )
    args = parser.parse_args()

    paths = sorted(TRAIN.glob("*__horizontal_well.csv"))
    if args.limit:
        paths = paths[: args.limit]
    all_rows: list[dict[str, object]] = []
    for path in paths:
        all_rows.extend(
            one_well(path, args.max_segments, args.min_steps, args.boundary_step)
        )

    df = pd.DataFrame(all_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    summary = weighted_rmse(df)
    summary.to_csv(args.summary_out, index=False)
    print(summary.to_string(index=False))
    print(f"wrote {args.out}")
    print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()
