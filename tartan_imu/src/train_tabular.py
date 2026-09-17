#!/usr/bin/env python3
"""Train a unified CatBoost baseline and produce a test submission."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool

from score_validation import build_solution, load_official_metric, score_components


def load_cache(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as loaded:
        return {key: np.asarray(loaded[key]) for key in loaded.files}


def hierarchical_weights(platform: np.ndarray, traj_id: np.ndarray) -> np.ndarray:
    """Equal platform weight, then equal trajectory weight within each platform."""
    frame = pd.DataFrame(
        {"platform": platform.astype(str), "traj_id": traj_id.astype(str)}
    )
    platform_trajs = frame.groupby("platform")["traj_id"].nunique().to_dict()
    traj_rows = frame.groupby(["platform", "traj_id"]).size().to_dict()
    weights = np.asarray(
        [
            1.0 / platform_trajs[p] / traj_rows[(p, t)]
            for p, t in zip(frame["platform"], frame["traj_id"])
        ],
        dtype=np.float64,
    )
    return (weights / weights.mean()).astype(np.float32)


def make_model(
    iterations: int, seed: int, depth: int, learning_rate: float
) -> CatBoostRegressor:
    return CatBoostRegressor(
        loss_function="MultiRMSE",
        eval_metric="MultiRMSE",
        iterations=iterations,
        depth=depth,
        learning_rate=learning_rate,
        l2_leaf_reg=6.0,
        random_seed=seed,
        random_strength=0.5,
        bootstrap_type="Bayesian",
        bagging_temperature=0.5,
        od_type="Iter",
        od_wait=70,
        allow_writing_files=False,
        thread_count=-1,
        verbose=50,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("tartan_imu/artifacts/features_v1"),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("tartan_imu/data/extracted"),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("tartan_imu/artifacts/catboost_v1"),
    )
    parser.add_argument(
        "--submission",
        type=Path,
        default=Path("tartan_imu/submissions/E001_catboost_v1.csv"),
    )
    parser.add_argument("--iterations", type=int, default=700)
    parser.add_argument("--depth", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=0.045)
    parser.add_argument("--seed", type=int, default=20260909)
    args = parser.parse_args()

    started = time.time()
    train = load_cache(args.features / "train.npz")
    val = load_cache(args.features / "val.npz")
    test = load_cache(args.features / "test.npz")
    if not np.array_equal(train["feature_names"], val["feature_names"]):
        raise ValueError("train/val feature mismatch")
    if not np.array_equal(train["feature_names"], test["feature_names"]):
        raise ValueError("train/test feature mismatch")

    train_weights = hierarchical_weights(train["platform"], train["traj_id"])
    val_weights = hierarchical_weights(val["platform"], val["traj_id"])
    fit_pool = Pool(train["X"], train["y"], weight=train_weights)
    val_pool = Pool(val["X"], val["y"], weight=val_weights)

    model = make_model(args.iterations, args.seed, args.depth, args.learning_rate)
    model.fit(
        fit_pool,
        eval_set=val_pool,
        use_best_model=True,
        early_stopping_rounds=70,
    )
    best_iteration = max(1, model.get_best_iteration() + 1)
    val_prediction = np.asarray(model.predict(val["X"]), dtype=np.float64)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(args.out_dir / "selection_model.cbm")
    val_csv = args.out_dir / "validation_predictions.csv"
    pd.DataFrame(
        {
            "window_id": val["window_id"],
            "vx": val_prediction[:, 0],
            "vy": val_prediction[:, 1],
            "vz": val_prediction[:, 2],
        }
    ).to_csv(val_csv, index=False)

    metric_path = Path(
        "tartan_imu/official/TartanIMU/starter/kaggle_metric_tartanimu_score.py"
    )
    solution = build_solution(args.data_root, "val")
    metric = load_official_metric(metric_path)
    validation = score_components(solution, pd.read_csv(val_csv), metric)

    full_x = np.concatenate([train["X"], val["X"]], axis=0)
    full_y = np.concatenate([train["y"], val["y"]], axis=0)
    full_platform = np.concatenate([train["platform"], val["platform"]])
    full_traj = np.concatenate([train["traj_id"], val["traj_id"]])
    full_weights = hierarchical_weights(full_platform, full_traj)
    final_model = make_model(best_iteration, args.seed, args.depth, args.learning_rate)
    final_model.fit(Pool(full_x, full_y, weight=full_weights))
    final_model.save_model(args.out_dir / "final_model.cbm")

    test_prediction = np.asarray(final_model.predict(test["X"]), dtype=np.float64)
    args.submission.parent.mkdir(parents=True, exist_ok=True)
    submission = pd.DataFrame(
        {
            "window_id": test["window_id"],
            "vx": test_prediction[:, 0],
            "vy": test_prediction[:, 1],
            "vz": test_prediction[:, 2],
        }
    )
    submission.to_csv(args.submission, index=False, float_format="%.8f")
    raw = args.submission.read_bytes()
    result = {
        "experiment_id": "E001",
        "method": "single CatBoost MultiRMSE model; direct velocity; no platform routing",
        "seed": args.seed,
        "requested_iterations": args.iterations,
        "best_iteration": best_iteration,
        "depth": args.depth,
        "learning_rate": args.learning_rate,
        "features": int(train["X"].shape[1]),
        "train_rows": int(len(train["X"])),
        "validation_rows": int(len(val["X"])),
        "test_rows": int(len(test["X"])),
        "validation": validation,
        "submission": str(args.submission),
        "submission_md5": hashlib.md5(raw).hexdigest(),
        "submission_sha256": hashlib.sha256(raw).hexdigest(),
        "runtime_seconds": time.time() - started,
    }
    manifest = args.out_dir / "manifest.json"
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
