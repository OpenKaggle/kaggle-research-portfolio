#!/usr/bin/env python3
"""Build the labelled validation solution and call the organizers' exact scorer."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_official_metric(path: Path):
    spec = importlib.util.spec_from_file_location("tartanimu_official_metric", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_solution(
    root: Path,
    split: str = "val",
    midpoint: int = 100,
    position_offset: int = 199,
) -> pd.DataFrame:
    windows = pd.read_csv(root / "index" / f"{split}_windows.csv")
    targets = pd.read_csv(root / "index" / f"{split}_targets.csv").set_index("window_id")
    chunks: list[pd.DataFrame] = []
    for traj_id, rows in windows.groupby("traj_id", sort=False):
        rows = rows.sort_values("win_idx").copy()
        platform = str(rows["platform"].iloc[0])
        path = root / split / platform / f"{traj_id}.npz"
        with np.load(path) as z:
            ts = np.asarray(z["ts"])
            quat = np.asarray(z["quat"])
            pos = np.asarray(z["pos"])
        starts = rows["win_idx"].to_numpy(np.int64) * 200
        mids = starts + midpoint
        position_samples = starts + position_offset
        ends = starts + 199
        if ends.max() >= len(ts):
            raise ValueError(f"window out of bounds: {path}")
        frame = pd.DataFrame(
            {
                "window_id": rows["window_id"].to_numpy(np.int64),
                "traj_id": str(traj_id),
                "win_idx": rows["win_idx"].to_numpy(np.int64),
                "platform": platform,
                "qx": quat[mids, 0],
                "qy": quat[mids, 1],
                "qz": quat[mids, 2],
                "qw": quat[mids, 3],
                "gx": pos[position_samples, 0],
                "gy": pos[position_samples, 1],
                "gz": pos[position_samples, 2],
                "dt": ts[ends] - ts[starts],
            }
        )
        gt = targets.loc[frame["window_id"], ["vx", "vy", "vz"]].to_numpy(float)
        frame[["vx_gt", "vy_gt", "vz_gt"]] = gt
        chunks.append(frame)
    return pd.concat(chunks, ignore_index=True)


def score_components(solution: pd.DataFrame, submission: pd.DataFrame, metric) -> dict:
    score = float(metric.score(solution.copy(), submission.copy(), "window_id"))
    pred = submission.rename(columns={"vx": "vx_pred", "vy": "vy_pred", "vz": "vz_pred"})
    merged = solution.merge(pred, on="window_id", how="left")
    trajectory_rows = []
    for (platform, traj_id), group in merged.groupby(["platform", "traj_id"], sort=False):
        group = group.sort_values("win_idx")
        trajectory_rows.append(
            {
                "platform": platform,
                "traj_id": traj_id,
                "ave": float(metric._ave_traj(group)),
                "ate20": float(metric._ate_traj(group)),
            }
        )
    traj = pd.DataFrame(trajectory_rows)
    by_platform = traj.groupby("platform")[["ave", "ate20"]].mean()
    return {
        "score": score,
        "macro_ave": float(by_platform["ave"].mean()),
        "macro_ate20": float(by_platform["ate20"].mean()),
        "by_platform": {
            idx: {"ave": float(row["ave"]), "ate20": float(row["ate20"])}
            for idx, row in by_platform.iterrows()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("tartan_imu/data/extracted"))
    parser.add_argument("--split", choices=("train", "val"), default="val")
    parser.add_argument("--prediction", type=Path, default=None)
    parser.add_argument("--midpoint", type=int, choices=(99, 100), default=100)
    parser.add_argument(
        "--metric",
        type=Path,
        default=Path("tartan_imu/official/TartanIMU/starter/kaggle_metric_tartanimu_score.py"),
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    solution = build_solution(args.root, args.split, args.midpoint)
    if args.prediction is None:
        submission = solution[["window_id", "vx_gt", "vy_gt", "vz_gt"]].rename(
            columns={"vx_gt": "vx", "vy_gt": "vy", "vz_gt": "vz"}
        )
    else:
        submission = pd.read_csv(args.prediction)
    metric = load_official_metric(args.metric)
    result = score_components(solution, submission, metric)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n")


if __name__ == "__main__":
    main()
