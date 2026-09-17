#!/usr/bin/env python3
"""Cache shared-trunk embeddings and all unified-head predictions.

This uses the released TartanIMU unified checkpoint exactly as documented.  It
does not recover or infer hidden test platform labels.  For train/val the
released platform column is stored only for evaluation and later supervised
training.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

from tartan_imu.model.registry import build_backbone


PLATFORMS = ("car", "dog", "drone", "human")


def update_recursive(base: dict, extra: dict) -> None:
    for key, value in extra.items():
        if isinstance(value, dict):
            base.setdefault(key, {})
            update_recursive(base[key], value)
        else:
            base[key] = value


def load_model(config_path: Path, model_yaml: Path, checkpoint_path: Path):
    cfg = yaml.safe_load(config_path.read_text())
    update_recursive(cfg, yaml.safe_load(model_yaml.read_text()))
    cfg["train"]["use_multi_gpu"] = False
    model = build_backbone(cfg["model"]["model_name"], cfg)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    result = model.load_state_dict(
        checkpoint.get("model_state_dict", checkpoint), strict=False
    )
    if result.missing_keys or result.unexpected_keys:
        raise RuntimeError(
            f"checkpoint mismatch: missing={result.missing_keys}, "
            f"unexpected={result.unexpected_keys}"
        )
    model.eval()
    step = int(cfg["data"]["imu_freq"] / cfg["data"]["sample_freq"])
    window = int(cfg["model_param"]["window_time"] * cfg["data"]["imu_freq"])
    sequence = int(cfg["train"]["seq_len"])
    return model, step, window, sequence


def make_windows(imu: np.ndarray, win_idx: np.ndarray, window: int, step: int):
    result = np.empty((len(win_idx), 6, window // step), dtype=np.float32)
    # Released arrays are accel|gyro; the model expects gyro|accel.
    feature = np.concatenate([imu[:, 3:6], imu[:, 0:3]], axis=1)
    for row, index in enumerate(win_idx):
        segment = feature[index * window : (index + 1) * window]
        if len(segment) != window:
            raise ValueError(f"incomplete window {index}: {len(segment)} != {window}")
        result[row] = segment[::step].T
    return result


@torch.inference_mode()
def infer_trajectory(model, windows: np.ndarray, sequence: int, batch_seqs: int):
    count = len(windows)
    padding = (-count) % sequence
    if padding:
        windows = np.concatenate([windows, np.repeat(windows[-1:], padding, axis=0)])
    groups = windows.reshape(-1, sequence, windows.shape[1], windows.shape[2])
    embeddings: list[np.ndarray] = []
    predictions: list[np.ndarray] = []
    for start in range(0, len(groups), batch_seqs):
        chunk = torch.from_numpy(groups[start : start + batch_seqs])
        features = model.model(chunk)
        batch = len(chunk)
        heads = [
            model.heads[name](features, batch, sequence).reshape(-1, 3)
            for name in PLATFORMS
        ]
        embeddings.append(features.cpu().numpy().reshape(-1, features.shape[-1]))
        predictions.append(torch.stack(heads, dim=1).cpu().numpy())
    return (
        np.concatenate(embeddings, axis=0)[:count].astype(np.float32),
        np.concatenate(predictions, axis=0)[:count].astype(np.float32),
    )


def trajectory_path(root: Path, split: str, platform: str | None, traj_id: str):
    if split == "test":
        return root / "test" / f"{traj_id}.npz"
    if platform is None:
        raise ValueError("labelled split is missing platform")
    return root / split / platform / f"{traj_id}.npz"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "val", "test"), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model-yaml", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-seqs", type=int, default=32)
    args = parser.parse_args()

    torch.manual_seed(20260909)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    index = pd.read_csv(args.data_root / "index" / f"{args.split}_windows.csv")
    model, step, window, sequence = load_model(
        args.config, args.model_yaml, args.checkpoint
    )
    print(
        json.dumps(
            {
                "split": args.split,
                "rows": len(index),
                "trajectories": int(index["traj_id"].nunique()),
                "window": window,
                "step": step,
                "sequence": sequence,
                "parameters": int(sum(p.numel() for p in model.parameters())),
            },
            sort_keys=True,
        ),
        flush=True,
    )

    embedding = np.empty((len(index), 128), dtype=np.float32)
    head_prediction = np.empty((len(index), len(PLATFORMS), 3), dtype=np.float32)
    completed = 0
    groups = list(index.groupby("traj_id", sort=False))
    for number, (traj_id, rows) in enumerate(groups, start=1):
        ordered = rows.sort_values("win_idx")
        platform = None if args.split == "test" else str(ordered["platform"].iloc[0])
        path = trajectory_path(args.data_root, args.split, platform, str(traj_id))
        with np.load(path) as loaded:
            imu = np.asarray(loaded["imu"], dtype=np.float32)
        windows = make_windows(
            imu, ordered["win_idx"].to_numpy(np.int64), window, step
        )
        emb, pred = infer_trajectory(model, windows, sequence, args.batch_seqs)
        locations = ordered.index.to_numpy(np.int64)
        embedding[locations] = emb
        head_prediction[locations] = pred
        completed += len(ordered)
        if number % 10 == 0 or number == len(groups):
            print(
                f"{args.split}: {number}/{len(groups)} trajectories, "
                f"{completed}/{len(index)} rows",
                flush=True,
            )

    payload: dict[str, np.ndarray] = {
        "window_id": index["window_id"].to_numpy(np.int64),
        "traj_id": index["traj_id"].astype(str).to_numpy(),
        "win_idx": index["win_idx"].to_numpy(np.int64),
        "embedding": embedding,
        "head_prediction": head_prediction,
        "head_names": np.asarray(PLATFORMS),
    }
    if "platform" in index:
        payload["platform"] = index["platform"].astype(str).to_numpy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **payload)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
