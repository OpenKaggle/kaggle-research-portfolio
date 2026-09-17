#!/usr/bin/env python3
"""Evaluate the existing NeuroGolf DSL on official ARC-AGI-2 public tasks.

The search fits only each task's demonstration pairs. Public test outputs are
used strictly for evaluation. This is a small, auditable baseline and a source
of per-task evidence for the Paper Track; it is not a Kaggle submission runner.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
import tempfile

import numpy as np


NEUROGOLF_ROOT = pathlib.Path("$HOME/Desktop/kaggleonnx")
sys.path.insert(0, str(NEUROGOLF_ROOT))

from tools.dsl.search import run_program, search_program  # noqa: E402


def exact(prediction: list[list[int]], target: list[list[int]]) -> bool:
    return np.array_equal(
        np.asarray(prediction, dtype=np.int64),
        np.asarray(target, dtype=np.int64),
    )


def zero_like(grid: list[list[int]]) -> list[list[int]]:
    return np.zeros_like(np.asarray(grid, dtype=np.int64)).tolist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=pathlib.Path,
        default=pathlib.Path(__file__).parent / "official/ARC-AGI-2/data/evaluation",
    )
    parser.add_argument("--max-depth", type=int, default=2, choices=(1, 2))
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path(__file__).parent / "artifacts/neurogolf_dsl",
    )
    args = parser.parse_args()

    task_paths = sorted(args.data_dir.glob("*.json"))
    if not task_paths:
        raise SystemExit(f"no JSON tasks in {args.data_dir}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    submission: dict[str, list[dict[str, list[list[int]]]]] = {}
    solved_attempt1 = 0
    solved_pass2 = 0
    hits = 0

    # Reuse the proven NeuroGolf search unchanged by presenting ARC files under
    # its taskNNN naming convention. Symlinks are temporary and never modify the
    # archived NeuroGolf project or the official data checkout.
    with tempfile.TemporaryDirectory(prefix="arc2-neurogolf-dsl-") as raw_tmp:
        tmp_dir = pathlib.Path(raw_tmp)
        for index, task_path in enumerate(task_paths, start=1):
            os.symlink(task_path, tmp_dir / f"task{index:03d}.json")

        for index, task_path in enumerate(task_paths, start=1):
            task = json.loads(task_path.read_text())
            hit = search_program(index, tmp_dir, max_depth=args.max_depth)
            if hit is not None:
                hits += 1

            task_predictions: list[dict[str, list[list[int]]]] = []
            attempt1_correct = 0
            pass2_correct = 0
            for test_example in task.get("test", []):
                test_input = test_example["input"]
                target = test_example.get("output")
                if hit is None:
                    attempt1 = test_input
                    attempt2 = zero_like(test_input)
                else:
                    predicted = run_program(
                        hit.program, np.asarray(test_input, dtype=np.int64)
                    )
                    attempt1 = test_input if predicted is None else predicted.tolist()
                    # Identity is a genuinely different, cheap hypothesis unless
                    # the selected DSL program is itself identity.
                    attempt2 = zero_like(test_input) if attempt1 == test_input else test_input

                task_predictions.append(
                    {"attempt_1": attempt1, "attempt_2": attempt2}
                )
                if target is not None:
                    a1_ok = exact(attempt1, target)
                    a2_ok = exact(attempt2, target)
                    attempt1_correct += int(a1_ok)
                    pass2_correct += int(a1_ok or a2_ok)

            submission[task_path.stem] = task_predictions
            solved_attempt1 += attempt1_correct
            solved_pass2 += pass2_correct
            rows.append(
                {
                    "task_id": task_path.stem,
                    "n_train": len(task.get("train", [])),
                    "n_test": len(task.get("test", [])),
                    "dsl_hit": hit is not None,
                    "depth": "" if hit is None else hit.depth,
                    "program": "" if hit is None else repr(hit.program),
                    "attempt1_correct": attempt1_correct,
                    "pass2_correct": pass2_correct,
                }
            )

    total_outputs = sum(int(row["n_test"]) for row in rows)
    summary = {
        "dataset": str(args.data_dir),
        "tasks": len(rows),
        "test_outputs": total_outputs,
        "max_depth": args.max_depth,
        "train_perfect_dsl_hits": hits,
        "attempt1_exact": solved_attempt1,
        "pass2_exact": solved_pass2,
        "attempt1_accuracy": solved_attempt1 / total_outputs,
        "pass2_accuracy": solved_pass2 / total_outputs,
        "note": "Search used demonstrations only; public test outputs only scored results.",
    }

    with (args.out_dir / "per_task.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out_dir / "submission_public_eval.json").write_text(
        json.dumps(submission, separators=(",", ":"))
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
