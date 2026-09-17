#!/usr/bin/env python3
"""Atomically activate exactly one preregistered stage from a user receipt.

This tool performs no Kaggle action.  It only changes an eligible stage to
RUNNING after validating a narrow, one-run authorization receipt against the
current contract bytes and frozen notebook.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
import pathlib
import sys
import tempfile
from typing import Any

try:
    from paper.tools.audit_three_stage_pipeline import STAGE_ORDER, audit
    from paper.tools.build_stage_receipt import contract_root
except ModuleNotFoundError:  # Direct execution from paper/tools.
    from audit_three_stage_pipeline import STAGE_ORDER, audit  # type: ignore
    from build_stage_receipt import contract_root  # type: ignore


ACTIONS = {
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
EXPECTED_INITIAL_STATES = {
    "private_development": "PENDING_PREREQUISITE",
    "sealed_holdout": "NOT_AUTHORIZED",
    "competition_rerun": "NOT_AUTHORIZED",
}
EXPECTED_NEXT_ACTIONS = {
    "private_development": "PRIVATE_DEVELOPMENT",
    "sealed_holdout": "SEALED_HOLDOUT",
    "competition_rerun": "COMPETITION_RERUN",
}
AUTHORIZATION_FIELDS = {
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def digest(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise ValueError(f"{label} fields differ: missing={missing}, extra={extra}")
    return value


def parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def project_file(root: pathlib.Path, raw: Any, label: str) -> tuple[pathlib.Path, str]:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a repository-relative path")
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} is unsafe")
    path = (root / pathlib.Path(*relative.parts)).resolve()
    try:
        normalized = path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"{label} escapes the project root") from error
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {raw}")
    return path, normalized


def validate_authorization(
    root: pathlib.Path,
    payload: Any,
    stage: str,
    candidate_id: str,
    contract_sha256_before: str,
    existing_notebook: Any,
) -> tuple[datetime, dict[str, str]]:
    payload = exact_keys(payload, AUTHORIZATION_FIELDS, "stage authorization")
    expected = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "stage": stage,
        "decision": "AUTHORIZE_ONE_STAGE_RUN",
        "authorized": True,
        "authorized_by_user": True,
        "contract_sha256_before": contract_sha256_before,
        "allowed_external_action": ACTIONS[stage],
        "one_run_only": True,
        "read_terminal_evidence_after_run": True,
        "public_leaderboard_used_for_selection": False,
        "future_stages_authorized": False,
    }
    drift = {
        key: {"expected": value, "actual": payload.get(key)}
        for key, value in expected.items()
        if payload.get(key) != value
    }
    if drift:
        raise ValueError(
            "stage authorization differs from the eligible transition: "
            + json.dumps(drift, sort_keys=True)
        )
    authorized_at = parse_timestamp(payload.get("authorized_at"), "authorized_at")
    claim = payload.get("claim_boundary")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("authorization claim boundary is missing")
    notebook = exact_keys(payload.get("notebook"), {"path", "sha256"}, "notebook")
    notebook_path, notebook_relative = project_file(root, notebook.get("path"), "notebook")
    actual_notebook_hash = digest(notebook_path)
    if notebook.get("sha256") != actual_notebook_hash:
        raise ValueError("authorization notebook hash mismatch")
    normalized_notebook = {
        "path": notebook_relative,
        "sha256": actual_notebook_hash,
    }
    if existing_notebook is not None and existing_notebook != normalized_notebook:
        raise ValueError("authorization notebook differs from the frozen stage notebook")
    return authorized_at, normalized_notebook


def prior_completion_time(
    root: pathlib.Path, contract: dict[str, Any], stage: str
) -> datetime:
    if stage == "private_development":
        binding = contract["runtime_smoke_prerequisite"].get("terminal_receipt")
        timestamp_field = "status_verified_at_cst"
        label = "runtime-smoke terminal receipt"
    else:
        previous = STAGE_ORDER[STAGE_ORDER.index(stage) - 1]
        binding = contract["stages"][previous].get("receipt")
        timestamp_field = "completed_at"
        label = f"{previous} receipt"
    if not isinstance(binding, dict):
        raise ValueError(f"{label} binding is missing")
    path, _ = project_file(root, binding.get("path"), label)
    if digest(path) != binding.get("sha256"):
        raise ValueError(f"{label} hash mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    return parse_timestamp(payload.get(timestamp_field), f"{label}.{timestamp_field}")


def authorize_stage(
    contract_path: pathlib.Path,
    stage: str,
    authorization_path: pathlib.Path,
) -> dict[str, Any]:
    if stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage: {stage!r}")
    contract_path = contract_path.resolve()
    before_bytes = contract_path.read_bytes()
    before_hash = sha256_bytes(before_bytes)
    current = audit(contract_path)
    if not current["passes"]:
        raise ValueError(
            "pipeline contract does not pass before stage authorization: "
            + json.dumps(current["violations"], sort_keys=True)
        )
    if current["next_action"] != EXPECTED_NEXT_ACTIONS[stage]:
        raise ValueError(
            f"{stage} is not the next eligible stage: {current['next_action']}"
        )
    contract = json.loads(before_bytes)
    item = contract["stages"][stage]
    if (
        item.get("state") != EXPECTED_INITIAL_STATES[stage]
        or item.get("receipt") is not None
        or item.get("authorization") is not None
    ):
        raise ValueError(f"{stage} is not in its unbound pre-run state")
    root = contract_root(contract_path, contract)
    authorization_path = authorization_path.resolve()
    try:
        authorization_relative = authorization_path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("authorization receipt must be inside the project root") from error
    if not authorization_path.is_file():
        raise ValueError("authorization receipt does not exist")
    authorization_bytes = authorization_path.read_bytes()
    authorization = json.loads(authorization_bytes)
    authorized_at, notebook = validate_authorization(
        root,
        authorization,
        stage,
        contract["candidate_id"],
        before_hash,
        item.get("notebook"),
    )
    prior_completed = prior_completion_time(root, contract, stage)
    if authorized_at <= prior_completed:
        raise ValueError("stage authorization does not postdate its prerequisite")

    updated = json.loads(before_bytes)
    updated_item = updated["stages"][stage]
    updated_item["state"] = "RUNNING"
    updated_item["notebook"] = notebook
    updated_item["authorization"] = {
        "path": authorization_relative,
        "sha256": sha256_bytes(authorization_bytes),
    }
    rendered = (json.dumps(updated, indent=2) + "\n").encode("utf-8")

    temporary_path: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=contract_path.parent,
            prefix=f".{contract_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = pathlib.Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        prospective = audit(temporary_path)
        if not prospective["passes"]:
            raise ValueError(
                "prospective contract failed audit: "
                + json.dumps(prospective["violations"], sort_keys=True)
            )
        if contract_path.read_bytes() != before_bytes:
            raise ValueError("contract changed before atomic stage authorization")
        if authorization_path.read_bytes() != authorization_bytes:
            raise ValueError("authorization receipt changed before commit")
        validate_authorization(
            root,
            authorization,
            stage,
            contract["candidate_id"],
            before_hash,
            item.get("notebook"),
        )
        os.replace(temporary_path, contract_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    committed = audit(contract_path)
    if (
        not committed["passes"]
        or committed["stage_states"].get(stage) != "RUNNING"
    ):
        raise RuntimeError("atomic stage authorization produced an invalid contract")
    return {
        "stage": stage,
        "state": "RUNNING",
        "authorization_path": authorization_relative,
        "authorization_sha256": sha256_bytes(authorization_bytes),
        "contract_sha256_before": before_hash,
        "contract_sha256_after": sha256_bytes(contract_path.read_bytes()),
        "external_action_performed": False,
        "allowed_external_action": ACTIONS[stage],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--stage", choices=STAGE_ORDER, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        result = authorize_stage(args.contract, args.stage, args.authorization)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
