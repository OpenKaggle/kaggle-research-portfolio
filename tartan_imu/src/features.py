#!/usr/bin/env python3
"""Deterministic, leak-free IMU feature extraction for the TartanIMU challenge."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

WINDOW = 200


def _add(parts: list[np.ndarray], names: list[str], prefix: str, values: np.ndarray) -> None:
    values = np.asarray(values, dtype=np.float32)
    if values.ndim == 1:
        values = values[:, None]
    parts.append(values)
    names.extend(f"{prefix}_{i}" for i in range(values.shape[1]))


def window_features(windows: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Extract per-window statistics from (windows, 200, 6) raw IMU."""
    w = np.asarray(windows, dtype=np.float32)
    parts: list[np.ndarray] = []
    names: list[str] = []

    mean = w.mean(axis=1)
    std = w.std(axis=1)
    centered = w - mean[:, None, :]
    rms = np.sqrt(np.mean(w * w, axis=1))
    quant = np.quantile(w, [0.10, 0.25, 0.50, 0.75, 0.90], axis=1)
    slope_t = np.arange(WINDOW, dtype=np.float32) - (WINDOW - 1) / 2
    slope = np.einsum("t,ntc->nc", slope_t, centered) / np.sum(slope_t * slope_t)
    diff = np.diff(w, axis=1)

    for prefix, values in (
        ("mean", mean),
        ("std", std),
        ("q10", quant[0]),
        ("q25", quant[1]),
        ("median", quant[2]),
        ("q75", quant[3]),
        ("q90", quant[4]),
        ("min", w.min(axis=1)),
        ("max", w.max(axis=1)),
        ("rms", rms),
        ("absmean", np.abs(w).mean(axis=1)),
        ("first", w[:, 0]),
        ("last", w[:, -1]),
        ("delta", w[:, -1] - w[:, 0]),
        ("slope", slope),
        ("diff_absmean", np.abs(diff).mean(axis=1)),
        ("diff_std", diff.std(axis=1)),
        ("diff_rms", np.sqrt(np.mean(diff * diff, axis=1))),
    ):
        _add(parts, names, prefix, values)

    norms = np.stack(
        [np.linalg.norm(w[:, :, :3], axis=2), np.linalg.norm(w[:, :, 3:], axis=2)],
        axis=2,
    )
    nq = np.quantile(norms, [0.10, 0.50, 0.90], axis=1)
    for prefix, values in (
        ("norm_mean", norms.mean(axis=1)),
        ("norm_std", norms.std(axis=1)),
        ("norm_q10", nq[0]),
        ("norm_median", nq[1]),
        ("norm_q90", nq[2]),
        ("norm_min", norms.min(axis=1)),
        ("norm_max", norms.max(axis=1)),
        ("norm_rms", np.sqrt(np.mean(norms * norms, axis=1))),
    ):
        _add(parts, names, prefix, values)

    chunk_mean = w.reshape(len(w), 10, 20, 6).mean(axis=2).reshape(len(w), -1)
    chunk_std = w.reshape(len(w), 4, 50, 6).std(axis=2).reshape(len(w), -1)
    _add(parts, names, "chunk20_mean", chunk_mean)
    _add(parts, names, "chunk50_std", chunk_std)

    spectrum = np.abs(np.fft.rfft(centered, axis=1)).astype(np.float32) / WINDOW
    bands = ((1, 3), (3, 6), (6, 11), (11, 21), (21, 41), (41, 61), (61, 81), (81, 101))
    band_values = []
    for lo, hi in bands:
        band_values.append(np.sqrt(np.mean(spectrum[:, lo:hi] ** 2, axis=1)))
    _add(parts, names, "fft_band_rms", np.concatenate(band_values, axis=1))

    denom = np.maximum(std[:, :, None] * std[:, None, :], 1e-8)
    corr = np.einsum("ntc,ntd->ncd", centered, centered) / WINDOW / denom
    pairs = [(i, j) for i in range(6) for j in range(i + 1, 6)]
    corr_values = np.stack([corr[:, i, j] for i, j in pairs], axis=1)
    _add(parts, names, "corr", corr_values)

    x = np.concatenate(parts, axis=1).astype(np.float32)
    if not np.isfinite(x).all():
        raise ValueError("non-finite feature generated")
    return x, names


