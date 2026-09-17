#!/usr/bin/env python3
"""Idempotently register lifecycle receipts in campaign status and the experiment ledger."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_COLUMNS = [
    "started_at_utc", "experiment", "task", "hypothesis", "only_change",
    "local_evaluator", "local_score", "cross_corridor_summary", "fd_lwr_summary",
    "runtime_seconds", "peak_memory_mb", "submission_path", "sha256",
    "submission_id", "public_score", "status", "conclusion",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_ledger(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPERIMENT_COLUMNS:
            raise ValueError("experiment ledger header does not match the frozen contract")
        return list(reader)


def _ledger_text(rows: list[dict[str, str]]) -> str:
    sink = io.StringIO(newline="")
    writer = csv.DictWriter(sink, fieldnames=EXPERIMENT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return sink.getvalue()


def _utc_z(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("receipt execution timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _relative_receipt(traffic_root: Path, receipt_path: Path) -> str:
    try:
        return str(receipt_path.resolve().relative_to(traffic_root.resolve()))
    except ValueError as error:
        raise ValueError("receipt must be stored inside the traffic workspace") from error


def _validate_registration_inputs(
    receipt: dict[str, object],
    status_path: Path,
    ledger_path: Path,
    submission_ledger_path: Path,
    *,
    status_already_registered: bool,
    ledger_already_registered: bool,
) -> None:
    inputs = receipt["inputs"]
    if not status_already_registered and inputs["campaign_status.json"] != sha256(status_path):
        raise ValueError("receipt was not generated from the current campaign status")
    if not ledger_already_registered and inputs["experiment_ledger.csv"] != sha256(ledger_path):
        raise ValueError("receipt was not generated from the current experiment ledger")
    if inputs["submission_ledger.csv"] != sha256(submission_ledger_path):
        raise ValueError("receipt submission-ledger input is stale")


def _append_once(
    rows: list[dict[str, str]], receipt_sha: str, row: dict[str, str]
) -> tuple[list[dict[str, str]], bool]:
    matching_sha = [existing for existing in rows if existing["sha256"] == receipt_sha]
    if len(matching_sha) > 1:
        raise ValueError("receipt appears more than once in the experiment ledger")
    if matching_sha:
        return rows, False
    conflicting_name = [existing for existing in rows if existing["experiment"] == row["experiment"]]
    if conflicting_name:
        raise ValueError("experiment name is already registered with another receipt")
    timestamp = datetime.fromisoformat(row["started_at_utc"].replace("Z", "+00:00"))
    if rows:
        previous = datetime.fromisoformat(rows[-1]["started_at_utc"].replace("Z", "+00:00"))
        if timestamp < previous:
            raise ValueError("receipt execution time would make the experiment ledger non-monotonic")
    return [*rows, row], True


def register_readiness(traffic_root: Path, receipt_path: Path) -> dict[str, object]:
    traffic_root = traffic_root.resolve()
    receipt_path = receipt_path.resolve()
    artifacts = traffic_root / "artifacts"
    status_path = artifacts / "campaign_status.json"
    ledger_path = artifacts / "experiment_ledger.csv"
    submission_ledger_path = artifacts / "submission_ledger.csv"
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] not in {"READY", "READY_FOR_FINAL_SELECTION"}:
        raise ValueError("only clean or D-3 preselection readiness may be activated")
    activation = receipt.get("activation", {})
    activation_age = activation.get("observed_as_of_age_seconds")
    if activation.get("requested") is not True or activation_age is None:
        raise ValueError("readiness receipt was not generated in activation mode")
    if not (-60 <= float(activation_age) <= 15 * 60):
        raise ValueError("readiness receipt did not pass the live activation clock gate")
    if receipt["archive_sha_verified_now"] is not True:
        raise ValueError("activated readiness must verify the public archive SHA now")
    if receipt["status"] == "READY_FOR_FINAL_SELECTION" and (
        receipt["phase"] != "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"
        or receipt["checks_failed"] != 1
        or len(receipt.get("failures", [])) != 1
        or receipt["failures"][0].get("requirement") != "D3_final_selection_control"
    ):
        raise ValueError("D-3 preselection readiness has an invalid failure set")
    receipt_sha = sha256(receipt_path)
    receipt_rel = _relative_receipt(traffic_root, receipt_path)
    status = json.loads(status_path.read_text())
    rows = _read_ledger(ledger_path)
    status_registered = status.get("lifecycle", {}).get("readiness", {}).get("receipt_sha256") == receipt_sha
    ledger_registered = any(row["sha256"] == receipt_sha for row in rows)
    _validate_registration_inputs(
        receipt, status_path, ledger_path, submission_ledger_path,
        status_already_registered=status_registered,
        ledger_already_registered=ledger_registered,
    )

    status["lifecycle"].update({"as_of": receipt["as_of"], "phase": receipt["phase"]})
    status["lifecycle"]["readiness"] = {
        "status": receipt["status"],
        "checks_passed": receipt["checks_passed"],
        "checks_warned": receipt["checks_warned"],
        "checks_failed": receipt["checks_failed"],
        "archive_sha_verified_now": receipt["archive_sha_verified_now"],
        "runtime_seconds": receipt["runtime_seconds"],
        "peak_memory_mb": receipt["peak_memory_mb"],
        "receipt_path": receipt_rel,
        "receipt_sha256": receipt_sha,
    }
    ledger_row = {
        "started_at_utc": _utc_z(str(receipt["executed_at_utc"])),
        "experiment": str(receipt["experiment"]),
        "task": "all",
        "hypothesis": "The lifecycle evidence remains valid at the declared competition phase",
        "only_change": "Register a read-only campaign audit; no prediction or Kaggle action",
        "local_evaluator": "Four-task lifecycle integrity and information-boundary audit",
        "local_score": f"{receipt['checks_passed']} PASS {receipt['checks_warned']} WARN {receipt['checks_failed']} FAIL",
        "cross_corridor_summary": "All released panels and frozen cross-corridor evidence remain covered",
        "fd_lwr_summary": "Public FD retained; organizer-only LWR remains inaccessible and null",
        "runtime_seconds": str(receipt["runtime_seconds"]),
        "peak_memory_mb": str(receipt["peak_memory_mb"]),
        "submission_path": f"traffic/{receipt_rel}",
        "sha256": receipt_sha,
        "submission_id": "",
        "public_score": "",
        "status": str(receipt["status"]),
        "conclusion": str(receipt["goal_completion_boundary"]),
    }
    updated_rows, appended = _append_once(rows, receipt_sha, ledger_row)
    if not status_registered:
        _atomic_write(status_path, json.dumps(status, indent=2) + "\n")
    if appended:
        _atomic_write(ledger_path, _ledger_text(updated_rows))
    return {"status": "REGISTERED" if appended or not status_registered else "ALREADY_REGISTERED", "receipt_sha256": receipt_sha}


def register_final_selection(traffic_root: Path, receipt_path: Path) -> dict[str, object]:
    traffic_root = traffic_root.resolve()
    receipt_path = receipt_path.resolve()
    artifacts = traffic_root / "artifacts"
    status_path = artifacts / "campaign_status.json"
    ledger_path = artifacts / "experiment_ledger.csv"
    submission_ledger_path = artifacts / "submission_ledger.csv"
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] != "FINAL_SELECTED" or receipt["selection_final"] is not True:
        raise ValueError("only a completed non-dry final-selection receipt may be registered")
    if receipt["external_kaggle_action_performed"] is not False:
        raise ValueError("the selector must not claim an unverified external Kaggle action")
    clock_gate = receipt.get("clock_gate", {})
    live_age = clock_gate.get("observed_as_of_age_seconds")
    readiness_age = clock_gate.get("observed_D3_readiness_age_seconds")
    if clock_gate.get("live_clock_enforced") is not True or live_age is None:
        raise ValueError("final-selection receipt did not enforce the live clock")
    if not (-60 <= float(live_age) <= 15 * 60):
        raise ValueError("final-selection receipt failed the live clock window")
    if readiness_age is None or not (0 <= float(readiness_age) <= 15 * 60):
        raise ValueError("final-selection receipt did not consume fresh D-3 readiness")
    receipt_sha = sha256(receipt_path)
    receipt_rel = _relative_receipt(traffic_root, receipt_path)
    status = json.loads(status_path.read_text())
    rows = _read_ledger(ledger_path)
    selected = receipt["selected"]
    if (
        selected["submission_id"] != status["current_best"]["submission_id"]
        or selected["sha256"] != status["current_best"]["sha256"]
        or float(selected["public_score"]) != float(status["current_best"]["public_score"])
        or receipt["fallback"]["submission_id"] != status["current_candidate"]["fallback_submission_id"]
        or receipt["inputs"]["readiness_receipt.json"] != status["lifecycle"]["readiness"]["receipt_sha256"]
    ):
        raise ValueError("final-selection receipt disagrees with frozen campaign state")
    status_registered = status.get("final_selection", {}).get("receipt_sha256") == receipt_sha
    ledger_registered = any(row["sha256"] == receipt_sha for row in rows)
    _validate_registration_inputs(
        receipt, status_path, ledger_path, submission_ledger_path,
        status_already_registered=status_registered,
        ledger_already_registered=ledger_registered,
    )

    status["final_selection"] = {
        "status": receipt["status"],
        "as_of": receipt["as_of"],
        "executed_at_utc": receipt["executed_at_utc"],
        "submission_id": selected["submission_id"],
        "public_score": selected["public_score"],
        "sha256": selected["sha256"],
        "fallback_submission_id": receipt["fallback"]["submission_id"],
        "external_kaggle_action_performed": False,
        "campaign_goal_complete": False,
        "receipt_path": receipt_rel,
        "receipt_sha256": receipt_sha,
    }
    status["next_action"] = "Rerun and activate campaign readiness for the postselection READY receipt; do not modify predictions except for a documented bugfix."
    ledger_row = {
        "started_at_utc": _utc_z(str(receipt["executed_at_utc"])),
        "experiment": str(receipt["experiment"]),
        "task": "all",
        "hypothesis": "The highest completed frozen candidate remains the final selection at D-3",
        "only_change": "Internal final-selection registration; no prediction change or Kaggle mutation",
        "local_evaluator": "Live-clock and fresh-D3-readiness gated final selector",
        "local_score": f"FINAL_SELECTED submission {selected['submission_id']}",
        "cross_corridor_summary": "Frozen whole-table lineage and full replay remain valid",
        "fd_lwr_summary": "No hidden Queue truth boundary flows or hidden ODME metrics used",
        "runtime_seconds": str(receipt["runtime_seconds"]),
        "peak_memory_mb": str(receipt["peak_memory_mb"]),
        "submission_path": f"traffic/{receipt_rel}",
        "sha256": receipt_sha,
        "submission_id": str(selected["submission_id"]),
        "public_score": str(selected["public_score"]),
        "status": "FINAL_SELECTED",
        "conclusion": "Final candidate registered internally; postselection readiness audit remains required",
    }
    updated_rows, appended = _append_once(rows, receipt_sha, ledger_row)
    if not status_registered:
        _atomic_write(status_path, json.dumps(status, indent=2) + "\n")
    if appended:
        _atomic_write(ledger_path, _ledger_text(updated_rows))
    return {"status": "REGISTERED" if appended or not status_registered else "ALREADY_REGISTERED", "receipt_sha256": receipt_sha}


def register_system_manifest(traffic_root: Path, receipt_path: Path) -> dict[str, object]:
    """Atomically register a currently valid implementation-and-evidence manifest."""
    from system_implementation_manifest_audit import verify_current_manifest

    traffic_root = traffic_root.resolve()
    receipt_path = receipt_path.resolve()
    artifacts = traffic_root / "artifacts"
    status_path = artifacts / "campaign_status.json"
    ledger_path = artifacts / "experiment_ledger.csv"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "VALID" or receipt.get("errors") != []:
        raise ValueError("only a valid system implementation manifest may be registered")
    if any(receipt.get("information_boundary", {}).values()):
        raise ValueError("system implementation manifest crossed an information boundary")
    verification_errors = verify_current_manifest(traffic_root, receipt_path)
    if verification_errors:
        raise ValueError("system implementation manifest is stale: " + "; ".join(verification_errors))

    receipt_sha = sha256(receipt_path)
    receipt_rel = _relative_receipt(traffic_root, receipt_path)
    status = json.loads(status_path.read_text(encoding="utf-8"))
    rows = _read_ledger(ledger_path)
    state = status.get("system_implementation_manifest", {})
    status_registered = state.get("receipt_sha256") == receipt_sha
    ledger_registered = any(row["sha256"] == receipt_sha for row in rows)
    status["system_implementation_manifest"] = {
        "status": receipt["status"],
        "files_hashed": receipt["files_hashed"],
        "category_counts": receipt["category_counts"],
        "canonical_receipts_verified": receipt["canonical_receipts_verified"],
        "official_code_commit": receipt["official_code_commit"],
        "runtime_seconds": receipt["runtime_seconds"],
        "peak_memory_mb": receipt["peak_memory_mb"],
        "contract_path": receipt["contract_path"],
        "manifest_sha256": receipt["outputs"]["system_implementation_manifest.csv"],
        "receipt_path": receipt_rel,
        "receipt_sha256": receipt_sha,
    }
    ledger_row = {
        "started_at_utc": _utc_z(str(receipt["executed_at_utc"])),
        "experiment": str(receipt["experiment"]),
        "task": "all",
        "hypothesis": "A reproducible campaign requires one closed fingerprint of implementation and core evidence",
        "only_change": "Register a read-only code config test documentation and receipt manifest; no prediction or Kaggle action",
        "local_evaluator": "Deterministic path-set discovery canonical receipt validation and current SHA recomputation",
        "local_score": f"VALID across {receipt['files_hashed']} files and {receipt['canonical_receipts_verified']} canonical receipts",
        "cross_corridor_summary": "Manifest pins the receipts that cover all released State Queue Physics and ODME panels",
        "fd_lwr_summary": "No competition data submission artifact hidden label boundary flow or hidden metric read",
        "runtime_seconds": str(receipt["runtime_seconds"]),
        "peak_memory_mb": str(receipt["peak_memory_mb"]),
        "submission_path": f"traffic/{receipt_rel}",
        "sha256": receipt_sha,
        "submission_id": "",
        "public_score": "",
        "status": "VALID",
        "conclusion": "Implementation and canonical evidence versions are now machine-verifiable as one closed set",
    }
    updated_rows, appended = _append_once(rows, receipt_sha, ledger_row)
    if not status_registered:
        _atomic_write(status_path, json.dumps(status, indent=2) + "\n")
    if appended and not ledger_registered:
        _atomic_write(ledger_path, _ledger_text(updated_rows))
    return {
        "status": "REGISTERED" if appended or not status_registered else "ALREADY_REGISTERED",
        "receipt_sha256": receipt_sha,
    }
