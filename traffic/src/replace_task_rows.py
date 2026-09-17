#!/usr/bin/env python3
"""Replace exactly one task in a merged submission while preserving all other rows."""

from __future__ import annotations

import argparse
import csv
import io
import math
from datetime import datetime, timezone
from pathlib import Path


MERGED_HEADER = ["submission_id", "task", "speed_kmh", "flow_vph", "queue_pred", "path_flow"]
KEYS = {
    "state": ["panel", "timestamp", "station_id", "link_id", "mask_regime"],
    "queue": ["window_id", "timestamp", "link_id"],
    "odme": ["panel", "departure_time", "path_id"],
}
VALUES = {"state": ["speed_kmh", "flow_vph"], "queue": ["queue_pred"], "odme": ["path_flow"]}


def _timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp lacks a timezone: {value!r}")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _key(row: dict[str, str], task: str) -> tuple[str, ...]:
    return tuple(_timestamp(row[column]) if column == "timestamp" else str(row[column]) for column in KEYS[task])


def load_replacement(path: Path, task: str) -> dict[tuple[str, ...], tuple[str, ...]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = KEYS[task] + VALUES[task]
        missing = [column for column in required if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"replacement is missing columns: {missing}")
        result: dict[tuple[str, ...], tuple[str, ...]] = {}
        for row_number, row in enumerate(reader, start=2):
            natural_key = _key(row, task)
            if natural_key in result:
                raise ValueError(f"replacement row {row_number}: duplicate natural key {natural_key}")
            values = tuple(str(row[column]) for column in VALUES[task])
            numeric = [float(value) for value in values]
            if not all(math.isfinite(value) for value in numeric):
                raise ValueError(f"replacement row {row_number}: non-finite prediction")
            if task == "state" and any(value < 0 for value in numeric):
                raise ValueError(f"replacement row {row_number}: state values must be non-negative")
            if task == "queue" and numeric[0] not in (0, 1):
                raise ValueError(f"replacement row {row_number}: queue_pred must be binary")
            if task == "odme" and numeric[0] < 0:
                raise ValueError(f"replacement row {row_number}: path_flow must be non-negative")
            result[natural_key] = values
    return result


def _csv_line(row: list[str]) -> str:
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerow(row)
    return buffer.getvalue()


def replace_task(anchor: Path, key_path: Path, replacement_path: Path, task: str, output: Path) -> dict[str, int]:
    replacement = load_replacement(replacement_path, task)
    used: set[tuple[str, ...]] = set()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    try:
        with (
            anchor.open("r", encoding="utf-8", newline="") as anchor_handle,
            key_path.open("r", encoding="utf-8", newline="") as key_handle,
            temporary.open("w", encoding="utf-8", newline="") as sink,
        ):
            anchor_header_line = anchor_handle.readline()
            if next(csv.reader([anchor_header_line])) != MERGED_HEADER:
                raise ValueError("anchor merged header mismatch")
            sink.write(anchor_header_line)
            key_reader = csv.DictReader(key_handle)
            if not {"submission_id", "task", *KEYS[task]}.issubset(key_reader.fieldnames or []):
                raise ValueError("submission key lacks required task columns")

            total_rows = target_rows = 0
            for row_number, anchor_line in enumerate(anchor_handle, start=2):
                try:
                    key_row = next(key_reader)
                except StopIteration as exc:
                    raise ValueError("anchor has more rows than submission key") from exc
                anchor_row = next(csv.reader([anchor_line]))
                if len(anchor_row) != len(MERGED_HEADER):
                    raise ValueError(f"anchor row {row_number}: malformed merged row")
                if anchor_row[0] != key_row["submission_id"] or anchor_row[1] != key_row["task"]:
                    raise ValueError(f"anchor row {row_number}: submission key alignment mismatch")

                if anchor_row[1] == task:
                    natural_key = _key(key_row, task)
                    if natural_key not in replacement:
                        raise ValueError(f"anchor row {row_number}: replacement lacks key {natural_key}")
                    row_changed = False
                    for column, value in zip(VALUES[task], replacement[natural_key]):
                        position = MERGED_HEADER.index(column)
                        if float(anchor_row[position]) != float(value):
                            anchor_row[position] = value
                            row_changed = True
                    # Preserve byte identity for numerically unchanged rows.
                    # This turns the merged output into strong evidence that a
                    # single-task candidate changed only its declared cells.
                    sink.write(_csv_line(anchor_row) if row_changed else anchor_line)
                    used.add(natural_key)
                    target_rows += 1
                else:
                    sink.write(anchor_line)
                total_rows += 1

            if next(key_reader, None) is not None:
                raise ValueError("anchor has fewer rows than submission key")
            unused = len(replacement) - len(used)
            if unused:
                raise ValueError(f"replacement has {unused} rows not present in the submission key")
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return {"total_rows": total_rows, "target_rows": target_rows, "replacement_rows": len(replacement)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--replacement", type=Path, required=True)
    parser.add_argument("--task", choices=sorted(KEYS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replace_task(
        args.anchor.resolve(), args.key.resolve(), args.replacement.resolve(), args.task, args.output.resolve()
    )
    print(
        f"Wrote {result['total_rows']:,} rows; replaced {result['target_rows']:,} {args.task} rows "
        f"from {result['replacement_rows']:,} natural-key predictions."
    )


if __name__ == "__main__":
    main()
