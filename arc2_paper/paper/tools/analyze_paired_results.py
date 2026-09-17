#!/usr/bin/env python3
"""Compute paired ARC pass@2 effects with whole-task bootstrap intervals."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path


REQUIRED_COLUMNS = {
    "task_id",
    "output_index",
    "anchor_attempt_1_correct",
    "anchor_attempt_2_correct",
    "method_attempt_1_correct",
    "method_attempt_2_correct",
    "oracle_pool_correct",
}


def bit(value: str, context: str) -> int:
    if value not in {"0", "1"}:
        raise ValueError(f"{context}: expected 0 or 1, got {value!r}")
    return int(value)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def binomial_two_sided(benefit: int, harm: int) -> float | None:
    total = benefit + harm
    if total == 0:
        return None
    low = min(benefit, harm)
    tail = sum(math.comb(total, value) for value in range(low + 1)) / (2**total)
    return min(1.0, 2 * tail)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paired_csv", type=Path)
    parser.add_argument("--bootstrap-replicates", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.bootstrap_replicates < 1000:
        raise SystemExit("use at least 1000 bootstrap replicates")

    with args.paired_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or not REQUIRED_COLUMNS <= set(reader.fieldnames):
            raise ValueError(f"missing columns: {sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))}")
        rows = []
        seen = set()
        for line_number, row in enumerate(reader, 2):
            task_id = row["task_id"]
            if len(task_id) != 8 or any(value not in "0123456789abcdef" for value in task_id):
                raise ValueError(f"line {line_number}: task_id must be eight lowercase hex characters")
            try:
                output_index = int(row["output_index"])
            except ValueError as error:
                raise ValueError(f"line {line_number}: output_index must be a nonnegative integer") from error
            if str(output_index) != row["output_index"] or output_index < 0:
                raise ValueError(f"line {line_number}: output_index must be a nonnegative integer")
            key = (task_id, output_index)
            if key in seen:
                raise ValueError(f"line {line_number}: duplicate task/output {key}")
            seen.add(key)
            anchor_1 = bit(row["anchor_attempt_1_correct"], f"line {line_number}")
            anchor_2 = bit(row["anchor_attempt_2_correct"], f"line {line_number}")
            method_1 = bit(row["method_attempt_1_correct"], f"line {line_number}")
            method_2 = bit(row["method_attempt_2_correct"], f"line {line_number}")
            oracle = bit(row["oracle_pool_correct"], f"line {line_number}")
            anchor_pass2 = int(anchor_1 or anchor_2)
            method_pass2 = int(method_1 or method_2)
            if oracle < anchor_pass2 or oracle < method_pass2:
                raise ValueError(
                    f"line {line_number}: oracle pool must contain every scored anchor/method success"
                )
            rows.append(
                {
                    "task_id": row["task_id"],
                    "anchor_1": anchor_1,
                    "anchor_pass2": anchor_pass2,
                    "method_1": method_1,
                    "method_pass2": method_pass2,
                    "oracle_pool": oracle,
                }
            )
    if not rows:
        raise ValueError("paired result table is empty")

    by_task = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    task_ids = sorted(by_task)

    def rates(sampled_tasks: list[str]) -> tuple[float, float]:
        sampled = [row for task_id in sampled_tasks for row in by_task[task_id]]
        anchor = sum(row["anchor_pass2"] for row in sampled) / len(sampled)
        method = sum(row["method_pass2"] for row in sampled) / len(sampled)
        return anchor, method

    anchor_rate, method_rate = rates(task_ids)
    oracle_rate = sum(row["oracle_pool"] for row in rows) / len(rows)
    oracle_gap = oracle_rate - anchor_rate
    oracle_gap_recovery = (
        (method_rate - anchor_rate) / oracle_gap if oracle_gap > 0 else None
    )
    benefit = sum(row["anchor_pass2"] == 0 and row["method_pass2"] == 1 for row in rows)
    harm = sum(row["anchor_pass2"] == 1 and row["method_pass2"] == 0 for row in rows)
    neutral = len(rows) - benefit - harm
    rng = random.Random(args.seed)
    deltas = []
    for _ in range(args.bootstrap_replicates):
        sample = [rng.choice(task_ids) for _ in task_ids]
        anchor, method = rates(sample)
        deltas.append(method - anchor)

    report = {
        "tasks": len(task_ids),
        "task_outputs": len(rows),
        "anchor_attempt1_rate": sum(row["anchor_1"] for row in rows) / len(rows),
        "anchor_attempt2_incremental_rate": sum(row["anchor_pass2"] - row["anchor_1"] for row in rows) / len(rows),
        "anchor_pass2_rate": anchor_rate,
        "method_attempt1_rate": sum(row["method_1"] for row in rows) / len(rows),
        "method_attempt2_incremental_rate": sum(row["method_pass2"] - row["method_1"] for row in rows) / len(rows),
        "method_pass2_rate": method_rate,
        "delta_pass2": method_rate - anchor_rate,
        "oracle_pool_rate": oracle_rate,
        "oracle_gain_over_anchor": oracle_gap,
        "selector_regret_to_oracle": oracle_rate - method_rate,
        "oracle_gap_recovery": oracle_gap_recovery,
        "paired_task_bootstrap_95_ci": [percentile(deltas, 0.025), percentile(deltas, 0.975)],
        "bootstrap_replicates": args.bootstrap_replicates,
        "bootstrap_seed": args.seed,
        "beneficial_outputs": benefit,
        "harmful_outputs": harm,
        "neutral_outputs": neutral,
        "paired_sign_test_two_sided_p": binomial_two_sided(benefit, harm),
        "source_sha256": hashlib.sha256(args.paired_csv.read_bytes()).hexdigest(),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
