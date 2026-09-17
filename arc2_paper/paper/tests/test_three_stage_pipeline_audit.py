#!/usr/bin/env python3
"""Regression checks for the fail-closed three-stage execution contract."""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL_PATH = ROOT / "paper/tools/audit_three_stage_pipeline.py"
CONTRACT_PATH = ROOT / "paper/manifests/three_stage_pipeline_v1.json"


def load_tool():
    spec = importlib.util.spec_from_file_location("arc2_three_stage_audit", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load_tool()


class ThreeStagePipelineAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def audit_mutation(self, mutate):
        payload = copy.deepcopy(self.contract)
        mutate(payload)
        with tempfile.TemporaryDirectory(prefix="arc2-three-stage-") as raw:
            path = pathlib.Path(raw) / "contract.json"
            payload["project_root"] = str(ROOT)
            path.write_text(json.dumps(payload), encoding="utf-8")
            return AUDIT.audit(path)

    def test_current_contract_is_valid_but_incomplete(self) -> None:
        result = AUDIT.audit(CONTRACT_PATH)
        self.assertTrue(result["passes"])
        self.assertFalse(result["pipeline_complete"])
        self.assertEqual(result["runtime_smoke_status"], "UNKNOWN")
        self.assertEqual(
            result["holdout_integrity_status"],
            "CONTAMINATED_FOR_V176_GENERALIZATION",
        )
        self.assertTrue(result["holdout_promotion_blocked"])
        self.assertEqual(
            result["generalization_route"],
            "SYSTEMS_NEGATIVE_NO_VERIFIED_UNTOUCHED_CORPUS",
        )
        self.assertEqual(
            result["next_action"],
            "SYSTEMS_NEGATIVE_ONLY_NO_EXTERNAL_GENERALIZATION_RUN",
        )

    def test_holdout_integrity_receipt_hash_is_enforced(self) -> None:
        def mutate(payload):
            payload["holdout_integrity"]["receipt"]["sha256"] = "0" * 64

        result = self.audit_mutation(mutate)
        self.assertFalse(result["passes"])
        self.assertIn(
            "holdout_integrity_receipt_sha256_mismatch",
            {row["code"] for row in result["violations"]},
        )

    def test_same_v3_candidate_cannot_clear_contamination(self) -> None:
        def mutate(payload):
            payload["holdout_integrity"]["status"] = (
                "CLEAR_FOR_METHOD_GENERALIZATION"
            )
            payload["holdout_integrity"]["promotion_blocked"] = False

        result = self.audit_mutation(mutate)
        self.assertFalse(result["passes"])
        self.assertIn(
            "v3_holdout_integrity_status_cannot_be_cleared",
            {row["code"] for row in result["violations"]},
        )

    def test_corpus_availability_receipt_hash_is_enforced(self) -> None:
        def mutate(payload):
            payload["holdout_integrity"]["corpus_availability_receipt"][
                "sha256"
            ] = "0" * 64

        result = self.audit_mutation(mutate)
        self.assertFalse(result["passes"])
        self.assertIn(
            "corpus_availability_receipt_sha256_mismatch",
            {row["code"] for row in result["violations"]},
        )

    def test_smoke_cannot_be_marked_passed_without_terminal_receipt(self) -> None:
        result = self.audit_mutation(
            lambda payload: payload["runtime_smoke_prerequisite"].update(status="PASSED")
        )
        self.assertFalse(result["passes"])
        self.assertIn(
            "runtime_smoke_terminal_receipt_binding_missing",
            {row["code"] for row in result["violations"]},
        )

    def test_unknown_smoke_rejects_a_terminal_receipt(self) -> None:
        def mutate(payload):
            payload["runtime_smoke_prerequisite"]["terminal_receipt"] = payload[
                "deadline_receipt"
            ]

        result = self.audit_mutation(mutate)
        self.assertFalse(result["passes"])
        self.assertIn(
            "runtime_smoke_unknown_with_terminal_receipt",
            {row["code"] for row in result["violations"]},
        )

    def test_last_authorized_state_hash_is_enforced(self) -> None:
        def mutate(payload):
            payload["runtime_smoke_prerequisite"]["last_authorized_run_manifest"][
                "sha256"
            ] = "0" * 64

        result = self.audit_mutation(mutate)
        self.assertFalse(result["passes"])
        self.assertIn(
            "last_authorized_run_manifest_sha256_mismatch",
            {row["code"] for row in result["violations"]},
        )

    def test_failed_stage_schema_hash_is_enforced(self) -> None:
        def mutate(payload):
            payload["stage_failure_receipt_schema"]["sha256"] = "0" * 64

        result = self.audit_mutation(mutate)
        self.assertFalse(result["passes"])
        self.assertIn(
            "stage_failure_receipt_schema_sha256_mismatch",
            {row["code"] for row in result["violations"]},
        )

    def test_development_cannot_start_while_smoke_is_unknown(self) -> None:
        result = self.audit_mutation(
            lambda payload: payload["stages"]["private_development"].update(
                state="RUNNING"
            )
        )
        self.assertFalse(result["passes"])
        self.assertIn(
            "development_started_without_passing_runtime_smoke",
            {row["code"] for row in result["violations"]},
        )

    def test_complete_contract_cannot_keep_pending_stages(self) -> None:
        result = self.audit_mutation(lambda payload: payload.update(status="COMPLETE"))
        self.assertFalse(result["passes"])
        self.assertIn(
            "complete_contract_has_pending_stages",
            {row["code"] for row in result["violations"]},
        )

    def test_completed_receipt_scope_must_match_contract(self) -> None:
        stage_contract = self.contract["stages"]["private_development"]
        receipt = {
            "schema_version": 1,
            "stage": "private_development",
            "candidate_id": self.contract["candidate_id"],
            "experiment_id": "fixture-development",
            "hypothesis": stage_contract["hypothesis"],
            "single_changed_factor": stage_contract["single_changed_factor"],
            "data_split": stage_contract["data_split"],
            "authoritative_status": "COMPLETE",
            "public_leaderboard_used_for_selection": False,
            "started_at": "2026-09-09T08:00:00+08:00",
            "completed_at": "2026-09-09T08:01:00+08:00",
            "metrics": {
                "tasks": 47,
                "outputs": 50,
                "method_exact_outputs": 48,
                "anchor_exact_outputs": 47,
                "attempt_1_exact_outputs": 47,
                "attempt_2_incremental_outputs": 1,
                "method_accuracy": 0.96,
                "anchor_accuracy": 0.94,
                "delta_vs_anchor": 0.02,
            },
            "runtime": {
                "wall_seconds": 60,
                "peak_memory_mb": 1,
                "failed_tasks": 0,
                "failure_rate": 0,
                "timed_out_task_ids": [],
            },
            "family_coverage": {
                bucket: {
                    "tasks": 0,
                    "method_solved": 0,
                    "anchor_solved": 0,
                    "delta": 0,
                    "failed_tasks": 0,
                }
                for bucket in self.contract["required_family_buckets"]
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
                "notebook_sha256": stage_contract["notebook"]["sha256"],
                "input_manifest_sha256": "1" * 64,
                "submission_sha256": "2" * 64,
                "artifact_manifest_sha256": "3" * 64,
            },
            "gates": {"all_passed": True, "promote_to_holdout": True},
        }
        violations = []
        AUDIT.validate_complete_receipt(
            receipt,
            "private_development",
            self.contract["candidate_id"],
            set(self.contract["required_family_buckets"]),
            stage_contract,
            violations,
        )
        self.assertIn(
            "stage_metric_scope_mismatch",
            {row["code"] for row in violations},
        )


if __name__ == "__main__":
    unittest.main()
