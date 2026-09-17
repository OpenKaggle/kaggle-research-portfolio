#!/usr/bin/env python3
"""One-shot evaluator for the implementation-sealed typed-object audit fold."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import pathlib
import resource
import shutil
import tempfile
import time
from datetime import datetime, timezone
from typing import Any

from typed_object_correspondence import Grid, solve_task


ROOT = pathlib.Path(__file__).resolve().parent


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(first: Grid, second: Grid) -> bool:
    return first == second


def detached_task(task: dict[str, Any]) -> tuple[dict[str, Any], list[Grid]]:
    challenge = {
        "train": [
            {"input": item["input"], "output": item["output"]}
            for item in task["train"]
        ],
        "test": [{"input": item["input"]} for item in task["test"]],
    }
    targets = [item["output"] for item in task["test"]]
    return challenge, targets


def evaluate(manifest: dict[str, Any], training_root: pathlib.Path) -> tuple[list[dict], dict, dict]:
    rows: list[dict[str, Any]] = []
    traces: dict[str, Any] = {}
    challenges: dict[str, Any] = {}
    for task_id in manifest["audit"]["task_ids"]:
        task_path = training_root / f"{task_id}.json"
        expected_hash = manifest["audit"]["task_file_sha256"][task_id]
        if sha256(task_path) != expected_hash:
            raise ValueError(f"audit task hash mismatch: {task_id}")
        labeled = json.loads(task_path.read_text(encoding="utf-8"))
        challenge, targets = detached_task(labeled)
        challenges[task_id] = challenge
        predictions, trace = solve_task(challenge)
        traces[task_id] = trace
        for output_index, target in enumerate(targets):
            selected = predictions is not None
            correct = bool(selected and exact(predictions[output_index], target))
            rows.append(
                {
                    "task_id": task_id,
                    "output_index": output_index,
                    "selected": selected,
                    "correct": correct,
                    "reason": trace["reason"],
                    "all_demo_programs": trace.get("all_demo_programs", 0),
                    "prediction_shape": (
                        f"{len(predictions[output_index])}x{len(predictions[output_index][0])}"
                        if selected
                        else ""
                    ),
                    "target_shape": f"{len(target)}x{len(target[0])}",
                }
            )
    return rows, traces, challenges


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=ROOT / "paper/manifests/typed_object_family_audit_v1.json",
    )
    parser.add_argument(
        "--solver",
        type=pathlib.Path,
        default=ROOT / "typed_object_correspondence.py",
    )
    parser.add_argument("--expected-solver-sha256", required=True)
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=ROOT / "artifacts/typed_object_family_audit_v1",
    )
    parser.add_argument(
        "--receipt",
        type=pathlib.Path,
        default=ROOT / "paper/results/typed_object_family_audit_v1_2026-09-09.json",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    solver_path = args.solver.resolve()
    out_dir = args.out_dir.resolve()
    receipt_path = args.receipt.resolve()
    if out_dir.exists() or receipt_path.exists():
        raise SystemExit("one-shot audit output or receipt already exists; refusing rerun")
    if sha256(solver_path) != args.expected_solver_sha256:
        raise SystemExit("solver hash differs from the pre-evaluation freeze")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "SEALED_BEFORE_IMPLEMENTATION":
        raise SystemExit("audit manifest is not sealed")
    if manifest["audit"].get("one_shot_evaluation") is not True:
        raise SystemExit("audit manifest does not declare one-shot evaluation")

    grouped = json.loads(
        (ROOT / manifest["source"]["grouped_manifest_path"]).read_text(encoding="utf-8")
    )
    training_root = ROOT / grouped["dataset"]["path"]
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    rows, traces, challenges = evaluate(manifest, training_root)
    wall_seconds = time.perf_counter() - started
    completed_at = datetime.now(timezone.utc).isoformat()

    selected = sum(bool(row["selected"]) for row in rows)
    correct = sum(bool(row["correct"]) for row in rows)
    incorrect = selected - correct
    selected_tasks = len({row["task_id"] for row in rows if row["selected"]})
    gate = manifest["gate"]
    gates = {
        "minimum_unique_loo_safe_outputs": selected
        >= gate["minimum_unique_loo_safe_outputs"],
        "minimum_exact_selected_outputs": correct >= gate["minimum_exact_selected_outputs"],
        "maximum_incorrect_selected_outputs": incorrect
        <= gate["maximum_incorrect_selected_outputs"],
    }
    gates["all_passed"] = all(gates.values())

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = pathlib.Path(
        tempfile.mkdtemp(prefix="typed-object-audit-", dir=out_dir.parent)
    )
    try:
        per_output_path = temporary / "per_output.csv"
        with per_output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        trace_path = temporary / "task_traces.json"
        trace_path.write_text(json.dumps(traces, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        challenge_path = temporary / "challenge_without_test_outputs.json"
        challenge_path.write_text(
            json.dumps(challenges, separators=(",", ":"), sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary_path = temporary / "summary.json"
        summary = {
            "schema_version": 1,
            "experiment_id": manifest["experiment_id"],
            "hypothesis": manifest["hypothesis"],
            "single_changed_factor": manifest["single_changed_factor"],
            "candidate_family": manifest["candidate_family"],
            "data_split": f"implementation-sealed grouped fold {manifest['audit_fold']} exclusions",
            "public_leaderboard_used_for_selection": False,
            "tasks": manifest["audit"]["task_count"],
            "outputs": len(rows),
            "selected_tasks": selected_tasks,
            "unique_loo_safe_outputs": selected,
            "exact_selected_outputs": correct,
            "incorrect_selected_outputs": incorrect,
            "coverage": selected / len(rows),
            "direct_precision": correct / selected if selected else None,
            "wall_seconds": wall_seconds,
            "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "started_at": started_at,
            "completed_at": completed_at,
            "gates": gates,
            "claim_boundary": manifest["audit"]["scoring_boundary"],
        }
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifact_manifest = {
            "summary_sha256": sha256(summary_path),
            "per_output_sha256": sha256(per_output_path),
            "task_traces_sha256": sha256(trace_path),
            "challenge_without_test_outputs_sha256": sha256(challenge_path),
        }
        artifact_manifest_path = temporary / "artifact_manifest.json"
        artifact_manifest_path.write_text(
            json.dumps(artifact_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, out_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    receipt = {
        **summary,
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256(manifest_path),
        "solver_path": solver_path.relative_to(ROOT).as_posix(),
        "solver_sha256": sha256(solver_path),
        "runner_path": pathlib.Path(__file__).resolve().relative_to(ROOT).as_posix(),
        "runner_sha256": sha256(pathlib.Path(__file__).resolve()),
        "artifacts": {
            key: value
            for key, value in json.loads(
                (out_dir / "artifact_manifest.json").read_text(encoding="utf-8")
            ).items()
        },
        "artifact_manifest_sha256": sha256(out_dir / "artifact_manifest.json"),
        "interpretation": (
            "prospective implementation audit of an independent candidate family; "
            "not development-stage, sealed-holdout, public-evaluation, or Kaggle evidence"
        ),
    }
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=receipt_path.parent,
        prefix=f".{receipt_path.name}.",
        suffix=".tmp",
        encoding="utf-8",
        delete=False,
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temporary_receipt = pathlib.Path(handle.name)
    os.replace(temporary_receipt, receipt_path)
    print(json.dumps({**summary, "receipt_sha256": sha256(receipt_path)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
