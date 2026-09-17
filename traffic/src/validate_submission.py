#!/usr/bin/env python3
"""Stream-validate a merged TrafficFlowBench submission and emit a JSON report."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import TextIO


HEADER = ["submission_id", "task", "speed_kmh", "flow_vph", "queue_pred", "path_flow"]
TASKS = {"state", "queue", "odme"}


def _number(value: str, *, row_number: int, column: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {column} is not numeric: {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"row {row_number}: {column} is not finite: {value!r}")
    return result


def _check_task_domain(row: list[str], row_number: int) -> None:
    task = row[1]
    if task not in TASKS:
        raise ValueError(f"row {row_number}: unknown task {task!r}")
    speed = _number(row[2], row_number=row_number, column="speed_kmh")
    flow = _number(row[3], row_number=row_number, column="flow_vph")
    queue = _number(row[4], row_number=row_number, column="queue_pred")
    path_flow = _number(row[5], row_number=row_number, column="path_flow")
    if task == "state":
        if speed < 0 or flow < 0:
            raise ValueError(f"row {row_number}: state predictions must be non-negative")
        if queue != 0 or path_flow != 0:
            raise ValueError(f"row {row_number}: inactive state fields must be zero")
    elif task == "queue":
        if speed != 0 or flow != 0 or path_flow != 0:
            raise ValueError(f"row {row_number}: inactive queue fields must be zero")
        if queue not in (0, 1):
            raise ValueError(f"row {row_number}: queue_pred must be binary")
    else:
        if speed != 0 or flow != 0 or queue != 0:
            raise ValueError(f"row {row_number}: inactive ODME fields must be zero")
        if path_flow < 0:
            raise ValueError(f"row {row_number}: path_flow must be non-negative")


def _open_key(path: Path | None) -> tuple[TextIO | None, csv.DictReader | None]:
    if path is None:
        return None, None
    handle = path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(handle)
    required = {"submission_id", "task"}
    if not required.issubset(reader.fieldnames or []):
        handle.close()
        raise ValueError(f"submission key lacks columns {sorted(required)}")
    return handle, reader


def validate(submission: Path, key: Path | None = None) -> dict[str, object]:
    digest = hashlib.sha256()
    with submission.open("rb") as raw:
        for block in iter(lambda: raw.read(8 * 1024 * 1024), b""):
            digest.update(block)

    counts: Counter[str] = Counter()
    key_handle, key_reader = _open_key(key)
    try:
        with submission.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError("submission is empty") from exc
            if header != HEADER:
                raise ValueError(f"header mismatch: expected {HEADER}, got {header}")

            last_id = 0
            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(HEADER):
                    raise ValueError(f"row {row_number}: expected 6 fields, got {len(row)}")
                if any(value == "" for value in row):
                    raise ValueError(f"row {row_number}: blank field")
                try:
                    submission_id = int(row[0])
                except ValueError as exc:
                    raise ValueError(f"row {row_number}: invalid submission_id {row[0]!r}") from exc
                if submission_id != last_id + 1:
                    raise ValueError(
                        f"row {row_number}: expected submission_id {last_id + 1}, got {submission_id}"
                    )
                last_id = submission_id
                _check_task_domain(row, row_number)
                counts[row[1]] += 1

                if key_reader is not None:
                    try:
                        key_row = next(key_reader)
                    except StopIteration as exc:
                        raise ValueError("submission has more rows than submission_key.csv") from exc
                    if str(key_row["submission_id"]) != row[0] or str(key_row["task"]) != row[1]:
                        raise ValueError(
                            f"row {row_number}: submission key mismatch: "
                            f"submission=({row[0]}, {row[1]}), key=({key_row['submission_id']}, {key_row['task']})"
                        )

            if key_reader is not None and next(key_reader, None) is not None:
                raise ValueError("submission has fewer rows than submission_key.csv")
    finally:
        if key_handle is not None:
            key_handle.close()

    return {
        "status": "VALID",
        "submission": str(submission.resolve()),
        "bytes": submission.stat().st_size,
        "sha256": digest.hexdigest(),
        "rows": sum(counts.values()),
        "submission_id_min": 1 if counts else None,
        "submission_id_max": sum(counts.values()) if counts else None,
        "task_rows": {task: counts[task] for task in ("state", "queue", "odme")},
        "key_checked": key is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--expected-manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = validate(args.submission.resolve(), args.key.resolve() if args.key else None)
    if args.expected_manifest:
        expected = json.loads(args.expected_manifest.read_text(encoding="utf-8"))
        comparisons = {
            "sha256": expected.get("submission_sha256") == report["sha256"],
            "bytes": expected.get("submission_bytes") == report["bytes"],
            "rows": expected.get("row_counts", {}).get("all") == report["rows"],
            "task_rows": all(
                expected.get("row_counts", {}).get(task) == report["task_rows"][task]
                for task in ("state", "queue", "odme")
            ),
        }
        report["expected_manifest_checks"] = comparisons
        if not all(comparisons.values()):
            raise SystemExit(f"manifest mismatch: {json.dumps(comparisons, sort_keys=True)}")

    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
