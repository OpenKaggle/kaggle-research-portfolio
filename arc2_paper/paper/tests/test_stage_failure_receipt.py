#!/usr/bin/env python3
"""Schema and cross-field regressions for failed-stage diagnostic receipts."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile

from jsonschema import FormatChecker
from jsonschema.validators import validator_for


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    BUCKETS,
    GOOD_HASH,
    binding,
    build_complete_contract,
    sha256,
    write_json,
)
from paper.tools.audit_three_stage_pipeline import audit  # noqa: E402


def failure_receipt(
    notebook_sha256: str,
    failure_class: str = "solver",
    stage: str = "private_development",
) -> dict:
    status_by_name = {
        name: (
            "PASS"
            if failure_class == "solver" or list(("format", "cache", "seed", "budget")).index(name)
            < list(("format", "cache", "seed", "budget")).index(failure_class)
            else "FAIL"
            if name == failure_class
            else "NOT_REACHED"
        )
        for name in ("format", "cache", "seed", "budget")
    }
    solver_failure = failure_class == "solver"
    format_passed = failure_class != "format"
    return {
        "schema_version": 1,
        "stage": stage,
        "candidate_id": "candidate-v1",
        "experiment_id": f"failed-{stage}-v1",
        "hypothesis": "The frozen candidate improves or preserves its anchor.",
        "single_changed_factor": "data split only",
        "data_split": stage,
        "solver_family": "family-a",
        "authoritative_status": "COMPLETE",
        "public_leaderboard_used_for_selection": False,
        "started_at": {
            "private_development": "2026-09-09T00:41:00+00:00",
            "sealed_holdout": "2026-09-09T01:31:00+00:00",
            "competition_rerun": "2026-09-09T02:31:00+00:00",
        }[stage],
        "completed_at": {
            "private_development": "2026-09-09T00:51:00+00:00",
            "sealed_holdout": "2026-09-09T01:41:00+00:00",
            "competition_rerun": "2026-09-09T02:41:00+00:00",
        }[stage],
        "failure_class": failure_class,
        "diagnostics": [
            {
                "name": name,
                "status": status_by_name[name],
                "evidence_sha256": None if status_by_name[name] == "NOT_REACHED" else GOOD_HASH,
                "notes": f"{name} diagnostic frozen",
            }
            for name in ("format", "cache", "seed", "budget")
        ],
        "family_failures": {
            bucket: {
                "tasks": 1 if bucket == "geometry" else 0,
                "failed_tasks": 1 if bucket == "geometry" else 0,
                "affected_task_ids": ["1234abcd"] if bucket == "geometry" else [],
            }
            for bucket in BUCKETS
        },
        "runtime": {
            "wall_seconds": 600,
            "peak_memory_mb": 1024,
            "attempted_tasks": 10,
            "failed_tasks": 1,
            "failure_rate": 0.1,
            "timed_out_task_ids": [],
        },
        "submission_format": {
            "validated": format_passed,
            "task_keys_exact": format_passed,
            "output_counts_exact": True,
            "exactly_two_attempts": True,
            "rectangular_grids": True,
            "dimensions_1_to_30": True,
            "colors_0_to_9": True,
        },
        "artifacts": {
            "notebook_sha256": notebook_sha256,
            "input_manifest_sha256": GOOD_HASH,
            "artifact_manifest_sha256": GOOD_HASH,
            "log_sha256": GOOD_HASH,
            "submission_sha256": GOOD_HASH if solver_failure else None,
            "failure_log_sha256": GOOD_HASH if solver_failure else None,
        },
        "minimal_counterexample": {
            "required": solver_failure,
            "task_id": "1234abcd" if solver_failure else None,
            "output_index": 0 if solver_failure else None,
            "family_bucket": "geometry" if solver_failure else None,
            "artifact_sha256": GOOD_HASH if solver_failure else None,
            "construction_notes": "Minimal one-output counterexample" if solver_failure else "Not applicable before solver diagnosis",
        },
        "ablation": {
            "required": solver_failure,
            "hypothesis": "One isolated solver change repairs the counterexample" if solver_failure else None,
            "single_changed_factor": "solver primitive" if solver_failure else None,
            "control_artifact_sha256": "b" * 64 if solver_failure else None,
            "treatment_artifact_sha256": "c" * 64 if solver_failure else None,
            "outcome": "NO_IMPROVEMENT" if solver_failure else None,
            "improvement_outputs": 0 if solver_failure else None,
        },
        "streak_policy": {
            "prior_no_improvement_streak": 0,
            "current_no_improvement_streak": 1,
            "prior_same_failure_streak": 0,
            "current_same_failure_streak": 1,
            "history_receipt_sha256": None,
            "action": "KEEP_CURRENT_SOLVER",
            "next_solver_family": None,
        },
        "public_research_reproduction": {
            "required": False,
            "source_citation": None,
            "source_url": None,
            "reproduction_artifact_sha256": None,
            "result": None,
        },
        "claim_boundary": "A failed stage is diagnostic evidence, not accuracy or promotion evidence.",
    }


def failed_contract(root: pathlib.Path, receipt: dict) -> pathlib.Path:
    contract_path, contract, _ = build_complete_contract(root)
    receipt_path = root / "failed-development.json"
    write_json(receipt_path, receipt)
    contract["status"] = "ACTIVE_NOT_COMPLETE"
    contract["stages"]["private_development"]["state"] = "FAILED"
    contract["stages"]["private_development"]["receipt"] = binding(receipt_path, root)
    for stage in ("sealed_holdout", "competition_rerun"):
        contract["stages"][stage]["state"] = "NOT_AUTHORIZED"
        contract["stages"][stage]["receipt"] = None
        contract["stages"][stage]["authorization"] = None
    write_json(contract_path, contract)
    return contract_path


def violation_codes(contract_path: pathlib.Path) -> set[str]:
    return {item["code"] for item in audit(contract_path)["violations"]}


def main() -> None:
    schema = json.loads(
        (ROOT / "paper/schemas/stage_failure_receipt_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, format_checker=FormatChecker())

    with tempfile.TemporaryDirectory(prefix="arc2-stage-failure-") as raw:
        root = pathlib.Path(raw)
        _, _, receipts = build_complete_contract(root)
        notebook_hash = sha256(root / "private_development.ipynb")

        first_solver = failure_receipt(notebook_hash)
        validator.validate(first_solver)
        contract_path = failed_contract(root, first_solver)
        result = audit(contract_path)
        assert result["passes"] is True
        assert result["pipeline_complete"] is False
        assert result["next_action"] == "STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT"

        format_failure = failure_receipt(notebook_hash, "format")
        validator.validate(format_failure)
        contract_path = failed_contract(root, format_failure)
        assert audit(contract_path)["passes"] is True

        wrong_order = copy.deepcopy(first_solver)
        wrong_order["diagnostics"][0], wrong_order["diagnostics"][1] = (
            wrong_order["diagnostics"][1],
            wrong_order["diagnostics"][0],
        )
        contract_path = failed_contract(root, wrong_order)
        assert "failed_stage_diagnostic_sequence_mismatch" in violation_codes(contract_path)

        no_counterexample = copy.deepcopy(first_solver)
        no_counterexample["minimal_counterexample"].update(
            required=False,
            task_id=None,
            output_index=None,
            family_bucket=None,
            artifact_sha256=None,
        )
        contract_path = failed_contract(root, no_counterexample)
        assert "failed_stage_counterexample_requirement_mismatch" in violation_codes(contract_path)

        second_no_gain = copy.deepcopy(first_solver)
        second_no_gain["streak_policy"].update(
            prior_no_improvement_streak=1,
            current_no_improvement_streak=2,
            history_receipt_sha256=GOOD_HASH,
            action="SWITCH_SOLVER_FAMILY",
            next_solver_family="family-b",
        )
        contract_path = failed_contract(root, second_no_gain)
        assert audit(contract_path)["passes"] is True
        second_no_gain["streak_policy"].update(
            action="KEEP_CURRENT_SOLVER",
            next_solver_family=None,
        )
        contract_path = failed_contract(root, second_no_gain)
        assert "failed_stage_streak_action_mismatch" in violation_codes(contract_path)

        third_same = copy.deepcopy(first_solver)
        third_same["streak_policy"].update(
            prior_no_improvement_streak=2,
            current_no_improvement_streak=3,
            prior_same_failure_streak=2,
            current_same_failure_streak=3,
            history_receipt_sha256=GOOD_HASH,
            action="REPRODUCE_PUBLIC_RESEARCH",
        )
        third_same["public_research_reproduction"] = {
            "required": True,
            "source_citation": "Public method, exact version",
            "source_url": "https://example.org/paper",
            "reproduction_artifact_sha256": GOOD_HASH,
            "result": "INCONCLUSIVE",
        }
        validator.validate(third_same)
        contract_path = failed_contract(root, third_same)
        assert audit(contract_path)["passes"] is True
        third_same["public_research_reproduction"] = {
            "required": False,
            "source_citation": None,
            "source_url": None,
            "reproduction_artifact_sha256": None,
            "result": None,
        }
        contract_path = failed_contract(root, third_same)
        assert "failed_stage_public_research_requirement_mismatch" in violation_codes(
            contract_path
        )

        missing_family = copy.deepcopy(first_solver)
        del missing_family["family_failures"]["search"]
        contract_path = failed_contract(root, missing_family)
        assert "failed_stage_family_buckets_incomplete" in violation_codes(contract_path)

        extra = copy.deepcopy(first_solver)
        extra["manual_override"] = True
        assert not validator.is_valid(extra)

        assert receipts["private_development"].is_file()

    print("stage failure receipt regression passed")


if __name__ == "__main__":
    main()
