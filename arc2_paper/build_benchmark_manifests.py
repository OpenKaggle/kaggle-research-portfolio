#!/usr/bin/env python3
"""Freeze disjoint work-stratified development and holdout task manifests."""

from __future__ import annotations

import hashlib
import json
import pathlib


SEED = "arc2026-ab-v2-work-stratified"
TASKS_PER_QUARTILE = 12


def cells(grid: list[list[int]]) -> int:
    return len(grid) * len(grid[0]) if grid and grid[0] else 0


def estimated_nvarc_work(task: dict) -> tuple[int, int, int, int]:
    train_input = sum(cells(pair["input"]) for pair in task["train"])
    train_output = sum(cells(pair["output"]) for pair in task["train"])
    test_input = sum(cells(pair["input"]) for pair in task["test"])
    ratios = sorted(
        cells(pair["output"]) / max(1, cells(pair["input"])) for pair in task["train"]
    )
    output_ratio = ratios[len(ratios) // 2] if ratios else 1.0
    estimated_test_output = round(test_input * output_ratio)
    token_work = 16 * (train_input + train_output) + 8 * estimated_test_output
    return token_work, estimated_test_output, train_input + train_output, test_input


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    data_dir = root / "official/ARC-AGI-2/data/training"
    tasks = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(data_dir.glob("*.json"))
    }
    ordered = sorted(tasks, key=lambda task_id: (estimated_nvarc_work(tasks[task_id]), task_id))
    quartiles = [
        ordered[index * len(ordered) // 4 : (index + 1) * len(ordered) // 4]
        for index in range(4)
    ]
    development: list[dict] = []
    holdout: list[dict] = []
    for quartile_index, quartile_ids in enumerate(quartiles):
        deterministic_order = sorted(
            quartile_ids,
            key=lambda task_id: hashlib.sha256(
                f"{SEED}:{quartile_index}:{task_id}".encode("utf-8")
            ).digest(),
        )
        for split, selected in (
            (development, deterministic_order[:TASKS_PER_QUARTILE]),
            (
                holdout,
                deterministic_order[TASKS_PER_QUARTILE : 2 * TASKS_PER_QUARTILE],
            ),
        ):
            split.extend(
                {
                    "task_id": task_id,
                    "work_quartile": quartile_index + 1,
                    "estimated_nvarc_work": list(estimated_nvarc_work(tasks[task_id])),
                }
                for task_id in selected
            )
    development_ids = {row["task_id"] for row in development}
    holdout_ids = {row["task_id"] for row in holdout}
    assert len(development_ids) == 48
    assert len(holdout_ids) == 48
    assert not development_ids & holdout_ids
    manifest = {
        "source": "arcprize/ARC-AGI-2 GitHub commit f3283f7",
        "seed": SEED,
        "selection": (
            "SHA256 deterministic order within four input-only work quartiles; "
            "first 12 per quartile for development, next 12 for sealed holdout"
        ),
        "development": development,
        "holdout": holdout,
    }
    output = root / "benchmark_manifests.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output}: development=48, holdout=48, overlap=0")


if __name__ == "__main__":
    main()
