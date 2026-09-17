#!/usr/bin/env python3
"""Atomically bind a validated terminal failure receipt to one running stage.

The receipt must diagnose the already-finished run under the frozen failure
contract.  This tool neither authorizes nor starts a run, and a committed
failure stops the current candidate contract instead of silently permitting a
retry that would erase its history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import tempfile
from typing import Any

try:
    from paper.tools.audit_three_stage_pipeline import (
        STAGE_ORDER,
        audit,
        validate_failed_receipt,
    )
    from paper.tools.build_stage_receipt import contract_root
except ModuleNotFoundError:  # Direct execution from paper/tools.
    from audit_three_stage_pipeline import (  # type: ignore
        STAGE_ORDER,
        audit,
        validate_failed_receipt,
    )
    from build_stage_receipt import contract_root  # type: ignore


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def receipt_in_project(
    root: pathlib.Path, receipt_path: pathlib.Path
) -> tuple[pathlib.Path, str]:
    path = receipt_path.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError("receipt must be inside the contract project root") from error
    if not path.is_file():
        raise ValueError(f"receipt does not exist: {path}")
    return path, relative.as_posix()


def commit_stage_failure_receipt(
    contract_path: pathlib.Path,
    stage: str,
    receipt_path: pathlib.Path,
) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    if stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage: {stage!r}")

    before_bytes = contract_path.read_bytes()
    before_sha256 = sha256_bytes(before_bytes)
    contract = json.loads(before_bytes)
    current_audit = audit(contract_path)
    if not current_audit["passes"]:
        raise ValueError(
            "pipeline contract does not pass before failure receipt commit: "
            + json.dumps(current_audit["violations"], sort_keys=True)
        )
    if contract_path.read_bytes() != before_bytes:
        raise ValueError("contract changed while its current state was being audited")

    stage_contract = contract["stages"][stage]
    if stage_contract.get("state") != "RUNNING" or stage_contract.get("receipt") is not None:
        raise ValueError(f"{stage} must be RUNNING with no bound receipt before commit")

    root = contract_root(contract_path, contract)
    receipt_path, receipt_relative = receipt_in_project(root, receipt_path)
    receipt_bytes = receipt_path.read_bytes()
    receipt_sha256 = sha256_bytes(receipt_bytes)
    receipt = json.loads(receipt_bytes)

    receipt_violations: list[dict[str, Any]] = []
    validate_failed_receipt(
        receipt,
        stage,
        contract["candidate_id"],
        set(contract["required_family_buckets"]),
        stage_contract,
        receipt_violations,
    )
    if receipt_violations:
        raise ValueError(
            "failure receipt failed normalized validation: "
            + json.dumps(receipt_violations, sort_keys=True)
        )

    updated = json.loads(before_bytes)
    updated_stage = updated["stages"][stage]
    updated_stage["state"] = "FAILED"
    updated_stage["receipt"] = {
        "path": receipt_relative,
        "sha256": receipt_sha256,
    }
    updated["status"] = "ACTIVE_NOT_COMPLETE"
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
        if receipt_path.read_bytes() != receipt_bytes:
            raise ValueError("receipt changed while the prospective contract was being audited")
        if contract_path.read_bytes() != before_bytes:
            raise ValueError("contract changed before atomic replacement")

        os.replace(temporary_path, contract_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    committed = audit(contract_path)
    if (
        not committed["passes"]
        or committed["stage_states"].get(stage) != "FAILED"
        or committed["next_action"]
        != "STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT"
    ):
        raise RuntimeError("atomic failure receipt commit produced an invalid contract")
    return {
        "stage": stage,
        "state": "FAILED",
        "receipt_path": receipt_relative,
        "receipt_sha256": receipt_sha256,
        "contract_sha256_before": before_sha256,
        "contract_sha256_after": sha256_bytes(contract_path.read_bytes()),
        "pipeline_complete": False,
        "next_action": committed["next_action"],
        "external_action_performed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--stage", choices=STAGE_ORDER, required=True)
    parser.add_argument("--receipt", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        result = commit_stage_failure_receipt(args.contract, args.stage, args.receipt)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