def add_trajectory_context(x: np.ndarray, names: list[str]) -> tuple[np.ndarray, list[str]]:
    """Add same-trajectory context without platform labels or hidden information."""
    core_idx = [i for i, n in enumerate(names) if n.startswith(("mean_", "std_", "rms_", "norm_mean_", "norm_std_"))]
    core = x[:, core_idx]
    context = [x]
    context_names = list(names)

    for shift in (-5, -2, -1, 1, 2, 5):
        idx = np.clip(np.arange(len(x)) + shift, 0, len(x) - 1)
        context.append(core[idx])
        context_names.extend(f"ctx_s{shift:+d}_{names[i]}" for i in core_idx)

    for radius in (2, 5):
        padded = np.pad(core, ((radius, radius), (0, 0)), mode="edge")
        csum = np.vstack([np.zeros((1, core.shape[1]), dtype=np.float64), np.cumsum(padded, axis=0)])
        rolled = (csum[2 * radius + 1:] - csum[: -(2 * radius + 1)]) / (2 * radius + 1)
        context.append(rolled.astype(np.float32))
        context_names.extend(f"ctx_r{radius}_{names[i]}" for i in core_idx)

    global_stats = np.concatenate(
        [np.median(core, axis=0), np.std(core, axis=0)], axis=0
    ).astype(np.float32)
    context.append(np.repeat(global_stats[None, :], len(x), axis=0))
    context_names.extend([f"traj_median_{names[i]}" for i in core_idx])
    context_names.extend([f"traj_std_{names[i]}" for i in core_idx])

    pos = np.linspace(0.0, 1.0, len(x), dtype=np.float32)
    context.append(np.stack([pos, 1.0 - pos], axis=1))
    context_names.extend(["trajectory_fraction", "trajectory_fraction_reverse"])
    out = np.concatenate(context, axis=1).astype(np.float32)
    return out, context_names


def _trajectory_path(root: Path, split: str, platform: str | None, traj_id: str) -> Path:
    if split == "test":
        return root / split / f"{traj_id}.npz"
    assert platform is not None
    return root / split / platform / f"{traj_id}.npz"


def extract_split(root: Path, split: str, out: Path) -> None:
    index = pd.read_csv(root / "index" / f"{split}_windows.csv")
    target = None
    if split != "test":
        target = pd.read_csv(root / "index" / f"{split}_targets.csv").set_index("window_id")

    x_parts: list[np.ndarray] = []
    ids: list[np.ndarray] = []
    trajs: list[np.ndarray] = []
    win_idxs: list[np.ndarray] = []
    platforms: list[np.ndarray] = []
    y_parts: list[np.ndarray] = []
    feature_names: list[str] | None = None

    grouped = list(index.groupby("traj_id", sort=False))
    for number, (traj_id, rows) in enumerate(grouped, start=1):
        rows = rows.sort_values("win_idx")
        platform = None if split == "test" else str(rows["platform"].iloc[0])
        path = _trajectory_path(root, split, platform, str(traj_id))
        if not path.exists():
            raise FileNotFoundError(path)
        with np.load(path) as loaded:
            imu = np.asarray(loaded["imu"], dtype=np.float32)
        wi = rows["win_idx"].to_numpy(np.int64)
        if wi.min() < 0 or (wi.max() + 1) * WINDOW > len(imu):
            raise ValueError(f"window index out of bounds for {path}")
        windows = np.stack([imu[k * WINDOW : (k + 1) * WINDOW] for k in wi])
        raw_x, raw_names = window_features(windows)
        traj_x, traj_names = add_trajectory_context(raw_x, raw_names)
        if feature_names is None:
            feature_names = traj_names
        elif feature_names != traj_names:
            raise ValueError("feature name/order mismatch")

        x_parts.append(traj_x)
        ids.append(rows["window_id"].to_numpy(np.int64))
        trajs.append(np.repeat(str(traj_id), len(rows)))
        win_idxs.append(wi)
        platforms.append(np.repeat(platform or "unknown", len(rows)))
        if target is not None:
            y_parts.append(target.loc[rows["window_id"], ["vx", "vy", "vz"]].to_numpy(np.float32))
        if number % 25 == 0 or number == len(grouped):
            print(f"{split}: {number}/{len(grouped)} trajectories")

    payload: dict[str, np.ndarray] = {
        "X": np.concatenate(x_parts),
        "window_id": np.concatenate(ids),
        "traj_id": np.concatenate(trajs),
        "win_idx": np.concatenate(win_idxs),
        "platform": np.concatenate(platforms),
        "feature_names": np.asarray(feature_names),
    }
    if y_parts:
        payload["y"] = np.concatenate(y_parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **payload)
    print(f"wrote {out}: X={payload['X'].shape}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("tartan_imu/data/extracted"))
    parser.add_argument("--out-dir", type=Path, default=Path("tartan_imu/artifacts/features_v1"))
    parser.add_argument("--splits", nargs="+", choices=("train", "val", "test"), default=("train", "val", "test"))
    args = parser.parse_args()
    for split in args.splits:
        extract_split(args.root, split, args.out_dir / f"{split}.npz")


if __name__ == "__main__":
    main()
