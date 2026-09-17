#!/usr/bin/env python3
"""Regression checks for local runtime-smoke receipt construction and commit."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    binding,
    build_complete_contract,
    sha256,
    write_json,
)
from paper.tools.audit_three_stage_pipeline import audit  # noqa: E402
from paper.tools.build_runtime_smoke_receipt import (  # noqa: E402
    KERNEL,
    PARENT_RUNTIME_SHA256,
    RUNTIME_SHA256,
    build_runtime_smoke_receipt,
    validate_terminal_receipt,
)
from paper.tools.commit_runtime_smoke_receipt import (  # noqa: E402
    commit_runtime_smoke_receipt,
)


def make_active(root: pathlib.Path) -> tuple[pathlib.Path, dict]:
    contract_path, complete, _ = build_complete_contract(root)
    contract = copy.deepcopy(complete)
    contract["status"] = "ACTIVE_NOT_COMPLETE"
    prerequisite = contract["runtime_smoke_prerequisite"]
    prerequisite["status"] = "UNKNOWN"
    prerequisite["terminal_receipt"] = None
    for stage, state in (
        ("private_development", "PENDING_PREREQUISITE"),
        ("sealed_holdout", "NOT_AUTHORIZED"),
        ("competition_rerun", "NOT_AUTHORIZED"),
    ):
        contract["stages"][stage]["state"] = state
        contract["stages"][stage]["receipt"] = None
        contract["stages"][stage]["authorization"] = None

    notebook = root / "smoke.ipynb"
    notebook.write_text("{}\n", encoding="utf-8")
    metadata = root / "kernel-metadata.json"
    metadata.write_text("{}\n", encoding="utf-8")
    run_manifest_path = root / "last_authorized_run_manifest.json"
    run_manifest = {
        "status": "RUNNING",
        "runtime_sha256": RUNTIME_SHA256,
        "parent_runtime_sha256": PARENT_RUNTIME_SHA256,
        "notebook_sha256": sha256(notebook),
        "kernel_metadata_sha256": sha256(metadata),
        "artifacts": {
            "notebook": {"path": "smoke.ipynb", "sha256": sha256(notebook)},
            "kernel_metadata": {
                "path": "kernel-metadata.json",
                "sha256": sha256(metadata),
            },
        },
    }
    write_json(run_manifest_path, run_manifest)
    prerequisite["last_authorized_run_manifest"] = binding(run_manifest_path, root)
    write_json(contract_path, contract)
    assert audit(contract_path)["passes"] is True
    return contract_path, contract


def write_observation(
    root: pathlib.Path,
    status: str,
    downloaded: bool,
) -> pathlib.Path:
    path = root / "terminal-run-manifest.json"
    write_json(
        path,
        {
            "schema_version": 1,
            "kernel": KERNEL,
            "kernel_version": 1,
            "authoritative_kernel_status": status,
            "status_verified_at_cst": "2026-09-09T00:30:00+00:00",
            "observation_mode": "READ_ONLY_KAGGLE_STATUS",
            "raw_status": f'{KERNEL} has status "{status.lower()}"',
            "artifacts_downloaded": downloaded,
        },
    )
    return path


def write_passing_artifacts(root: pathlib.Path) -> pathlib.Path:
    output = root / "terminal-output"
    output.mkdir()
    log = output / "trm-smoke.log"
    log.write_text("Loading checkpoint\nstep 1 complete\n", encoding="utf-8")
    submission = output / "trm_submission.json"
    submission.write_text(
        json.dumps({"bc1d5164": [{"attempt_1": [[1]], "attempt_2": [[2]]}]}) + "\n",
        encoding="utf-8",
    )
    guards = {
        "runtime_returncode_zero": True,
        "checkpoint_loaded": True,
        "optimizer_constructed": True,
        "scheduler_path_preserved": True,
        "first_step_checkpoint_saved": True,
        "submission_exists": True,
        "submission_schema_valid": True,
    }
    write_json(
        output / "trm-smoke-receipt.json",
        {
            "purpose": "runtime compatibility smoke; not an accuracy experiment",
            "repair_id": "offline_wandb_stdout_helper_v2",
            "single_change": "offline logger helper only",
            "task_id": "bc1d5164",
            "task_count": 1,
            "epochs": 1,
            "expected_optimizer_steps": 1,
            "runtime_sha256": RUNTIME_SHA256,
            "parent_runtime_sha256": PARENT_RUNTIME_SHA256,
            "challenge_sha256": "a" * 64,
            "submission_sha256": hashlib.sha256(submission.read_bytes()).hexdigest(),
            "elapsed_seconds": 42.5,
            "returncode": 0,
            "guards": guards,
            "all_guards_passed": True,
        },
    )
    return output


def write_receipt(root: pathlib.Path, payload: dict) -> pathlib.Path:
    path = root / "terminal-runtime-smoke-receipt.json"
    write_json(path, payload)
    return path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arc2-runtime-smoke-pass-") as raw:
        root = pathlib.Path(raw)
        contract_path, _ = make_active(root)
        observation = write_observation(root, "COMPLETE", True)
        artifacts = write_passing_artifacts(root)
        receipt = build_runtime_smoke_receipt(contract_path, observation, artifacts)
        assert validate_terminal_receipt(contract_path, receipt) == "PASSED"
        receipt_path = write_receipt(root, receipt)
        result = commit_runtime_smoke_receipt(contract_path, receipt_path)
        committed = json.loads(contract_path.read_text(encoding="utf-8"))
        assert result["runtime_smoke_status"] == "PASSED"
        assert result["next_action"] == "PRIVATE_DEVELOPMENT"
        assert result["development_started"] is False
        assert committed["runtime_smoke_prerequisite"]["status"] == "PASSED"
        assert committed["stages"]["private_development"]["state"] == "PENDING_PREREQUISITE"
        assert audit(contract_path)["passes"] is True

        receipt_bytes = receipt_path.read_bytes()
        receipt_payload = json.loads(receipt_bytes)
        receipt_payload["manual_override"] = True
        write_json(receipt_path, receipt_payload)
        committed["runtime_smoke_prerequisite"]["terminal_receipt"] = binding(
            receipt_path, root
        )
        write_json(contract_path, committed)
        extra_field_audit = audit(contract_path)
        assert extra_field_audit["passes"] is False
        assert "runtime_smoke_terminal_receipt_fields_invalid" in {
            row["code"] for row in extra_field_audit["violations"]
        }

        malformed_payload = json.loads(receipt_bytes)
        malformed_payload["guards"] = []
        write_json(receipt_path, malformed_payload)
        committed["runtime_smoke_prerequisite"]["terminal_receipt"] = binding(
            receipt_path, root
        )
        write_json(contract_path, committed)
        malformed_audit = audit(contract_path)
        assert malformed_audit["passes"] is False
        assert "runtime_smoke_terminal_guards_missing" in {
            row["code"] for row in malformed_audit["violations"]
        }

        receipt_path.write_bytes(receipt_bytes)
        committed["runtime_smoke_prerequisite"]["terminal_receipt"] = binding(
            receipt_path, root
        )
        write_json(contract_path, committed)
        (artifacts / "trm-smoke.log").write_text("mutated after binding\n", encoding="utf-8")
        drift_audit = audit(contract_path)
        assert drift_audit["passes"] is False
        assert "runtime_smoke_source_artifact_sha256_mismatch" in {
            row["code"] for row in drift_audit["violations"]
        }

    with tempfile.TemporaryDirectory(prefix="arc2-runtime-smoke-fail-") as raw:
        root = pathlib.Path(raw)
        contract_path, _ = make_active(root)
        observation = write_observation(root, "ERROR", False)
        receipt = build_runtime_smoke_receipt(contract_path, observation, None)
        assert validate_terminal_receipt(contract_path, receipt) == "FAILED"
        receipt_path = write_receipt(root, receipt)
        result = commit_runtime_smoke_receipt(contract_path, receipt_path)
        assert result["runtime_smoke_status"] == "FAILED"
        assert result["next_action"] == "STOP_TRM_ROUTE_AND_SWITCH_SOLVER_FAMILY"
        assert result["development_started"] is False

    with tempfile.TemporaryDirectory(prefix="arc2-runtime-smoke-negative-") as raw:
        root = pathlib.Path(raw)
        contract_path, _ = make_active(root)
        running = write_observation(root, "RUNNING", False)
        running_payload = json.loads(running.read_text(encoding="utf-8"))
        running_payload["authoritative_kernel_status"] = "RUNNING"
        running_payload["raw_status"] = 'status "running"'
        write_json(running, running_payload)
        try:
            build_runtime_smoke_receipt(contract_path, running, None)
        except ValueError as error:
            assert "not terminal" in str(error)
        else:
            raise AssertionError("RUNNING observation produced a terminal receipt")

        observation = write_observation(root, "COMPLETE", True)
        artifacts = write_passing_artifacts(root)
        receipt = build_runtime_smoke_receipt(contract_path, observation, artifacts)
        receipt_path = write_receipt(root, receipt)
        before = contract_path.read_bytes()
        (artifacts / "trm-smoke.log").write_text("mutated\n", encoding="utf-8")
        try:
            commit_runtime_smoke_receipt(contract_path, receipt_path)
        except ValueError as error:
            assert "changed after receipt construction" in str(error)
        else:
            raise AssertionError("source-artifact drift was committed")
        assert contract_path.read_bytes() == before

        try:
            build_runtime_smoke_receipt(contract_path, observation, None)
        except ValueError as error:
            assert "COMPLETE terminal status requires" in str(error) or "artifacts_downloaded" in str(error)
        else:
            raise AssertionError("COMPLETE observation passed without artifacts")

    current_contract = ROOT / "paper/manifests/three_stage_pipeline_v1.json"
    current_before = current_contract.read_bytes()
    try:
        commit_runtime_smoke_receipt(current_contract, ROOT / "does-not-exist.json")
    except ValueError as error:
        assert "does not exist" in str(error)
    else:
        raise AssertionError("missing receipt changed the active contract")
    assert current_contract.read_bytes() == current_before

    print("runtime-smoke receipt builder/commit regression passed")


if __name__ == "__main__":
    main()
