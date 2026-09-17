#!/usr/bin/env python3
"""Strict pre-submission validator for Biohub node/edge CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


COLUMNS = [
    "id",
    "dataset",
    "row_type",
    "node_id",
    "t",
    "z",
    "y",
    "x",
    "source_id",
    "target_id",
]
NODE_FIELDS = ("node_id", "t", "z", "y", "x")
EDGE_SENTINELS = ("node_id", "t", "z", "y", "x")


def integer(row: dict[str, str], field: str, row_number: int, errors: list[str]) -> int | None:
    try:
        value = int(row[field])
    except (KeyError, TypeError, ValueError):
        errors.append(f"row {row_number}: {field} is not an integer")
        return None
    return value


def expected_from_test_dir(test_dir: Path) -> tuple[set[str], dict[str, tuple[int, int, int, int]]]:
    datasets = set()
    shapes = {}
    for path in sorted(test_dir.glob("*.zarr")):
        dataset = path.name.removesuffix(".zarr")
        datasets.add(dataset)
        metadata = path / "0" / "zarr.json"
        if metadata.is_file():
            info = json.loads(metadata.read_text(encoding="utf-8"))
            shape = tuple(int(value) for value in info["shape"])
            if len(shape) == 4:
                shapes[dataset] = shape
    return datasets, shapes


def validate(path: Path, expected: set[str], shapes: dict[str, tuple[int, int, int, int]]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    nodes: dict[str, dict[int, tuple[int, int, int, int]]] = defaultdict(dict)
    positions: dict[str, set[tuple[int, int, int, int]]] = defaultdict(set)
    edges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    seen_edges: dict[str, set[tuple[int, int]]] = defaultdict(set)
    row_types: Counter[str] = Counter()
    dataset_rows: Counter[str] = Counter()

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            errors.append(f"header mismatch: expected {COLUMNS}, got {reader.fieldnames}")
        for zero_index, row in enumerate(reader):
            row_number = zero_index + 2
            row_id = integer(row, "id", row_number, errors)
            if row_id is not None and row_id != zero_index:
                errors.append(f"row {row_number}: id {row_id} is not contiguous expected {zero_index}")
            dataset = row.get("dataset", "")
            if not dataset:
                errors.append(f"row {row_number}: empty dataset")
                continue
            dataset_rows[dataset] += 1
            row_type = row.get("row_type", "")
            row_types[row_type] += 1

            if row_type == "node":
                values = {field: integer(row, field, row_number, errors) for field in NODE_FIELDS}
                source = integer(row, "source_id", row_number, errors)
                target = integer(row, "target_id", row_number, errors)
                if source != -1 or target != -1:
                    errors.append(f"row {row_number}: node edge fields must be -1")
                if any(value is None for value in values.values()):
                    continue
                node_id = values["node_id"]
                coords = (values["t"], values["z"], values["y"], values["x"])
                if node_id < 0 or any(value < 0 for value in coords):
                    errors.append(f"row {row_number}: negative biological node value")
                if node_id in nodes[dataset]:
                    errors.append(f"row {row_number}: duplicate node_id {node_id} in {dataset}")
                if coords in positions[dataset]:
                    warnings.append(f"row {row_number}: duplicate node coordinate {coords} in {dataset}")
                nodes[dataset][node_id] = coords
                positions[dataset].add(coords)
                if dataset in shapes:
                    if any(value >= limit for value, limit in zip(coords, shapes[dataset])):
                        errors.append(
                            f"row {row_number}: coordinate {coords} outside shape {shapes[dataset]}"
                        )
            elif row_type == "edge":
                sentinels = [integer(row, field, row_number, errors) for field in EDGE_SENTINELS]
                if any(value != -1 for value in sentinels):
                    errors.append(f"row {row_number}: edge node fields must be -1")
                source = integer(row, "source_id", row_number, errors)
                target = integer(row, "target_id", row_number, errors)
                if source is None or target is None:
                    continue
                edge = (source, target)
                if source < 0 or target < 0 or source == target:
                    errors.append(f"row {row_number}: invalid edge {edge}")
                if edge in seen_edges[dataset]:
                    errors.append(f"row {row_number}: duplicate edge {edge} in {dataset}")
                seen_edges[dataset].add(edge)
                edges[dataset].append(edge)
            else:
                errors.append(f"row {row_number}: unknown row_type {row_type!r}")

    actual = set(dataset_rows)
    if expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append(f"missing datasets: {missing}")
        if extra:
            errors.append(f"unexpected datasets: {extra}")
    if not nodes:
        errors.append("no node rows")
    if row_types.get("edge", 0) == 0:
        warnings.append("no edge rows")

    topology = {}
    for dataset in sorted(actual):
        incoming: Counter[int] = Counter()
        outgoing: Counter[int] = Counter()
        for source, target in edges[dataset]:
            if source not in nodes[dataset] or target not in nodes[dataset]:
                errors.append(f"{dataset}: dangling edge {(source, target)}")
                continue
            source_t = nodes[dataset][source][0]
            target_t = nodes[dataset][target][0]
            if target_t != source_t + 1:
                errors.append(
                    f"{dataset}: edge {(source, target)} is not next-frame ({source_t}->{target_t})"
                )
            incoming[target] += 1
            outgoing[source] += 1
        max_in = max(incoming.values(), default=0)
        max_out = max(outgoing.values(), default=0)
        if max_in > 1:
            errors.append(f"{dataset}: max indegree {max_in} exceeds 1")
        if max_out > 2:
            errors.append(f"{dataset}: max outdegree {max_out} exceeds 2")
        topology[dataset] = {
            "rows": dataset_rows[dataset],
            "nodes": len(nodes[dataset]),
            "edges": len(edges[dataset]),
            "max_indegree": max_in,
            "max_outdegree": max_out,
            "division_parents": sum(value == 2 for value in outgoing.values()),
        }

    return {
        "path": str(path),
        "valid": not errors,
        "rows": sum(dataset_rows.values()),
        "datasets": sorted(actual),
        "row_types": dict(sorted(row_types.items())),
        "topology": topology,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--test-dir", type=Path)
    parser.add_argument("--expected", help="Comma-separated dataset IDs")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    expected: set[str] = set()
    shapes: dict[str, tuple[int, int, int, int]] = {}
    if args.test_dir:
        expected, shapes = expected_from_test_dir(args.test_dir)
    if args.expected:
        expected.update(item.strip() for item in args.expected.split(",") if item.strip())

    report = validate(args.submission, expected, shapes)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()

