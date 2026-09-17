#!/usr/bin/env python3
"""Freeze an official failed OOF terminal state and update its ledger row safely."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAILED_TERMINAL_STATUSES = {"ERROR", "CANCELLED", "CANCEL_ACKNOWLEDGED"}
TERMINAL_ACTIVITY_CLASSIFICATIONS = {
    "ACTIVE_BUT_RUNTIME_INFEASIBLE",
    "RUNTIME_LIMIT_CANCELLATION_ACKNOWLEDGED",
}
ALLOWED_EVIDENCE_NAMES = {
    "budgeted_oof_protocol.json",
    "budgeted_oof_partial.json",
    "budgeted_oof_receipt.json",
    "fold_0_train.log",
    "fold_0_predict.log",
    "fold_1_train.log",
    "fold_1_predict.log",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def write_ledger_atomic(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def classify_failure(
    status: str, message: str | None, runtime_limit_evidence: bool = False
) -> tuple[str, str]:
    if status == "CANCEL_ACKNOWLEDGED":
        if runtime_limit_evidence:
            return (
                "official_runtime_limit_cancel_acknowledged",
                "FAILED_RUNTIME_LIMIT",
            )
        return "cancel_acknowledged", "CANCELLED"
    if status == "CANCELLED":
        return "cancelled", "CANCELLED"
    normalized = (message or "").lower()
    if re.search(r"time|runtime|compute|12\s*hour|quota", normalized):
        return "official_runtime_or_compute_limit", "FAILED_RUNTIME_LIMIT"
    return "official_terminal_error_after_runtime_infeasible_run", "FAILED_TERMINAL_ERROR"


def record_terminal(
    status_path: Path,
    activity_path: Path,
    output_dir: Path,
    ledger_path: Path,
    receipt_path: Path,
    experiment_id: str,
) -> dict:
    status_receipt = json.loads(status_path.read_text(encoding="utf-8"))
    activity = json.loads(activity_path.read_text(encoding="utf-8"))
    status = str(status_receipt.get("status", "")).upper()
    kernel = str(status_receipt.get("kernel", ""))

    if status not in FAILED_TERMINAL_STATUSES:
        raise ValueError(
            f"refusing terminal-failure disposition for non-failed status {status!r}"
        )
    if status_receipt.get("source") != "Official Kaggle kernel status and execution log APIs":
        raise ValueError("status receipt is not from the official Kaggle API")
    if activity.get("source") != "Official authenticated Kaggle Notebook UI Logs page":
        raise ValueError("activity receipt is not from the authenticated Kaggle UI")
    if activity.get("kernel") != kernel:
        raise ValueError("status and activity kernel identifiers differ")
    if activity.get("classification") not in TERMINAL_ACTIVITY_CLASSIFICATIONS:
        raise ValueError("activity receipt does not prove runtime infeasibility")
    if activity.get("projection", {}).get("assessment") != "runtime_infeasible":
        raise ValueError("runtime projection is not marked infeasible")
    if activity.get("intervention", {}).get("parallel_rerun_allowed") is not False:
        raise ValueError("activity receipt does not preserve the no-parallel-run gate")
    if not output_dir.is_dir():
        raise ValueError("official output collection directory is missing")

    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    matching = [row for row in rows if row.get("experiment_id") == experiment_id]
    if len(matching) != 1:
        raise ValueError(f"expected exactly one {experiment_id} ledger row")
    row = matching[0]
    if row.get("kaggle_kernel") != kernel:
        raise ValueError("terminal kernel does not match the experiment ledger")

    evidence_files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name in ALLOWED_EVIDENCE_NAMES:
            evidence_files.append(
                {
                    "name": path.name,
                    "relative_path": str(path.relative_to(output_dir)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    latest_observation = activity.get("activity_observations", [])[-1]
    latest_runtime = latest_observation.get("runtime_seconds")
    runtime_limit_evidence = (
        isinstance(latest_runtime, (int, float))
        and latest_runtime >= 12 * 3600 - 60
        and activity.get("intervention", {}).get("cancelled") is False
        and activity.get("projection", {}).get("assessment")
        == "runtime_infeasible"
    )
    failure_kind, ledger_outcome = classify_failure(
        status, status_receipt.get("failure_message"), runtime_limit_evidence
    )
    receipt = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_terminal_failure",
        "experiment_id": experiment_id,
        "kernel": kernel,
        "script_version_id": activity.get("script_version_id"),
        "official_terminal_status": status,
        "failure_message": status_receipt.get("failure_message"),
        "failure_kind": failure_kind,
        "ledger_outcome": ledger_outcome,
        "official_status_receipt_sha256": sha256(status_path),
        "activity_receipt_sha256": sha256(activity_path),
        "latest_observed_runtime_seconds": latest_runtime,
        "runtime_limit_evidence": runtime_limit_evidence,
        "runtime_projection_hours_two_folds": activity.get("projection", {}).get(
            "projected_training_hours_two_folds"
        ),
        "official_output_collection_attempted": True,
        "evidence_availability": (
            "minimal_artifacts_present"
            if evidence_files
            else "official_output_empty_or_no_allowed_artifacts"
        ),
        "evidence_files": evidence_files,
        "recovery_authorized": True,
        "recovery_scope": "one epoch per fold; no parallel execution",
    }

    evidence_summary = ",".join(item["name"] for item in evidence_files) or "none"
    terminal_note = (
        f"official terminal status {status} checked {status_receipt.get('checked_at_utc')}; "
        f"failure_kind={failure_kind}; status receipt SHA256 "
        f"{receipt['official_status_receipt_sha256']}; activity receipt SHA256 "
        f"{receipt['activity_receipt_sha256']}; collected allowed artifacts={evidence_summary}; "
        "one-epoch recovery authorized only after terminal receipt and fresh preflight"
    )
    existing_note = row.get("notes", "")
    if terminal_note not in existing_note:
        row["notes"] = f"{existing_note}; {terminal_note}" if existing_note else terminal_note
    row["outcome"] = ledger_outcome
    runtime = receipt["latest_observed_runtime_seconds"]
    if runtime is not None:
        row["runtime_seconds"] = str(runtime)

    # The receipt is committed before the ledger. A retry is idempotent and repairs a
    # process interruption between the two atomic replacements.
    write_json_atomic(receipt_path, receipt)
    write_ledger_atomic(ledger_path, fieldnames, rows)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status", type=Path, default=ROOT / "official" / "oof_kernel_status.json"
    )
    parser.add_argument(
        "--activity",
        type=Path,
        default=ROOT / "official" / "oof_runtime_activity.json",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "kaggle_runs" / "BH-0002-terminal"
    )
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "EXPERIMENT_LEDGER.csv"
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=ROOT / "artifacts" / "oof_terminal_disposition.json",
    )
    parser.add_argument("--experiment-id", default="BH-0002")
    args = parser.parse_args()
    receipt = record_terminal(
        args.status,
        args.activity,
        args.output_dir,
        args.ledger,
        args.receipt,
        args.experiment_id,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
