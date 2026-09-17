#!/usr/bin/env python3
"""Freeze the label-blind audit set for a new typed-object solver family."""

from __future__ import annotations

import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
GROUPED = ROOT / "paper/manifests/grouped_folds_v1.json"
BENCHMARK = ROOT / "benchmark_manifests.json"
OUTPUT = ROOT / "paper/manifests/typed_object_family_audit_v1.json"
AUDIT_FOLD = 0
MANUALLY_EXPOSED_TASK_IDS = {
    "a85d4709",
    "c8cbb738",
    "8e1813be",
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    grouped = json.loads(GROUPED.read_text(encoding="utf-8"))
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    fold = next(item for item in grouped["folds"] if item["fold"] == AUDIT_FOLD)
    development = {item["task_id"] for item in benchmark["development"]}
    holdout = {item["task_id"] for item in benchmark["holdout"]}
    frozen_exclusions = development | holdout | MANUALLY_EXPOSED_TASK_IDS
    task_ids = sorted(set(fold["task_ids"]) - frozen_exclusions)
    if not task_ids:
        raise ValueError("typed-object audit set is empty")
    if set(task_ids) & (development | holdout):
        raise ValueError("typed-object audit set overlaps a benchmark split")

    training_root = ROOT / grouped["dataset"]["path"]
    files = {task_id: training_root / f"{task_id}.json" for task_id in task_ids}
    if any(not path.is_file() for path in files.values()):
        raise ValueError("typed-object audit task file is missing")

    manifest = {
        "schema_version": 1,
        "status": "SEALED_BEFORE_IMPLEMENTATION",
        "experiment_id": "20260909-typed-object-correspondence-v1",
        "candidate_family": "typed_object_correspondence_v1",
        "hypothesis": (
            "A fixed property-based object extraction and placement program family, "
            "selected only by demonstration reconstruction and leave-one-demonstration-out "
            "stability, yields nonzero unique exact candidates on an implementation-sealed "
            "task-disjoint audit fold."
        ),
        "single_changed_factor": (
            "add typed_object_correspondence_v1 candidates; data, fallback attempts, "
            "selection thresholds, and all existing solver families remain absent or fixed"
        ),
        "audit_fold": AUDIT_FOLD,
        "source": {
            "grouped_manifest_path": "paper/manifests/grouped_folds_v1.json",
            "grouped_manifest_sha256": sha256(GROUPED),
            "benchmark_manifest_path": "benchmark_manifests.json",
            "benchmark_manifest_sha256": sha256(BENCHMARK),
            "training_tree_sha256": grouped["dataset"]["tree_sha256"],
            "manifest_builder_path": "paper/tools/build_typed_object_audit_manifest.py",
            "manifest_builder_sha256": sha256(pathlib.Path(__file__)),
        },
        "exclusions": {
            "development_task_ids": sorted(development),
            "sealed_holdout_task_ids": sorted(holdout),
            "manually_exposed_in_this_session": sorted(MANUALLY_EXPOSED_TASK_IDS),
            "rule": (
                "exclude every existing 48-task benchmark member and every task whose "
                "complete labeled JSON was displayed before implementation freeze"
            ),
        },
        "audit": {
            "task_count": len(task_ids),
            "task_ids": task_ids,
            "task_file_sha256": {
                task_id: sha256(path) for task_id, path in sorted(files.items())
            },
            "labels_sealed_during_implementation": True,
            "one_shot_evaluation": True,
            "selection_inputs": "task demonstrations and test inputs only",
            "scoring_boundary": "test outputs detached before inference and used once after code hash freeze",
        },
        "gate": {
            "minimum_unique_loo_safe_outputs": 1,
            "minimum_exact_selected_outputs": 1,
            "maximum_incorrect_selected_outputs": 0,
            "promotion_effect": (
                "implementation evidence only; cannot open the existing sealed holdout "
                "or replace the three-stage runtime prerequisite"
            ),
        },
        "claim_boundary": (
            "This audit set is public-training data and is not the existing sealed holdout, "
            "public evaluation, hidden competition test, or Kaggle score. The experiment is "
            "prospective only relative to the new implementation hash and disclosed exposures."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "task_count": len(task_ids),
                "manifest_sha256": sha256(OUTPUT),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
