#!/usr/bin/env python3
"""Compare authenticated Kaggle ARC files with the pinned GitHub checkout.

Optionally materializes labeled evaluation tasks in an evaluator-only directory
for frozen, label-detached audits. The output labels in that directory must
never be used by candidate generation, calibration, or selector fitting.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


SPLITS = ("training", "evaluation")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def display_path(path: Path, root: Path) -> str:
    """Use a repository-relative path when possible, otherwise an absolute path."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def combine_task(challenge: dict, solutions: list) -> dict:
    tests = challenge["test"]
    if len(tests) != len(solutions):
        raise ValueError("challenge/solution output count mismatch")
    return {
        "train": challenge["train"],
        "test": [
            {"input": test["input"], "output": output}
            for test, output in zip(tests, solutions, strict=True)
        ],
    }


def main() -> None:
    here = Path(__file__).resolve()
    paper_root = here.parents[1]
    arc_root = paper_root.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--competition-dir",
        type=Path,
        default=arc_root / "official/competition_files",
    )
    parser.add_argument(
        "--github-data-dir",
        type=Path,
        default=arc_root / "official/ARC-AGI-2/data",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=paper_root / "results/dataset_revision_audit_2026-09-09.json",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=paper_root / "results/dataset_revision_tasks_2026-09-09.csv",
    )
    parser.add_argument(
        "--materialize-evaluation",
        type=Path,
        default=None,
        help="write combined labeled evaluation tasks to this evaluator-only directory",
    )
    args = parser.parse_args()

    # Normalize every CLI path before deriving repository-relative provenance.
    # Without this, an explicit relative path can fail `relative_to()` even
    # when it names the same in-repository file as the absolute default.
    args.competition_dir = args.competition_dir.resolve()
    args.github_data_dir = args.github_data_dir.resolve()
    args.output_json = args.output_json.resolve()
    args.output_csv = args.output_csv.resolve()
    if args.materialize_evaluation is not None:
        args.materialize_evaluation = args.materialize_evaluation.resolve()

    manifest_path = args.competition_dir / "competition_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("user_has_entered") is not True:
        raise RuntimeError("competition manifest does not prove authenticated entry")
    for name, expected in manifest["files"].items():
        path = args.competition_dir / name
        if path.stat().st_size != expected["bytes"] or sha256(path) != expected["sha256"]:
            raise RuntimeError(f"competition file differs from manifest: {name}")

    rows = []
    split_reports = {}
    combined_by_split = {}
    for split in SPLITS:
        challenges = json.loads(
            (args.competition_dir / f"arc-agi_{split}_challenges.json").read_text(
                encoding="utf-8"
            )
        )
        solutions = json.loads(
            (args.competition_dir / f"arc-agi_{split}_solutions.json").read_text(
                encoding="utf-8"
            )
        )
        if set(challenges) != set(solutions):
            raise RuntimeError(f"{split}: challenge and solution task IDs differ")
        combined = {
            task_id: combine_task(challenges[task_id], solutions[task_id])
            for task_id in sorted(challenges)
        }
        combined_by_split[split] = combined
        github = {
            path.stem: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((args.github_data_dir / split).glob("*.json"))
        }
        common = sorted(set(combined) & set(github))
        statuses = Counter()
        for task_id in sorted(set(combined) | set(github)):
            kaggle = combined.get(task_id)
            old = github.get(task_id)
            if kaggle is None:
                status = "github_only"
                train_equal = test_inputs_equal = solutions_equal = full_equal = False
                kaggle_outputs = 0
                github_outputs = len(old["test"])
            elif old is None:
                status = "kaggle_only"
                train_equal = test_inputs_equal = solutions_equal = full_equal = False
                kaggle_outputs = len(kaggle["test"])
                github_outputs = 0
            else:
                train_equal = kaggle["train"] == old["train"]
                test_inputs_equal = [row["input"] for row in kaggle["test"]] == [
                    row["input"] for row in old["test"]
                ]
                solutions_equal = [row["output"] for row in kaggle["test"]] == [
                    row["output"] for row in old["test"]
                ]
                full_equal = kaggle == old
                kaggle_outputs = len(kaggle["test"])
                github_outputs = len(old["test"])
                if full_equal:
                    status = "exact"
                elif not train_equal:
                    status = "train_changed"
                elif not test_inputs_equal:
                    status = "test_input_changed"
                elif kaggle_outputs != github_outputs:
                    status = "output_count_changed"
                elif not solutions_equal:
                    status = "solution_changed"
                else:
                    status = "other_changed"
            statuses[status] += 1
            rows.append(
                {
                    "split": split,
                    "task_id": task_id,
                    "status": status,
                    "kaggle_outputs": kaggle_outputs,
                    "github_outputs": github_outputs,
                    "train_equal": int(train_equal),
                    "test_inputs_equal": int(test_inputs_equal),
                    "solutions_equal": int(solutions_equal),
                    "full_equal": int(full_equal),
                }
            )
        split_reports[split] = {
            "kaggle_tasks": len(combined),
            "kaggle_outputs": sum(len(task["test"]) for task in combined.values()),
            "github_tasks": len(github),
            "github_outputs": sum(len(task["test"]) for task in github.values()),
            "common_task_ids": len(common),
            "kaggle_only_task_ids": sorted(set(combined) - set(github)),
            "github_only_task_ids": sorted(set(github) - set(combined)),
            "status_counts": dict(sorted(statuses.items())),
        }

    materialized = None
    if args.materialize_evaluation is not None:
        materialized_root = args.materialize_evaluation
        destination = materialized_root / "tasks"
        destination.mkdir(parents=True, exist_ok=True)
        expected_ids = set(combined_by_split["evaluation"])
        existing_ids = {
            path.stem
            for path in destination.glob("*.json")
            if path.name != "SOURCE_RECEIPT.json"
        }
        if existing_ids and existing_ids != expected_ids:
            raise RuntimeError("materialized directory contains a different task-ID set")
        for task_id, task in combined_by_split["evaluation"].items():
            (destination / f"{task_id}.json").write_text(
                json.dumps(task, separators=(",", ":"), sort_keys=True) + "\n",
                encoding="utf-8",
            )
        paths = sorted(
            path
            for path in destination.glob("*.json")
            if path.name != "SOURCE_RECEIPT.json"
        )
        source_receipt = {
            "classification": "evaluator_only_public_labels",
            "candidate_generation_allowed": False,
            "selector_fitting_allowed": False,
            "source_competition_manifest_sha256": sha256(manifest_path),
            "tasks": len(paths),
            "outputs": sum(
                len(task["test"]) for task in combined_by_split["evaluation"].values()
            ),
            "tree_sha256": tree_hash(paths, destination),
        }
        source_receipt_path = materialized_root / "SOURCE_RECEIPT.json"
        source_receipt_path.write_text(
            json.dumps(source_receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        materialized = {
            "path": display_path(destination, arc_root),
            **source_receipt,
            "source_receipt": display_path(source_receipt_path, arc_root),
            "source_receipt_sha256": sha256(source_receipt_path),
        }

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "competition_manifest": display_path(manifest_path, arc_root),
        "competition_manifest_sha256": sha256(manifest_path),
        "github_upstream_commit": "f3283f727488ad98fe575ea6a5ac981e4a188e49",
        "splits": split_reports,
        "materialized_evaluation": materialized,
        "task_csv": display_path(args.output_csv, paper_root),
        "task_csv_sha256": sha256(args.output_csv),
        "claim_boundary": (
            "Public evaluation outputs are evaluator-only and forbidden from candidate "
            "generation, calibration, selector fitting, and threshold selection."
        ),
    }
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
