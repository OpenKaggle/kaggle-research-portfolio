#!/usr/bin/env python3
"""Bind a launched recovery kernel to audited local code and its official status."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_LAUNCH_STATUSES = {"RUNNING", "COMPLETE"}


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


def record_launch(
    preflight_path: Path,
    local_source_path: Path,
    remote_source_path: Path,
    metadata_path: Path,
    status_path: Path,
    ledger_path: Path,
    receipt_path: Path,
    script_version_id: int,
    run_url: str,
    experiment_id: str,
) -> dict:
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    status_receipt = json.loads(status_path.read_text(encoding="utf-8"))

    if preflight.get("valid") is not True or preflight.get("launch_allowed") is not True:
        raise ValueError("recovery preflight does not authorize launch")
    if preflight.get("terminal_evidence_valid") is not True:
        raise ValueError("recovery preflight lacks bound terminal evidence")
    if not local_source_path.is_file() or not remote_source_path.is_file():
        raise ValueError("local or pulled-back recovery source is missing")
    local_hash = sha256(local_source_path)
    remote_hash = sha256(remote_source_path)
    if local_hash != remote_hash or local_hash != preflight.get("source_sha256"):
        raise ValueError("pulled-back recovery source differs from audited local source")
    if sha256(metadata_path) != preflight.get("metadata_sha256"):
        raise ValueError("recovery metadata changed after preflight")
    if not metadata.get("is_private"):
        raise ValueError("recovery kernel must remain private")
    if metadata.get("enable_gpu") is not True or metadata.get("enable_internet") is not False:
        raise ValueError("recovery kernel must use GPU with internet disabled")

    official_status = str(status_receipt.get("status", "")).upper()
    if status_receipt.get("source") != "Official Kaggle kernel status and execution log APIs":
        raise ValueError("recovery status receipt is not from the official Kaggle API")
    if status_receipt.get("kernel") != metadata.get("id"):
        raise ValueError("official recovery kernel does not match metadata")
    if official_status not in ACCEPTED_LAUNCH_STATUSES:
        raise ValueError(f"recovery kernel is not live or complete: {official_status!r}")
    if status_receipt.get("failure_message") is not None:
        raise ValueError("recovery launch already has an official failure message")
    if not isinstance(script_version_id, int) or script_version_id <= 0:
        raise ValueError("script version id must be a positive integer")
    expected_url_suffix = f"/edit/run/{script_version_id}"
    kernel_path = str(metadata["id"]).split("/", 1)[1]
    if expected_url_suffix not in run_url or f"/code/{metadata['id'].split('/', 1)[0]}/{kernel_path}" not in run_url:
        raise ValueError("run URL does not bind the recovery kernel and script version")

    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    matching = [row for row in rows if row.get("experiment_id") == experiment_id]
    if len(matching) != 1:
        raise ValueError(f"expected exactly one {experiment_id} ledger row")
    row = matching[0]
    if row.get("kaggle_kernel") != metadata.get("id"):
        raise ValueError("ledger recovery kernel differs from metadata")
    if row.get("code_version") != local_hash:
        raise ValueError("ledger recovery code hash differs from launched source")

    ledger_outcome = (
        "RUNNING" if official_status == "RUNNING" else "COMPLETE_AWAITING_FINALIZATION"
    )
    receipt = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_recovery_launch",
        "experiment_id": experiment_id,
        "kernel": metadata["id"],
        "script_version_id": script_version_id,
        "run_url": run_url,
        "official_kernel_status": official_status,
        "ledger_outcome": ledger_outcome,
        "local_source_sha256": local_hash,
        "pulled_remote_source_sha256": remote_hash,
        "metadata_sha256": sha256(metadata_path),
        "preflight_sha256": sha256(preflight_path),
        "official_status_receipt_sha256": sha256(status_path),
        "private": True,
        "gpu_enabled": True,
        "internet_enabled": False,
        "competition_submission_authorized": False,
    }
    launch_note = (
        f"official recovery run {script_version_id}; pulled-back source SHA256 "
        f"{remote_hash}; official status {official_status} checked "
        f"{status_receipt.get('checked_at_utc')}; launch receipt {receipt_path.name}; "
        "diagnostic only and not authorized for competition submission"
    )
    existing_note = row.get("notes", "")
    if launch_note not in existing_note:
        row["notes"] = f"{existing_note}; {launch_note}" if existing_note else launch_note
    row["outcome"] = ledger_outcome

    write_json_atomic(receipt_path, receipt)
    write_ledger_atomic(ledger_path, fieldnames, rows)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preflight",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_preflight.json",
    )
    parser.add_argument(
        "--local-source",
        type=Path,
        default=(
            ROOT
            / "kernels"
            / "biohub_budgeted_embryo_oof_1ep_recovery"
            / "biohub-budgeted-embryo-oof-1ep.py"
        ),
    )
    parser.add_argument(
        "--remote-source",
        type=Path,
        default=(
            ROOT
            / "kaggle_runs"
            / "BH-0003-source"
            / "biohub-budgeted-embryo-oof-1ep.py"
        ),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=(
            ROOT
            / "kernels"
            / "biohub_budgeted_embryo_oof_1ep_recovery"
            / "kernel-metadata.json"
        ),
    )
    parser.add_argument(
        "--status",
        type=Path,
        default=ROOT / "official" / "oof_recovery_launch_status.json",
    )
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "EXPERIMENT_LEDGER.csv"
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_launch.json",
    )
    parser.add_argument("--script-version-id", type=int, required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--experiment-id", default="BH-0003")
    args = parser.parse_args()
    receipt = record_launch(
        args.preflight,
        args.local_source,
        args.remote_source,
        args.metadata,
        args.status,
        args.ledger,
        args.receipt,
        args.script_version_id,
        args.run_url,
        args.experiment_id,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
