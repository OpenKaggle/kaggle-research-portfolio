#!/usr/bin/env python3
"""Pair-score frozen ARC benchmark submissions without changing generation.

The script consumes only a completed training-only Kaggle benchmark directory.
It compares an unchanged anchor submission with one fixed method, emits the
Paper Track paired-result table, and stratifies effects by demo-derived
structure.  Evaluation/test labels are neither accepted nor discovered.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path


DEFAULT_ORACLE_CANDIDATES = (
    "nvarc_kgmon.json",
    "nvarc_portfolio.json",
    "nvarc_full_probmul_3.json",
    "trm_submission_early.json",
    "trm_submission_final.json",
    "benchmark_nvarc1_trm1.json",
    "submission.json",
)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_grid(grid: object, context: str) -> list[list[int]]:
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        raise ValueError(f"{context}: invalid height")
    if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
        raise ValueError(f"{context}: invalid width")
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        raise ValueError(f"{context}: non-rectangular")
    if any(type(value) is not int or not 0 <= value <= 9 for row in grid for value in row):
        raise ValueError(f"{context}: invalid color")
    return grid


def validate_submission(challenges: dict, submission: dict, name: str) -> None:
    if set(challenges) != set(submission):
        raise ValueError(f"{name}: task keys differ from benchmark challenge")
    for task_id, task in challenges.items():
        rows = submission[task_id]
        if not isinstance(rows, list) or len(rows) != len(task["test"]):
            raise ValueError(f"{name}:{task_id}: output count mismatch")
        for output_index, attempts in enumerate(rows):
            if not isinstance(attempts, dict) or set(attempts) != {"attempt_1", "attempt_2"}:
                raise ValueError(f"{name}:{task_id}_{output_index}: invalid attempt keys")
            for attempt_name, grid in attempts.items():
                validate_grid(grid, f"{name}:{task_id}_{output_index}:{attempt_name}")


def shape(grid: list[list[int]]) -> tuple[int, int]:
    return len(grid), len(grid[0])


def relation(values: list[int]) -> str:
    signs = {0 if value == 0 else 1 if value > 0 else -1 for value in values}
    if signs == {0}:
        return "same"
    if signs <= {0, 1} and 1 in signs:
        return "increase"
    if signs <= {-1, 0} and -1 in signs:
        return "decrease"
    return "mixed"


def background(grid: list[list[int]]) -> int:
    counts = Counter(value for row in grid for value in row)
    return min(counts, key=lambda value: (-counts[value], value))


def component_count(grid: list[list[int]]) -> int:
    height, width = shape(grid)
    bg = background(grid)
    active = {(row, col) for row in range(height) for col in range(width) if grid[row][col] != bg}
    count = 0
    while active:
        count += 1
        start = active.pop()
        queue = deque([start])
        while queue:
            row, col = queue.popleft()
            for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if neighbor in active:
                    active.remove(neighbor)
                    queue.append(neighbor)
    return count


def task_features(task: dict) -> dict[str, str | int]:
    shape_deltas = []
    color_deltas = []
    component_deltas = []
    for pair in task["train"]:
        input_grid = validate_grid(pair["input"], "train input")
        output_grid = validate_grid(pair["output"], "train output")
        in_h, in_w = shape(input_grid)
        out_h, out_w = shape(output_grid)
        shape_deltas.append((out_h * out_w) - (in_h * in_w))
        color_deltas.append(len({v for row in output_grid for v in row}) - len({v for row in input_grid for v in row}))
        component_deltas.append(component_count(output_grid) - component_count(input_grid))
    shape_family = relation(shape_deltas)
    color_family = relation(color_deltas)
    component_family = relation(component_deltas)
    change_axes = sum(value != "same" for value in (shape_family, color_family, component_family))
    return {
        "shape_family": shape_family,
        "color_family": color_family,
        "component_family": component_family,
        "structural_change_axes": change_axes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--anchor", default="nvarc_kgmon.json")
    parser.add_argument("--method", default="submission.json")
    parser.add_argument(
        "--oracle-candidate",
        action="append",
        dest="oracle_candidates",
        help="repeatable candidate filename; defaults to every predeclared completed-run candidate",
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    challenges_path = args.run_dir / "benchmark_challenges.json"
    solutions_path = args.run_dir / "benchmark_solutions.json"
    anchor_path = args.run_dir / args.anchor
    method_path = args.run_dir / args.method
    paths = (challenges_path, solutions_path, anchor_path, method_path)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit(f"missing completed-run artifacts: {missing}")

    challenges = load_json(challenges_path)
    solutions = load_json(solutions_path)
    anchor = load_json(anchor_path)
    method = load_json(method_path)
    if set(solutions) != set(challenges):
        raise ValueError("solutions are not aligned to benchmark challenges")
    validate_submission(challenges, anchor, "anchor")
    validate_submission(challenges, method, "method")

    oracle_names = args.oracle_candidates or [
        name for name in DEFAULT_ORACLE_CANDIDATES if (args.run_dir / name).is_file()
    ]
    for required_name in (args.anchor, args.method):
        if required_name not in oracle_names:
            oracle_names.append(required_name)
    oracle_submissions = {}
    oracle_paths = []
    for name in oracle_names:
        path = args.run_dir / name
        if not path.is_file():
            raise SystemExit(f"missing requested oracle candidate: {path}")
        candidate = load_json(path)
        validate_submission(challenges, candidate, f"oracle:{name}")
        oracle_submissions[name] = candidate
        oracle_paths.append(path)

    rows = []
    for task_id, task in challenges.items():
        features = task_features(task)
        expected_rows = solutions[task_id]
        if len(expected_rows) != len(task["test"]):
            raise ValueError(f"{task_id}: solution output count mismatch")
        for output_index, expected in enumerate(expected_rows):
            expected = validate_grid(expected, f"solution:{task_id}_{output_index}")
            anchor_row = anchor[task_id][output_index]
            method_row = method[task_id][output_index]
            a1 = int(anchor_row["attempt_1"] == expected)
            a2 = int(anchor_row["attempt_2"] == expected)
            m1 = int(method_row["attempt_1"] == expected)
            m2 = int(method_row["attempt_2"] == expected)
            anchor_pass2 = int(a1 or a2)
            method_pass2 = int(m1 or m2)
            oracle_pool_correct = int(
                any(
                    expected in candidate[task_id][output_index].values()
                    for candidate in oracle_submissions.values()
                )
            )
            rows.append(
                {
                    "task_id": task_id,
                    "output_index": output_index,
                    "anchor_attempt_1_correct": a1,
                    "anchor_attempt_2_correct": a2,
                    "method_attempt_1_correct": m1,
                    "method_attempt_2_correct": m2,
                    "oracle_pool_correct": oracle_pool_correct,
                    "anchor_pass2": anchor_pass2,
                    "method_pass2": method_pass2,
                    "benefit": int(not anchor_pass2 and method_pass2),
                    "harm": int(anchor_pass2 and not method_pass2),
                    "attempt_1_same": int(anchor_row["attempt_1"] == method_row["attempt_1"]),
                    "attempt_2_changed": int(anchor_row["attempt_2"] != method_row["attempt_2"]),
                    **features,
                }
            )

    output_dir = args.output_dir or args.run_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    paired_path = output_dir / "paired_results.csv"
    with paired_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    family_rows = []
    for feature in ("shape_family", "color_family", "component_family", "structural_change_axes"):
        grouped = defaultdict(list)
        for row in rows:
            grouped[str(row[feature])].append(row)
        for value, group in sorted(grouped.items()):
            family_rows.append(
                {
                    "feature": feature,
                    "value": value,
                    "outputs": len(group),
                    "anchor_pass2": sum(row["anchor_pass2"] for row in group),
                    "method_pass2": sum(row["method_pass2"] for row in group),
                    "delta": sum(row["method_pass2"] - row["anchor_pass2"] for row in group),
                    "benefit": sum(row["benefit"] for row in group),
                    "harm": sum(row["harm"] for row in group),
                }
            )
    family_path = output_dir / "family_summary.csv"
    with family_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(family_rows[0]))
        writer.writeheader()
        writer.writerows(family_rows)

    beneficial_tasks = {row["task_id"] for row in rows if row["benefit"]}
    harmful_tasks = {row["task_id"] for row in rows if row["harm"]}
    oracle_outputs = sum(row["oracle_pool_correct"] for row in rows)
    anchor_outputs = sum(row["anchor_pass2"] for row in rows)
    method_outputs = sum(row["method_pass2"] for row in rows)
    summary = {
        "data_boundary": "training-only completed benchmark artifacts",
        "tasks": len(challenges),
        "outputs": len(rows),
        "anchor": args.anchor,
        "method": args.method,
        "anchor_pass2": anchor_outputs,
        "method_pass2": method_outputs,
        "oracle_pool_candidates": oracle_names,
        "oracle_pool_pass2": oracle_outputs,
        "oracle_gain_over_anchor_outputs": oracle_outputs - anchor_outputs,
        "selector_regret_to_oracle_outputs": oracle_outputs - method_outputs,
        "delta_outputs": sum(row["method_pass2"] - row["anchor_pass2"] for row in rows),
        "beneficial_outputs": sum(row["benefit"] for row in rows),
        "harmful_outputs": sum(row["harm"] for row in rows),
        "beneficial_tasks": len(beneficial_tasks),
        "harmful_tasks": len(harmful_tasks),
        "attempt_1_changed_outputs": sum(not row["attempt_1_same"] for row in rows),
        "attempt_2_changed_outputs": sum(row["attempt_2_changed"] for row in rows),
        "development_gate": {
            "requires_at_least_one_net_output": True,
            "requires_zero_attempt1_changes": True,
            "passes": (
                sum(row["method_pass2"] - row["anchor_pass2"] for row in rows) >= 1
                and all(row["attempt_1_same"] for row in rows)
            ),
        },
        "input_sha256": {
            path.name: sha256(path)
            for path in dict.fromkeys((*paths, *oracle_paths))
        },
        "paired_csv_sha256": sha256(paired_path),
        "family_csv_sha256": sha256(family_path),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
