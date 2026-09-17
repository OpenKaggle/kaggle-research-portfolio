#!/usr/bin/env python3
"""Preflight the recovery OOF and prevent launch while its parent run is live."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAILED_TERMINAL_STATUSES = {"ERROR", "CANCELLED", "CANCEL_ACKNOWLEDGED"}
RECOVERY_METADATA_FIELDS = {
    "created_at_utc",
    "protocol",
    "purpose",
    "recovery_parent",
    "runtime_budget",
    "limitations",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operational_protocol(protocol: dict, epochs: int) -> dict:
    payload = json.loads(json.dumps(protocol))
    for key in RECOVERY_METADATA_FIELDS:
        payload.pop(key, None)
    payload.setdefault("training", {})["epochs"] = epochs
    return payload


def preflight(
    protocol_path: Path,
    source_path: Path,
    metadata_path: Path,
    parent_protocol_path: Path,
    current_status_path: Path,
    terminal_evidence_path: Path | None = None,
) -> dict:
    errors: list[str] = []
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    parent_protocol = json.loads(parent_protocol_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    current_status = json.loads(current_status_path.read_text(encoding="utf-8"))
    namespace = runpy.run_path(str(source_path), run_name="oof_recovery_preflight")

    runtime = protocol.get("runtime_budget", {})
    parent_epochs = parent_protocol.get("training", {}).get("epochs")
    if protocol.get("training", {}).get("epochs") != 1:
        errors.append("recovery protocol must use exactly one epoch per fold")
    if parent_epochs != 12:
        errors.append("parent protocol must use the expected 12 epochs")
    single_variable_contract = (
        parent_epochs == 12
        and operational_protocol(protocol, parent_epochs)
        == operational_protocol(parent_protocol, parent_epochs)
    )
    if not single_variable_contract:
        errors.append("recovery changes operational fields beyond training.epochs")
    if protocol.get("recovery_parent", {}).get("protocol_sha256") != sha256(
        parent_protocol_path
    ):
        errors.append("recovery parent protocol hash mismatch")
    if runtime.get("passes_prelaunch_runtime_gate") is not True:
        errors.append("runtime gate is not affirmatively passed")
    if float(runtime.get("estimated_total_seconds_with_reserve", float("inf"))) >= 12 * 3600:
        errors.append("reserved runtime projection is not below 12 hours")
    if namespace.get("PROTOCOL") != protocol:
        errors.append("embedded protocol differs from frozen recovery protocol")
    if namespace.get("SOURCE_PROTOCOL_SHA256") != sha256(protocol_path):
        errors.append("embedded source protocol SHA-256 mismatch")
    if namespace.get("METHOD") != "budgeted_embryo_oof_1ep_recovery":
        errors.append("recovery method name mismatch")
    if not metadata.get("is_private"):
        errors.append("kernel must be private")
    if not metadata.get("enable_gpu") or metadata.get("enable_internet"):
        errors.append("kernel must use GPU with internet disabled")
    if metadata.get("code_file") != source_path.name:
        errors.append("metadata code file mismatch")
    if "biohub-cell-tracking-during-development" not in metadata.get(
        "competition_sources", []
    ):
        errors.append("competition source is missing")

    current_status_value = str(current_status.get("status", "")).upper()
    terminal_evidence_valid = False
    terminal_evidence_sha256 = None
    if current_status_value in FAILED_TERMINAL_STATUSES:
        if terminal_evidence_path is None or not terminal_evidence_path.is_file():
            errors.append("failed parent requires a frozen terminal disposition receipt")
        else:
            terminal_evidence = json.loads(
                terminal_evidence_path.read_text(encoding="utf-8")
            )
            terminal_evidence_sha256 = sha256(terminal_evidence_path)
            terminal_evidence_valid = (
                terminal_evidence.get("status") == "accepted_terminal_failure"
                and terminal_evidence.get("kernel") == current_status.get("kernel")
                and terminal_evidence.get("official_terminal_status")
                == current_status_value
                and terminal_evidence.get("official_status_receipt_sha256")
                == sha256(current_status_path)
                and terminal_evidence.get("recovery_authorized") is True
            )
            if not terminal_evidence_valid:
                errors.append("terminal disposition receipt does not bind current status")
    launch_allowed = (
        not errors
        and current_status_value in FAILED_TERMINAL_STATUSES
        and terminal_evidence_valid
    )
    if launch_allowed:
        report_status = "ready_to_launch"
    elif current_status_value == "COMPLETE" and not errors:
        report_status = "awaiting_completed_output_validation"
    elif not errors:
        report_status = "ready_waiting_current_terminal"
    else:
        report_status = "rejected"
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": report_status,
        "valid": not errors,
        "launch_allowed": launch_allowed,
        "current_parent_kernel_status": current_status_value,
        "required_parent_failed_terminal_statuses": sorted(FAILED_TERMINAL_STATUSES),
        "complete_parent_requires_output_validation": True,
        "terminal_evidence_valid": terminal_evidence_valid,
        "terminal_evidence_sha256": terminal_evidence_sha256,
        "protocol_sha256": sha256(protocol_path),
        "source_sha256": sha256(source_path),
        "metadata_sha256": sha256(metadata_path),
        "single_variable_contract": single_variable_contract,
        "changed_operational_fields": ["training.epochs"]
        if single_variable_contract
        else None,
        "parent_epochs": parent_epochs,
        "recovery_epochs": protocol.get("training", {}).get("epochs"),
        "estimated_total_hours_with_reserve": runtime.get(
            "estimated_total_hours_with_reserve"
        ),
        "headroom_hours": runtime.get("headroom_hours"),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_embryo_oof_1ep_recovery.json",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=(
            ROOT
            / "kernels"
            / "biohub_budgeted_embryo_oof_1ep_recovery"
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
        "--parent-protocol",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_embryo_oof.json",
    )
    parser.add_argument(
        "--current-status",
        type=Path,
        default=ROOT / "official" / "oof_kernel_status.json",
    )
    parser.add_argument(
        "--terminal-evidence",
        type=Path,
        default=ROOT / "artifacts" / "oof_terminal_disposition.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_preflight.json",
    )
    args = parser.parse_args()
    report = preflight(
        args.protocol,
        args.source,
        args.metadata,
        args.parent_protocol,
        args.current_status,
        args.terminal_evidence,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
