#!/usr/bin/env python3
"""Regression for sealing a benchmark that reports the V176 exact overlay."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="arc2-v176-finalizer-") as raw:
        run_dir = Path(raw)
        task_ids = [f"{index:08x}" for index in range(48)]
        challenges = {
            task_id: {
                "train": [
                    {"input": [[0]], "output": [[0]]},
                    {"input": [[1]], "output": [[1]]},
                ],
                "test": [{"input": [[0]]}],
            }
            for task_id in task_ids
        }
        solutions = {task_id: [[[0]]] for task_id in task_ids}
        anchor = {
            task_id: [{"attempt_1": [[1]], "attempt_2": [[1]]}]
            for task_id in task_ids
        }
        method = {
            task_id: [{"attempt_1": [[1]], "attempt_2": [[0]]}]
            for task_id in task_ids
        }
        write(run_dir / "benchmark_challenges.json", challenges)
        write(run_dir / "benchmark_solutions.json", solutions)
        write(
            run_dir / "benchmark_manifest.json",
            {
                "tasks": [
                    {"task_id": task_id, "work_quartile": index // 12 + 1}
                    for index, task_id in enumerate(task_ids)
                ],
                "quartile_counts": {"q1": 12, "q2": 12, "q3": 12, "q4": 12},
            },
        )
        write(
            run_dir / "run_manifest.json",
            {"started_at_cst": "2026-09-09T00:00:00+08:00"},
        )
        for name in (
            "nvarc_kgmon.json",
            "nvarc_portfolio.json",
            "nvarc_full_probmul_3.json",
            "nvarc_submission.json",
        ):
            write(run_dir / name, anchor)
        write(run_dir / "submission.json", method)
        write(
            run_dir / "ab-benchmark-report.json",
            {
                "benchmark_tasks": 48,
                "total_outputs": 48,
                "nvarc_completed_tasks": 48,
                "nvarc_unfinished_tasks": [],
                "trm_available": False,
                "trm_marker": None,
                "policy_scores": {
                    "kgmon": {"solved_outputs": 0},
                    "agreement_exact_v176": {"solved_outputs": 48},
                },
                "nvarc_unique_outputs_vs_trm": 0,
                "trm_unique_outputs_vs_nvarc": 0,
                "nvarc_trm_overlap_outputs": 0,
                "nvarc_trm_oracle_outputs": 0,
                "nvarc_trm_oracle_accuracy": 0.0,
            },
        )
        write(
            run_dir / "exact-overlay-receipt.json",
            {
                "solution_blind": True,
                "enabled_rules": [
                    "scale_by_distinct_color_count",
                    "reconstruct_centered_square_perimeters",
                ],
                "task_count": 48,
                "test_output_count": 48,
                "changed_attempt_2_outputs": 48,
                "ambiguous_outputs_abstained": 0,
                "rows": [
                    {"task_id": task_id, "output_index": 0}
                    for task_id in task_ids
                ],
            },
        )
        with (run_dir / "nvarc-receipt-rank0.jsonl").open("w", encoding="utf-8") as handle:
            for index, task_id in enumerate(task_ids):
                handle.write(
                    json.dumps(
                        {
                            "rank": 0,
                            "task_id": task_id,
                            "elapsed_seconds": 1.0,
                            "timed_out": False,
                            "decode_batches_finished": 1,
                            "decode_batches_planned": 1,
                            "finished_at": 1000.0 + index,
                        }
                    )
                    + "\n"
                )

        output_dir = run_dir / "sealed"
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "finalize_kaggle_benchmark.py"),
                str(run_dir),
                "--output-dir",
                str(output_dir),
                "--completed-at-cst",
                "2026-09-09T01:00:00+08:00",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        receipt = json.loads(completed.stdout)
        assert receipt["selection_policy"]["method_policy_score_key"] == "agreement_exact_v176"
        assert receipt["exact_overlay"]["solution_blind"] is True
        assert receipt["exact_overlay"]["sha256"]
        assert receipt["selection_policy"]["attempt_1_changed_outputs"] == 0

        (run_dir / "exact-overlay-receipt.json").unlink()
        rejected = subprocess.run(
            [
                sys.executable,
                str(root / "finalize_kaggle_benchmark.py"),
                str(run_dir),
                "--output-dir",
                str(output_dir),
                "--completed-at-cst",
                "2026-09-09T01:00:00+08:00",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode != 0
        assert "exact-overlay-receipt.json is missing" in rejected.stderr
    print("V176 finalizer regression passed")


if __name__ == "__main__":
    main()
