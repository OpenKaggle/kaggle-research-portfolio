#!/usr/bin/env python3
"""Audit the unpacked public release without using any withheld labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


EXPECTED_DAYS = {"train": 273, "validation": 31, "private": 30}
TEMPLATE_KEYS = {
    "state": ["panel", "timestamp", "station_id", "link_id", "mask_regime"],
    "queue": ["window_id", "timestamp", "link_id"],
    "odme": ["panel", "departure_time", "path_id"],
}
EXPECTED_TASK_ROWS = {"state": 6_740_599, "queue": 174_000, "odme": 70_708}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parquet_group(path: Path) -> str:
    text = str(path)
    if "mainline_states_masked" in text:
        return "mainline_states_masked"
    if "/mainline_states/" in text:
        return "mainline_states"
    if "/ramp_states/" in text:
        return "ramp_states"
    if path.name == "window_history.parquet":
        return "task2_window_history"
    return "other"


def _metadata(root: Path) -> dict[str, object]:
    schema_signatures: dict[str, Counter[str]] = defaultdict(Counter)
    stats = defaultdict(lambda: {"files": 0, "rows": 0, "speed_nulls": 0, "flow_nulls": 0})
    for path in root.rglob("*.parquet"):
        parquet = pq.ParquetFile(path)
        group = _parquet_group(path)
        schema = parquet.schema_arrow.remove_metadata()
        schema_signatures[group][str(schema)] += 1
        stats[group]["files"] += 1
        stats[group]["rows"] += parquet.metadata.num_rows
        names = parquet.schema_arrow.names
        for row_group_index in range(parquet.metadata.num_row_groups):
            row_group = parquet.metadata.row_group(row_group_index)
            for column, target in (("speed_kmh", "speed_nulls"), ("flow_vph", "flow_nulls")):
                if column in names:
                    column_stats = row_group.column(names.index(column)).statistics
                    if column_stats is not None and column_stats.null_count is not None:
                        stats[group][target] += int(column_stats.null_count)
    return {
        "groups": dict(stats),
        "schema_variant_counts": {
            group: len(signatures) for group, signatures in schema_signatures.items()
        },
        "schema_file_counts": {
            group: sum(signatures.values()) for group, signatures in schema_signatures.items()
        },
    }


def _partition_counts(release: Path, panels: list[str]) -> tuple[dict[str, object], list[str]]:
    result = {}
    errors = []
    for panel in panels:
        panel_dir = release / "corridors" / panel
        counts = {}
        for split, expected in EXPECTED_DAYS.items():
            unmasked = list((panel_dir / split / "mainline_states").glob("**/*.parquet"))
            masked = list((panel_dir / split / "mainline_states_masked").glob("**/*.parquet"))
            ramps = list((panel_dir / split / "ramp_states").glob("**/*.parquet"))
            counts[split] = {
                "mainline_unmasked_files": len(unmasked),
                "mainline_masked_files": len(masked),
                "ramp_files": len(ramps),
            }
            expected_unmasked = expected if split == "train" else 0
            if len(unmasked) != expected_unmasked:
                errors.append(f"{panel}/{split}: unmasked files {len(unmasked)} != {expected_unmasked}")
            if len(masked) != expected:
                errors.append(f"{panel}/{split}: masked files {len(masked)} != {expected}")
            if len(ramps) != expected:
                errors.append(f"{panel}/{split}: ramp files {len(ramps)} != {expected}")
        result[panel] = counts
    return result, errors


def _template_audit(release: Path, panels: list[str]) -> tuple[dict[str, object], list[str]]:
    result = {}
    errors = []
    for task, keys in TEMPLATE_KEYS.items():
        root = release / f"task{ {'state': 1, 'queue': 2, 'odme': 4}[task] }"
        paths = sorted(
            path
            for path in root.glob("*/*/sample_submission_*.csv")
            if path.parent.name in {"validation", "private"}
        )
        total_rows = 0
        duplicates = 0
        missing_key_values = 0
        panels_seen = set()
        splits_seen = set()
        for path in paths:
            frame = pd.read_csv(path, usecols=keys, dtype=str)
            total_rows += len(frame)
            duplicates += int(frame.duplicated(keys).sum())
            missing_key_values += int(frame[keys].isna().any(axis=1).sum())
            panels_seen.add(path.parent.parent.name)
            splits_seen.add(path.parent.name)
        result[task] = {
            "files": len(paths),
            "rows": total_rows,
            "duplicate_natural_keys_within_file": duplicates,
            "rows_with_missing_natural_key": missing_key_values,
            "panels": sorted(panels_seen),
            "splits": sorted(splits_seen),
        }
        if total_rows != EXPECTED_TASK_ROWS[task]:
            errors.append(f"{task}: template rows {total_rows} != {EXPECTED_TASK_ROWS[task]}")
        if duplicates:
            errors.append(f"{task}: {duplicates} duplicate natural keys")
        if missing_key_values:
            errors.append(f"{task}: {missing_key_values} rows have missing natural keys")
        expected_panels = len(panels) if task != "queue" else len(panels) - 2
        if len(panels_seen) != expected_panels or splits_seen != {"validation", "private"}:
            errors.append(f"{task}: incomplete panel/split coverage")
    return result, errors


def _key_audit(path: Path) -> tuple[dict[str, object], list[str]]:
    rows = 0
    expected_id = 1
    task_counts = Counter()
    errors = []
    for chunk in pd.read_csv(path, chunksize=500_000, dtype=str):
        ids = pd.to_numeric(chunk.submission_id, errors="coerce")
        if ids.isna().any() or int(ids.iloc[0]) != expected_id:
            errors.append(f"submission key id sequence breaks near row {rows + 1}")
            break
        expected = pd.RangeIndex(expected_id, expected_id + len(chunk))
        if not (ids.to_numpy(dtype="int64") == expected.to_numpy(dtype="int64")).all():
            errors.append(f"submission key ids are non-contiguous near row {rows + 1}")
            break
        task_counts.update(chunk.task.value_counts().to_dict())
        rows += len(chunk)
        expected_id += len(chunk)
    if dict(task_counts) != EXPECTED_TASK_ROWS:
        errors.append(f"submission key task counts mismatch: {dict(task_counts)}")
    return {
        "rows": rows,
        "submission_id_min": 1 if rows else None,
        "submission_id_max": expected_id - 1 if rows else None,
        "task_rows": dict(task_counts),
        "sha256": _sha256(path),
    }, errors


def run(release: Path, output: Path) -> dict[str, object]:
    started = time.perf_counter()
    manifest = json.loads((release / "config" / "corridors.json").read_text(encoding="utf-8"))
    panels = [record["corridor_id"] for record in manifest["panels"]]
    errors = []
    partitions, partition_errors = _partition_counts(release, panels)
    errors.extend(partition_errors)
    templates, template_errors = _template_audit(release, panels)
    errors.extend(template_errors)
    key, key_errors = _key_audit(release / "submission_key.csv")
    errors.extend(key_errors)
    parquet = _metadata(release)
    expected_schema_variants = {
        "mainline_states": 1,
        "mainline_states_masked": 1,
        "ramp_states": 1,
        "task2_window_history": 1,
    }
    for group, expected in expected_schema_variants.items():
        actual = parquet["schema_variant_counts"].get(group, 0)
        if actual != expected:
            errors.append(f"{group}: schema variants {actual} != {expected}")
    report = {
        "status": "VALID" if not errors else "INVALID",
        "release": str(release),
        "files": sum(1 for path in release.rglob("*") if path.is_file()),
        "panels": panels,
        "partition_counts": partitions,
        "templates": templates,
        "submission_key": key,
        "parquet_metadata": parquet,
        "errors": errors,
        "runtime_seconds": time.perf_counter() - started,
        "truth_boundary": "No validation/private labels were accessed or reconstructed; this is a public-package structural audit.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.release_root.resolve(), args.output.resolve())
    print(json.dumps({
        "status": report["status"],
        "files": report["files"],
        "panels": len(report["panels"]),
        "templates": report["templates"],
        "submission_key": report["submission_key"],
        "parquet_schema_variants": report["parquet_metadata"]["schema_variant_counts"],
        "errors": report["errors"],
        "runtime_seconds": report["runtime_seconds"],
    }, indent=2))


if __name__ == "__main__":
    main()
