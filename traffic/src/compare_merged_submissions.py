#!/usr/bin/env python3
"""Prove that a merged candidate differs from its anchor only as intended."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


HEADER = ["submission_id", "task", "speed_kmh", "flow_vph", "queue_pred", "path_flow"]


def compare(anchor: Path, candidate: Path) -> dict[str, object]:
    changed_by_task: Counter[str] = Counter()
    changed_by_column: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    numeric_delta = defaultdict(lambda: {"count": 0, "sum": 0.0, "sum_abs": 0.0, "max_abs": 0.0})
    rows = 0
    with (
        anchor.open("r", encoding="utf-8", newline="") as left_handle,
        candidate.open("r", encoding="utf-8", newline="") as right_handle,
    ):
        left = csv.reader(left_handle)
        right = csv.reader(right_handle)
        if next(left, None) != HEADER or next(right, None) != HEADER:
            raise ValueError("merged header mismatch")
        for row_number, pair in enumerate(zip(left, right, strict=True), start=2):
            anchor_row, candidate_row = pair
            if len(anchor_row) != len(HEADER) or len(candidate_row) != len(HEADER):
                raise ValueError(f"row {row_number}: malformed row")
            if anchor_row[:2] != candidate_row[:2]:
                raise ValueError(f"row {row_number}: submission_id/task changed")
            changed_columns = [
                column for column, old, new in zip(HEADER[2:], anchor_row[2:], candidate_row[2:]) if old != new
            ]
            if changed_columns:
                changed_by_task[anchor_row[1]] += 1
                for column in changed_columns:
                    changed_by_column[column] += 1
                    position = HEADER.index(column)
                    old_value = anchor_row[position]
                    new_value = candidate_row[position]
                    transitions[f"{column}:{old_value}->{new_value}"] += 1
                    try:
                        delta = float(new_value) - float(old_value)
                    except ValueError:
                        pass
                    else:
                        stats = numeric_delta[column]
                        stats["count"] += 1
                        stats["sum"] += delta
                        stats["sum_abs"] += abs(delta)
                        stats["max_abs"] = max(stats["max_abs"], abs(delta))
            rows += 1
    report = {
        "status": "VALID",
        "rows_compared": rows,
        "changed_rows": sum(changed_by_task.values()),
        "changed_rows_by_task": dict(changed_by_task),
        "changed_cells_by_column": dict(changed_by_column),
    }
    if len(transitions) <= 100:
        report["value_transitions"] = dict(transitions)
    else:
        report["value_transition_summary"] = {
            "distinct_transitions": len(transitions),
            "most_common_examples": dict(transitions.most_common(20)),
            "numeric_delta_by_column": {
                column: {
                    **stats,
                    "mean": stats["sum"] / max(stats["count"], 1),
                    "mean_abs": stats["sum_abs"] / max(stats["count"], 1),
                }
                for column, stats in numeric_delta.items()
            },
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expect-task", choices=["state", "queue", "odme"])
    parser.add_argument("--expect-column")
    parser.add_argument("--expect-changed-rows", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = compare(args.anchor.resolve(), args.candidate.resolve())
    if args.expect_changed_rows is not None and report["changed_rows"] != args.expect_changed_rows:
        raise SystemExit(f"expected {args.expect_changed_rows} changed rows, got {report['changed_rows']}")
    if args.expect_task and set(report["changed_rows_by_task"]) != {args.expect_task}:
        raise SystemExit(f"unexpected changed tasks: {report['changed_rows_by_task']}")
    if args.expect_column and set(report["changed_cells_by_column"]) != {args.expect_column}:
        raise SystemExit(f"unexpected changed columns: {report['changed_cells_by_column']}")
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
