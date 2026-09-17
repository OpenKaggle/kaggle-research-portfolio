#!/usr/bin/env python3
"""Audit the full hypothesis-to-receipt attribution chain for submitted artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import resource
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


WORKFLOW_TEXT_COLUMNS = [
    "hypothesis", "only_change", "local_evaluator", "local_score",
    "cross_corridor_summary", "fd_lwr_summary", "conclusion",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def nested_value(document: dict[str, object], path: list[str]) -> object:
    value: object = document
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(path))
        value = value[key]
    return value


def exact_gain(parent: str, child: str) -> str:
    return f"{Decimal(child) - Decimal(parent):.5f}"


def run(traffic_root: Path, config_path: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    receipt_path = output_root / "submission_attribution_receipt.json"
    if receipt_path.exists():
        raise ValueError("output root already contains a submission attribution receipt")
    config = json.loads(config_path.read_text())
    artifacts = traffic_root / "artifacts"
    experiment_ledger_path = artifacts / "experiment_ledger.csv"
    submission_ledger_path = artifacts / "submission_ledger.csv"
    with experiment_ledger_path.open(newline="", encoding="utf-8") as handle:
        experiment_rows = list(csv.DictReader(handle))
    with submission_ledger_path.open(newline="", encoding="utf-8") as handle:
        submission_rows = list(csv.DictReader(handle))
    backfill_path = artifacts / "legacy_resource_replay_v1" / "legacy_resource_replay_receipt.json"
    backfill = json.loads(backfill_path.read_text())
    covered_resource_fields = set(backfill["covered_legacy_fields"])
    backfill_measurements = {
        measurement["experiment"]: measurement for measurement in backfill["measurements"]
    }
    experiments = {row["experiment"]: row for row in experiment_rows}
    submissions = {int(row["submission_id"]): row for row in submission_rows}

    errors: list[str] = []
    stage_rows: list[dict[str, object]] = []
    input_hashes: dict[str, str] = {
        "submission_attribution_chain_v1.json": _sha256(config_path),
        "experiment_ledger.csv": _sha256(experiment_ledger_path),
        "submission_ledger.csv": _sha256(submission_ledger_path),
        "legacy_resource_replay_receipt.json": _sha256(backfill_path),
    }
    stages = sorted(config["stages"], key=lambda stage: stage["order"])
    if [stage["order"] for stage in stages] != list(range(1, len(stages) + 1)):
        errors.append("stage order is not contiguous")
    if len(submission_rows) != len(stages):
        errors.append("submission ledger contains rows outside the declared attribution chain")

    score_by_id: dict[int, str] = {}
    for stage in stages:
        name = stage["experiment"]
        submission_id = int(stage["submission_id"])
        experiment = experiments.get(name)
        submission = submissions.get(submission_id)
        if experiment is None:
            errors.append(f"{name}: experiment ledger row missing")
            continue
        if submission is None:
            errors.append(f"{name}: Kaggle submission receipt missing")
            continue
        if any(not experiment[column].strip() for column in WORKFLOW_TEXT_COLUMNS):
            errors.append(f"{name}: workflow text field missing")
        missing_resources = [
            field for field in ("runtime_seconds", "peak_memory_mb")
            if not experiment[field].strip()
        ]
        resource_mode = "ORIGINAL"
        if missing_resources:
            resource_mode = "DETERMINISTIC_REPLAY_BACKFILL"
            if backfill["status"] != "COMPLETE_REPLAY_BACKFILL" or not all(
                f"{name}:{field}" in covered_resource_fields for field in missing_resources
            ):
                errors.append(f"{name}: runtime or memory evidence missing")
            measurement = backfill_measurements.get(name)
            if not measurement or measurement.get("replay_output_sha256") != stage["artifact_sha256"]:
                errors.append(f"{name}: resource backfill does not reproduce the submission artifact")
        if (
            experiment["sha256"] != stage["artifact_sha256"]
            or experiment["submission_id"] != str(submission_id)
            or Decimal(experiment["public_score"]) != Decimal(stage["public_score"])
        ):
            errors.append(f"{name}: experiment-ledger submission attribution mismatch")
        if (
            submission["experiment"] != name
            or submission["status"] != "COMPLETE"
            or submission["sha256"] != stage["artifact_sha256"]
            or Decimal(submission["public_score"]) != Decimal(stage["public_score"])
            or submission["private_score"].strip()
        ):
            errors.append(f"{name}: Kaggle receipt mismatch or private score unexpectedly populated")

        artifact_path = traffic_root / stage["artifact_path"]
        artifact_sha = _sha256(artifact_path) if artifact_path.is_file() else None
        if artifact_sha != stage["artifact_sha256"]:
            errors.append(f"{name}: submission artifact SHA mismatch")
        input_hashes[stage["artifact_path"]] = artifact_sha or "MISSING"

        validation_path = traffic_root / stage["validation_path"]
        validation_sha = _sha256(validation_path) if validation_path.is_file() else None
        if validation_sha != stage["validation_sha256"]:
            errors.append(f"{name}: validation receipt SHA mismatch")
        else:
            validation = json.loads(validation_path.read_text())
            if (
                validation["status"] != "VALID"
                or validation["key_checked"] is not True
                or validation["rows"] != config["expected_whole_table_rows"]
                or validation["task_rows"] != config["expected_task_rows"]
            ):
                errors.append(f"{name}: whole-table validation contract failed")
        input_hashes[stage["validation_path"]] = validation_sha or "MISSING"

        for local in stage["local_evidence"]:
            local_path = traffic_root / local["path"]
            local_sha = _sha256(local_path) if local_path.is_file() else None
            input_hashes[local["path"]] = local_sha or "MISSING"
            if local_sha != local["sha256"]:
                errors.append(f"{name}: local evaluator receipt SHA mismatch")
                continue
            evidence = json.loads(local_path.read_text())
            if evidence.get("status") != local["status"] or evidence.get("decision") != local["decision"]:
                errors.append(f"{name}: local evaluator status or decision mismatch")
            hidden_paths = []
            if local.get("hidden_metric_path"):
                hidden_paths.append(local["hidden_metric_path"])
            hidden_paths.extend(local.get("hidden_metric_paths", []))
            for hidden_path in hidden_paths:
                if nested_value(evidence, hidden_path) is not None:
                    errors.append(f"{name}: hidden metric {'.'.join(hidden_path)} is populated")

        parent_id = stage["parent_submission_id"]
        gain = None
        if parent_id is not None:
            if int(parent_id) not in score_by_id:
                errors.append(f"{name}: parent is not an earlier verified stage")
            else:
                gain = exact_gain(score_by_id[int(parent_id)], stage["public_score"])
                if gain != stage["public_gain_from_parent"]:
                    errors.append(f"{name}: public gain does not close exactly")
            diff_path = traffic_root / stage["diff_path"]
            diff_sha = _sha256(diff_path) if diff_path.is_file() else None
            input_hashes[stage["diff_path"]] = diff_sha or "MISSING"
            if diff_sha != stage["diff_sha256"]:
                errors.append(f"{name}: whole-table diff SHA mismatch")
            else:
                diff = json.loads(diff_path.read_text())
                if (
                    diff["status"] != "VALID"
                    or diff["rows_compared"] != config["expected_whole_table_rows"]
                    or diff["changed_rows"] != stage["expected_changed_rows"]
                    or diff["changed_rows_by_task"] != {stage["changed_task"]: stage["expected_changed_rows"]}
                    or diff["changed_cells_by_column"] != stage["expected_changed_cells"]
                ):
                    errors.append(f"{name}: single-task whole-table diff contract failed")

        score_by_id[submission_id] = stage["public_score"]
        stage_rows.append({
            "order": stage["order"],
            "experiment": name,
            "submission_id": submission_id,
            "parent_submission_id": parent_id if parent_id is not None else "",
            "changed_task": stage["changed_task"] or "anchor",
            "changed_rows": stage["expected_changed_rows"] if parent_id is not None else 0,
            "artifact_sha256": artifact_sha,
            "public_score": stage["public_score"],
            "public_gain_from_parent": gain or "",
            "whole_table_valid": validation_sha == stage["validation_sha256"],
            "kaggle_receipt_complete": submission["status"] == "COMPLETE",
            "resource_evidence": resource_mode,
        })

    if stages:
        total_gain = exact_gain(stages[0]["public_score"], stages[-1]["public_score"])
        component_gain_sum = sum(
            (Decimal(stage["public_gain_from_parent"]) for stage in stages if stage["parent_submission_id"] is not None),
            Decimal("0"),
        )
        if total_gain != config["expected_total_public_gain"] or component_gain_sum != Decimal(total_gain):
            errors.append("component gains do not close to the total public-score gain")
    else:
        total_gain = None
        errors.append("attribution chain has no stages")
    if any(config["information_boundary"].values()):
        errors.append("attribution config permits hidden information")

    output_root.mkdir(parents=True, exist_ok=True)
    stage_path = output_root / "submission_attribution_stages.csv"
    with stage_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "order", "experiment", "submission_id", "parent_submission_id", "changed_task",
            "changed_rows", "artifact_sha256", "public_score", "public_gain_from_parent",
            "whole_table_valid", "kaggle_receipt_complete",
            "resource_evidence",
        ])
        writer.writeheader()
        writer.writerows(stage_rows)
    receipt: dict[str, object] = {
        "status": "VALID" if not errors else "FAIL",
        "experiment": "submission_attribution_audit_v1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "stages_verified": len(stage_rows),
        "submission_ids": [row["submission_id"] for row in stage_rows],
        "single_task_changes": {
            row["changed_task"]: row["changed_rows"]
            for row in stage_rows if row["changed_task"] != "anchor"
        },
        "public_score_attribution": {
            "anchor": stages[0]["public_score"],
            "queue_gain": stages[1]["public_gain_from_parent"],
            "odme_gain": stages[2]["public_gain_from_parent"],
            "current_best": stages[-1]["public_score"],
            "total_gain": total_gain,
            "component_gains_close_exactly": not errors and component_gain_sum == Decimal(total_gain),
        },
        "workflow_steps_verified_per_submitted_stage": [
            "hypothesis", "single_task_change_or_anchor", "local_evaluator",
            "whole_table_validation", "kaggle_receipt", "component_attribution",
        ],
        "errors": errors,
        "information_boundary": {
            "private_scores_used": False,
            "hidden_queue_truth_used": False,
            "organizer_boundary_flows_used": False,
            "hidden_odme_metrics_used": False,
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": input_hashes,
        "outputs": {"submission_attribution_stages.csv": _sha256(stage_path)},
        "decision": "ATTRIBUTION_CHAIN_CLOSED" if not errors else "ATTRIBUTION_CHAIN_INVALID",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    if errors:
        raise SystemExit(1)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "submission_attribution_chain_v1.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.traffic_root.resolve(), args.config.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
