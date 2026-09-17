#!/usr/bin/env python3
"""Train one platform-agnostic regressor on released trunk/head features."""
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
from train_tabular import hierarchical_weights


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=True) as loaded:
        return {key: np.asarray(loaded[key]) for key in loaded.files}


def assemble(raw: dict[str, np.ndarray], official: dict[str, np.ndarray]):
    if not np.array_equal(raw["window_id"], official["window_id"]):
        raise ValueError("raw/official window_id order mismatch")
    head = official["head_prediction"].reshape(len(raw["X"]), -1)
    # A single regressor sees all four released heads simultaneously; there is
    # no platform ID input, classifier, argmax dispatch, or per-platform model.
    x = np.concatenate([raw["X"], official["embedding"], head], axis=1)
    if not np.isfinite(x).all():
        raise ValueError("non-finite stacked feature")
    return x.astype(np.float32, copy=False)


def make_model(iterations: int, seed: int) -> CatBoostRegressor:
    return CatBoostRegressor(
        loss_function="MultiRMSE",
        eval_metric="MultiRMSE",
        iterations=iterations,
        depth=8,
        learning_rate=0.04,
        l2_leaf_reg=8.0,
        random_seed=seed,
        random_strength=0.35,
        bootstrap_type="Bayesian",
        bagging_temperature=0.4,
        od_type="Iter",
        od_wait=70,
        allow_writing_files=False,
        thread_count=-1,
        verbose=50,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--official-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--metric", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--submission", type=Path, default=None)
    parser.add_argument("--iterations", type=int, default=600)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--reuse-selection", action="store_true")
    parser.add_argument("--experiment-id", default="E002")
    args = parser.parse_args()

    started = time.time()
    train_raw = load_npz(args.raw_dir / "train.npz")
    val_raw = load_npz(args.raw_dir / "val.npz")
    train_official = load_npz(args.official_dir / "train.npz")
    val_official = load_npz(args.official_dir / "val.npz")
    train_x = assemble(train_raw, train_official)
    val_x = assemble(val_raw, val_official)
    train_weight = hierarchical_weights(train_raw["platform"], train_raw["traj_id"])
    val_weight = hierarchical_weights(val_raw["platform"], val_raw["traj_id"])

    if args.reuse_selection:
        model = CatBoostRegressor()
        model.load_model(args.out_dir / "selection_model.cbm")
    else:
        model = make_model(args.iterations, args.seed)
        model.fit(
            Pool(train_x, train_raw["y"], weight=train_weight),
            eval_set=Pool(val_x, val_raw["y"], weight=val_weight),
            use_best_model=True,
            early_stopping_rounds=70,
        )
    best_iteration = int(model.tree_count_)
    validation_prediction = np.asarray(model.predict(val_x), dtype=np.float64)
    validation_frame = pd.DataFrame(
        {
            "window_id": val_raw["window_id"],
            "vx": validation_prediction[:, 0],
            "vy": validation_prediction[:, 1],
            "vz": validation_prediction[:, 2],
        }
    )
    solution = build_solution(args.data_root, "val")
    metric = load_official_metric(args.metric)
    validation = score_components(solution, validation_frame, metric)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(args.out_dir / "selection_model.cbm")
    validation_frame.to_csv(args.out_dir / "validation_predictions.csv", index=False)
    result: dict[str, object] = {
        "experiment_id": args.experiment_id,
        "method": "one CatBoost regressor over raw IMU features plus released unified trunk/all-head outputs; no routing",
        "seed": args.seed,
        "features": int(train_x.shape[1]),
        "requested_iterations": args.iterations,
        "best_iteration": best_iteration,
        "train_rows": int(len(train_x)),
        "validation_rows": int(len(val_x)),
        "validation": validation,
    }

    if args.submission is not None:
        test_raw = load_npz(args.raw_dir / "test.npz")
        test_official = load_npz(args.official_dir / "test.npz")
        test_x = assemble(test_raw, test_official)
        full_x = np.concatenate([train_x, val_x])
        full_y = np.concatenate([train_raw["y"], val_raw["y"]])
        full_platform = np.concatenate([train_raw["platform"], val_raw["platform"]])
        full_traj = np.concatenate([train_raw["traj_id"], val_raw["traj_id"]])
        full_weight = hierarchical_weights(full_platform, full_traj)
        final_model = make_model(best_iteration, args.seed)
        final_model.fit(Pool(full_x, full_y, weight=full_weight))
        final_model.save_model(args.out_dir / "final_model.cbm")
        test_prediction = np.asarray(final_model.predict(test_x), dtype=np.float64)
        submission = pd.DataFrame(
            {
                "window_id": test_raw["window_id"],
                "vx": test_prediction[:, 0],
                "vy": test_prediction[:, 1],
                "vz": test_prediction[:, 2],
            }
        )
        args.submission.parent.mkdir(parents=True, exist_ok=True)
        submission.to_csv(args.submission, index=False, float_format="%.8f")
        raw_bytes = args.submission.read_bytes()
        result.update(
            {
                "test_rows": int(len(test_x)),
                "submission": str(args.submission),
                "submission_md5": hashlib.md5(raw_bytes).hexdigest(),
                "submission_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            }
        )

    result["runtime_seconds"] = time.time() - started
    (args.out_dir / "manifest.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
