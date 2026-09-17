#!/usr/bin/env python3
"""Fail-closed validation and immutable hash receipt for a candidate CSV."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("tartan_imu/data/extracted/sample_submission.csv"),
    )
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args()

    sample = pd.read_csv(args.sample)
    candidate = pd.read_csv(args.submission)
    expected_columns = ["window_id", "vx", "vy", "vz"]
    if candidate.columns.tolist() != expected_columns:
        raise SystemExit(f"wrong columns/order: {candidate.columns.tolist()}")
    if len(candidate) != len(sample):
        raise SystemExit(f"wrong row count: {len(candidate)} != {len(sample)}")
    if not candidate["window_id"].equals(sample["window_id"]):
        raise SystemExit("window_id values/order do not exactly match sample_submission.csv")
    if candidate["window_id"].duplicated().any():
        raise SystemExit("duplicate window_id")
    values = candidate[["vx", "vy", "vz"]].to_numpy(float)
    if not np.isfinite(values).all():
        raise SystemExit("non-finite prediction")
    if np.max(np.abs(values)) > 100:
        raise SystemExit("prediction magnitude exceeds 100 m/s safety bound")

    raw = args.submission.read_bytes()
    receipt = {
        "submission": str(args.submission),
        "rows": int(len(candidate)),
        "columns": expected_columns,
        "id_order_exact": True,
        "finite": True,
        "max_abs_component": float(np.max(np.abs(values))),
        "mean_velocity": candidate[["vx", "vy", "vz"]].mean().to_dict(),
        "std_velocity": candidate[["vx", "vy", "vz"]].std().to_dict(),
        "md5": hashlib.md5(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    print(rendered)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered + "\n")


if __name__ == "__main__":
    main()
