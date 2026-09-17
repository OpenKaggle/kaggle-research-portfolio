#!/usr/bin/env python3
"""Audit per-family exact coverage, exclusive solves, and pairwise overlap."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path


REQUIRED_COLUMNS = {"task_id", "output_index", "solver_family", "exact_correct"}
FAMILY_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")


def bit(value: str, context: str) -> int:
    if value not in {"0", "1"}:
        raise ValueError(f"{context}: expected 0 or 1, got {value!r}")
    return int(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("family_csv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    by_output: dict[tuple[str, int], dict[str, int]] = defaultdict(dict)
    with args.family_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise ValueError(
                f"missing columns: {sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))}"
            )
        for line_number, row in enumerate(reader, 2):
            task_id = row["task_id"]
            if len(task_id) != 8 or any(value not in "0123456789abcdef" for value in task_id):
                raise ValueError(f"line {line_number}: task_id must be eight lowercase hex characters")
            try:
                output_index = int(row["output_index"])
            except ValueError as error:
                raise ValueError(
                    f"line {line_number}: output_index must be a nonnegative integer"
                ) from error
            if str(output_index) != row["output_index"] or output_index < 0:
                raise ValueError(f"line {line_number}: output_index must be a nonnegative integer")
            family = row["solver_family"]
            if not FAMILY_PATTERN.fullmatch(family):
                raise ValueError(f"line {line_number}: solver_family must be lowercase snake case")
            key = (task_id, output_index)
            if family in by_output[key]:
                raise ValueError(f"line {line_number}: duplicate family/output {family!r}, {key}")
            by_output[key][family] = bit(row["exact_correct"], f"line {line_number}")

    if not by_output:
        raise ValueError("family result table is empty")
    family_sets = {tuple(sorted(values)) for values in by_output.values()}
    if len(family_sets) != 1:
        raise ValueError("every task output must contain the same solver-family rows")
    families = list(next(iter(family_sets)))
    if len(families) < 2:
        raise ValueError("family coverage requires at least two solver families")

    task_outputs = len(by_output)
    family_rows = []
    for family in families:
        exact = sum(values[family] for values in by_output.values())
        exclusive = sum(
            values[family] == 1 and sum(values.values()) == 1
            for values in by_output.values()
        )
        family_rows.append(
            {
                "family": family,
                "exact_outputs": exact,
                "exact_rate": exact / task_outputs,
                "exclusive_exact_outputs": exclusive,
                "exclusive_rate": exclusive / task_outputs,
            }
        )

    overlaps = []
    for family_a, family_b in combinations(families, 2):
        both = sum(
            values[family_a] == 1 and values[family_b] == 1
            for values in by_output.values()
        )
        only_a = sum(
            values[family_a] == 1 and values[family_b] == 0
            for values in by_output.values()
        )
        only_b = sum(
            values[family_a] == 0 and values[family_b] == 1
            for values in by_output.values()
        )
        neither = task_outputs - both - only_a - only_b
        union = both + only_a + only_b
        overlaps.append(
            {
                "family_a": family_a,
                "family_b": family_b,
                "both_exact": both,
                "only_a_exact": only_a,
                "only_b_exact": only_b,
                "neither_exact": neither,
                "jaccard_exact": both / union if union else None,
            }
        )

    oracle_union = sum(any(values.values()) for values in by_output.values())
    report = {
        "tasks": len({task_id for task_id, _ in by_output}),
        "task_outputs": task_outputs,
        "families": family_rows,
        "pairwise_overlap": overlaps,
        "oracle_union_outputs": oracle_union,
        "oracle_union_rate": oracle_union / task_outputs,
        "source_sha256": hashlib.sha256(args.family_csv.read_bytes()).hexdigest(),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
