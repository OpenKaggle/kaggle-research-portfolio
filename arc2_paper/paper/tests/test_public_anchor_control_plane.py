#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from paper.tools.audit_public_anchor_control_plane import audit_payload  # noqa: E402


MANIFEST = ROOT / "paper/manifests/public_anchor_control_plane_v1.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def violation_codes(payload: dict) -> set[str]:
    return {item.split(":", 1)[0] for item in audit_payload(ROOT, payload)["violations"]}


def test_active_manifest_passes() -> None:
    result = audit_payload(ROOT, load_manifest())
    assert result["passes"], result
    assert result["control_status"] == "PUBLIC_ANCHOR_SUBMITTED_RUNNING"
    assert result["next_action"] == "WAIT_FOR_SUBMISSION_56287444_TERMINAL_STATE"
    assert result["local_public_output"] == {
        "tasks": 120,
        "outputs": 172,
        "exact_pass2": 3,
        "computed_source_tasks": 4,
        "accuracy_claim_allowed": False,
    }
    assert result["kaggle_dry_run"] == {
        "status": "PASSED",
        "attempts_used": 1,
        "dependency_repairs_used": 0,
        "resolved_kernel_ref": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
        "runtime_seconds": 1697.0,
        "submission": {"tasks": 120, "outputs": 172, "exact_pass2": 3},
    }
    assert result["competition_submission"] == {
        "status": "PENDING",
        "submission_id": 56287444,
        "submitted_kernel_ref": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
        "submitted_version": 1,
        "public_score": None,
        "monitor_automation_id": "arc2-public-anchor-submission-monitor",
    }


def test_candidate_hash_drift_fails() -> None:
    payload = copy.deepcopy(load_manifest())
    payload["candidate"]["notebook"]["sha256"] = "0" * 64
    codes = violation_codes(payload)
    assert "candidate_notebook_sha256_mismatch" in codes
    assert "candidate_not_byte_identical_to_source" in codes


def test_old_route_and_extra_anchor_fail() -> None:
    payload = copy.deepcopy(load_manifest())
    payload["route"] = "RETURN_TO_STABLE_V2_TRM"
    payload["authorization"]["old_v2_trm_actions_allowed"] = True
    payload["authorization"]["additional_public_anchor_allowed"] = True
    codes = violation_codes(payload)
    assert "route_invalid" in codes
    assert "old_v2_trm_actions_not_blocked" in codes
    assert "additional_public_anchor_not_blocked" in codes


def test_failure_budget_and_additional_submission_fail() -> None:
    payload = copy.deepcopy(load_manifest())
    payload["gates"]["kaggle_dry_run"]["maximum_attempts"] = 3
    payload["gates"]["kaggle_dry_run"]["maximum_dependency_repairs"] = 2
    payload["authorization"]["submission_allowed_now"] = True
    codes = violation_codes(payload)
    assert "dry_run_failure_budget_invalid" in codes
    assert "additional_submission_not_blocked" in codes


def test_terminal_receipt_hash_drift_fails() -> None:
    payload = copy.deepcopy(load_manifest())
    payload["kaggle_dry_run_receipt"]["sha256"] = "0" * 64
    codes = violation_codes(payload)
    assert "kaggle_dry_run_receipt_sha256_mismatch" in codes


if __name__ == "__main__":
    test_active_manifest_passes()
    test_candidate_hash_drift_fails()
    test_old_route_and_extra_anchor_fail()
    test_failure_budget_and_additional_submission_fail()
    test_terminal_receipt_hash_drift_fails()
    print("public anchor control-plane tests passed")
