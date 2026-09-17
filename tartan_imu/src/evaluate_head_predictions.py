#!/usr/bin/env python3
"""Evaluate cached unified-head predictions with the exact challenge metric."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from score_validation import build_solution, load_official_metric, score_components


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--split", default="val")
    parser.add_argument("--metric", type=Path, required=True)
    args = parser.parse_args()

    with np.load(args.cache, allow_pickle=True) as loaded:
        window_id = loaded["window_id"]
        predictions = loaded["head_prediction"]
        heads = loaded["head_names"].astype(str)
        platform = loaded["platform"].astype(str)

    solution = build_solution(args.data_root, args.split)
    metric = load_official_metric(args.metric)
    results: dict[str, object] = {}
    for index, name in enumerate(heads):
        frame = pd.DataFrame(
            {
                "window_id": window_id,
                "vx": predictions[:, index, 0],
                "vy": predictions[:, index, 1],
                "vz": predictions[:, index, 2],
            }
        )
        results[f"fixed_{name}"] = score_components(solution, frame, metric)

    selected = np.empty((len(window_id), 3), dtype=np.float32)
    for index, name in enumerate(heads):
        selected[platform == name] = predictions[platform == name, index]
    oracle_frame = pd.DataFrame(
        {
            "window_id": window_id,
            "vx": selected[:, 0],
            "vy": selected[:, 1],
            "vz": selected[:, 2],
        }
    )
    results["released_platform_routing"] = score_components(
        solution, oracle_frame, metric
    )
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
