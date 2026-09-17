#!/usr/bin/env python3
"""Fail-closed audit for development -> holdout -> competition execution.

The active contract may be structurally valid while incomplete. A stage marked
COMPLETE must point to a normalized, hash-bound receipt containing the score,
family coverage, runtime, failure, format, and artifact evidence needed by the
ARC-AGI-2 execution protocol.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from datetime import datetime
from typing import Any


STAGE_ORDER = ("private_development", "sealed_holdout", "competition_rerun")
STAGE_STATES = {
    "PENDING_PREREQUISITE",
    "NOT_AUTHORIZED",
    "RUNNING",
    "FAILED",
    "COMPLETE",
}
CONTRACT_STATES = {"ACTIVE_NOT_COMPLETE", "COMPLETE"}
ACTIVE_STATES = {"RUNNING", "FAILED", "COMPLETE"}
SHA256 = re.compile(r"[0-9a-f]{64}")
TASK_ID = re.compile(r"[0-9a-f]{8}")
DIAGNOSTIC_ORDER = ("format", "cache", "seed", "budget")
RUNTIME_SMOKE_KERNEL = "jahyee/arc2-trm-wandb-log-compat-smoke-v2"
RUNTIME_SMOKE_RUNTIME_SHA256 = (
    "8ac51e00df2f220ff8742bddceae9a84a407e426734975db2f55234460a48776"
)
RUNTIME_SMOKE_PARENT_RUNTIME_SHA256 = (
    "17d8757c874f14d20aee0368054137874e8df16f2dd8f0fe9e521d5aff2c9e82"
)
RUNTIME_SMOKE_RECEIPT_FIELDS = {
    "schema_version",
    "artifact_status",
    "kernel",
    "kernel_version",
    "authoritative_kernel_status",
    "status_verified_at_cst",
    "is_private",
    "internet_enabled",
    "data_boundary",
    "purpose",
    "task_id",
    "task_count",
    "epochs",
    "expected_optimizer_steps",
    "runtime_sha256",
    "parent_runtime_sha256",
    "elapsed_seconds",
    "returncode",
    "guards",
    "source_artifacts",
    "source_paths",
    "claim_boundary",
}
RUNTIME_SMOKE_GUARD_FIELDS = {
    "runtime_returncode_zero",
    "checkpoint_loaded",
    "optimizer_constructed",
    "scheduler_path_preserved",
    "first_step_checkpoint_saved",
    "submission_exists",
    "submission_schema_valid",
}
RUNTIME_SMOKE_TERMINAL_GUARD_FIELDS = RUNTIME_SMOKE_GUARD_FIELDS | {
    "all_guards_passed"
}
RUNTIME_SMOKE_SOURCE_FIELDS = {
    "run_manifest.json",
    "trm-smoke-receipt.json",
    "trm-smoke.log",
    "trm_submission.json",
    "notebook_sha256",
    "kernel_metadata_sha256",
}
RUNTIME_SMOKE_OBSERVATION_FIELDS = {
    "schema_version",
    "kernel",
    "kernel_version",
    "authoritative_kernel_status",
    "status_verified_at_cst",
    "observation_mode",
    "raw_status",
    "artifacts_downloaded",
}
RUNTIME_SMOKE_SOURCE_RECEIPT_FIELDS = {
    "purpose",
    "repair_id",
    "single_change",
    "task_id",
    "task_count",
    "epochs",
    "expected_optimizer_steps",
    "runtime_sha256",
    "parent_runtime_sha256",
    "challenge_sha256",
    "submission_sha256",
    "elapsed_seconds",
    "returncode",
    "guards",
    "all_guards_passed",
}
STAGE_AUTHORIZATION_FIELDS = {
    "schema_version",
    "candidate_id",
    "stage",
    "decision",
    "authorized",
    "authorized_by_user",
    "authorized_at",
    "contract_sha256_before",
    "notebook",
    "allowed_external_action",
    "one_run_only",
    "read_terminal_evidence_after_run",
    "public_leaderboard_used_for_selection",
    "future_stages_authorized",
    "claim_boundary",
}
STAGE_AUTHORIZATION_ACTIONS = {
    "private_development": (
        "KAGGLE_RUN_PRIVATE_DEVELOPMENT_ONCE_AND_READ_TERMINAL_ARTIFACTS"
    ),
    "sealed_holdout": (
        "KAGGLE_RUN_SEALED_HOLDOUT_ONCE_AND_READ_TERMINAL_ARTIFACTS"
    ),
    "competition_rerun": (
        "KAGGLE_RERUN_SUBMIT_FROZEN_NOTEBOOK_ONCE_AND_READ_RECEIPT"
    ),
}
HOLDOUT_INTEGRITY_FIELDS = {
    "status",
    "promotion_blocked",
    "receipt",
    "generalization_route",
    "corpus_availability_receipt",
    "claim_boundary",
}
HOLDOUT_INTEGRITY_STATUSES = {
    "CLEAR_FOR_METHOD_GENERALIZATION",
    "CONTAMINATED_FOR_V176_GENERALIZATION",
}
HOLDOUT_INTEGRITY_RECEIPT_FIELDS = {
    "schema_version",
    "result_type",
    "candidate_id",
    "audit_status",
    "decision",
    "external_actions_performed",
    "holdout_solutions_read_by_this_audit",
    "holdout_task_ids_disclosed",
    "historical_facts",
    "derived_holdout",
    "provenance",
    "permitted_claims",
    "forbidden_claims",
    "claim_boundary",
}
CONTAMINATED_HOLDOUT_STATUS = "CONTAMINATED_FOR_V176_GENERALIZATION"
CONTAMINATED_HOLDOUT_DECISION = (
    "BLOCK_V3_HOLDOUT_PROMOTION_UNTIL_NEW_UNTOUCHED_HOLDOUT"
)
CONTAMINATED_HOLDOUT_ID_SHA256 = (
    "f773c6318e99281d2fb49aed126f7febf297ab5a15059fc3493b40f3ff948718"
)
SYSTEMS_NEGATIVE_ROUTE = "SYSTEMS_NEGATIVE_NO_VERIFIED_UNTOUCHED_CORPUS"
POSITIVE_ROUTE = "POSITIVE_ROUTE_WITH_VERIFIED_UNTOUCHED_CORPUS"
CORPUS_AVAILABILITY_RECEIPT_FIELDS = {
    "schema_version",
    "checked_at_cst",
    "checked_at_utc",
    "audit_status",
    "candidate_id",
    "method",
    "eligibility_requirements",
    "local_source_evidence",
    "adjudication",
    "permitted_use_of_domain_shift_corpora",
    "current_decision",
    "positive_route_reopen_contract",
    "authorization_boundary",
    "claim_boundary",
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(items: list[dict[str, Any]], code: str, **details: Any) -> None:
    items.append({"code": code, **details})


def validate_object_keys(
    value: Any,
    required: set[str],
    allowed: set[str],
    violations: list[dict[str, Any]],
    code: str,
    **details: Any,
) -> None:
    if not isinstance(value, dict):
        return
    missing = sorted(required - set(value))
    extra = sorted(set(value) - allowed)
    if missing or extra:
        add(violations, code, missing=missing, extra=extra, **details)


def resolve_file(
    root: pathlib.Path,
    raw: Any,
    violations: list[dict[str, Any]],
    code_prefix: str,
) -> pathlib.Path | None:
    if not isinstance(raw, str) or not raw:
        add(violations, f"{code_prefix}_path_missing")
        return None
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        add(violations, f"{code_prefix}_path_unsafe", path=raw)
        return None
    path = (root / pathlib.Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        add(violations, f"{code_prefix}_path_escapes_root", path=raw)
        return None
    if not path.is_file():
        add(violations, f"{code_prefix}_file_missing", path=raw)
        return None
    return path


def verify_bound_file(
    root: pathlib.Path,
    binding: Any,
    violations: list[dict[str, Any]],
    code_prefix: str,
) -> pathlib.Path | None:
    if not isinstance(binding, dict):
        add(violations, f"{code_prefix}_binding_missing")
        return None
    path = resolve_file(root, binding.get("path"), violations, code_prefix)
    expected = binding.get("sha256")
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        add(violations, f"{code_prefix}_sha256_invalid")
    elif path is not None:
        actual = digest(path)
        if actual != expected:
            add(
                violations,
                f"{code_prefix}_sha256_mismatch",
                expected=expected,
                actual=actual,
            )
    return path


def parse_timestamp(value: Any, field: str, violations: list[dict[str, Any]]) -> datetime | None:
    if not isinstance(value, str):
        add(violations, "stage_timestamp_missing", field=field)
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        add(violations, "stage_timestamp_invalid", field=field)
        return None
    if parsed.tzinfo is None:
        add(violations, "stage_timestamp_without_timezone", field=field)
        return None
    return parsed


def validate_corpus_availability_receipt(
    root: pathlib.Path,
    binding_value: Any,
    candidate_id: str,
    violations: list[dict[str, Any]],
) -> None:
    path = verify_bound_file(
        root,
        binding_value,
        violations,
        "corpus_availability_receipt",
    )
    if path is None:
        return
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        add(violations, "corpus_availability_receipt_json_invalid")
        return
    validate_object_keys(
        receipt,
        CORPUS_AVAILABILITY_RECEIPT_FIELDS,
        CORPUS_AVAILABILITY_RECEIPT_FIELDS,
        violations,
        "corpus_availability_receipt_fields_invalid",
    )
    if not isinstance(receipt, dict):
        add(violations, "corpus_availability_receipt_invalid")
        return
    expected_identity = {
        "schema_version": 1,
        "audit_status": "NO_VERIFIED_ELIGIBLE_ARC_AGI_2_GENERALIZATION_CORPUS",
        "candidate_id": candidate_id,
        "method": "local provenance and prior-solution-access audit only; no network or Kaggle action",
        "current_decision": "PIVOT_V176_TO_SYSTEMS_NEGATIVE",
    }
    drift = sorted(
        key for key, expected in expected_identity.items() if receipt.get(key) != expected
    )
    if drift:
        add(violations, "corpus_availability_receipt_identity_mismatch", fields=drift)

    checked_cst = parse_timestamp(
        receipt.get("checked_at_cst"), "corpus_availability.checked_at_cst", violations
    )
    checked_utc = parse_timestamp(
        receipt.get("checked_at_utc"), "corpus_availability.checked_at_utc", violations
    )
    if checked_cst is not None and checked_utc is not None and checked_cst != checked_utc:
        add(violations, "corpus_availability_timestamp_mismatch")
    requirements = receipt.get("eligibility_requirements")
    if (
        not isinstance(requirements, dict)
        or len(requirements) != 6
        or any(value is not True for value in requirements.values())
    ):
        add(violations, "corpus_availability_requirements_invalid")
    expected_corpora = [
        {"stem": "arc-agi_training", "tasks": 400, "outputs": 416},
        {"stem": "arc-agi_evaluation", "tasks": 400, "outputs": 419},
        {"stem": "arc-agi_training2", "tasks": 1000, "outputs": 1076},
        {"stem": "arc-agi_evaluation2", "tasks": 120, "outputs": 172},
        {"stem": "arc-agi_concept", "tasks": 160, "outputs": 480},
    ]
    source_evidence = receipt.get("local_source_evidence")
    if not isinstance(source_evidence, dict) or set(source_evidence) != {
        "audit_tool",
        "bundled_parent_readme",
        "v175_five_corpus_receipt",
        "v3_holdout_integrity_receipt",
    }:
        add(violations, "corpus_availability_source_evidence_invalid")
    else:
        for name, item in source_evidence.items():
            verify_bound_file(
                root,
                item,
                violations,
                f"corpus_availability_source_{name}",
            )
        source_receipt = source_evidence["v175_five_corpus_receipt"]
        if source_receipt.get("aggregate") != {
            "tasks": 2080,
            "outputs": 2563,
            "fired_tasks": 753,
            "fired_outputs": 1103,
            "correct_fired_outputs": 1103,
        }:
            add(violations, "corpus_availability_aggregate_mismatch")
        if source_receipt.get("corpora") != expected_corpora:
            add(violations, "corpus_availability_corpora_mismatch")
    adjudication = receipt.get("adjudication")
    if (
        not isinstance(adjudication, dict)
        or len(adjudication) != 5
        or any(
            not isinstance(value, str)
            or not value.startswith(("INELIGIBLE", "NOT_VERIFIED"))
            for value in adjudication.values()
        )
    ):
        add(violations, "corpus_availability_adjudication_invalid")
    permitted = receipt.get("permitted_use_of_domain_shift_corpora")
    if not isinstance(permitted, str) or "domain-shift mechanistic stress test" not in permitted:
        add(violations, "corpus_availability_domain_shift_boundary_missing")
    reopen = receipt.get("positive_route_reopen_contract")
    if not isinstance(reopen, dict) or set(reopen) != {
        "required_before_acquisition_or_solution_view",
        "required_receipts",
        "stop_conditions",
    }:
        add(violations, "corpus_availability_reopen_contract_invalid")
    boundary = receipt.get("authorization_boundary")
    if (
        not isinstance(boundary, dict)
        or len(boundary) != 6
        or any(value is not False for value in boundary.values())
    ):
        add(violations, "corpus_availability_authorization_boundary_invalid")
    if not isinstance(receipt.get("claim_boundary"), str) or not receipt[
        "claim_boundary"
    ].strip():
        add(violations, "corpus_availability_claim_boundary_missing")


def validate_stage_authorization(
    root: pathlib.Path,
    binding: Any,
    stage: str,
    candidate_id: str,
    stage_notebook: Any,
    violations: list[dict[str, Any]],
) -> datetime | None:
    path = verify_bound_file(root, binding, violations, f"{stage}_authorization")
    if path is None:
        return None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        add(violations, "stage_authorization_json_invalid", stage=stage)
        return None
    validate_object_keys(
        receipt,
        STAGE_AUTHORIZATION_FIELDS,
        STAGE_AUTHORIZATION_FIELDS,
        violations,
        "stage_authorization_fields_invalid",
        stage=stage,
    )
    if not isinstance(receipt, dict):
        add(violations, "stage_authorization_invalid", stage=stage)
        return None
    expected = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "stage": stage,
        "decision": "AUTHORIZE_ONE_STAGE_RUN",
        "authorized": True,
        "authorized_by_user": True,
        "allowed_external_action": STAGE_AUTHORIZATION_ACTIONS[stage],
        "one_run_only": True,
        "read_terminal_evidence_after_run": True,
        "public_leaderboard_used_for_selection": False,
        "future_stages_authorized": False,
    }
    drift = sorted(key for key, value in expected.items() if receipt.get(key) != value)
    if drift:
        add(
            violations,
            "stage_authorization_identity_mismatch",
            stage=stage,
            fields=drift,
        )
    prior_hash = receipt.get("contract_sha256_before")
    if not isinstance(prior_hash, str) or not SHA256.fullmatch(prior_hash):
        add(violations, "stage_authorization_prior_hash_invalid", stage=stage)
    claim = receipt.get("claim_boundary")
    if not isinstance(claim, str) or not claim.strip():
        add(violations, "stage_authorization_claim_boundary_missing", stage=stage)
    notebook = receipt.get("notebook")
    validate_object_keys(
        notebook,
        {"path", "sha256"},
        {"path", "sha256"},
        violations,
        "stage_authorization_notebook_fields_invalid",
        stage=stage,
    )
    verify_bound_file(
        root,
        notebook,
        violations,
        f"{stage}_authorization_notebook",
    )
    if notebook != stage_notebook:
        add(violations, "stage_authorization_notebook_mismatch", stage=stage)
    return parse_timestamp(
        receipt.get("authorized_at"), f"{stage}.authorization.authorized_at", violations
    )


def validate_holdout_integrity(
    root: pathlib.Path,
    value: Any,
    candidate_id: str,
    violations: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> tuple[str | None, bool]:
    validate_object_keys(
        value,
        HOLDOUT_INTEGRITY_FIELDS,
        HOLDOUT_INTEGRITY_FIELDS,
        violations,
        "holdout_integrity_fields_invalid",
    )
    if not isinstance(value, dict):
        add(violations, "holdout_integrity_missing")
        return None, False

    status = value.get("status")
    if status not in HOLDOUT_INTEGRITY_STATUSES:
        add(violations, "holdout_integrity_status_invalid", status=status)
        status = None
    contaminated = status == CONTAMINATED_HOLDOUT_STATUS
    if (
        candidate_id == "conservative_exact_overlay_v3"
        and status != CONTAMINATED_HOLDOUT_STATUS
    ):
        add(violations, "v3_holdout_integrity_status_cannot_be_cleared")
    if value.get("promotion_blocked") is not contaminated:
        add(violations, "holdout_integrity_promotion_flag_mismatch")
    route = value.get("generalization_route")
    corpus_receipt = value.get("corpus_availability_receipt")
    if contaminated:
        if route != SYSTEMS_NEGATIVE_ROUTE:
            add(violations, "contaminated_holdout_route_mismatch")
        validate_corpus_availability_receipt(
            root,
            corpus_receipt,
            candidate_id,
            violations,
        )
        add(
            warnings,
            "v176_systems_negative_route_active",
            decision="PIVOT_V176_TO_SYSTEMS_NEGATIVE",
        )
    else:
        if route != POSITIVE_ROUTE:
            add(violations, "clear_holdout_route_mismatch")
        if corpus_receipt is not None:
            add(violations, "clear_holdout_has_systems_negative_receipt")
    claim_boundary = value.get("claim_boundary")
    if not isinstance(claim_boundary, str) or not claim_boundary.strip():
        add(violations, "holdout_integrity_claim_boundary_missing")

    path = verify_bound_file(
        root,
        value.get("receipt"),
        violations,
        "holdout_integrity_receipt",
    )
    if path is None:
        return status, contaminated
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        add(violations, "holdout_integrity_receipt_json_invalid")
        return status, contaminated
    validate_object_keys(
        receipt,
        HOLDOUT_INTEGRITY_RECEIPT_FIELDS,
        HOLDOUT_INTEGRITY_RECEIPT_FIELDS,
        violations,
        "holdout_integrity_receipt_fields_invalid",
    )
    if not isinstance(receipt, dict):
        add(violations, "holdout_integrity_receipt_invalid")
        return status, contaminated

    expected_identity = {
        "schema_version": 1,
        "result_type": "historical_holdout_integrity_audit",
        "candidate_id": candidate_id,
        "audit_status": status,
        "external_actions_performed": False,
        "holdout_solutions_read_by_this_audit": False,
        "holdout_task_ids_disclosed": False,
        "claim_boundary": claim_boundary,
    }
    drift = sorted(
        key for key, expected in expected_identity.items() if receipt.get(key) != expected
    )
    if drift:
        add(violations, "holdout_integrity_receipt_identity_mismatch", fields=drift)

    provenance = receipt.get("provenance")
    if not isinstance(provenance, dict):
        add(violations, "holdout_integrity_provenance_missing")
    else:
        for name, binding_value in provenance.items():
            if name == "historical_training_solutions_sha256":
                if (
                    not isinstance(binding_value, str)
                    or not SHA256.fullmatch(binding_value)
                ):
                    add(violations, "holdout_integrity_historical_solution_hash_invalid")
                continue
            verify_bound_file(
                root,
                binding_value,
                violations,
                f"holdout_integrity_provenance_{name}",
            )

    if contaminated:
        expected_historical = {
            "source_audit_task_universe": 1000,
            "source_audit_loaded_all_training_solutions": True,
            "source_audit_selected_tasks": 2,
            "selected_tasks_all_in_development": True,
            "development_preregistration_embeds_source_audit_result": True,
            "holdout_preregistration_pairs_that_development_candidate": True,
        }
        expected_holdout = {
            "tasks": 48,
            "outputs": 49,
            "task_id_set_sha256": CONTAMINATED_HOLDOUT_ID_SHA256,
            "disjoint_from_development": True,
            "v176_selected_tasks": 0,
            "v176_behavior_known_before_holdout_run": "always abstains on this slice",
        }
        expected_permitted = [
            "execution/runtime evidence for the unchanged parent",
            "format and artifact-integrity evidence",
        ]
        expected_forbidden = [
            "sealed-holdout evidence for V176 overlay contribution",
            "new-task generalization of the two V176 rules",
            "Progress or Novelty from this 48-task slice",
        ]
        if receipt.get("decision") != CONTAMINATED_HOLDOUT_DECISION:
            add(violations, "holdout_integrity_decision_mismatch")
        if receipt.get("historical_facts") != expected_historical:
            add(violations, "holdout_integrity_historical_facts_mismatch")
        if receipt.get("derived_holdout") != expected_holdout:
            add(violations, "holdout_integrity_derived_holdout_mismatch")
        if receipt.get("permitted_claims") != expected_permitted:
            add(violations, "holdout_integrity_permitted_claims_mismatch")
        if receipt.get("forbidden_claims") != expected_forbidden:
            add(violations, "holdout_integrity_forbidden_claims_mismatch")
        add(
            warnings,
            "holdout_contaminated_for_method_generalization",
            decision=CONTAMINATED_HOLDOUT_DECISION,
        )
    else:
        expected_clear_historical = {
            "independent_labeled_corpus": True,
            "solutions_unavailable_during_method_construction": True,
            "method_frozen_before_solution_access": True,
        }
        expected_clear_fields = {
            "tasks",
            "outputs",
            "disjoint_from_development",
            "method_behavior_known_before_holdout_run",
        }
        expected_clear_claims = [
            "prospective method-generalization evidence after one authorized run"
        ]
        expected_clear_forbidden = ["policy tuning from holdout results"]
        if receipt.get("decision") != "ALLOW_HOLDOUT_PROMOTION":
            add(violations, "holdout_integrity_decision_mismatch")
        if receipt.get("historical_facts") != expected_clear_historical:
            add(violations, "clear_holdout_integrity_historical_facts_mismatch")
        clear_holdout = receipt.get("derived_holdout")
        if not isinstance(clear_holdout, dict) or set(clear_holdout) != expected_clear_fields:
            add(violations, "clear_holdout_integrity_scope_invalid")
        else:
            tasks = clear_holdout.get("tasks")
            outputs = clear_holdout.get("outputs")
            if (
                type(tasks) is not int
                or type(outputs) is not int
                or tasks <= 0
                or outputs < tasks
                or clear_holdout.get("disjoint_from_development") is not True
                or clear_holdout.get("method_behavior_known_before_holdout_run")
                is not False
            ):
                add(violations, "clear_holdout_integrity_scope_invalid")
        required_clear_provenance = {
            "candidate_preregistration",
            "holdout_manifest",
            "integrity_audit",
        }
        if not isinstance(provenance, dict) or not required_clear_provenance <= set(
            provenance
        ):
            add(violations, "clear_holdout_integrity_provenance_incomplete")
        if receipt.get("permitted_claims") != expected_clear_claims:
            add(violations, "clear_holdout_integrity_permitted_claims_mismatch")
        if receipt.get("forbidden_claims") != expected_clear_forbidden:
            add(violations, "clear_holdout_integrity_forbidden_claims_mismatch")
    return status, contaminated


def validate_grid_format(format_receipt: Any, stage: str, violations: list[dict[str, Any]]) -> None:
    required_true = {
        "validated",
        "task_keys_exact",
        "output_counts_exact",
        "exactly_two_attempts",
        "rectangular_grids",
        "dimensions_1_to_30",
        "colors_0_to_9",
    }
    if not isinstance(format_receipt, dict):
        add(violations, "stage_format_receipt_missing", stage=stage)
        return
    validate_object_keys(
        format_receipt,
        required_true,
        required_true,
        violations,
        "stage_format_fields_invalid",
        stage=stage,
    )
    failed = sorted(key for key in required_true if format_receipt.get(key) is not True)
    if failed:
        add(violations, "stage_format_guards_failed", stage=stage, guards=failed)


def validate_metrics(metrics: Any, stage: str, violations: list[dict[str, Any]]) -> float | None:
    if not isinstance(metrics, dict):
        add(violations, "stage_metrics_missing", stage=stage)
        return None
    if type(metrics.get("tasks")) is not int or type(metrics.get("outputs")) is not int:
        add(violations, "stage_metric_integer_missing", stage=stage)
        return None
    tasks = metrics["tasks"]
    outputs = metrics["outputs"]
    if tasks <= 0 or outputs <= 0:
        add(violations, "stage_metric_count_out_of_range", stage=stage)
        return None

    scored_fields = (
        "method_exact_outputs",
        "anchor_exact_outputs",
        "attempt_1_exact_outputs",
        "attempt_2_incremental_outputs",
        "method_accuracy",
        "anchor_accuracy",
        "delta_vs_anchor",
    )
    expected_fields = {"tasks", "outputs", "local_labels_available", *scored_fields}
    validate_object_keys(
        metrics,
        expected_fields,
        expected_fields,
        violations,
        "stage_metric_fields_invalid",
        stage=stage,
    )
    if stage == "competition_rerun":
        if metrics.get("local_labels_available") is not False:
            add(violations, "competition_hidden_labels_must_be_unavailable", stage=stage)
        leaked = sorted(key for key in scored_fields if metrics.get(key) is not None)
        if leaked:
            add(
                violations,
                "competition_per_output_correctness_forbidden",
                stage=stage,
                fields=leaked,
            )
        return None

    if metrics.get("local_labels_available") is not True:
        add(violations, "labeled_stage_metrics_not_declared", stage=stage)
    integer_fields = (
        "method_exact_outputs",
        "anchor_exact_outputs",
        "attempt_1_exact_outputs",
        "attempt_2_incremental_outputs",
    )
    if any(type(metrics.get(key)) is not int for key in integer_fields):
        add(violations, "stage_metric_integer_missing", stage=stage)
        return None
    method = metrics["method_exact_outputs"]
    anchor = metrics["anchor_exact_outputs"]
    attempt_1 = metrics["attempt_1_exact_outputs"]
    attempt_2 = metrics["attempt_2_incremental_outputs"]
    if tasks <= 0 or outputs <= 0 or not all(0 <= value <= outputs for value in (method, anchor, attempt_1, attempt_2)):
        add(violations, "stage_metric_count_out_of_range", stage=stage)
        return None
    if attempt_1 + attempt_2 != method:
        add(violations, "attempt_decomposition_mismatch", stage=stage)
    expected_accuracy = method / outputs
    expected_anchor = anchor / outputs
    expected_delta = expected_accuracy - expected_anchor
    for key, expected in (
        ("method_accuracy", expected_accuracy),
        ("anchor_accuracy", expected_anchor),
        ("delta_vs_anchor", expected_delta),
    ):
        value = metrics.get(key)
        if not isinstance(value, (int, float)) or abs(float(value) - expected) > 1e-12:
            add(violations, "stage_metric_arithmetic_mismatch", stage=stage, field=key)
    return expected_delta


def validate_runtime(runtime: Any, stage: str, tasks: int | None, violations: list[dict[str, Any]]) -> None:
    if not isinstance(runtime, dict):
        add(violations, "stage_runtime_missing", stage=stage)
        return
    runtime_fields = {
        "wall_seconds",
        "peak_memory_mb",
        "failed_tasks",
        "failure_rate",
        "timed_out_task_ids",
    }
    validate_object_keys(
        runtime,
        runtime_fields,
        runtime_fields,
        violations,
        "stage_runtime_fields_invalid",
        stage=stage,
    )
    wall = runtime.get("wall_seconds")
    peak = runtime.get("peak_memory_mb")
    failed = runtime.get("failed_tasks")
    rate = runtime.get("failure_rate")
    if not isinstance(wall, (int, float)) or wall <= 0:
        add(violations, "stage_wall_time_invalid", stage=stage)
    if not isinstance(peak, (int, float)) or peak <= 0:
        add(violations, "stage_peak_memory_invalid", stage=stage)
    if type(failed) is not int or failed < 0 or (tasks is not None and failed > tasks):
        add(violations, "stage_failed_task_count_invalid", stage=stage)
    elif tasks is not None:
        expected = failed / tasks
        if not isinstance(rate, (int, float)) or abs(float(rate) - expected) > 1e-12:
            add(violations, "stage_failure_rate_mismatch", stage=stage)
    timeouts = runtime.get("timed_out_task_ids")
    if not isinstance(timeouts, list) or not all(isinstance(value, str) for value in timeouts):
        add(violations, "stage_timeout_ids_invalid", stage=stage)


def validate_family_coverage(
    coverage: Any,
    required_buckets: set[str],
    stage: str,
    expected_tasks: int | None,
    expected_failed_tasks: int | None,
    violations: list[dict[str, Any]],
) -> None:
    if not isinstance(coverage, dict) or set(coverage) != required_buckets:
        add(
            violations,
            "stage_family_buckets_incomplete",
            stage=stage,
            expected=sorted(required_buckets),
            actual=sorted(coverage) if isinstance(coverage, dict) else None,
        )
        return
    total_tasks = 0
    total_failed_tasks = 0
    counts_valid = True
    for bucket, row in coverage.items():
        if not isinstance(row, dict):
            add(violations, "stage_family_row_invalid", stage=stage, bucket=bucket)
            counts_valid = False
            continue
        row_fields = {
            "correctness_available",
            "tasks",
            "method_solved",
            "anchor_solved",
            "delta",
            "failed_tasks",
        }
        validate_object_keys(
            row,
            row_fields,
            row_fields,
            violations,
            "stage_family_fields_invalid",
            stage=stage,
            bucket=bucket,
        )
        if stage == "competition_rerun":
            if row.get("correctness_available") is not False:
                add(
                    violations,
                    "competition_family_correctness_must_be_unavailable",
                    stage=stage,
                    bucket=bucket,
                )
            if any(row.get(key) is not None for key in ("method_solved", "anchor_solved", "delta")):
                add(
                    violations,
                    "competition_family_correctness_forbidden",
                    stage=stage,
                    bucket=bucket,
                )
            if type(row.get("tasks")) is not int or type(row.get("failed_tasks")) is not int:
                add(violations, "stage_family_row_invalid", stage=stage, bucket=bucket)
                counts_valid = False
                continue
            if row["tasks"] < 0 or not 0 <= row["failed_tasks"] <= row["tasks"]:
                add(violations, "stage_family_count_out_of_range", stage=stage, bucket=bucket)
                counts_valid = False
            else:
                total_tasks += row["tasks"]
                total_failed_tasks += row["failed_tasks"]
            continue

        if row.get("correctness_available") is not True:
            add(violations, "labeled_family_correctness_not_declared", stage=stage, bucket=bucket)
        required = {"tasks", "method_solved", "anchor_solved", "delta", "failed_tasks"}
        if any(type(row.get(key)) is not int for key in required):
            add(violations, "stage_family_row_invalid", stage=stage, bucket=bucket)
            counts_valid = False
            continue
        if row["tasks"] < 0 or not all(0 <= row[key] <= row["tasks"] for key in ("method_solved", "anchor_solved", "failed_tasks")):
            add(violations, "stage_family_count_out_of_range", stage=stage, bucket=bucket)
            counts_valid = False
        else:
            total_tasks += row["tasks"]
            total_failed_tasks += row["failed_tasks"]
        if row["delta"] != row["method_solved"] - row["anchor_solved"]:
            add(violations, "stage_family_delta_mismatch", stage=stage, bucket=bucket)
    if counts_valid and expected_tasks is not None and total_tasks != expected_tasks:
        add(
            violations,
            "stage_family_task_total_mismatch",
            stage=stage,
            expected=expected_tasks,
            actual=total_tasks,
        )
    if (
        counts_valid
        and expected_failed_tasks is not None
        and total_failed_tasks != expected_failed_tasks
    ):
        add(
            violations,
            "stage_family_failed_total_mismatch",
            stage=stage,
            expected=expected_failed_tasks,
            actual=total_failed_tasks,
        )


def validate_failed_receipt(
    receipt: Any,
    stage: str,
    candidate_id: str,
    required_buckets: set[str],
    stage_contract: dict[str, Any],
    violations: list[dict[str, Any]],
) -> tuple[datetime | None, datetime | None, str | None]:
    if not isinstance(receipt, dict):
        add(violations, "failed_stage_receipt_invalid", stage=stage)
        return None, None, None
    fields = {
        "schema_version",
        "stage",
        "candidate_id",
        "experiment_id",
        "hypothesis",
        "single_changed_factor",
        "data_split",
        "solver_family",
        "authoritative_status",
        "public_leaderboard_used_for_selection",
        "started_at",
        "completed_at",
        "failure_class",
        "diagnostics",
        "family_failures",
        "runtime",
        "submission_format",
        "artifacts",
        "minimal_counterexample",
        "ablation",
        "streak_policy",
        "public_research_reproduction",
        "claim_boundary",
    }
    validate_object_keys(
        receipt,
        fields,
        fields,
        violations,
        "failed_stage_receipt_fields_invalid",
        stage=stage,
    )
    if receipt.get("schema_version") != 1 or receipt.get("stage") != stage:
        add(violations, "failed_stage_receipt_identity_mismatch", stage=stage)
    if receipt.get("candidate_id") != candidate_id:
        add(violations, "failed_stage_candidate_mismatch", stage=stage)
    for key in ("experiment_id", "solver_family", "claim_boundary"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            add(violations, "failed_stage_field_missing", stage=stage, field=key)
    for key in ("hypothesis", "single_changed_factor", "data_split"):
        if receipt.get(key) != stage_contract.get(key):
            add(violations, "failed_stage_preregistration_mismatch", stage=stage, field=key)
    if receipt.get("authoritative_status") not in {"ERROR", "FAILED", "COMPLETE"}:
        add(violations, "failed_stage_not_terminal", stage=stage)
    if receipt.get("public_leaderboard_used_for_selection") is not False:
        add(violations, "public_leaderboard_selection_forbidden", stage=stage)

    started = parse_timestamp(receipt.get("started_at"), f"{stage}.started_at", violations)
    completed = parse_timestamp(receipt.get("completed_at"), f"{stage}.completed_at", violations)
    if started is not None and completed is not None and completed <= started:
        add(violations, "failed_stage_nonpositive_duration", stage=stage)

    failure_class = receipt.get("failure_class")
    if failure_class not in {*DIAGNOSTIC_ORDER, "solver"}:
        add(violations, "failed_stage_failure_class_invalid", stage=stage)
        failure_class = None

    diagnostics = receipt.get("diagnostics")
    if not isinstance(diagnostics, list) or len(diagnostics) != len(DIAGNOSTIC_ORDER):
        add(violations, "failed_stage_diagnostic_order_invalid", stage=stage)
    else:
        if failure_class in DIAGNOSTIC_ORDER:
            failure_index = DIAGNOSTIC_ORDER.index(failure_class)
            expected_statuses = tuple(
                "PASS" if index < failure_index else "FAIL" if index == failure_index else "NOT_REACHED"
                for index in range(len(DIAGNOSTIC_ORDER))
            )
        elif failure_class == "solver":
            expected_statuses = ("PASS",) * len(DIAGNOSTIC_ORDER)
        else:
            expected_statuses = (None,) * len(DIAGNOSTIC_ORDER)
        for index, (name, expected_status) in enumerate(zip(DIAGNOSTIC_ORDER, expected_statuses)):
            row = diagnostics[index]
            row_fields = {"name", "status", "evidence_sha256", "notes"}
            if not isinstance(row, dict):
                add(violations, "failed_stage_diagnostic_row_invalid", stage=stage, diagnostic=name)
                continue
            validate_object_keys(
                row,
                row_fields,
                row_fields,
                violations,
                "failed_stage_diagnostic_fields_invalid",
                stage=stage,
                diagnostic=name,
            )
            if row.get("name") != name or row.get("status") != expected_status:
                add(violations, "failed_stage_diagnostic_sequence_mismatch", stage=stage, diagnostic=name)
            evidence = row.get("evidence_sha256")
            if expected_status == "NOT_REACHED":
                if evidence is not None:
                    add(violations, "failed_stage_unreached_diagnostic_has_evidence", stage=stage, diagnostic=name)
            elif not isinstance(evidence, str) or not SHA256.fullmatch(evidence):
                add(violations, "failed_stage_diagnostic_hash_invalid", stage=stage, diagnostic=name)
            if not isinstance(row.get("notes"), str) or not row["notes"].strip():
                add(violations, "failed_stage_diagnostic_notes_missing", stage=stage, diagnostic=name)

    family_failures = receipt.get("family_failures")
    if not isinstance(family_failures, dict) or set(family_failures) != required_buckets:
        add(violations, "failed_stage_family_buckets_incomplete", stage=stage)
    else:
        for bucket, row in family_failures.items():
            row_fields = {"tasks", "failed_tasks", "affected_task_ids"}
            if not isinstance(row, dict):
                add(violations, "failed_stage_family_row_invalid", stage=stage, bucket=bucket)
                continue
            validate_object_keys(
                row,
                row_fields,
                row_fields,
                violations,
                "failed_stage_family_fields_invalid",
                stage=stage,
                bucket=bucket,
            )
            tasks = row.get("tasks")
            failed = row.get("failed_tasks")
            task_ids = row.get("affected_task_ids")
            if type(tasks) is not int or type(failed) is not int or tasks < 0 or not 0 <= failed <= tasks:
                add(violations, "failed_stage_family_count_invalid", stage=stage, bucket=bucket)
            if (
                not isinstance(task_ids, list)
                or len(task_ids) != len(set(task_ids))
                or not all(isinstance(task_id, str) and TASK_ID.fullmatch(task_id) for task_id in task_ids)
                or (type(failed) is int and len(task_ids) != failed)
            ):
                add(violations, "failed_stage_family_task_ids_invalid", stage=stage, bucket=bucket)

    runtime = receipt.get("runtime")
    runtime_fields = {
        "wall_seconds",
        "peak_memory_mb",
        "attempted_tasks",
        "failed_tasks",
        "failure_rate",
        "timed_out_task_ids",
    }
    if not isinstance(runtime, dict):
        add(violations, "failed_stage_runtime_missing", stage=stage)
    else:
        validate_object_keys(
            runtime,
            runtime_fields,
            runtime_fields,
            violations,
            "failed_stage_runtime_fields_invalid",
            stage=stage,
        )
        attempted = runtime.get("attempted_tasks")
        failed = runtime.get("failed_tasks")
        if (
            type(attempted) is not int
            or type(failed) is not int
            or not 1 <= attempted <= stage_contract.get("expected_tasks", 0)
            or not 1 <= failed <= attempted
        ):
            add(violations, "failed_stage_runtime_count_invalid", stage=stage)
        else:
            rate = runtime.get("failure_rate")
            if type(rate) not in {int, float} or abs(float(rate) - failed / attempted) > 1e-12:
                add(violations, "failed_stage_failure_rate_mismatch", stage=stage)
        for key in ("wall_seconds", "peak_memory_mb"):
            if type(runtime.get(key)) not in {int, float} or runtime[key] < 0:
                add(violations, "failed_stage_runtime_value_invalid", stage=stage, field=key)
        timeouts = runtime.get("timed_out_task_ids")
        if (
            not isinstance(timeouts, list)
            or len(timeouts) != len(set(timeouts))
            or not all(isinstance(task_id, str) and TASK_ID.fullmatch(task_id) for task_id in timeouts)
            or (type(failed) is int and len(timeouts) > failed)
        ):
            add(violations, "failed_stage_timeout_ids_invalid", stage=stage)

    format_receipt = receipt.get("submission_format")
    format_fields = {
        "validated",
        "task_keys_exact",
        "output_counts_exact",
        "exactly_two_attempts",
        "rectangular_grids",
        "dimensions_1_to_30",
        "colors_0_to_9",
    }
    if not isinstance(format_receipt, dict):
        add(violations, "failed_stage_format_receipt_missing", stage=stage)
    else:
        validate_object_keys(
            format_receipt,
            format_fields,
            format_fields,
            violations,
            "failed_stage_format_fields_invalid",
            stage=stage,
        )
        if any(type(format_receipt.get(key)) is not bool for key in format_fields):
            add(violations, "failed_stage_format_boolean_invalid", stage=stage)
        else:
            guards_pass = all(format_receipt[key] for key in format_fields - {"validated"})
            if format_receipt["validated"] != guards_pass:
                add(violations, "failed_stage_format_aggregate_mismatch", stage=stage)
            if failure_class == "format" and format_receipt["validated"] is not False:
                add(violations, "failed_stage_format_failure_not_proven", stage=stage)
            if failure_class not in {None, "format"} and format_receipt["validated"] is not True:
                add(violations, "failed_stage_prior_format_check_not_passed", stage=stage)

    artifacts = receipt.get("artifacts")
    artifact_fields = {
        "notebook_sha256",
        "input_manifest_sha256",
        "artifact_manifest_sha256",
        "log_sha256",
        "submission_sha256",
        "failure_log_sha256",
    }
    if not isinstance(artifacts, dict):
        add(violations, "failed_stage_artifacts_missing", stage=stage)
    else:
        validate_object_keys(
            artifacts,
            artifact_fields,
            artifact_fields,
            violations,
            "failed_stage_artifact_fields_invalid",
            stage=stage,
        )
        for key in ("notebook_sha256", "input_manifest_sha256", "artifact_manifest_sha256", "log_sha256"):
            if not isinstance(artifacts.get(key), str) or not SHA256.fullmatch(artifacts[key]):
                add(violations, "failed_stage_artifact_hash_invalid", stage=stage, field=key)
        for key in ("submission_sha256", "failure_log_sha256"):
            value = artifacts.get(key)
            if value is not None and (not isinstance(value, str) or not SHA256.fullmatch(value)):
                add(violations, "failed_stage_artifact_hash_invalid", stage=stage, field=key)
        expected_notebook = stage_contract.get("notebook")
        expected_notebook_hash = expected_notebook.get("sha256") if isinstance(expected_notebook, dict) else None
        if artifacts.get("notebook_sha256") != expected_notebook_hash:
            add(violations, "failed_stage_notebook_receipt_mismatch", stage=stage)
        if failure_class == "solver" and not isinstance(artifacts.get("failure_log_sha256"), str):
            add(violations, "failed_stage_solver_failure_log_missing", stage=stage)

    counterexample = receipt.get("minimal_counterexample")
    counterexample_fields = {
        "required",
        "task_id",
        "output_index",
        "family_bucket",
        "artifact_sha256",
        "construction_notes",
    }
    if not isinstance(counterexample, dict):
        add(violations, "failed_stage_counterexample_missing", stage=stage)
    else:
        validate_object_keys(
            counterexample,
            counterexample_fields,
            counterexample_fields,
            violations,
            "failed_stage_counterexample_fields_invalid",
            stage=stage,
        )
        required = failure_class == "solver"
        if counterexample.get("required") is not required:
            add(violations, "failed_stage_counterexample_requirement_mismatch", stage=stage)
        filled_fields = ("task_id", "output_index", "family_bucket", "artifact_sha256")
        if required:
            if not isinstance(counterexample.get("task_id"), str) or not TASK_ID.fullmatch(counterexample["task_id"]):
                add(violations, "failed_stage_counterexample_task_invalid", stage=stage)
            if type(counterexample.get("output_index")) is not int or counterexample["output_index"] < 0:
                add(violations, "failed_stage_counterexample_output_invalid", stage=stage)
            if counterexample.get("family_bucket") not in required_buckets:
                add(violations, "failed_stage_counterexample_family_invalid", stage=stage)
            if not isinstance(counterexample.get("artifact_sha256"), str) or not SHA256.fullmatch(counterexample["artifact_sha256"]):
                add(violations, "failed_stage_counterexample_hash_invalid", stage=stage)
            bucket = counterexample.get("family_bucket")
            if (
                isinstance(family_failures, dict)
                and bucket in family_failures
                and isinstance(family_failures[bucket], dict)
                and counterexample.get("task_id") not in family_failures[bucket].get("affected_task_ids", [])
            ):
                add(violations, "failed_stage_counterexample_not_in_family_failures", stage=stage)
        elif any(counterexample.get(key) is not None for key in filled_fields):
            add(violations, "failed_stage_unneeded_counterexample_populated", stage=stage)
        if not isinstance(counterexample.get("construction_notes"), str) or not counterexample["construction_notes"].strip():
            add(violations, "failed_stage_counterexample_notes_missing", stage=stage)

    ablation = receipt.get("ablation")
    ablation_fields = {
        "required",
        "hypothesis",
        "single_changed_factor",
        "control_artifact_sha256",
        "treatment_artifact_sha256",
        "outcome",
        "improvement_outputs",
    }
    if not isinstance(ablation, dict):
        add(violations, "failed_stage_ablation_missing", stage=stage)
    else:
        validate_object_keys(
            ablation,
            ablation_fields,
            ablation_fields,
            violations,
            "failed_stage_ablation_fields_invalid",
            stage=stage,
        )
        required = failure_class == "solver"
        if ablation.get("required") is not required:
            add(violations, "failed_stage_ablation_requirement_mismatch", stage=stage)
        filled_fields = (
            "hypothesis",
            "single_changed_factor",
            "control_artifact_sha256",
            "treatment_artifact_sha256",
            "outcome",
            "improvement_outputs",
        )
        if required:
            for key in ("hypothesis", "single_changed_factor"):
                if not isinstance(ablation.get(key), str) or not ablation[key].strip():
                    add(violations, "failed_stage_ablation_text_missing", stage=stage, field=key)
            for key in ("control_artifact_sha256", "treatment_artifact_sha256"):
                if not isinstance(ablation.get(key), str) or not SHA256.fullmatch(ablation[key]):
                    add(violations, "failed_stage_ablation_hash_invalid", stage=stage, field=key)
            if ablation.get("control_artifact_sha256") == ablation.get("treatment_artifact_sha256"):
                add(violations, "failed_stage_ablation_artifacts_identical", stage=stage)
            outcome = ablation.get("outcome")
            improvement = ablation.get("improvement_outputs")
            if outcome not in {"IMPROVED", "NO_IMPROVEMENT", "REGRESSED"} or type(improvement) is not int:
                add(violations, "failed_stage_ablation_outcome_invalid", stage=stage)
            elif (
                (outcome == "IMPROVED" and improvement <= 0)
                or (outcome == "NO_IMPROVEMENT" and improvement != 0)
                or (outcome == "REGRESSED" and improvement >= 0)
            ):
                add(violations, "failed_stage_ablation_outcome_mismatch", stage=stage)
        elif any(ablation.get(key) is not None for key in filled_fields):
            add(violations, "failed_stage_unneeded_ablation_populated", stage=stage)

    streak = receipt.get("streak_policy")
    streak_fields = {
        "prior_no_improvement_streak",
        "current_no_improvement_streak",
        "prior_same_failure_streak",
        "current_same_failure_streak",
        "history_receipt_sha256",
        "action",
        "next_solver_family",
    }
    current_same = None
    if not isinstance(streak, dict):
        add(violations, "failed_stage_streak_policy_missing", stage=stage)
    else:
        validate_object_keys(
            streak,
            streak_fields,
            streak_fields,
            violations,
            "failed_stage_streak_fields_invalid",
            stage=stage,
        )
        prior_no = streak.get("prior_no_improvement_streak")
        current_no = streak.get("current_no_improvement_streak")
        prior_same = streak.get("prior_same_failure_streak")
        current_same = streak.get("current_same_failure_streak")
        if (
            type(prior_no) is not int
            or type(current_no) is not int
            or prior_no < 0
            or current_no != prior_no + 1
        ):
            add(violations, "failed_stage_no_improvement_streak_invalid", stage=stage)
        if (
            type(prior_same) is not int
            or type(current_same) is not int
            or prior_same < 0
            or current_same != prior_same + 1
        ):
            add(violations, "failed_stage_same_failure_streak_invalid", stage=stage)
        history = streak.get("history_receipt_sha256")
        history_required = (type(prior_no) is int and prior_no > 0) or (
            type(prior_same) is int and prior_same > 0
        )
        if history_required != isinstance(history, str) or (
            isinstance(history, str) and not SHA256.fullmatch(history)
        ):
            add(violations, "failed_stage_history_receipt_hash_invalid", stage=stage)
        expected_action = None
        if type(current_same) is int and current_same >= 3:
            expected_action = "REPRODUCE_PUBLIC_RESEARCH"
        elif type(current_no) is int and current_no >= 2:
            expected_action = "SWITCH_SOLVER_FAMILY"
        elif type(current_no) is int and type(current_same) is int:
            expected_action = "KEEP_CURRENT_SOLVER"
        if streak.get("action") != expected_action:
            add(violations, "failed_stage_streak_action_mismatch", stage=stage)
        next_family = streak.get("next_solver_family")
        if expected_action == "SWITCH_SOLVER_FAMILY":
            if (
                not isinstance(next_family, str)
                or not next_family.strip()
                or next_family == receipt.get("solver_family")
            ):
                add(violations, "failed_stage_next_solver_family_invalid", stage=stage)
        elif next_family is not None:
            add(violations, "failed_stage_unexpected_next_solver_family", stage=stage)

    research = receipt.get("public_research_reproduction")
    research_fields = {
        "required",
        "source_citation",
        "source_url",
        "reproduction_artifact_sha256",
        "result",
    }
    if not isinstance(research, dict):
        add(violations, "failed_stage_public_research_missing", stage=stage)
    else:
        validate_object_keys(
            research,
            research_fields,
            research_fields,
            violations,
            "failed_stage_public_research_fields_invalid",
            stage=stage,
        )
        required = type(current_same) is int and current_same >= 3
        if research.get("required") is not required:
            add(violations, "failed_stage_public_research_requirement_mismatch", stage=stage)
        filled_fields = ("source_citation", "source_url", "reproduction_artifact_sha256", "result")
        if required:
            for key in ("source_citation", "source_url"):
                if not isinstance(research.get(key), str) or not research[key].strip():
                    add(violations, "failed_stage_public_research_source_missing", stage=stage, field=key)
            source_url = research.get("source_url")
            if isinstance(source_url, str) and not source_url.startswith(("https://", "http://")):
                add(violations, "failed_stage_public_research_url_invalid", stage=stage)
            if not isinstance(research.get("reproduction_artifact_sha256"), str) or not SHA256.fullmatch(research["reproduction_artifact_sha256"]):
                add(violations, "failed_stage_public_research_hash_invalid", stage=stage)
            if research.get("result") not in {"CONFIRMED", "REFUTED", "INCONCLUSIVE"}:
                add(violations, "failed_stage_public_research_result_invalid", stage=stage)
        elif any(research.get(key) is not None for key in filled_fields):
            add(violations, "failed_stage_unneeded_public_research_populated", stage=stage)

    experiment_id = receipt.get("experiment_id")
    return started, completed, experiment_id if isinstance(experiment_id, str) else None


def validate_complete_receipt(
    receipt: Any,
    stage: str,
    candidate_id: str,
    required_buckets: set[str],
    stage_contract: dict[str, Any],
    violations: list[dict[str, Any]],
) -> tuple[datetime | None, datetime | None, float | None, str | None]:
    if not isinstance(receipt, dict):
        add(violations, "stage_receipt_invalid", stage=stage)
        return None, None, None, None
    common_fields = {
        "schema_version",
        "stage",
        "candidate_id",
        "experiment_id",
        "hypothesis",
        "single_changed_factor",
        "data_split",
        "authoritative_status",
        "public_leaderboard_used_for_selection",
        "started_at",
        "completed_at",
        "metrics",
        "family_coverage",
        "runtime",
        "submission_format",
        "artifacts",
        "gates",
    }
    allowed_fields = common_fields | ({"kaggle"} if stage == "competition_rerun" else set())
    validate_object_keys(
        receipt,
        common_fields,
        allowed_fields,
        violations,
        "stage_receipt_fields_invalid",
        stage=stage,
    )
    if receipt.get("schema_version") != 1 or receipt.get("stage") != stage:
        add(violations, "stage_receipt_identity_mismatch", stage=stage)
    if receipt.get("candidate_id") != candidate_id:
        add(violations, "stage_candidate_mismatch", stage=stage)
    for key in ("experiment_id", "hypothesis", "single_changed_factor", "data_split"):
        if not isinstance(receipt.get(key), str) or not receipt[key].strip():
            add(violations, "stage_preregistration_field_missing", stage=stage, field=key)
    for receipt_key, contract_key in (
        ("hypothesis", "hypothesis"),
        ("single_changed_factor", "single_changed_factor"),
        ("data_split", "data_split"),
    ):
        if receipt.get(receipt_key) != stage_contract.get(contract_key):
            add(
                violations,
                "stage_preregistration_mismatch",
                stage=stage,
                field=receipt_key,
            )
    if receipt.get("authoritative_status") != "COMPLETE":
        add(violations, "stage_not_authoritatively_complete", stage=stage)
    if receipt.get("public_leaderboard_used_for_selection") is not False:
        add(violations, "public_leaderboard_selection_forbidden", stage=stage)

    started = parse_timestamp(receipt.get("started_at"), f"{stage}.started_at", violations)
    completed = parse_timestamp(receipt.get("completed_at"), f"{stage}.completed_at", violations)
    if started is not None and completed is not None and completed <= started:
        add(violations, "stage_nonpositive_duration", stage=stage)

    metrics = receipt.get("metrics")
    delta = validate_metrics(metrics, stage, violations)
    tasks = metrics.get("tasks") if isinstance(metrics, dict) and type(metrics.get("tasks")) is int else None
    if isinstance(metrics, dict):
        for field, contract_field in (
            ("tasks", "expected_tasks"),
            ("outputs", "expected_outputs"),
        ):
            if metrics.get(field) != stage_contract.get(contract_field):
                add(
                    violations,
                    "stage_metric_scope_mismatch",
                    stage=stage,
                    field=field,
                    expected=stage_contract.get(contract_field),
                    actual=metrics.get(field),
                )
    runtime = receipt.get("runtime")
    validate_runtime(runtime, stage, tasks, violations)
    failed_tasks = (
        runtime.get("failed_tasks")
        if isinstance(runtime, dict) and type(runtime.get("failed_tasks")) is int
        else None
    )
    validate_family_coverage(
        receipt.get("family_coverage"),
        required_buckets,
        stage,
        tasks,
        failed_tasks,
        violations,
    )
    validate_grid_format(receipt.get("submission_format"), stage, violations)

    artifacts = receipt.get("artifacts")
    required_hashes = {
        "notebook_sha256",
        "input_manifest_sha256",
        "submission_sha256",
        "artifact_manifest_sha256",
    }
    if not isinstance(artifacts, dict):
        add(violations, "stage_artifacts_missing", stage=stage)
    else:
        validate_object_keys(
            artifacts,
            required_hashes,
            required_hashes,
            violations,
            "stage_artifact_fields_invalid",
            stage=stage,
        )
        bad = sorted(
            key
            for key in required_hashes
            if not isinstance(artifacts.get(key), str) or not SHA256.fullmatch(artifacts[key])
        )
        if bad:
            add(violations, "stage_artifact_hash_invalid", stage=stage, fields=bad)
        expected_notebook = (
            stage_contract.get("notebook", {}).get("sha256")
            if isinstance(stage_contract.get("notebook"), dict)
            else None
        )
        if expected_notebook is not None and artifacts.get("notebook_sha256") != expected_notebook:
            add(violations, "stage_notebook_receipt_mismatch", stage=stage)

    gates = receipt.get("gates")
    validate_object_keys(
        gates,
        {"all_passed"},
        {"all_passed", "promote_to_holdout", "non_degradation_vs_anchor"},
        violations,
        "stage_gate_fields_invalid",
        stage=stage,
    )
    if not isinstance(gates, dict) or gates.get("all_passed") is not True:
        add(violations, "stage_hard_gates_failed", stage=stage)
    if stage == "private_development" and (
        not isinstance(gates, dict) or gates.get("promote_to_holdout") is not True
    ):
        add(violations, "development_not_promoted", stage=stage)
    if stage == "sealed_holdout":
        if delta is not None and delta < 0:
            add(violations, "holdout_regressed_vs_anchor", stage=stage, delta=delta)
        if not isinstance(gates, dict) or gates.get("non_degradation_vs_anchor") is not True:
            add(violations, "holdout_non_degradation_gate_failed", stage=stage)
    if stage == "competition_rerun":
        kaggle = receipt.get("kaggle")
        if not isinstance(kaggle, dict):
            add(violations, "competition_kaggle_receipt_missing", stage=stage)
        else:
            kaggle_fields = {
                "submission_id",
                "leaderboard_score",
                "submission_status",
                "score_scope",
                "notebook_version",
                "kernel_slug",
                "score_observed_at",
                "submission_receipt_sha256",
                "reference_name",
                "reference_score",
                "reference_scope",
                "delta_vs_reference",
                "reference_receipt_sha256",
            }
            validate_object_keys(
                kaggle,
                kaggle_fields,
                kaggle_fields,
                violations,
                "competition_kaggle_fields_invalid",
                stage=stage,
            )
            if not isinstance(kaggle.get("submission_id"), (str, int)) or not str(kaggle["submission_id"]).strip():
                add(violations, "competition_submission_id_missing", stage=stage)
            if not isinstance(kaggle.get("leaderboard_score"), (int, float)):
                add(violations, "competition_leaderboard_score_missing", stage=stage)
            elif not 0 <= float(kaggle["leaderboard_score"]) <= 1:
                add(violations, "competition_leaderboard_score_out_of_range", stage=stage)
            if kaggle.get("submission_status") != "complete":
                add(violations, "competition_submission_not_complete", stage=stage)
            if kaggle.get("score_scope") not in {
                "public_leaderboard",
                "private_leaderboard",
                "final",
            }:
                add(violations, "competition_score_scope_invalid", stage=stage)
            if type(kaggle.get("notebook_version")) is not int or kaggle["notebook_version"] < 1:
                add(violations, "competition_notebook_version_invalid", stage=stage)
            if not isinstance(kaggle.get("kernel_slug"), str) or not kaggle["kernel_slug"].strip():
                add(violations, "competition_kernel_slug_missing", stage=stage)
            parse_timestamp(
                kaggle.get("score_observed_at"),
                f"{stage}.kaggle.score_observed_at",
                violations,
            )
            if not isinstance(kaggle.get("submission_receipt_sha256"), str) or not SHA256.fullmatch(kaggle["submission_receipt_sha256"]):
                add(violations, "competition_submission_receipt_hash_invalid", stage=stage)
            reference = stage_contract.get("score_reference")
            if not isinstance(reference, dict):
                add(violations, "competition_score_reference_missing", stage=stage)
            else:
                mapping = {
                    "name": "reference_name",
                    "score": "reference_score",
                    "scope": "reference_scope",
                    "receipt_sha256": "reference_receipt_sha256",
                }
                mismatched = sorted(
                    source
                    for source, target in mapping.items()
                    if kaggle.get(target) != reference.get(source)
                )
                if mismatched:
                    add(
                        violations,
                        "competition_score_reference_mismatch",
                        stage=stage,
                        fields=mismatched,
                    )
                score = kaggle.get("leaderboard_score")
                reference_score = kaggle.get("reference_score")
                delta = kaggle.get("delta_vs_reference")
                if (
                    not isinstance(score, (int, float))
                    or not isinstance(reference_score, (int, float))
                    or not isinstance(delta, (int, float))
                    or abs(float(delta) - (float(score) - float(reference_score))) > 1e-12
                ):
                    add(violations, "competition_score_delta_mismatch", stage=stage)
    experiment_id = receipt.get("experiment_id")
    return (
        started,
        completed,
        delta,
        experiment_id if isinstance(experiment_id, str) else None,
    )


def validate_runtime_smoke_terminal_receipt(
    root: pathlib.Path,
    prerequisite: dict[str, Any],
    receipt: Any,
    violations: list[dict[str, Any]],
) -> tuple[str | None, bool | None]:
    validate_object_keys(
        receipt,
        RUNTIME_SMOKE_RECEIPT_FIELDS,
        RUNTIME_SMOKE_RECEIPT_FIELDS,
        violations,
        "runtime_smoke_terminal_receipt_fields_invalid",
    )
    if not isinstance(receipt, dict):
        add(violations, "runtime_smoke_terminal_receipt_not_object")
        return None, None
    expected = {
        "schema_version": 1,
        "artifact_status": "terminal_runtime_smoke",
        "kernel": RUNTIME_SMOKE_KERNEL,
        "kernel_version": 1,
        "is_private": True,
        "internet_enabled": False,
        "task_id": "bc1d5164",
        "task_count": 1,
        "epochs": 1,
        "expected_optimizer_steps": 1,
        "runtime_sha256": RUNTIME_SMOKE_RUNTIME_SHA256,
        "parent_runtime_sha256": RUNTIME_SMOKE_PARENT_RUNTIME_SHA256,
    }
    mismatched = sorted(key for key, value in expected.items() if receipt.get(key) != value)
    if mismatched:
        add(
            violations,
            "runtime_smoke_terminal_frozen_identity_mismatch",
            fields=mismatched,
        )
    for field in ("data_boundary", "purpose", "claim_boundary"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            add(violations, "runtime_smoke_terminal_text_missing", field=field)

    terminal_status = receipt.get("authoritative_kernel_status")
    if terminal_status not in {"COMPLETE", "ERROR", "CANCELLED"}:
        add(violations, "runtime_smoke_terminal_status_invalid")
        terminal_status = None
    verified = parse_timestamp(
        receipt.get("status_verified_at_cst"),
        "runtime_smoke.terminal_receipt.status_verified_at_cst",
        violations,
    )
    boundary = parse_timestamp(
        prerequisite.get("authorization_boundary_cst"),
        "runtime_smoke.authorization_boundary_cst",
        violations,
    )
    if boundary is not None and verified is not None and verified <= boundary:
        add(violations, "runtime_smoke_terminal_receipt_not_post_boundary")

    guards = receipt.get("guards")
    validate_object_keys(
        guards,
        RUNTIME_SMOKE_TERMINAL_GUARD_FIELDS,
        RUNTIME_SMOKE_TERMINAL_GUARD_FIELDS,
        violations,
        "runtime_smoke_terminal_guard_fields_invalid",
    )
    all_passed: bool | None = None
    if not isinstance(guards, dict):
        add(violations, "runtime_smoke_terminal_guards_missing")
    else:
        invalid = sorted(name for name in RUNTIME_SMOKE_TERMINAL_GUARD_FIELDS if type(guards.get(name)) is not bool)
        if invalid:
            add(violations, "runtime_smoke_terminal_guard_type_invalid", guards=invalid)
        elif guards["all_guards_passed"] != all(
            guards[name] for name in RUNTIME_SMOKE_GUARD_FIELDS
        ):
            add(violations, "runtime_smoke_terminal_guard_aggregate_mismatch")
        else:
            all_passed = guards["all_guards_passed"]

    hashes = receipt.get("source_artifacts")
    paths = receipt.get("source_paths")
    validate_object_keys(
        hashes,
        RUNTIME_SMOKE_SOURCE_FIELDS,
        RUNTIME_SMOKE_SOURCE_FIELDS,
        violations,
        "runtime_smoke_source_artifact_fields_invalid",
    )
    validate_object_keys(
        paths,
        RUNTIME_SMOKE_SOURCE_FIELDS,
        RUNTIME_SMOKE_SOURCE_FIELDS,
        violations,
        "runtime_smoke_source_path_fields_invalid",
    )
    resolved: dict[str, pathlib.Path | None] = {
        name: None for name in RUNTIME_SMOKE_SOURCE_FIELDS
    }
    if isinstance(hashes, dict) and isinstance(paths, dict):
        for name in RUNTIME_SMOKE_SOURCE_FIELDS:
            expected_hash = hashes.get(name)
            raw_path = paths.get(name)
            if expected_hash is None or raw_path is None:
                if expected_hash is not None or raw_path is not None:
                    add(
                        violations,
                        "runtime_smoke_source_path_hash_pair_incomplete",
                        artifact=name,
                    )
                continue
            safe_name = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            path = resolve_file(
                root,
                raw_path,
                violations,
                f"runtime_smoke_source_{safe_name}",
            )
            resolved[name] = path
            if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash):
                add(
                    violations,
                    "runtime_smoke_source_artifact_sha256_invalid",
                    artifact=name,
                )
            elif path is not None and digest(path) != expected_hash:
                add(
                    violations,
                    "runtime_smoke_source_artifact_sha256_mismatch",
                    artifact=name,
                    expected=expected_hash,
                    actual=digest(path),
                )
        for name in ("run_manifest.json", "notebook_sha256", "kernel_metadata_sha256"):
            if hashes.get(name) is None:
                add(violations, "runtime_smoke_required_source_missing", artifact=name)

    frozen_path = resolve_file(
        root,
        prerequisite.get("last_authorized_run_manifest", {}).get("path")
        if isinstance(prerequisite.get("last_authorized_run_manifest"), dict)
        else None,
        violations,
        "runtime_smoke_frozen_run_manifest",
    )
    frozen_run: dict[str, Any] | None = None
    if frozen_path is not None:
        try:
            parsed = json.loads(frozen_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            add(violations, "runtime_smoke_frozen_run_manifest_json_invalid")
        else:
            if isinstance(parsed, dict):
                frozen_run = parsed
            else:
                add(violations, "runtime_smoke_frozen_run_manifest_not_object")
    if frozen_run is not None and isinstance(hashes, dict):
        comparisons = {
            "notebook_sha256": frozen_run.get("notebook_sha256"),
            "kernel_metadata_sha256": frozen_run.get("kernel_metadata_sha256"),
        }
        drift = sorted(name for name, value in comparisons.items() if hashes.get(name) != value)
        if drift:
            add(violations, "runtime_smoke_pushed_artifact_identity_mismatch", fields=drift)
        if frozen_run.get("runtime_sha256") != RUNTIME_SMOKE_RUNTIME_SHA256 or frozen_run.get(
            "parent_runtime_sha256"
        ) != RUNTIME_SMOKE_PARENT_RUNTIME_SHA256:
            add(violations, "runtime_smoke_frozen_runtime_identity_mismatch")

    observation = None
    observation_path = resolved.get("run_manifest.json")
    if observation_path is not None:
        try:
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            add(violations, "runtime_smoke_observation_json_invalid")
        validate_object_keys(
            observation,
            RUNTIME_SMOKE_OBSERVATION_FIELDS,
            RUNTIME_SMOKE_OBSERVATION_FIELDS,
            violations,
            "runtime_smoke_observation_fields_invalid",
        )
        if isinstance(observation, dict):
            if observation.get("schema_version") != 1 or observation.get("kernel") != RUNTIME_SMOKE_KERNEL or observation.get("kernel_version") != 1:
                add(violations, "runtime_smoke_observation_identity_mismatch")
            if observation.get("observation_mode") != "READ_ONLY_KAGGLE_STATUS":
                add(violations, "runtime_smoke_observation_mode_invalid")
            if type(observation.get("artifacts_downloaded")) is not bool:
                add(violations, "runtime_smoke_observation_download_flag_invalid")
            if observation.get("authoritative_kernel_status") != terminal_status or observation.get(
                "status_verified_at_cst"
            ) != receipt.get("status_verified_at_cst"):
                add(violations, "runtime_smoke_observation_receipt_mismatch")
            raw_status = observation.get("raw_status")
            if not isinstance(raw_status, str) or not isinstance(terminal_status, str) or terminal_status.lower() not in raw_status.lower():
                add(violations, "runtime_smoke_observation_raw_status_mismatch")

    source_receipt = None
    source_receipt_path = resolved.get("trm-smoke-receipt.json")
    if source_receipt_path is not None:
        try:
            source_receipt = json.loads(source_receipt_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            add(violations, "runtime_smoke_source_receipt_json_invalid")
        validate_object_keys(
            source_receipt,
            RUNTIME_SMOKE_SOURCE_RECEIPT_FIELDS,
            RUNTIME_SMOKE_SOURCE_RECEIPT_FIELDS,
            violations,
            "runtime_smoke_source_receipt_fields_invalid",
        )
    if isinstance(source_receipt, dict):
        source_guards = source_receipt.get("guards")
        validate_object_keys(
            source_guards,
            RUNTIME_SMOKE_GUARD_FIELDS,
            RUNTIME_SMOKE_GUARD_FIELDS,
            violations,
            "runtime_smoke_source_guard_fields_invalid",
        )
        fixed_source = {
            "purpose": "runtime compatibility smoke; not an accuracy experiment",
            "repair_id": "offline_wandb_stdout_helper_v2",
            "task_id": "bc1d5164",
            "task_count": 1,
            "epochs": 1,
            "expected_optimizer_steps": 1,
            "runtime_sha256": RUNTIME_SMOKE_RUNTIME_SHA256,
            "parent_runtime_sha256": RUNTIME_SMOKE_PARENT_RUNTIME_SHA256,
        }
        source_drift = sorted(
            key for key, value in fixed_source.items() if source_receipt.get(key) != value
        )
        if source_drift:
            add(violations, "runtime_smoke_source_receipt_identity_mismatch", fields=source_drift)
        challenge_hash = source_receipt.get("challenge_sha256")
        if not isinstance(challenge_hash, str) or not SHA256.fullmatch(challenge_hash):
            add(violations, "runtime_smoke_source_challenge_hash_invalid")
        if not isinstance(source_guards, dict) or any(
            type(source_guards.get(name)) is not bool for name in RUNTIME_SMOKE_GUARD_FIELDS
        ):
            add(violations, "runtime_smoke_source_guard_type_invalid")
        else:
            source_all = source_receipt.get("all_guards_passed")
            if type(source_all) is not bool or source_all != all(source_guards.values()):
                add(violations, "runtime_smoke_source_guard_aggregate_mismatch")
            if isinstance(guards, dict) and any(
                guards.get(name) != source_guards.get(name)
                for name in RUNTIME_SMOKE_GUARD_FIELDS
            ):
                add(violations, "runtime_smoke_source_terminal_guard_mismatch")
        elapsed = source_receipt.get("elapsed_seconds")
        returncode = source_receipt.get("returncode")
        if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
            add(violations, "runtime_smoke_source_elapsed_invalid")
        if type(returncode) is not int:
            add(violations, "runtime_smoke_source_returncode_invalid")
        if receipt.get("elapsed_seconds") != elapsed or receipt.get("returncode") != returncode:
            add(violations, "runtime_smoke_source_runtime_mismatch")
        submission_path = resolved.get("trm_submission.json")
        submission_hash = source_receipt.get("submission_sha256")
        if submission_path is None:
            if submission_hash is not None or (
                isinstance(source_guards, dict)
                and source_guards.get("submission_exists") is True
            ):
                add(violations, "runtime_smoke_source_missing_submission_claimed")
        elif not isinstance(hashes, dict) or submission_hash != hashes.get("trm_submission.json"):
            add(violations, "runtime_smoke_source_submission_hash_mismatch")
        if resolved.get("trm-smoke.log") is None:
            add(violations, "runtime_smoke_source_log_missing")
    else:
        if isinstance(guards, dict) and any(guards.get(name) is True for name in RUNTIME_SMOKE_GUARD_FIELDS):
            add(violations, "runtime_smoke_guards_without_source_receipt")
        if receipt.get("elapsed_seconds") is not None or receipt.get("returncode") is not None:
            add(violations, "runtime_smoke_runtime_without_source_receipt")

    if terminal_status == "COMPLETE" and all_passed is True:
        if not isinstance(observation, dict) or observation.get("artifacts_downloaded") is not True:
            add(violations, "runtime_smoke_pass_without_downloaded_artifacts")
        for name in ("trm-smoke-receipt.json", "trm-smoke.log", "trm_submission.json"):
            if not isinstance(hashes, dict) or hashes.get(name) is None:
                add(violations, "runtime_smoke_pass_artifacts_incomplete", artifact=name)
    return terminal_status, all_passed


def validate_runtime_smoke_prerequisite(
    root: pathlib.Path,
    prerequisite: Any,
    violations: list[dict[str, Any]],
) -> str | None:
    if not isinstance(prerequisite, dict):
        add(violations, "runtime_smoke_prerequisite_missing")
        return None
    if prerequisite.get("kernel") != "jahyee/arc2-trm-wandb-log-compat-smoke-v2":
        add(violations, "runtime_smoke_kernel_mismatch")
    if prerequisite.get("kernel_version") != 1:
        add(violations, "runtime_smoke_version_mismatch")
    for field in (
        "last_authorized_run_manifest",
        "local_only_boundary_receipt",
        "local_behavioral_receipt",
        "local_micro_smoke_receipt",
    ):
        verify_bound_file(root, prerequisite.get(field), violations, field)

    observed = parse_timestamp(
        prerequisite.get("last_authorized_observation_cst"),
        "runtime_smoke.last_authorized_observation_cst",
        violations,
    )
    boundary = parse_timestamp(
        prerequisite.get("authorization_boundary_cst"),
        "runtime_smoke.authorization_boundary_cst",
        violations,
    )
    if observed is not None and boundary is not None and boundary <= observed:
        add(violations, "runtime_smoke_boundary_order_invalid")

    status = prerequisite.get("status")
    if status not in {"UNKNOWN", "PASSED", "FAILED"}:
        add(violations, "runtime_smoke_status_invalid")
        return status
    terminal_binding = prerequisite.get("terminal_receipt")
    if status == "UNKNOWN":
        if prerequisite.get("last_authorized_status") != "RUNNING":
            add(violations, "runtime_smoke_unknown_without_running_observation")
        if terminal_binding is not None:
            add(violations, "runtime_smoke_unknown_with_terminal_receipt")
        return status

    terminal_path = verify_bound_file(
        root, terminal_binding, violations, "runtime_smoke_terminal_receipt"
    )
    if terminal_path is None:
        return status
    try:
        receipt = json.loads(terminal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        add(violations, "runtime_smoke_terminal_receipt_json_invalid")
        return status
    terminal_status, all_passed = validate_runtime_smoke_terminal_receipt(
        root, prerequisite, receipt, violations
    )
    if status == "PASSED":
        if terminal_status != "COMPLETE" or all_passed is not True:
            add(violations, "runtime_smoke_pass_not_proven")
    elif all_passed is not False:
        add(violations, "runtime_smoke_failure_not_proven")
    return status


def audit(contract_path: pathlib.Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if contract.get("schema_version") != 1:
        add(violations, "unsupported_schema_version")
    contract_status = contract.get("status")
    if contract_status not in CONTRACT_STATES:
        add(violations, "contract_status_invalid", status=contract_status)
    root_raw = contract.get("project_root")
    if not isinstance(root_raw, str) or not root_raw:
        add(violations, "project_root_missing")
        root = contract_path.parent.resolve()
    else:
        root = (contract_path.parent / root_raw).resolve()
    candidate_id = contract.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        add(violations, "candidate_id_missing")
        candidate_id = ""

    verify_bound_file(root, contract.get("deadline_receipt"), violations, "deadline_receipt")
    verify_bound_file(
        root,
        contract.get("stage_receipt_schema"),
        violations,
        "stage_receipt_schema",
    )
    verify_bound_file(
        root,
        contract.get("stage_failure_receipt_schema"),
        violations,
        "stage_failure_receipt_schema",
    )
    verify_bound_file(
        root,
        contract.get("stage_measurement_builder"),
        violations,
        "stage_measurement_builder",
    )
    verify_bound_file(
        root,
        contract.get("competition_observation_schema"),
        violations,
        "competition_observation_schema",
    )
    verify_bound_file(
        root,
        contract.get("stage_authorization_schema"),
        violations,
        "stage_authorization_schema",
    )
    verify_bound_file(
        root,
        contract.get("stage_authorizer"),
        violations,
        "stage_authorizer",
    )
    buckets_raw = contract.get("required_family_buckets")
    if not isinstance(buckets_raw, list) or len(buckets_raw) != len(set(buckets_raw)):
        add(violations, "required_family_buckets_invalid")
        required_buckets: set[str] = set()
    else:
        required_buckets = set(buckets_raw)
    expected_buckets = {"geometry", "object", "color", "topology", "counting", "composition", "search"}
    if required_buckets != expected_buckets:
        add(violations, "required_family_buckets_wrong", actual=sorted(required_buckets))

    anti_tuning = contract.get("anti_tuning")
    if not isinstance(anti_tuning, dict) or anti_tuning.get("public_leaderboard_used_for_policy_selection") is not False:
        add(violations, "anti_tuning_contract_invalid")

    holdout_integrity_status, holdout_promotion_blocked = validate_holdout_integrity(
        root,
        contract.get("holdout_integrity"),
        candidate_id,
        violations,
        warnings,
    )

    prerequisite_status = validate_runtime_smoke_prerequisite(
        root, contract.get("runtime_smoke_prerequisite"), violations
    )

    stages = contract.get("stages")
    if not isinstance(stages, dict) or tuple(stages) != STAGE_ORDER:
        add(violations, "stage_order_invalid", expected=list(STAGE_ORDER))
        stages = stages if isinstance(stages, dict) else {}

    states: dict[str, str | None] = {}
    completed_times: dict[str, datetime | None] = {}
    authorization_times: dict[str, datetime | None] = {}
    experiment_ids: list[str] = []
    for index, stage in enumerate(STAGE_ORDER, 1):
        item = stages.get(stage)
        if not isinstance(item, dict):
            add(violations, "stage_contract_missing", stage=stage)
            states[stage] = None
            continue
        if item.get("sequence") != index:
            add(violations, "stage_sequence_invalid", stage=stage)
        for key in ("hypothesis", "single_changed_factor", "data_split"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                add(violations, "stage_contract_field_missing", stage=stage, field=key)
        for key in ("expected_tasks", "expected_outputs"):
            if type(item.get(key)) is not int or item[key] <= 0:
                add(violations, "stage_expected_scope_invalid", stage=stage, field=key)
        if stage == "competition_rerun":
            reference = item.get("score_reference")
            reference_fields = {"name", "score", "scope", "receipt_sha256"}
            validate_object_keys(
                reference,
                reference_fields,
                reference_fields,
                violations,
                "competition_score_reference_fields_invalid",
                stage=stage,
            )
            if not isinstance(reference, dict):
                add(violations, "competition_score_reference_missing", stage=stage)
            else:
                if not isinstance(reference.get("name"), str) or not reference["name"].strip():
                    add(violations, "competition_score_reference_name_invalid", stage=stage)
                if not isinstance(reference.get("score"), (int, float)) or not 0 <= float(reference["score"]) <= 1:
                    add(violations, "competition_score_reference_value_invalid", stage=stage)
                if not isinstance(reference.get("scope"), str) or not reference["scope"].strip():
                    add(violations, "competition_score_reference_scope_invalid", stage=stage)
                if not isinstance(reference.get("receipt_sha256"), str) or not SHA256.fullmatch(reference["receipt_sha256"]):
                    add(violations, "competition_score_reference_hash_invalid", stage=stage)
        state = item.get("state")
        states[stage] = state
        if state not in STAGE_STATES:
            add(violations, "stage_state_invalid", stage=stage, state=state)
            continue

        notebook = item.get("notebook")
        if notebook is not None:
            verify_bound_file(root, notebook, violations, f"{stage}_notebook")
        elif state in ACTIVE_STATES:
            add(violations, "active_stage_notebook_missing", stage=stage)

        authorization_binding = item.get("authorization")
        if state in ACTIVE_STATES:
            authorization_times[stage] = validate_stage_authorization(
                root,
                authorization_binding,
                stage,
                candidate_id,
                notebook,
                violations,
            )
        else:
            authorization_times[stage] = None
            if authorization_binding is not None:
                add(violations, "inactive_stage_has_authorization", stage=stage)

        receipt_binding = item.get("receipt")
        if state == "COMPLETE":
            path = verify_bound_file(root, receipt_binding, violations, f"{stage}_receipt")
            receipt = None
            if path is not None:
                try:
                    receipt = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    add(violations, "stage_receipt_json_invalid", stage=stage)
            started, completed, _, experiment_id = validate_complete_receipt(
                receipt,
                stage,
                candidate_id,
                required_buckets,
                item,
                violations,
            )
            completed_times[stage] = completed
            authorized_at = authorization_times.get(stage)
            if (
                authorized_at is not None
                and started is not None
                and started < authorized_at
            ):
                add(violations, "stage_started_before_authorization", stage=stage)
            if (
                authorized_at is not None
                and completed is not None
                and completed <= authorized_at
            ):
                add(violations, "stage_completed_before_authorization", stage=stage)
            if experiment_id:
                experiment_ids.append(experiment_id)
        elif state == "FAILED":
            path = verify_bound_file(root, receipt_binding, violations, f"{stage}_receipt")
            started = None
            completed = None
            experiment_id = None
            if path is not None:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    add(violations, "failed_stage_receipt_json_invalid", stage=stage)
                else:
                    started, completed, experiment_id = validate_failed_receipt(
                        payload,
                        stage,
                        candidate_id,
                        required_buckets,
                        item,
                        violations,
                    )
            completed_times[stage] = completed
            authorized_at = authorization_times.get(stage)
            if (
                authorized_at is not None
                and started is not None
                and started < authorized_at
            ):
                add(violations, "stage_started_before_authorization", stage=stage)
            if (
                authorized_at is not None
                and completed is not None
                and completed <= authorized_at
            ):
                add(violations, "stage_completed_before_authorization", stage=stage)
            if experiment_id:
                experiment_ids.append(experiment_id)
        elif receipt_binding is not None:
            add(violations, "inactive_stage_has_terminal_receipt", stage=stage)

    development_state = states.get("private_development")
    holdout_state = states.get("sealed_holdout")
    competition_state = states.get("competition_rerun")
    if development_state in ACTIVE_STATES and prerequisite_status != "PASSED":
        add(violations, "development_started_without_passing_runtime_smoke")
    if holdout_state in ACTIVE_STATES and development_state != "COMPLETE":
        add(violations, "holdout_started_before_development_promotion")
    if competition_state in ACTIVE_STATES and holdout_state != "COMPLETE":
        add(violations, "competition_started_before_holdout_promotion")
    if holdout_promotion_blocked and holdout_state in ACTIVE_STATES:
        add(violations, "contaminated_holdout_stage_started")
    if holdout_promotion_blocked and competition_state in ACTIVE_STATES:
        add(violations, "competition_started_with_contaminated_holdout")
    for earlier, later in zip(STAGE_ORDER, STAGE_ORDER[1:]):
        first = completed_times.get(earlier)
        second = completed_times.get(later)
        if first is not None and second is not None and second <= first:
            add(violations, "stage_completion_order_invalid", earlier=earlier, later=later)
        later_authorized = authorization_times.get(later)
        if (
            first is not None
            and later_authorized is not None
            and later_authorized <= first
        ):
            add(
                violations,
                "stage_authorized_before_prior_completion",
                earlier=earlier,
                later=later,
            )
    if len(experiment_ids) != len(set(experiment_ids)):
        add(violations, "duplicate_stage_experiment_id")

    pending = [stage for stage in STAGE_ORDER if states.get(stage) != "COMPLETE"]
    if contract_status == "COMPLETE" and pending:
        add(violations, "complete_contract_has_pending_stages", stages=pending)
    if contract_status == "ACTIVE_NOT_COMPLETE" and not pending:
        add(violations, "active_contract_has_no_pending_stages")
    if pending:
        add(warnings, "pipeline_incomplete", stages=pending)
    if prerequisite_status == "UNKNOWN":
        add(warnings, "runtime_smoke_terminal_status_unknown")

    passes = not violations
    pipeline_complete = passes and not pending
    if pipeline_complete:
        next_action = "NONE_PIPELINE_COMPLETE"
    elif holdout_promotion_blocked:
        next_action = "SYSTEMS_NEGATIVE_ONLY_NO_EXTERNAL_GENERALIZATION_RUN"
    elif prerequisite_status == "UNKNOWN":
        next_action = "AUTHORIZED_READ_ONLY_RUNTIME_SMOKE_STATUS"
    elif prerequisite_status == "FAILED":
        next_action = "STOP_TRM_ROUTE_AND_SWITCH_SOLVER_FAMILY"
    elif any(state == "FAILED" for state in states.values()):
        next_action = "STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT"
    elif development_state != "COMPLETE":
        next_action = "PRIVATE_DEVELOPMENT"
    elif holdout_state != "COMPLETE":
        next_action = "SEALED_HOLDOUT"
    else:
        next_action = "COMPETITION_RERUN"
    return {
        "schema_version": 1,
        "contract": contract_path.name,
        "passes": passes,
        "pipeline_complete": pipeline_complete,
        "stage_states": states,
        "holdout_integrity_status": holdout_integrity_status,
        "holdout_promotion_blocked": holdout_promotion_blocked,
        "generalization_route": (
            contract.get("holdout_integrity", {}).get("generalization_route")
            if isinstance(contract.get("holdout_integrity"), dict)
            else None
        ),
        "runtime_smoke_status": prerequisite_status,
        "next_action": next_action,
        "warnings": warnings,
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = audit(args.contract.resolve())
    except (OSError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from error
    stream = sys.stdout if result["passes"] else sys.stderr
    print(json.dumps(result, indent=2, sort_keys=True), file=stream)
    raise SystemExit(0 if result["passes"] else 1)


if __name__ == "__main__":
    main()
