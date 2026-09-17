#!/usr/bin/env python3
"""Fix only V32's known onset T-5/T+30 off-by-one in its natural-key Queue file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


KEYS = ["window_id", "timestamp", "link_id"]


def fix(source: Path, output: Path, receipt_path: Path | None = None) -> dict[str, object]:
    frame = pd.read_csv(source, dtype={"window_id": str, "link_id": str})
    required = set(KEYS + ["queue_pred"])
    if not required.issubset(frame.columns):
        raise ValueError(f"source lacks columns {sorted(required - set(frame.columns))}")
    if frame[KEYS].isna().any().any() or frame.queue_pred.isna().any():
        raise ValueError("source contains blank key or prediction fields")
    if frame.duplicated(KEYS).any():
        raise ValueError("source contains duplicate Queue natural keys")
    if not set(pd.to_numeric(frame.queue_pred).unique()).issubset({0, 1}):
        raise ValueError("source queue_pred is not binary")
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)

    positives = frame.groupby("window_id").queue_pred.sum()
    onset_windows = positives[positives.eq(4)].index
    if len(onset_windows) != 80:
        raise ValueError(f"expected exactly 80 four-positive V32 onset windows, found {len(onset_windows)}")

    changed_rows = []
    for window_id in onset_windows:
        group = frame[frame.window_id.eq(window_id)]
        future_times = sorted(group.timestamp.unique())
        if len(future_times) != 6:
            raise ValueError(f"{window_id}: expected six forecast timestamps, found {len(future_times)}")
        positive = group[group.queue_pred.eq(1)]
        positive_times = sorted(positive.timestamp.unique())
        if positive.link_id.nunique() != 2 or positive.timestamp.nunique() != 2:
            raise ValueError(f"{window_id}: four positives are not two links over two times")
        if positive_times != future_times[-2:]:
            raise ValueError(f"{window_id}: positives are not the erroneous T+25/T+30 pair")
        drop_mask = frame.window_id.eq(window_id) & frame.timestamp.eq(future_times[-2]) & frame.queue_pred.eq(1)
        if int(drop_mask.sum()) != 2:
            raise ValueError(f"{window_id}: expected exactly two T+25 positives")
        changed_rows.extend(frame.index[drop_mask].tolist())

    before_positive = int(frame.queue_pred.sum())
    frame.loc[changed_rows, "queue_pred"] = 0
    after_positive = int(frame.queue_pred.sum())
    if len(changed_rows) != 160 or before_positive - after_positive != 160:
        raise AssertionError("the isolated fix must change exactly 160 positive rows")
    unchanged_rows = len(frame) - len(changed_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "status": "VALID",
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "total_queue_rows": len(frame),
        "onset_windows_fixed": len(onset_windows),
        "rows_changed_1_to_0": len(changed_rows),
        "rows_unchanged": unchanged_rows,
        "positive_rows_before": before_positive,
        "positive_rows_after": after_positive,
        "only_change": "For every four-positive V32 onset window, remove its two penultimate-horizon positives; keep the two final-horizon positives.",
    }
    if receipt_path:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    print(json.dumps(fix(args.source.resolve(), args.output.resolve(), args.receipt.resolve() if args.receipt else None), indent=2))


if __name__ == "__main__":
    main()
