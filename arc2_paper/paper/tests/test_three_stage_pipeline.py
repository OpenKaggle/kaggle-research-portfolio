#!/usr/bin/env python3
"""Positive and fail-closed checks for the three-stage pipeline auditor."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from paper.tools.audit_three_stage_pipeline import audit


BUCKETS = ("geometry", "object", "color", "topology", "counting", "composition", "search")
GOOD_HASH = "a" * 64
AUTH_ACTIONS = {
    "private_development": "KAGGLE_RUN_PRIVATE_DEVELOPMENT_ONCE_AND_READ_TERMINAL_ARTIFACTS",
    "sealed_holdout": "KAGGLE_RUN_SEALED_HOLDOUT_ONCE_AND_READ_TERMINAL_ARTIFACTS",
    "competition_rerun": "KAGGLE_RERUN_SUBMIT_FROZEN_NOTEBOOK_ONCE_AND_READ_RECEIPT",
}


def write_json(path: pathlib.Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: pathlib.Path, root: pathlib.Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}


def normalized_receipt(
    stage: str,
    completed_at: str,
    notebook_sha256: str = GOOD_HASH,
) -> dict:
    gates = {"all_passed": True}
    if stage == "private_development":
        gates["promote_to_holdout"] = True
    if stage == "sealed_holdout":
        gates["non_degradation_vs_anchor"] = True
    metrics = {
        "tasks": 10,
        "outputs": 10,
        "local_labels_available": True,
        "method_exact_outputs": 8,
        "anchor_exact_outputs": 7,
        "attempt_1_exact_outputs": 6,
        "attempt_2_incremental_outputs": 2,
        "method_accuracy": 0.8,
        "anchor_accuracy": 0.7,
        "delta_vs_anchor": 0.1,
    }
    family_task_counts = (2, 2, 2, 1, 1, 1, 1)
    family_coverage = {
        bucket: {
            "correctness_available": True,
            "tasks": family_task_counts[index],
            "method_solved": family_task_counts[index],
            "anchor_solved": max(0, family_task_counts[index] - 1),
            "delta": int(family_task_counts[index] > 0),
            "failed_tasks": 0,
        }
        for index, bucket in enumerate(BUCKETS)
    }
    if stage == "competition_rerun":
        metrics.update(
            {
                "local_labels_available": False,
                "method_exact_outputs": None,
                "anchor_exact_outputs": None,
                "attempt_1_exact_outputs": None,
                "attempt_2_incremental_outputs": None,
                "method_accuracy": None,
                "anchor_accuracy": None,
                "delta_vs_anchor": None,
            }
        )
        family_coverage = {
            bucket: {
                "correctness_available": False,
                "tasks": family_task_counts[index],
                "method_solved": None,
                "anchor_solved": None,
                "delta": None,
                "failed_tasks": 0,
            }
            for index, bucket in enumerate(BUCKETS)
        }
    receipt = {
        "schema_version": 1,
        "stage": stage,
        "candidate_id": "candidate-v1",
        "experiment_id": f"experiment-{stage}",
        "hypothesis": "The frozen candidate improves or preserves its anchor.",
        "single_changed_factor": "data split only",
        "data_split": stage,
        "authoritative_status": "COMPLETE",
        "public_leaderboard_used_for_selection": False,
        "started_at": {
            "private_development": "2026-09-09T00:41:00+00:00",
            "sealed_holdout": "2026-09-09T01:31:00+00:00",
            "competition_rerun": "2026-09-09T02:31:00+00:00",
        }[stage],
        "completed_at": completed_at,
        "metrics": metrics,
        "family_coverage": family_coverage,
        "runtime": {
            "wall_seconds": 100,
            "peak_memory_mb": 1024,
            "failed_tasks": 0,
            "failure_rate": 0.0,
            "timed_out_task_ids": [],
        },
        "submission_format": {
            "validated": True,
            "task_keys_exact": True,
            "output_counts_exact": True,
            "exactly_two_attempts": True,
            "rectangular_grids": True,
            "dimensions_1_to_30": True,
            "colors_0_to_9": True,
        },
        "artifacts": {
            "notebook_sha256": notebook_sha256,
            "input_manifest_sha256": GOOD_HASH,
            "submission_sha256": GOOD_HASH,
            "artifact_manifest_sha256": GOOD_HASH,
        },
        "gates": gates,
    }
    if stage == "competition_rerun":
        receipt["kaggle"] = {
            "submission_id": "123456",
            "leaderboard_score": 0.42,
            "submission_status": "complete",
            "score_scope": "public_leaderboard",
            "notebook_version": 1,
            "kernel_slug": "owner/kernel",
            "score_observed_at": "2026-09-09T03:05:00+00:00",
            "submission_receipt_sha256": GOOD_HASH,
            "reference_name": "ARC Prize 85% target",
            "reference_score": 0.85,
            "reference_scope": "private_evaluation_target",
            "delta_vs_reference": -0.43,
            "reference_receipt_sha256": GOOD_HASH,
        }
    return receipt


def build_complete_contract(root: pathlib.Path) -> tuple[pathlib.Path, dict, dict[str, pathlib.Path]]:
    deadline = root / "deadline.json"
    write_json(deadline, {"date": "2026-11-02"})
    schema = root / "stage_receipt.schema.json"
    write_json(schema, {"fixture": "stage receipt schema"})
    failure_schema = root / "stage_failure_receipt.schema.json"
    write_json(failure_schema, {"fixture": "stage failure receipt schema"})
    measurement_builder = root / "build_stage_measurement.py"
    measurement_builder.write_bytes(
        (PROJECT_ROOT / "paper/tools/build_stage_measurement.py").read_bytes()
    )
    competition_observation_schema = root / "competition_observation.schema.json"
    competition_observation_schema.write_bytes(
        (PROJECT_ROOT / "paper/schemas/competition_observation_v1.schema.json").read_bytes()
    )
    stage_authorization_schema = root / "stage_authorization.schema.json"
    stage_authorization_schema.write_bytes(
        (PROJECT_ROOT / "paper/schemas/stage_authorization_v1.schema.json").read_bytes()
    )
    stage_authorizer = root / "authorize_stage.py"
    stage_authorizer.write_bytes(
        (PROJECT_ROOT / "paper/tools/authorize_stage.py").read_bytes()
    )
    smoke_notebook = root / "runtime_smoke.ipynb"
    smoke_notebook.write_text("{}\n", encoding="utf-8")
    smoke_metadata = root / "runtime_smoke_metadata.json"
    smoke_metadata.write_text("{}\n", encoding="utf-8")
    frozen_run_manifest = root / "last_authorized_run_manifest.json"
    write_json(
        frozen_run_manifest,
        {
            "status": "RUNNING",
            "runtime_sha256": "8ac51e00df2f220ff8742bddceae9a84a407e426734975db2f55234460a48776",
            "parent_runtime_sha256": "17d8757c874f14d20aee0368054137874e8df16f2dd8f0fe9e521d5aff2c9e82",
            "notebook_sha256": sha256(smoke_notebook),
            "kernel_metadata_sha256": sha256(smoke_metadata),
            "artifacts": {
                "notebook": binding(smoke_notebook, root),
                "kernel_metadata": binding(smoke_metadata, root),
            },
        },
    )
    smoke_support = {
        "last_authorized_run_manifest": binding(frozen_run_manifest, root)
    }
    for name in (
        "local_only_boundary_receipt",
        "local_behavioral_receipt",
        "local_micro_smoke_receipt",
    ):
        path = root / f"{name}.json"
        write_json(path, {"fixture": name})
        smoke_support[name] = binding(path, root)

    holdout_integrity_receipt = root / "holdout_integrity.json"
    holdout_integrity_claim = (
        "Synthetic fixture proving the clear-state contract path only."
    )
    clear_integrity_provenance = {}
    for name in (
        "candidate_preregistration",
        "holdout_manifest",
        "integrity_audit",
    ):
        path = root / f"{name}.json"
        write_json(path, {"fixture": name})
        clear_integrity_provenance[name] = binding(path, root)
    write_json(
        holdout_integrity_receipt,
        {
            "schema_version": 1,
            "result_type": "historical_holdout_integrity_audit",
            "candidate_id": "candidate-v1",
            "audit_status": "CLEAR_FOR_METHOD_GENERALIZATION",
            "decision": "ALLOW_HOLDOUT_PROMOTION",
            "external_actions_performed": False,
            "holdout_solutions_read_by_this_audit": False,
            "holdout_task_ids_disclosed": False,
            "historical_facts": {
                "independent_labeled_corpus": True,
                "solutions_unavailable_during_method_construction": True,
                "method_frozen_before_solution_access": True,
            },
            "derived_holdout": {
                "tasks": 10,
                "outputs": 10,
                "disjoint_from_development": True,
                "method_behavior_known_before_holdout_run": False,
            },
            "provenance": clear_integrity_provenance,
            "permitted_claims": [
                "prospective method-generalization evidence after one authorized run"
            ],
            "forbidden_claims": ["policy tuning from holdout results"],
            "claim_boundary": holdout_integrity_claim,
        },
    )

    terminal_observation = root / "terminal_run_manifest.json"
    write_json(
        terminal_observation,
        {
            "schema_version": 1,
            "kernel": "jahyee/arc2-trm-wandb-log-compat-smoke-v2",
            "kernel_version": 1,
            "authoritative_kernel_status": "COMPLETE",
            "status_verified_at_cst": "2026-09-09T00:30:00+00:00",
            "observation_mode": "READ_ONLY_KAGGLE_STATUS",
            "raw_status": 'status "complete"',
            "artifacts_downloaded": True,
        },
    )
    smoke_log = root / "trm-smoke.log"
    smoke_log.write_text("Loading checkpoint\nstep 1 complete\n", encoding="utf-8")
    smoke_submission = root / "trm_submission.json"
    smoke_submission.write_text(
        json.dumps({"bc1d5164": [{"attempt_1": [[1]], "attempt_2": [[2]]}]}) + "\n",
        encoding="utf-8",
    )
    smoke_guards = {
        "runtime_returncode_zero": True,
        "checkpoint_loaded": True,
        "optimizer_constructed": True,
        "scheduler_path_preserved": True,
        "first_step_checkpoint_saved": True,
        "submission_exists": True,
        "submission_schema_valid": True,
    }
    source_smoke_receipt = root / "trm-smoke-receipt.json"
    write_json(
        source_smoke_receipt,
        {
            "purpose": "runtime compatibility smoke; not an accuracy experiment",
            "repair_id": "offline_wandb_stdout_helper_v2",
            "single_change": "offline logger helper only",
            "task_id": "bc1d5164",
            "task_count": 1,
            "epochs": 1,
            "expected_optimizer_steps": 1,
            "runtime_sha256": "8ac51e00df2f220ff8742bddceae9a84a407e426734975db2f55234460a48776",
            "parent_runtime_sha256": "17d8757c874f14d20aee0368054137874e8df16f2dd8f0fe9e521d5aff2c9e82",
            "challenge_sha256": GOOD_HASH,
            "submission_sha256": sha256(smoke_submission),
            "elapsed_seconds": 42.5,
            "returncode": 0,
            "guards": smoke_guards,
            "all_guards_passed": True,
        },
    )
    terminal = root / "runtime_smoke_terminal.json"
    write_json(
        terminal,
        {
            "schema_version": 1,
            "artifact_status": "terminal_runtime_smoke",
            "kernel": "jahyee/arc2-trm-wandb-log-compat-smoke-v2",
            "kernel_version": 1,
            "authoritative_kernel_status": "COMPLETE",
            "status_verified_at_cst": "2026-09-09T00:30:00+00:00",
            "is_private": True,
            "internet_enabled": False,
            "data_boundary": "one frozen public-training challenge; solutions never read",
            "purpose": "runtime compatibility smoke; not an accuracy experiment",
            "task_id": "bc1d5164",
            "task_count": 1,
            "epochs": 1,
            "expected_optimizer_steps": 1,
            "runtime_sha256": "8ac51e00df2f220ff8742bddceae9a84a407e426734975db2f55234460a48776",
            "parent_runtime_sha256": "17d8757c874f14d20aee0368054137874e8df16f2dd8f0fe9e521d5aff2c9e82",
            "elapsed_seconds": 42.5,
            "returncode": 0,
            "guards": {**smoke_guards, "all_guards_passed": True},
            "source_artifacts": {
                "run_manifest.json": sha256(terminal_observation),
                "trm-smoke-receipt.json": sha256(source_smoke_receipt),
                "trm-smoke.log": sha256(smoke_log),
                "trm_submission.json": sha256(smoke_submission),
                "notebook_sha256": sha256(smoke_notebook),
                "kernel_metadata_sha256": sha256(smoke_metadata),
            },
            "source_paths": {
                "run_manifest.json": terminal_observation.relative_to(root).as_posix(),
                "trm-smoke-receipt.json": source_smoke_receipt.relative_to(root).as_posix(),
                "trm-smoke.log": smoke_log.relative_to(root).as_posix(),
                "trm_submission.json": smoke_submission.relative_to(root).as_posix(),
                "notebook_sha256": smoke_notebook.relative_to(root).as_posix(),
                "kernel_metadata_sha256": smoke_metadata.relative_to(root).as_posix(),
            },
            "claim_boundary": "runtime evidence only; not accuracy evidence",
        },
    )
    notebooks: dict[str, pathlib.Path] = {}
    receipts: dict[str, pathlib.Path] = {}
    completed = (
        "2026-09-09T01:00:00+00:00",
        "2026-09-09T02:00:00+00:00",
        "2026-09-09T03:00:00+00:00",
    )
    authorized = (
        "2026-09-09T00:40:00+00:00",
        "2026-09-09T01:30:00+00:00",
        "2026-09-09T02:30:00+00:00",
    )
    stages = {}
    for sequence, (stage, timestamp, authorized_at) in enumerate(zip(
        ("private_development", "sealed_holdout", "competition_rerun"),
        completed,
        authorized,
        strict=True,
    ), 1):
        notebook = root / f"{stage}.ipynb"
        notebook.write_text("{}\n", encoding="utf-8")
        notebooks[stage] = notebook
        receipt_path = root / f"{stage}.json"
        write_json(receipt_path, normalized_receipt(stage, timestamp, sha256(notebook)))
        receipts[stage] = receipt_path
        authorization_path = root / f"{stage}-authorization.json"
        write_json(
            authorization_path,
            {
                "schema_version": 1,
                "candidate_id": "candidate-v1",
                "stage": stage,
                "decision": "AUTHORIZE_ONE_STAGE_RUN",
                "authorized": True,
                "authorized_by_user": True,
                "authorized_at": authorized_at,
                "contract_sha256_before": GOOD_HASH,
                "notebook": binding(notebook, root),
                "allowed_external_action": AUTH_ACTIONS[stage],
                "one_run_only": True,
                "read_terminal_evidence_after_run": True,
                "public_leaderboard_used_for_selection": False,
                "future_stages_authorized": False,
                "claim_boundary": "One stage only; no future stage is authorized.",
            },
        )
        stages[stage] = {
            "sequence": sequence,
            "state": "COMPLETE",
            "hypothesis": "The frozen candidate improves or preserves its anchor.",
            "single_changed_factor": "data split only",
            "data_split": stage,
            "expected_tasks": 10,
            "expected_outputs": 10,
            "notebook": binding(notebook, root),
            "authorization": binding(authorization_path, root),
            "receipt": binding(receipt_path, root),
        }
        if stage == "competition_rerun":
            stages[stage]["score_reference"] = {
                "name": "ARC Prize 85% target",
                "score": 0.85,
                "scope": "private_evaluation_target",
                "receipt_sha256": GOOD_HASH,
            }
    contract = {
        "schema_version": 1,
        "status": "COMPLETE",
        "project_root": ".",
        "candidate_id": "candidate-v1",
        "deadline_receipt": binding(deadline, root),
        "stage_receipt_schema": binding(schema, root),
        "stage_failure_receipt_schema": binding(failure_schema, root),
        "stage_measurement_builder": binding(measurement_builder, root),
        "competition_observation_schema": binding(
            competition_observation_schema, root
        ),
        "stage_authorization_schema": binding(stage_authorization_schema, root),
        "stage_authorizer": binding(stage_authorizer, root),
        "required_family_buckets": list(BUCKETS),
        "anti_tuning": {"public_leaderboard_used_for_policy_selection": False},
        "holdout_integrity": {
            "status": "CLEAR_FOR_METHOD_GENERALIZATION",
            "promotion_blocked": False,
            "receipt": binding(holdout_integrity_receipt, root),
            "generalization_route": "POSITIVE_ROUTE_WITH_VERIFIED_UNTOUCHED_CORPUS",
            "corpus_availability_receipt": None,
            "claim_boundary": holdout_integrity_claim,
        },
        "runtime_smoke_prerequisite": {
            "kernel": "jahyee/arc2-trm-wandb-log-compat-smoke-v2",
            "kernel_version": 1,
            "last_authorized_status": "RUNNING",
            "last_authorized_observation_cst": "2026-09-09T00:00:00+00:00",
            "authorization_boundary_cst": "2026-09-09T00:15:00+00:00",
            **smoke_support,
            "status": "PASSED",
            "terminal_receipt": binding(terminal, root),
        },
        "stages": stages,
    }
    contract_path = root / "contract.json"
    write_json(contract_path, contract)
    return contract_path, contract, receipts


def codes(result: dict) -> set[str]:
    return {item["code"] for item in result["violations"]}


def main() -> None:
    active = audit(PROJECT_ROOT / "paper/manifests/three_stage_pipeline_v1.json")
    assert active["passes"] is True
    assert active["pipeline_complete"] is False
    assert active["holdout_integrity_status"] == (
        "CONTAMINATED_FOR_V176_GENERALIZATION"
    )
    assert active["holdout_promotion_blocked"] is True
    assert active["generalization_route"] == (
        "SYSTEMS_NEGATIVE_NO_VERIFIED_UNTOUCHED_CORPUS"
    )
    assert active["next_action"] == (
        "SYSTEMS_NEGATIVE_ONLY_NO_EXTERNAL_GENERALIZATION_RUN"
    )

    with tempfile.TemporaryDirectory(prefix="arc2-three-stage-") as raw:
        root = pathlib.Path(raw)
        contract_path, contract, receipts = build_complete_contract(root)
        positive = audit(contract_path)
        assert positive["passes"] is True
        assert positive["pipeline_complete"] is True
        assert positive["next_action"] == "NONE_PIPELINE_COMPLETE"

        missing_integrity = copy.deepcopy(contract)
        del missing_integrity["holdout_integrity"]
        write_json(contract_path, missing_integrity)
        assert "holdout_integrity_missing" in codes(audit(contract_path))

        wrong_integrity_flag = copy.deepcopy(contract)
        wrong_integrity_flag["holdout_integrity"]["promotion_blocked"] = True
        write_json(contract_path, wrong_integrity_flag)
        assert "holdout_integrity_promotion_flag_mismatch" in codes(
            audit(contract_path)
        )

        contaminated_active = copy.deepcopy(contract)
        contaminated_active["holdout_integrity"]["status"] = (
            "CONTAMINATED_FOR_V176_GENERALIZATION"
        )
        contaminated_active["holdout_integrity"]["promotion_blocked"] = True
        write_json(contract_path, contaminated_active)
        contaminated_codes = codes(audit(contract_path))
        assert "contaminated_holdout_stage_started" in contaminated_codes
        assert "competition_started_with_contaminated_holdout" in contaminated_codes

        preauthorized_start = copy.deepcopy(contract)
        preauthorized_receipt = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        preauthorized_receipt["started_at"] = "2026-09-09T00:39:59+00:00"
        preauthorized_path = root / "private-development-preauthorization-start.json"
        write_json(preauthorized_path, preauthorized_receipt)
        preauthorized_start["stages"]["private_development"]["receipt"] = binding(
            preauthorized_path, root
        )
        write_json(contract_path, preauthorized_start)
        assert "stage_started_before_authorization" in codes(audit(contract_path))

        early_holdout = copy.deepcopy(contract)
        early_holdout["stages"]["private_development"]["state"] = "NOT_AUTHORIZED"
        early_holdout["stages"]["private_development"]["receipt"] = None
        early_holdout["stages"]["competition_rerun"]["state"] = "NOT_AUTHORIZED"
        early_holdout["stages"]["competition_rerun"]["receipt"] = None
        write_json(contract_path, early_holdout)
        assert "holdout_started_before_development_promotion" in codes(audit(contract_path))

        regressed = normalized_receipt(
            "sealed_holdout",
            "2026-09-09T02:00:00+00:00",
            sha256(root / "sealed_holdout.ipynb"),
        )
        regressed["metrics"].update(
            {
                "method_exact_outputs": 6,
                "anchor_exact_outputs": 7,
                "attempt_1_exact_outputs": 5,
                "attempt_2_incremental_outputs": 1,
                "method_accuracy": 0.6,
                "anchor_accuracy": 0.7,
                "delta_vs_anchor": -0.1,
            }
        )
        write_json(receipts["sealed_holdout"], regressed)
        regressed_contract = copy.deepcopy(contract)
        regressed_contract["stages"]["sealed_holdout"]["receipt"] = binding(
            receipts["sealed_holdout"], root
        )
        write_json(contract_path, regressed_contract)
        assert "holdout_regressed_vs_anchor" in codes(audit(contract_path))

        write_json(
            receipts["sealed_holdout"],
            normalized_receipt(
                "sealed_holdout",
                "2026-09-09T02:00:00+00:00",
                sha256(root / "sealed_holdout.ipynb"),
            ),
        )
        missing_id = normalized_receipt(
            "competition_rerun",
            "2026-09-09T03:00:00+00:00",
            sha256(root / "competition_rerun.ipynb"),
        )
        missing_id["kaggle"]["submission_id"] = ""
        write_json(receipts["competition_rerun"], missing_id)
        missing_id_contract = copy.deepcopy(contract)
        for stage in ("sealed_holdout", "competition_rerun"):
            missing_id_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, missing_id_contract)
        assert "competition_submission_id_missing" in codes(audit(contract_path))

        tuned = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        tuned["public_leaderboard_used_for_selection"] = True
        write_json(receipts["private_development"], tuned)
        tuned_contract = copy.deepcopy(contract)
        tuned_contract["stages"]["private_development"]["receipt"] = binding(
            receipts["private_development"], root
        )
        for stage in ("sealed_holdout", "competition_rerun"):
            write_json(
                receipts[stage],
                normalized_receipt(
                    stage,
                    "2026-09-09T02:00:00+00:00"
                    if stage == "sealed_holdout"
                    else "2026-09-09T03:00:00+00:00",
                    sha256(root / f"{stage}.ipynb"),
                ),
            )
            tuned_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, tuned_contract)
        assert "public_leaderboard_selection_forbidden" in codes(audit(contract_path))

        incomplete_family = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        del incomplete_family["family_coverage"]["search"]
        write_json(receipts["private_development"], incomplete_family)
        incomplete_contract = copy.deepcopy(contract)
        incomplete_contract["stages"]["private_development"]["receipt"] = binding(
            receipts["private_development"], root
        )
        for stage in ("sealed_holdout", "competition_rerun"):
            incomplete_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, incomplete_contract)
        assert "stage_family_buckets_incomplete" in codes(audit(contract_path))

        wrong_family_total = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        wrong_family_total["family_coverage"]["geometry"]["tasks"] += 1
        write_json(receipts["private_development"], wrong_family_total)
        wrong_family_contract = copy.deepcopy(contract)
        wrong_family_contract["stages"]["private_development"]["receipt"] = binding(
            receipts["private_development"], root
        )
        for stage in ("sealed_holdout", "competition_rerun"):
            wrong_family_contract["stages"][stage]["receipt"] = binding(
                receipts[stage], root
            )
        write_json(contract_path, wrong_family_contract)
        assert "stage_family_task_total_mismatch" in codes(audit(contract_path))

        wrong_scope = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        wrong_scope["metrics"]["tasks"] = 9
        write_json(receipts["private_development"], wrong_scope)
        wrong_scope_contract = copy.deepcopy(contract)
        wrong_scope_contract["stages"]["private_development"]["receipt"] = binding(
            receipts["private_development"], root
        )
        for stage in ("sealed_holdout", "competition_rerun"):
            wrong_scope_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, wrong_scope_contract)
        assert "stage_metric_scope_mismatch" in codes(audit(contract_path))

        preregistration_drift = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        preregistration_drift["single_changed_factor"] = "two factors changed"
        write_json(receipts["private_development"], preregistration_drift)
        drift_contract = copy.deepcopy(contract)
        drift_contract["stages"]["private_development"]["receipt"] = binding(
            receipts["private_development"], root
        )
        for stage in ("sealed_holdout", "competition_rerun"):
            drift_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, drift_contract)
        assert "stage_preregistration_mismatch" in codes(audit(contract_path))

        fabricated_hidden_correctness = normalized_receipt(
            "competition_rerun",
            "2026-09-09T03:00:00+00:00",
            sha256(root / "competition_rerun.ipynb"),
        )
        fabricated_hidden_correctness["metrics"]["method_exact_outputs"] = 8
        write_json(receipts["competition_rerun"], fabricated_hidden_correctness)
        fabricated_contract = copy.deepcopy(contract)
        fabricated_contract["stages"]["competition_rerun"]["receipt"] = binding(
            receipts["competition_rerun"], root
        )
        for stage in ("private_development", "sealed_holdout"):
            write_json(
                receipts[stage],
                normalized_receipt(
                    stage,
                    "2026-09-09T01:00:00+00:00"
                    if stage == "private_development"
                    else "2026-09-09T02:00:00+00:00",
                    sha256(root / f"{stage}.ipynb"),
                ),
            )
            fabricated_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, fabricated_contract)
        assert "competition_per_output_correctness_forbidden" in codes(
            audit(contract_path)
        )

        unregistered_receipt_field = normalized_receipt(
            "private_development",
            "2026-09-09T01:00:00+00:00",
            sha256(root / "private_development.ipynb"),
        )
        unregistered_receipt_field["manual_override"] = True
        write_json(receipts["private_development"], unregistered_receipt_field)
        unregistered_contract = copy.deepcopy(contract)
        unregistered_contract["stages"]["private_development"]["receipt"] = binding(
            receipts["private_development"], root
        )
        for stage in ("sealed_holdout", "competition_rerun"):
            unregistered_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, unregistered_contract)
        assert "stage_receipt_fields_invalid" in codes(audit(contract_path))

        wrong_score_gap = normalized_receipt(
            "competition_rerun",
            "2026-09-09T03:00:00+00:00",
            sha256(root / "competition_rerun.ipynb"),
        )
        wrong_score_gap["kaggle"]["delta_vs_reference"] = 0.0
        write_json(receipts["competition_rerun"], wrong_score_gap)
        wrong_gap_contract = copy.deepcopy(contract)
        wrong_gap_contract["stages"]["competition_rerun"]["receipt"] = binding(
            receipts["competition_rerun"], root
        )
        for stage in ("private_development", "sealed_holdout"):
            write_json(
                receipts[stage],
                normalized_receipt(
                    stage,
                    "2026-09-09T01:00:00+00:00"
                    if stage == "private_development"
                    else "2026-09-09T02:00:00+00:00",
                    sha256(root / f"{stage}.ipynb"),
                ),
            )
            wrong_gap_contract["stages"][stage]["receipt"] = binding(receipts[stage], root)
        write_json(contract_path, wrong_gap_contract)
        assert "competition_score_delta_mismatch" in codes(audit(contract_path))

    print("three-stage pipeline regression passed")


if __name__ == "__main__":
    main()
