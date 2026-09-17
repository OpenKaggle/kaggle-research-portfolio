#!/usr/bin/env python3
"""Audit campaign evidence, lifecycle gates, and information boundaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import resource
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from evidence_registry import register_readiness
from lifecycle_policy_audit import (
    experiment_policy_violations,
    parse_milestones,
    submission_policy_violations,
)
from system_implementation_manifest_audit import verify_current_manifest


EXPERIMENT_COLUMNS = [
    "started_at_utc", "experiment", "task", "hypothesis", "only_change",
    "local_evaluator", "local_score", "cross_corridor_summary", "fd_lwr_summary",
    "runtime_seconds", "peak_memory_mb", "submission_path", "sha256",
    "submission_id", "public_score", "status", "conclusion",
]
SUBMISSION_COLUMNS = [
    "submitted_at_utc", "competition", "experiment", "source", "submission_id",
    "filename", "sha256", "public_score", "private_score", "status", "conclusion",
]
MAX_ACTIVATION_AGE_SECONDS = 15 * 60
MAX_ACTIVATION_FUTURE_SKEW_SECONDS = 60


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def lifecycle(as_of: datetime, deadline: datetime) -> tuple[str, dict[str, datetime]]:
    if as_of.tzinfo is None or deadline.tzinfo is None:
        raise ValueError("lifecycle datetimes must be timezone-aware")
    gates = {
        "D30": deadline - timedelta(days=30),
        "D14": deadline - timedelta(days=14),
        "D7": deadline - timedelta(days=7),
        "D3": deadline - timedelta(days=3),
        "deadline": deadline,
    }
    if as_of < gates["D30"]:
        phase = "RESEARCH_BEFORE_D30"
    elif as_of < gates["D14"]:
        phase = "D30_BASELINES_COMPLETE"
    elif as_of < gates["D7"]:
        phase = "D14_CANDIDATE_FROZEN"
    elif as_of < gates["D3"]:
        phase = "D7_REPRODUCTION_ONLY"
    elif as_of < deadline:
        phase = "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"
    else:
        phase = "CLOSED"
    return phase, gates


def next_checkpoint(as_of: datetime, gates: dict[str, datetime]) -> str | None:
    for name in ("D30", "D14", "D7", "D3", "deadline"):
        if as_of < gates[name]:
            return gates[name].isoformat()
    return None


def _git_head(repo: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def validate_activation_timestamp(as_of: datetime, now: datetime) -> float:
    if as_of.tzinfo is None or now.tzinfo is None:
        raise ValueError("readiness activation requires timezone-aware datetimes")
    age = (now.astimezone(timezone.utc) - as_of.astimezone(timezone.utc)).total_seconds()
    if age < -MAX_ACTIVATION_FUTURE_SKEW_SECONDS:
        raise ValueError("cannot activate a readiness audit from a future simulated timestamp")
    if age > MAX_ACTIVATION_AGE_SECONDS:
        raise ValueError("cannot activate a stale readiness audit")
    return age


def _csv_rows(path: Path, expected: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        problems = [] if reader.fieldnames == expected else [
            f"header mismatch: expected {expected}, got {reader.fieldnames}"
        ]
        rows = list(reader)
    return rows, problems


def timestamps_monotonic(rows: list[dict[str, str]], column: str) -> bool:
    try:
        timestamps = [
            datetime.fromisoformat(row[column].replace("Z", "+00:00")) for row in rows
        ]
    except (KeyError, ValueError):
        return False
    return all(value.tzinfo is not None for value in timestamps) and timestamps == sorted(timestamps)


def readiness_status(checks: list[dict[str, object]], phase: str) -> str:
    failures = [row for row in checks if row["status"] == "FAIL"]
    warnings = [row for row in checks if row["status"] == "WARN"]
    if not failures:
        return "READY_WITH_DOCUMENTED_LEGACY_GAPS" if warnings else "READY"
    if (
        phase == "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"
        and len(failures) == 1
        and failures[0]["requirement"] == "D3_final_selection_control"
        and not warnings
    ):
        return "READY_FOR_FINAL_SELECTION"
    return "FAIL"


def run(
    traffic_root: Path,
    release: Path,
    as_of: datetime,
    output_root: Path,
    verify_archive: bool = False,
    activate: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    receipt_path = output_root / "campaign_readiness_receipt.json"
    if receipt_path.exists():
        if not activate:
            raise ValueError("output root already contains a readiness receipt; use a new path")
        existing = json.loads(receipt_path.read_text())
        register_readiness(traffic_root, receipt_path)
        print(json.dumps(existing, indent=2))
        return existing
    live_now = now or datetime.now(timezone.utc)
    activation_age_seconds = validate_activation_timestamp(as_of, live_now) if activate else None
    artifacts = traffic_root / "artifacts"
    status_path = artifacts / "campaign_status.json"
    status = json.loads(status_path.read_text())
    freeze_path = traffic_root / "config" / "current_best_freeze_v1.json"
    freeze = json.loads(freeze_path.read_text())
    phase, gates = lifecycle(as_of, datetime.fromisoformat(status["deadline_asia_shanghai"]))
    checks: list[dict[str, object]] = []

    def check(requirement: str, passed: bool, evidence: str, *, warning: bool = False) -> None:
        checks.append(
            {
                "requirement": requirement,
                "status": "PASS" if passed else ("WARN" if warning else "FAIL"),
                "evidence": evidence,
            }
        )

    release_receipt_path = artifacts / "public_release_audit.json"
    release_receipt = json.loads(release_receipt_path.read_text())
    key_path = release / "submission_key.csv"
    check(
        "public_release_download_and_integrity",
        release_receipt["status"] == "VALID"
        and release_receipt["files"] == 9698
        and len(release_receipt["panels"]) == 10
        and release_receipt["errors"] == []
        and _sha256(key_path) == status["public_release"]["submission_key_sha256"],
        "9,698 files; 10 panels; zero audit errors; current submission-key SHA matches",
    )
    archive = traffic_root / "data" / "2026-ieee-big-data-traffic-flow-bench.zip"
    actual_archive_sha = _sha256(archive) if verify_archive and archive.is_file() else None
    check(
        "public_archive_receipt",
        archive.is_file()
        and archive.stat().st_size == 9560138439
        and (
            actual_archive_sha == status["public_release"]["archive_sha256"]
            if verify_archive
            else len(status["public_release"]["archive_sha256"]) == 64
        ),
        f"archive bytes={archive.stat().st_size if archive.exists() else None}; "
        f"expected SHA={status['public_release']['archive_sha256']}; "
        f"verified-now SHA={actual_archive_sha}",
    )
    official_head = _git_head(traffic_root / "official")
    check(
        "official_code_pin",
        official_head == freeze["official_code_commit"],
        f"local HEAD={official_head}; frozen HEAD={freeze['official_code_commit']}",
    )
    runtime_state = status["runtime_environment"]
    runtime_path = traffic_root / runtime_state["receipt_path"]
    runtime_receipt = json.loads(runtime_path.read_text())
    check(
        "pinned_runtime_environment",
        runtime_receipt["status"] == "VALID"
        and runtime_receipt["errors"] == []
        and runtime_receipt["entrypoint_commands_verified"] == 11
        and runtime_receipt["capabilities_passed"] == 7
        and runtime_receipt["capabilities_failed"] == 0
        and runtime_receipt["unittests_passed"] >= 64
        and not any(runtime_receipt["information_boundary"].values())
        and _sha256(runtime_path) == runtime_state["receipt_sha256"]
        and _sha256(traffic_root / "requirements.lock")
        == runtime_receipt["inputs"]["requirements.lock"]
        and _sha256(traffic_root / "run.py") == runtime_receipt["inputs"]["run.py"]
        and _sha256(traffic_root / "src" / "runtime_environment_audit.py")
        == runtime_receipt["inputs"]["src/runtime_environment_audit.py"],
        "Python package closure numerical backend eleven entry points and seven runtime capabilities are pinned",
    )

    manifest_state = status["system_implementation_manifest"]
    manifest_path = traffic_root / manifest_state["receipt_path"]
    manifest_receipt = json.loads(manifest_path.read_text())
    manifest_drift = verify_current_manifest(traffic_root, manifest_path)
    check(
        "system_implementation_and_evidence_manifest",
        manifest_receipt["status"] == "VALID"
        and manifest_receipt["errors"] == []
        and manifest_receipt["files_hashed"] == 87
        and manifest_receipt["canonical_receipts_verified"] == 15
        and not any(manifest_receipt["information_boundary"].values())
        and manifest_drift == []
        and _sha256(manifest_path) == manifest_state["receipt_sha256"]
        and manifest_receipt["outputs"]["system_implementation_manifest.csv"]
        == manifest_state["manifest_sha256"],
        "87 implementation and evidence files are SHA-pinned and match the current closed path set",
    )

    anchor_manifest_path = artifacts / "v32_public_anchor_manifest.json"
    anchor_manifest = json.loads(anchor_manifest_path.read_text())
    anchor_path = traffic_root / anchor_manifest["submission_path"].removeprefix("traffic/")
    anchor_validation = json.loads((artifacts / "v32_public_anchor_validation.json").read_text())
    check(
        "v32_schema_integrity_anchor",
        anchor_validation["status"] == "VALID"
        and anchor_validation["rows"] == 6985307
        and _sha256(anchor_path) == anchor_manifest["submission_sha256"],
        "6,985,307 rows; contiguous official schema; artifact SHA matches pinned manifest",
    )

    experiment_rows, experiment_problems = _csv_rows(
        artifacts / "experiment_ledger.csv", EXPERIMENT_COLUMNS
    )
    submission_rows, submission_problems = _csv_rows(
        artifacts / "submission_ledger.csv", SUBMISSION_COLUMNS
    )
    first_id = str(freeze["anchor"]["submission_id"])
    best_id = str(status["current_best"]["submission_id"])
    first_matches = [row for row in submission_rows if row["submission_id"] == first_id]
    best_matches = [row for row in submission_rows if row["submission_id"] == best_id]
    first = first_matches[0] if len(first_matches) == 1 else None
    best = best_matches[0] if len(best_matches) == 1 else None
    check(
        "first_valid_kaggle_receipt",
        bool(
            first
            and first["status"] == "COMPLETE"
            and float(first["public_score"]) == float(status["anchor"]["public_score"])
            and first["sha256"] == freeze["anchor"]["merged_sha256"]
        ),
        f"submission {first_id} COMPLETE at {status['anchor']['public_score']} with frozen artifact SHA",
    )
    check(
        "current_best_kaggle_receipt",
        bool(
            best
            and best["status"] == "COMPLETE"
            and float(best["public_score"]) == float(status["current_best"]["public_score"])
            and best["sha256"] == status["current_best"]["sha256"]
        ),
        f"submission {best_id} COMPLETE at {status['current_best']['public_score']} with current-best SHA",
    )
    attribution_state = status["submission_attribution"]
    attribution_path = traffic_root / attribution_state["receipt_path"]
    attribution = json.loads(attribution_path.read_text())
    check(
        "submission_workflow_and_attribution_chain",
        attribution["status"] == "VALID"
        and attribution["errors"] == []
        and attribution["stages_verified"] == 3
        and attribution["submission_ids"] == [56106600, 56107311, 56108199]
        and attribution["single_task_changes"] == {"queue": 160, "odme": 70708}
        and attribution["public_score_attribution"]["component_gains_close_exactly"] is True
        and attribution["public_score_attribution"]["total_gain"] == "0.02887"
        and _sha256(attribution_path) == attribution_state["receipt_sha256"],
        "three submitted stages verify hypothesis change evaluator whole-table receipt and exact component attribution",
    )
    check(
        "ledger_schema_and_required_text",
        not experiment_problems
        and not submission_problems
        and all(
            all(
                row[column].strip()
                for column in [
                    *EXPERIMENT_COLUMNS[:9],
                    "submission_path", "sha256", "status", "conclusion",
                ]
            )
            for row in experiment_rows
        )
        and all(all(row[column].strip() for column in SUBMISSION_COLUMNS if column != "private_score") for row in submission_rows)
        and timestamps_monotonic(experiment_rows, "started_at_utc")
        and timestamps_monotonic(submission_rows, "submitted_at_utc")
        and len({row["submission_id"] for row in submission_rows}) == len(submission_rows),
        f"{len(experiment_rows)} experiment rows and {len(submission_rows)} unique submission rows; timestamps monotonic",
    )

    candidate_path = traffic_root / status["current_best"]["artifact_path"]
    candidate_sha = _sha256(candidate_path) if candidate_path.is_file() else None
    check(
        "current_best_artifact_integrity",
        bool(
            best
            and candidate_sha == best["sha256"]
            and candidate_sha == status["current_best"]["sha256"]
            and candidate_sha == freeze["current_best"]["expected_sha256"]
        ),
        f"candidate path={status['current_best']['artifact_path']}; verified-now SHA={candidate_sha}",
    )
    fallback_id = str(status["current_candidate"]["fallback_submission_id"])
    fallback_matches = [row for row in submission_rows if row["submission_id"] == fallback_id]
    fallback = fallback_matches[0] if len(fallback_matches) == 1 else None
    fallback_path = traffic_root / status["current_candidate"]["fallback_artifact_path"]
    fallback_sha = _sha256(fallback_path) if fallback_path.is_file() else None
    check(
        "fallback_artifact_integrity",
        bool(
            fallback
            and fallback["status"] == "COMPLETE"
            and fallback_sha == fallback["sha256"]
            and fallback_sha == status["current_candidate"]["parent_sha256"]
        ),
        f"fallback submission={fallback_id}; verified-now SHA={fallback_sha}",
    )
    missing_resource_pairs = {
        (row["experiment"], column)
        for row in experiment_rows
        for column in ("runtime_seconds", "peak_memory_mb")
        if not row[column].strip()
    }
    backfill_path = artifacts / "legacy_resource_replay_v1" / "legacy_resource_replay_receipt.json"
    backfill = json.loads(backfill_path.read_text()) if backfill_path.exists() else None
    covered_resource_pairs = {
        tuple(value.rsplit(":", 1))
        for value in (backfill or {}).get("covered_legacy_fields", [])
    }
    uncovered_resources = sorted(missing_resource_pairs - covered_resource_pairs)
    backfill_valid = bool(
        backfill
        and backfill["status"] == "COMPLETE_REPLAY_BACKFILL"
        and not uncovered_resources
    )
    check(
        "historical_runtime_and_memory_capture",
        not missing_resource_pairs or backfill_valid,
        (
            "all fields captured originally"
            if not missing_resource_pairs
            else f"{len(missing_resource_pairs)} original gaps covered by explicitly labeled deterministic replay evidence"
            if backfill_valid
            else "; ".join(f"{experiment}:{field}" for experiment, field in uncovered_resources)
        ),
        warning=True,
    )

    components = status["component_baselines"]
    state_receipt_path = artifacts / "task1_grouped_v32_frozen_profile_control_v1" / "task1_grouped_v32_control_receipt.json"
    check(
        "D30_state_baseline",
        components["state"]["status"] == "COMPLETE"
        and components["state"]["missing_predictions"] == 0
        and _sha256(state_receipt_path) == components["state"]["receipt_sha256"],
        "all 10 panels and 60 panel-regime groups; official State formula; zero missing predictions",
    )
    queue_receipt = json.loads((artifacts / "queue_offbyone_v1" / "queue_fix_receipt.json").read_text())
    check(
        "D30_queue_baseline",
        queue_receipt["status"] == "VALID"
        and queue_receipt["rows_changed_1_to_0"] == 160
        and any(row["submission_id"] == "56107311" and row["status"] == "COMPLETE" for row in submission_rows),
        "structural Queue baseline plus completed single-task leaderboard receipt; official labels explicitly withheld",
    )
    physics = components["physics_public_diagnostic"]
    check(
        "D30_physics_baseline_and_boundary",
        physics["status"] == "PUBLIC_COMPONENT_ONLY"
        and physics["S_LWR"] is None
        and physics["S_physics"] is None
        and physics["confirmation_S_FD"] > 0.98,
        "public FD branch measured; organizer-only LWR and full Physics remain null",
    )
    odme_receipt = json.loads(
        (artifacts / "odme_lambda_frontier_v1_focused" / "odme_lambda_frontier_receipt.json").read_text()
    )
    check(
        "D30_odme_baseline",
        odme_receipt["decision"] == "LOCAL_FRONTIER_CANDIDATE_EXISTS"
        and odme_receipt["metric_boundary"]["S_od"] is None
        and odme_receipt["metric_boundary"]["S_dev"] is None
        and odme_receipt["metric_boundary"]["S_attr"] is None,
        "lambda=5 nonnegative prior-regularized solver; S_link on 20 panel-splits; hidden metrics remain null",
    )
    four_task_state = status["four_task_baseline_audit"]
    four_task_path = traffic_root / four_task_state["receipt_path"]
    four_task_receipt = json.loads(four_task_path.read_text())
    check(
        "D30_four_task_baseline_contract",
        four_task_receipt["status"] == "VALID"
        and four_task_receipt["errors"] == []
        and four_task_receipt["tasks_verified"] == ["state", "queue", "physics", "odme"]
        and four_task_receipt["coverage"]["state_panel_regime_holdouts"] == 60
        and four_task_receipt["coverage"]["queue_eligible_panel_splits"] == 16
        and four_task_receipt["coverage"]["queue_changed_rows"] == 160
        and four_task_receipt["coverage"]["odme_panel_splits"] == 20
        and four_task_receipt["coverage"]["odme_all_panel_split_gains_positive"] is True
        and not any(four_task_receipt["information_boundary"].values())
        and _sha256(four_task_path) == four_task_state["receipt_sha256"],
        "SHA-bound task matrix plus State 60-group Queue 16-panel-split and ODME 20-panel-split evidence",
    )

    lineage_path = artifacts / "current_best_lineage_audit_v1" / "current_best_lineage_receipt.json"
    lineage = json.loads(lineage_path.read_text())
    replay_path = artifacts / "current_best_full_replay_v1" / "current_best_full_replay_receipt.json"
    replay = json.loads(replay_path.read_text())
    check(
        "D14_candidate_freeze_evidence",
        lineage["status"] == "VALID_FROZEN"
        and lineage["cell_for_cell_lineage"]["state_changed_rows"] == 0
        and _sha256(lineage_path) == status["current_candidate"]["lineage_audit"]["receipt_sha256"],
        "current best lineage is frozen with only Queue and ODME task changes",
    )
    check(
        "D7_full_reproduction",
        replay["status"] == "REPRODUCED_BYTE_IDENTICAL"
        and replay["byte_identical_to_canonical"] is True
        and replay["rebuilt_sha256"] == status["current_best"]["sha256"]
        and _sha256(replay_path) == status["current_candidate"]["full_replay"]["receipt_sha256"],
        f"20 ODME panel-splits and full table replayed in {replay['runtime_seconds']:.2f}s at {replay['peak_memory_mb']:.2f} MB",
    )
    check(
        "no_hidden_label_reconstruction",
        not any(replay["information_boundary"].values())
        and physics["S_LWR"] is None
        and physics["S_physics"] is None
        and odme_receipt["metric_boundary"]["S_od"] is None,
        "freeze config prohibits target truth, Queue labels, boundary flows, and hidden ODME metrics",
    )
    stopped = status["stopped_families"]
    policy_state = status["method_family_policy"]
    policy_path = traffic_root / policy_state["receipt_path"]
    policy_receipt = json.loads(policy_path.read_text())
    check(
        "failure_switch_and_A_group_absorption",
        policy_receipt["status"] == "VALID"
        and policy_receipt["errors"] == []
        and policy_receipt["two_failure_sequences_verified"] == 3
        and policy_receipt["A_group_trigger_failures_verified"] == 3
        and policy_receipt["A_group_absorbed_experiment"] == "task1_nonlinear_residual_ablation_v1"
        and _sha256(policy_path) == policy_state["receipt_sha256"]
        and len(stopped) >= 10
        and status["current_opportunity_audit"]["qualifying_independent_families"] == [],
        "three two-failure switch/freeze sequences and the three-failure A-group absorption are receipt- and SHA-verified",
    )
    lifecycle_state = status["lifecycle_policy"]
    lifecycle_policy_path = traffic_root / lifecycle_state["receipt_path"]
    lifecycle_policy_receipt = json.loads(lifecycle_policy_path.read_text())
    lifecycle_config_path = traffic_root / lifecycle_state["config_path"]
    lifecycle_config = json.loads(lifecycle_config_path.read_text())
    lifecycle_milestones = parse_milestones(lifecycle_config)
    current_experiment_violations = experiment_policy_violations(
        experiment_rows, as_of, lifecycle_milestones, lifecycle_config
    )
    current_submission_violations = submission_policy_violations(
        submission_rows, as_of, lifecycle_milestones, lifecycle_config
    )
    check(
        "lifecycle_deadlines_and_activity_policy",
        lifecycle_policy_receipt["status"] == "VALID"
        and lifecycle_policy_receipt["deadline_evidence_verified"] == 3
        and lifecycle_policy_receipt["post_freeze_experiment_violations"] == []
        and lifecycle_policy_receipt["post_freeze_submission_violations"] == []
        and all(lifecycle_policy_receipt["enforcement_probes"].values())
        and not any(lifecycle_policy_receipt["information_boundary"].values())
        and current_experiment_violations == []
        and current_submission_violations == []
        and _sha256(lifecycle_policy_path) == lifecycle_state["receipt_sha256"]
        and _sha256(lifecycle_config_path) == lifecycle_state["config_sha256"]
        and _sha256(traffic_root / "src" / "lifecycle_policy_audit.py")
        == lifecycle_policy_receipt["inputs"]["src/lifecycle_policy_audit.py"],
        "D30 D14 D7 evidence deadlines pass and the current ledger obeys post-freeze activity rules",
    )

    selection_key = "final_selection" if as_of >= gates["D3"] else "final_selection_preview"
    selection_state = status.get(selection_key, {})
    selection_relpath = selection_state.get("receipt_path")
    selection_path = traffic_root / selection_relpath if selection_relpath else None
    selection_receipt = (
        json.loads(selection_path.read_text())
        if selection_path is not None and selection_path.is_file()
        else None
    )
    selection_sha = _sha256(selection_path) if selection_path is not None and selection_path.is_file() else None
    if as_of < gates["D3"]:
        selection_ok = bool(
            selection_receipt
            and selection_state.get("status") == "PREVIEW_READY_NOT_FINAL"
            and selection_receipt["status"] == "PREVIEW_READY_NOT_FINAL"
            and selection_receipt["selection_final"] is False
            and selection_receipt["external_kaggle_action_performed"] is False
            and selection_receipt["selected"]["submission_id"] == int(best_id)
            and selection_receipt["selected"]["sha256"] == candidate_sha
            and selection_sha == selection_state.get("receipt_sha256")
        )
        selection_evidence = (
            f"pre-D3 selector preview verified; receipt SHA={selection_sha}; final selection remains false"
        )
    else:
        selection_ok = bool(
            selection_receipt
            and selection_state.get("status") == "FINAL_SELECTED"
            and selection_receipt["status"] == "FINAL_SELECTED"
            and selection_receipt["selection_final"] is True
            and gates["D3"] <= datetime.fromisoformat(selection_receipt["as_of"]) < gates["deadline"]
            and selection_receipt["selected"]["submission_id"] == int(best_id)
            and selection_receipt["selected"]["sha256"] == candidate_sha
            and selection_sha == selection_state.get("receipt_sha256")
        )
        selection_evidence = f"D3 final-selection receipt SHA={selection_sha}"
    check("D3_final_selection_control", selection_ok, selection_evidence)

    failures = [row for row in checks if row["status"] == "FAIL"]
    warnings = [row for row in checks if row["status"] == "WARN"]
    overall_status = readiness_status(checks, phase)
    output_root.mkdir(parents=True, exist_ok=True)
    checklist_path = output_root / "campaign_readiness_checklist.csv"
    with checklist_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["requirement", "status", "evidence"])
        writer.writeheader()
        writer.writerows(checks)
    receipt: dict[str, object] = {
        "status": overall_status,
        "experiment": (
            output_root.name
            if output_root.name.startswith("campaign_readiness_audit_")
            else "campaign_readiness_audit"
        ),
        "as_of": as_of.isoformat(),
        "executed_at_utc": live_now.astimezone(timezone.utc).isoformat(),
        "phase": phase,
        "deadline": status["deadline_asia_shanghai"],
        "milestones": {name: value.isoformat() for name, value in gates.items()},
        "checks_passed": sum(row["status"] == "PASS" for row in checks),
        "checks_warned": len(warnings),
        "checks_failed": len(failures),
        "warnings": warnings,
        "failures": failures,
        "goal_complete": False,
        "goal_completion_boundary": (
            "All preselection controls pass; perform the live-clock-gated final selection and rerun this audit."
            if overall_status == "READY_FOR_FINAL_SELECTION"
            else "Final candidate selection and deadline-phase controls are time-dependent and not yet due; this receipt proves current readiness, not final competition completion."
        ),
        "next_checkpoint": next_checkpoint(as_of, gates),
        "archive_sha_verified_now": verify_archive,
        "activation": {
            "requested": activate,
            "max_as_of_age_seconds": MAX_ACTIVATION_AGE_SECONDS,
            "max_future_skew_seconds": MAX_ACTIVATION_FUTURE_SKEW_SECONDS,
            "observed_as_of_age_seconds": activation_age_seconds,
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {
            "campaign_status.json": _sha256(status_path),
            "experiment_ledger.csv": _sha256(artifacts / "experiment_ledger.csv"),
            "submission_ledger.csv": _sha256(artifacts / "submission_ledger.csv"),
            "current_best_freeze_v1.json": _sha256(freeze_path),
            **({"legacy_resource_replay_receipt.json": _sha256(backfill_path)} if backfill else {}),
        },
        "outputs": {"campaign_readiness_checklist.csv": _sha256(checklist_path)},
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    if activate:
        register_readiness(traffic_root, receipt_path)
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-archive", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    run(
        args.traffic_root.resolve(), args.release_root.resolve(), args.as_of,
        args.output_root.resolve(), args.verify_archive, args.activate,
    )


if __name__ == "__main__":
    main()
