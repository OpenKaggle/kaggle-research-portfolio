#!/usr/bin/env python3
"""Audit the public exact-rule portfolio on official ARC-AGI-2 tasks.

Candidate generation sees demonstration pairs and test inputs only.  Test
outputs are detached before inference and used only after selection for the
reported metrics.  The strict policy admits a rule only when it also predicts
every training example while that example is held out.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import pathlib
import time
from collections import defaultdict
from typing import Any


Grid = list[list[int]]


def load_exact_predictions(module_path: pathlib.Path):
    spec = importlib.util.spec_from_file_location("arc_exact_rule_portfolio", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load exact-rule module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.exact_predictions


def grid_key(grid: Grid) -> str:
    return json.dumps(grid, separators=(",", ":"))


def valid_grid(grid: Any) -> bool:
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and isinstance(grid[0], list)
        and 1 <= len(grid[0]) <= 30
        and all(isinstance(row, list) and len(row) == len(grid[0]) for row in grid)
        and all(type(cell) is int and 0 <= cell <= 9 for row in grid for cell in row)
    )


def modal_fill(grid: Grid) -> Grid:
    counts: dict[int, int] = defaultdict(int)
    for row in grid:
        for cell in row:
            counts[cell] += 1
    background = max(sorted(counts), key=counts.get)
    return [[background for _ in row] for row in grid]


def group_predictions(predictions: dict[str, Grid]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for reason, grid in predictions.items():
        if not valid_grid(grid):
            continue
        key = grid_key(grid)
        group = groups.setdefault(key, {"grid": grid, "reasons": []})
        group["reasons"].append(reason)
    for group in groups.values():
        group["reasons"].sort()
    return groups


def leave_one_out_safe_reasons(
    exact_predictions,
    train_pairs: list[dict[str, Grid]],
    full_predictions: dict[str, Grid],
) -> tuple[list[str], dict[str, str]]:
    safe: list[str] = []
    failures: dict[str, str] = {}
    if len(train_pairs) < 2:
        return safe, {reason: "fewer_than_two_demonstrations" for reason in full_predictions}

    for reason in sorted(full_predictions):
        failure = ""
        for heldout_index, heldout in enumerate(train_pairs):
            fold_train = [pair for index, pair in enumerate(train_pairs) if index != heldout_index]
            fold_task = {"train": fold_train, "test": [{"input": heldout["input"]}]}
            try:
                fold_predictions = exact_predictions(fold_task, heldout["input"])
            except Exception as exc:  # A rejected rule must not terminate the audit.
                failure = f"fold_{heldout_index}_error:{type(exc).__name__}"
                break
            if fold_predictions.get(reason) != heldout["output"]:
                failure = f"fold_{heldout_index}_mismatch_or_absent"
                break
        if failure:
            failures[reason] = failure
        else:
            safe.append(reason)
    return safe, failures


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=pathlib.Path,
        default=root / "official/ARC-AGI-2/data/evaluation",
    )
    parser.add_argument(
        "--rule-module",
        type=pathlib.Path,
        default=root / "public_assets/trm_source/merge_agreement.py",
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=root / "artifacts/exact_rule_loo",
    )
    args = parser.parse_args()

    task_paths = sorted(args.data_dir.glob("*.json"))
    if not task_paths:
        raise SystemExit(f"no JSON tasks in {args.data_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    exact_predictions = load_exact_predictions(args.rule_module)

    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    submission: dict[str, list[dict[str, Grid]]] = {}
    challenge: dict[str, dict[str, Any]] = {}
    task_scores: dict[str, list[int]] = defaultdict(list)

    for task_path in task_paths:
        labeled_task = json.loads(task_path.read_text(encoding="utf-8"))
        train_pairs = labeled_task["train"]
        challenge_task = {
            "train": train_pairs,
            "test": [{"input": item["input"]} for item in labeled_task["test"]],
        }
        challenge[task_path.stem] = challenge_task
        output_rows: list[dict[str, Grid]] = []

        for output_index, (test_case, labeled_test) in enumerate(
            zip(challenge_task["test"], labeled_task["test"], strict=True)
        ):
            full = exact_predictions(challenge_task, test_case["input"])
            full = {reason: grid for reason, grid in full.items() if valid_grid(grid)}
            full_groups = group_predictions(full)
            safe_reasons, loo_failures = leave_one_out_safe_reasons(
                exact_predictions, train_pairs, full
            )
            safe_predictions = {reason: full[reason] for reason in safe_reasons}
            safe_groups = group_predictions(safe_predictions)

            selected_group = next(iter(safe_groups.values())) if len(safe_groups) == 1 else None
            test_input = test_case["input"]
            attempt_1 = [row[:] for row in test_input]
            fallback = modal_fill(test_input)
            attempt_2 = (
                selected_group["grid"]
                if selected_group is not None and selected_group["grid"] != attempt_1
                else fallback
            )
            if attempt_2 == attempt_1:
                attempt_2 = [[0 for _ in row] for row in test_input]
            output_rows.append({"attempt_1": attempt_1, "attempt_2": attempt_2})

            target = labeled_test["output"]
            direct_selected = selected_group is not None
            direct_correct = bool(direct_selected and selected_group["grid"] == target)
            pass2_correct = attempt_1 == target or attempt_2 == target
            task_scores[task_path.stem].append(int(pass2_correct))
            rows.append(
                {
                    "task_id": task_path.stem,
                    "output_index": output_index,
                    "n_train": len(train_pairs),
                    "all_train_rule_count": len(full),
                    "all_train_candidate_count": len(full_groups),
                    "loo_safe_rule_count": len(safe_reasons),
                    "loo_candidate_count": len(safe_groups),
                    "direct_selected": direct_selected,
                    "direct_correct": direct_correct,
                    "pass2_correct": pass2_correct,
                    "selected_reasons": "|".join(selected_group["reasons"]) if selected_group else "",
                    "all_train_reasons": "|".join(sorted(full)),
                    "loo_failures": json.dumps(loo_failures, sort_keys=True, separators=(",", ":")),
                    "predicted_shape": (
                        f"{len(selected_group['grid'])}x{len(selected_group['grid'][0])}"
                        if selected_group
                        else ""
                    ),
                    "target_shape": f"{len(target)}x{len(target[0])}",
                }
            )
        submission[task_path.stem] = output_rows

    elapsed = time.perf_counter() - started
    selected_rows = [row for row in rows if row["direct_selected"]]
    correct_selected = sum(int(row["direct_correct"]) for row in selected_rows)
    pass2_correct = sum(int(row["pass2_correct"]) for row in rows)
    production_unique = sum(int(row["all_train_candidate_count"] == 1) for row in rows)
    task_mean = sum(sum(scores) / len(scores) for scores in task_scores.values()) / len(task_scores)
    summary = {
        "dataset": str(args.data_dir),
        "rule_module": str(args.rule_module),
        "tasks": len(task_scores),
        "test_outputs": len(rows),
        "policy": "unique candidate among rules passing every leave-one-demonstration-out fold",
        "label_free_selection": True,
        "production_unique_outputs": production_unique,
        "loo_selected_outputs": len(selected_rows),
        "loo_correct_selected_outputs": correct_selected,
        "loo_direct_precision": (
            correct_selected / len(selected_rows) if selected_rows else None
        ),
        "loo_output_coverage": len(selected_rows) / len(rows),
        "fallback_inclusive_pass2_outputs": pass2_correct,
        "fallback_inclusive_pass2_output_accuracy": pass2_correct / len(rows),
        "fallback_inclusive_pass2_task_mean": task_mean,
        "wall_seconds": elapsed,
        "notes": (
            "Test outputs were detached before candidate generation and selection; "
            "they were used only to score the fixed policy."
        ),
    }

    per_output_path = args.out_dir / "per_output.csv"
    with per_output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    submission_path = args.out_dir / "submission_public_eval.json"
    submission_path.write_text(json.dumps(submission, separators=(",", ":")), encoding="utf-8")
    challenge_path = args.out_dir / "challenge_without_test_outputs.json"
    challenge_path.write_text(json.dumps(challenge, separators=(",", ":")), encoding="utf-8")
    summary["artifacts"] = {
        "per_output": str(per_output_path),
        "submission": str(submission_path),
        "challenge": str(challenge_path),
        "submission_sha256": sha256(submission_path),
    }
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
