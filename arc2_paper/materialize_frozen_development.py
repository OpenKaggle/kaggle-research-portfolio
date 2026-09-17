#!/usr/bin/env python3
"""Materialize the frozen 48-task development split for evaluator-only tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    run_dir = root / "kaggle_runs" / "development_stable_v2"
    manifest_path = run_dir / "benchmark_manifest.json"
    challenges_path = root / "official" / "competition_files" / "arc-agi_training_challenges.json"
    solutions_path = root / "official" / "competition_files" / "arc-agi_training_solutions.json"
    output_root = root / "evaluator_only" / "development_stable_v2"
    task_dir = output_root / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    challenges = json.loads(challenges_path.read_text(encoding="utf-8"))
    solutions = json.loads(solutions_path.read_text(encoding="utf-8"))
    task_ids = [row["task_id"] for row in manifest["tasks"]]
    if len(task_ids) != 48 or len(set(task_ids)) != 48:
        raise ValueError("expected 48 unique frozen development task IDs")
    if sorted(manifest["quartile_counts"].values()) != [12, 12, 12, 12]:
        raise ValueError("development split is not balanced 12/12/12/12")

    expected_names = {f"{task_id}.json" for task_id in task_ids}
    existing_names = {path.name for path in task_dir.glob("*.json")}
    if existing_names - expected_names:
        raise RuntimeError("evaluator-only directory contains stale task files")

    output_count = 0
    for task_id in task_ids:
        task = json.loads(json.dumps(challenges[task_id]))
        task_solutions = solutions[task_id]
        if len(task["test"]) != len(task_solutions):
            raise ValueError(f"solution count mismatch for {task_id}")
        for test_case, output in zip(task["test"], task_solutions, strict=True):
            test_case["output"] = output
            output_count += 1
        (task_dir / f"{task_id}.json").write_text(
            json.dumps(task, separators=(",", ":")),
            encoding="utf-8",
        )

    receipt = {
        "purpose": "evaluator-only frozen development materialization",
        "candidate_access": "forbidden",
        "task_count": len(task_ids),
        "output_count": output_count,
        "quartile_counts": manifest["quartile_counts"],
        "manifest_sha256": sha256(manifest_path),
        "training_challenges_sha256": sha256(challenges_path),
        "training_solutions_sha256": sha256(solutions_path),
        "task_ids": task_ids,
        "task_file_sha256": {
            task_id: sha256(task_dir / f"{task_id}.json") for task_id in task_ids
        },
    }
    receipt_path = output_root / "SOURCE_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**receipt, "receipt_sha256": sha256(receipt_path)}, indent=2))


if __name__ == "__main__":
    main()
