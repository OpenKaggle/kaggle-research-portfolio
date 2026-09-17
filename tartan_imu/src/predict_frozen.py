#!/usr/bin/env python3
"""Offline end-to-end inference for the frozen unified TartanIMU system."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    print("RUN", " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=True) as loaded:
        return {key: np.asarray(loaded[key]) for key in loaded.files}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--scripts-dir", type=Path, required=True)
    parser.add_argument("--official-source", type=Path, required=True)
    parser.add_argument("--official-config", type=Path, required=True)
    parser.add_argument("--model-yaml", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--regressor", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=None)
    parser.add_argument("--reuse-cache", action="store_true")
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args()

    started = time.time()
    args.work_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.work_dir / "raw_features"
    official_dir = args.work_dir / "official_embeddings"
    raw_cache = raw_dir / "test.npz"
    official_cache = official_dir / "test.npz"
    python = sys.executable

    if not args.reuse_cache or not raw_cache.exists():
        run(
            [
                python,
                str(args.scripts_dir / "features.py"),
                "--root",
                str(args.data_root),
                "--out-dir",
                str(raw_dir),
                "--splits",
                "test",
            ]
        )

    if not args.reuse_cache or not official_cache.exists():
        env = os.environ.copy()
        previous = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(args.official_source)
            if not previous
            else str(args.official_source) + os.pathsep + previous
        )
        run(
            [
                python,
                str(args.scripts_dir / "cache_official_embeddings.py"),
                "--split",
                "test",
                "--data-root",
                str(args.data_root),
                "--config",
                str(args.official_config),
                "--model-yaml",
                str(args.model_yaml),
                "--checkpoint",
                str(args.official_checkpoint),
                "--output",
                str(official_cache),
                "--batch-seqs",
                "32",
            ],
            env=env,
        )

    raw = load_npz(raw_cache)
    official = load_npz(official_cache)
    if not np.array_equal(raw["window_id"], official["window_id"]):
        raise SystemExit("raw/official window_id order mismatch")
    all_heads = official["head_prediction"].reshape(len(raw["X"]), -1)
    features = np.concatenate([raw["X"], official["embedding"], all_heads], axis=1)
    if features.shape[1] != 633 or not np.isfinite(features).all():
        raise SystemExit(f"invalid stacked features: {features.shape}")

    model = CatBoostRegressor()
    model.load_model(args.regressor)
    prediction = np.asarray(model.predict(features), dtype=np.float64)
    submission = pd.DataFrame(
        {
            "window_id": raw["window_id"],
            "vx": prediction[:, 0],
            "vy": prediction[:, 1],
            "vz": prediction[:, 2],
        }
    )
    sample = pd.read_csv(args.sample)
    if submission.columns.tolist() != ["window_id", "vx", "vy", "vz"]:
        raise SystemExit("wrong output columns")
    if not submission["window_id"].equals(sample["window_id"]):
        raise SystemExit("output IDs/order differ from sample submission")
    if not np.isfinite(submission[["vx", "vy", "vz"]].to_numpy()).all():
        raise SystemExit("non-finite output")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(args.output, index=False, float_format="%.8f")
    output_hash = sha256(args.output)
    if args.expected_sha256 and output_hash != args.expected_sha256:
        raise SystemExit(
            f"output hash mismatch: {output_hash} != {args.expected_sha256}"
        )
    receipt = {
        "output": str(args.output),
        "rows": int(len(submission)),
        "features": int(features.shape[1]),
        "sha256": output_hash,
        "regressor_sha256": sha256(args.regressor),
        "official_checkpoint_sha256": sha256(args.official_checkpoint),
        "runtime_seconds": time.time() - started,
        "offline_ready": True,
        "platform_input_or_routing": False,
    }
    receipt_path = args.receipt or args.output.with_suffix(".receipt.json")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
