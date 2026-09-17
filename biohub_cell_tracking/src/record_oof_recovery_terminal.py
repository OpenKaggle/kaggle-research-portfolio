#!/usr/bin/env python3
"""Freeze an official failed recovery terminal state without authorizing another run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_STATUS_SOURCE = "Official Kaggle kernel status and execution log APIs"
OFFICIAL_ACTIVITY_SOURCE = "Official authenticated Kaggle Notebook UI Logs page"
FAILED_TERMINAL_STATUSES = {"ERROR", "CANCELLED", "CANCEL_ACKNOWLEDGED"}
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
    status: str, message: str | None, runtime_limit_evidence: bool
) -> tuple[str, str]:
    if status == "CANCEL_ACKNOWLEDGED":
        if runtime_limit_evidence:
            return "official_runtime_limit_cancel_acknowledged", "FAILED_RUNTIME_LIMIT"
        return "cancel_acknowledged", "CANCELLED"
    if status == "CANCELLED":
        return "cancelled", "CANCELLED"
    if re.search(
        r"time|runtime|compute|12\s*hour|quota", (message or "").lower()
    ):
        return "official_runtime_or_compute_limit", "FAILED_RUNTIME_LIMIT"
    return "official_recovery_terminal_error", "FAILED_TERMINAL_ERROR"


def validate_activity(activity: dict, launch: dict) -> None:
    if activity.get("source") != OFFICIAL_ACTIVITY_SOURCE:
        raise ValueError("recovery activity receipt is not from authenticated Kaggle UI")
    for field in ("kernel", "script_version_id", "run_url"):
        if activity.get(field) != launch.get(field):
            raise ValueError(f"recovery activity {field} differs from launch receipt")
    intervention = activity.get("intervention", {})
    if intervention.get("parallel_rerun_allowed") is not False:
        raise ValueError("recovery activity does not preserve the no-parallel-run gate")
    if intervention.get("competition_submission_authorized") is not False:
        raise ValueError("recovery activity improperly authorizes submission")


def record_recovery_terminal(
    status_path: Path,
    launch_path: Path,
    activity_path: Path | None,
    output_dir: Path,
    ledger_path: Path,
    receipt_path: Path,
    experiment_id: str,
) -> dict:
    status_receipt = json.loads(status_path.read_text(encoding="utf-8"))
    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    status = str(status_receipt.get("status", "")).upper()

    if status not in FAILED_TERMINAL_STATUSES:
        raise ValueError(
            f"refusing recovery terminal-failure disposition for non-failed status {status!r}"
        )
    if launch.get("status") != "accepted_recovery_launch":
        raise ValueError("recovery launch receipt is not accepted")
    if launch.get("experiment_id") != experiment_id:
        raise ValueError("recovery launch experiment differs from requested experiment")
    if launch.get("competition_submission_authorized") is not False:
        raise ValueError("recovery launch improperly authorizes submission")
    if status_receipt.get("source") != OFFICIAL_STATUS_SOURCE:
        raise ValueError("recovery terminal status is not official Kaggle evidence")
    if status_receipt.get("log_api_error") is not None:
        raise ValueError("recovery terminal status has a log API error")
    for field in ("kernel", "script_version_id", "run_url"):
        if status_receipt.get(field) != launch.get(field):
            raise ValueError(
                f"recovery terminal {field.replace('_', ' ')} differs from launch receipt"
            )
    if not isinstance(launch.get("script_version_id"), int) or launch.get(
        "script_version_id", 0
    ) <= 0:
        raise ValueError("recovery launch script version is invalid")
    if not output_dir.is_dir():
        raise ValueError("official recovery output collection directory is missing")

    activity = None
    activity_hash = None
    latest_runtime = None
    if activity_path is not None and activity_path.is_file():
        activity = json.loads(activity_path.read_text(encoding="utf-8"))
        validate_activity(activity, launch)
        activity_hash = sha256(activity_path)
        observations = activity.get("activity_observations", [])
        if observations:
            latest_runtime = observations[-1].get("runtime_seconds")

    runtime_limit_evidence = bool(
        isinstance(latest_runtime, (int, float))
        and latest_runtime >= 12 * 3600 - 60
        and activity is not None
        and activity.get("intervention", {}).get("cancelled") is False
    )
    failure_kind, ledger_outcome = classify_failure(
        status, status_receipt.get("failure_message"), runtime_limit_evidence
    )

    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    matching = [row for row in rows if row.get("experiment_id") == experiment_id]
    if len(matching) != 1:
        raise ValueError(f"expected exactly one {experiment_id} ledger row")
    row = matching[0]
    if row.get("kaggle_kernel") != launch.get("kernel"):
        raise ValueError("recovery terminal kernel does not match the experiment ledger")

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

    receipt = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_recovery_terminal_failure",
        "experiment_id": experiment_id,
        "kernel": launch["kernel"],
        "script_version_id": launch["script_version_id"],
        "run_url": launch["run_url"],
        "official_terminal_status": status,
        "failure_message": status_receipt.get("failure_message"),
        "failure_kind": failure_kind,
        "ledger_outcome": ledger_outcome,
        "launch_receipt_sha256": sha256(launch_path),
        "official_status_receipt_sha256": sha256(status_path),
        "activity_receipt_sha256": activity_hash,
        "latest_observed_runtime_seconds": latest_runtime,
        "runtime_limit_evidence": runtime_limit_evidence,
        "official_output_collection_attempted": True,
        "evidence_availability": (
            "minimal_artifacts_present"
            if evidence_files
            else "official_output_empty_or_no_allowed_artifacts"
        ),
        "evidence_files": evidence_files,
        "further_recovery_authorized": False,
        "competition_submission_authorized": False,
        "promotion_authorized": False,
    }

    evidence_summary = ",".join(item["name"] for item in evidence_files) or "none"
    terminal_note = (
        f"official recovery terminal status {status} checked "
        f"{status_receipt.get('checked_at_utc')}; failure_kind={failure_kind}; "
        f"script_version_id={launch['script_version_id']}; status receipt SHA256 "
        f"{receipt['official_status_receipt_sha256']}; launch receipt SHA256 "
        f"{receipt['launch_receipt_sha256']}; collected allowed artifacts="
        f"{evidence_summary}; no further recovery, promotion, or competition submission authorized"
    )
    existing_note = row.get("notes", "")
    if terminal_note not in existing_note:
        row["notes"] = f"{existing_note}; {terminal_note}" if existing_note else terminal_note
    row["outcome"] = ledger_outcome
    if latest_runtime is not None and "runtime_seconds" in fieldnames:
        row["runtime_seconds"] = str(latest_runtime)

    # As with the parent recorder, a retry repairs a process interruption between
    # these two atomic replacements without changing the disposition.
    write_json_atomic(receipt_path, receipt)
    write_ledger_atomic(ledger_path, fieldnames, rows)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        type=Path,
        default=ROOT / "official" / "oof_recovery_kernel_status.json",
    )
    parser.add_argument(
        "--launch",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_launch.json",
    )
    parser.add_argument(
        "--activity",
        type=Path,
        default=ROOT / "official" / "oof_recovery_runtime_activity.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "kaggle_runs" / "BH-0003-terminal",
    )
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "EXPERIMENT_LEDGER.csv"
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_terminal_disposition.json",
    )
    parser.add_argument("--experiment-id", default="BH-0003")
    args = parser.parse_args()
    receipt = record_recovery_terminal(
        args.status,
        args.launch,
        args.activity,
        args.output_dir,
        args.ledger,
        args.receipt,
        args.experiment_id,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
