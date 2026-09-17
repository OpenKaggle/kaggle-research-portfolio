#!/usr/bin/env python3
"""Atomically bind a validated terminal runtime-smoke receipt.

The tool changes only the runtime-smoke prerequisite.  A passing receipt makes
private development the next action but does not authorize or start it.  Any
terminal kernel/guard failure freezes the prerequisite as FAILED.
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
    from paper.tools.audit_three_stage_pipeline import audit
    from paper.tools.build_runtime_smoke_receipt import validate_terminal_receipt
    from paper.tools.build_stage_receipt import contract_root
except ModuleNotFoundError:  # Direct execution from paper/tools.
    from audit_three_stage_pipeline import audit  # type: ignore
    from build_runtime_smoke_receipt import validate_terminal_receipt  # type: ignore
    from build_stage_receipt import contract_root  # type: ignore


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def commit_runtime_smoke_receipt(
    contract_path: pathlib.Path,
    receipt_path: pathlib.Path,
) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    before_bytes = contract_path.read_bytes()
    before_hash = sha256_bytes(before_bytes)
    current = audit(contract_path)
    if not current["passes"]:
        raise ValueError(
            "pipeline contract does not pass before runtime-smoke commit: "
            + json.dumps(current["violations"], sort_keys=True)
        )
    contract = json.loads(before_bytes)
    prerequisite = contract.get("runtime_smoke_prerequisite")
    if not isinstance(prerequisite, dict):
        raise ValueError("runtime-smoke prerequisite is missing")
    if prerequisite.get("status") != "UNKNOWN" or prerequisite.get("terminal_receipt") is not None:
        raise ValueError("runtime-smoke prerequisite must still be UNKNOWN and unbound")
    root = contract_root(contract_path, contract)
    receipt_path = receipt_path.resolve()
    try:
        receipt_relative = receipt_path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("receipt must be inside the contract project root") from error
    if not receipt_path.is_file():
        raise ValueError("runtime-smoke receipt does not exist")
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    derived_status = validate_terminal_receipt(contract_path, receipt)

    updated = json.loads(before_bytes)
    updated_prerequisite = updated["runtime_smoke_prerequisite"]
    updated_prerequisite["status"] = derived_status
    updated_prerequisite["terminal_receipt"] = {
        "path": receipt_relative,
        "sha256": sha256_bytes(receipt_bytes),
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
            raise ValueError("contract changed before atomic replacement")
        if receipt_path.read_bytes() != receipt_bytes:
            raise ValueError("receipt changed before atomic replacement")
        validate_terminal_receipt(contract_path, receipt)
        os.replace(temporary_path, contract_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    committed = audit(contract_path)
    if not committed["passes"] or committed["runtime_smoke_status"] != derived_status:
        raise RuntimeError("atomic runtime-smoke commit produced an invalid contract")
    return {
        "runtime_smoke_status": derived_status,
        "receipt_path": receipt_relative,
        "receipt_sha256": sha256_bytes(receipt_bytes),
        "contract_sha256_before": before_hash,
        "contract_sha256_after": sha256_bytes(contract_path.read_bytes()),
        "development_started": False,
        "next_action": committed["next_action"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--receipt", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        result = commit_runtime_smoke_receipt(args.contract, args.receipt)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
