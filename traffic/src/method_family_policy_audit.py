#!/usr/bin/env python3
"""Verify method-family switching and A-group absorption against frozen receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import resource
import time
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def _timestamp(row: dict[str, str]) -> datetime:
    return datetime.fromisoformat(row["started_at_utc"].replace("Z", "+00:00"))


def consecutive_in_task_stream(
    ledger: list[dict[str, str]], task_scope: str, experiments: list[str]
) -> bool:
    scoped = [row["experiment"] for row in ledger if row["task"] == task_scope]
    try:
        positions = [scoped.index(experiment) for experiment in experiments]
    except ValueError:
        return False
    return positions == list(range(positions[0], positions[0] + len(positions)))


def run(traffic_root: Path, config_path: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    receipt_path = output_root / "method_family_policy_receipt.json"
    if receipt_path.exists():
        raise ValueError("output root already contains a method-family policy receipt")
    config = json.loads(config_path.read_text())
    ledger_path = traffic_root / "artifacts" / "experiment_ledger.csv"
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        ledger = list(csv.DictReader(handle))
    ledger_by_name: dict[str, list[dict[str, str]]] = {}
    for row in ledger:
        ledger_by_name.setdefault(row["experiment"], []).append(row)

    errors: list[str] = []
    sequence_rows: list[dict[str, object]] = []
    receipt_hashes: dict[str, str] = {}

    def verify_attempt(attempt: dict[str, object], sequence: str, order: int) -> dict[str, str] | None:
        name = str(attempt["experiment"])
        matches = ledger_by_name.get(name, [])
        if len(matches) != 1:
            errors.append(f"{name}: expected exactly one experiment-ledger row")
            return None
        ledger_row = matches[0]
        if ledger_row["status"] != attempt["ledger_status"]:
            errors.append(f"{name}: ledger status mismatch")
        artifact = traffic_root / str(attempt["receipt_path"])
        if not artifact.is_file():
            errors.append(f"{name}: receipt missing")
            return ledger_row
        actual_sha = _sha256(artifact)
        receipt_hashes[str(attempt["receipt_path"])] = actual_sha
        if actual_sha != attempt["receipt_sha256"]:
            errors.append(f"{name}: receipt SHA mismatch")
        evidence = json.loads(artifact.read_text())
        if evidence.get("status") != attempt["receipt_status"]:
            errors.append(f"{name}: receipt status mismatch")
        if evidence.get("decision") != attempt["receipt_decision"]:
            errors.append(f"{name}: receipt decision mismatch")
        if attempt["outcome"] == "NO_IMPROVEMENT" and not (
            ledger_row["status"].startswith("STOPPED")
            or ledger_row["status"].startswith("FAILED")
        ):
            errors.append(f"{name}: no-improvement outcome lacks stopped/failed ledger status")
        sequence_rows.append({
            "sequence": sequence,
            "order": order,
            "experiment": name,
            "task": ledger_row["task"],
            "method_family": attempt["method_family"],
            "outcome": attempt["outcome"],
            "ledger_status": ledger_row["status"],
            "started_at_utc": ledger_row["started_at_utc"],
            "receipt_sha256": actual_sha,
        })
        return ledger_row

    required_failures = int(config["policy"]["switch_after_consecutive_no_improvement"])
    for sequence in config["two_failure_switches"]:
        attempts = sequence["attempts"]
        if len(attempts) != required_failures:
            errors.append(f"{sequence['name']}: attempt count does not match switch policy")
        names = [str(attempt["experiment"]) for attempt in attempts]
        rows = [verify_attempt(attempt, str(sequence["name"]), order) for order, attempt in enumerate(attempts, 1)]
        present_rows = [row for row in rows if row is not None]
        if len(present_rows) == len(attempts):
            if [_timestamp(row) for row in present_rows] != sorted(_timestamp(row) for row in present_rows):
                errors.append(f"{sequence['name']}: attempts are not chronological")
            if not consecutive_in_task_stream(ledger, str(sequence["task_scope"]), names):
                errors.append(f"{sequence['name']}: attempts are not consecutive in the task stream")
            next_matches = ledger_by_name.get(str(sequence["next_experiment"]), [])
            if len(next_matches) != 1 or _timestamp(next_matches[0]) <= _timestamp(present_rows[-1]):
                errors.append(f"{sequence['name']}: declared switch/freeze action is not later")

    absorption = config["A_group_absorption"]
    trigger_names = [str(name) for name in absorption["trigger_attempts"]]
    if len(trigger_names) != int(config["policy"]["absorb_A_group_after_same_task_failures"]):
        errors.append("A-group trigger count does not match policy")
    trigger_rows = []
    for name in trigger_names:
        matches = ledger_by_name.get(name, [])
        if len(matches) != 1 or not (
            matches[0]["status"].startswith("STOPPED")
            or matches[0]["status"].startswith("FAILED")
        ):
            errors.append(f"A-group trigger {name} is not a unique stopped/failed experiment")
        else:
            trigger_rows.append(matches[0])
    absorbed = absorption["absorbed_experiment"]
    absorbed_row = verify_attempt(absorbed, "A_group_absorption", 1)
    if absorbed_row is not None and trigger_rows:
        if _timestamp(absorbed_row) <= max(_timestamp(row) for row in trigger_rows):
            errors.append("A-group experiment was not evaluated after all three triggers")
    nonlinear_path = traffic_root / str(absorbed["receipt_path"])
    if nonlinear_path.is_file():
        nonlinear = json.loads(nonlinear_path.read_text())
        boundary = nonlinear["data_boundary"]
        if boundary["same_block_truth_dependency"] is not False:
            errors.append("A-group experiment depends on same-block truth")
        if boundary["training_label_availability_proof"]["unavailable_scored_split_labels_used"] is not False:
            errors.append("A-group experiment used unavailable scored-split labels")
        if any(value is not None for value in nonlinear["organizer_only_metrics"].values()):
            errors.append("A-group experiment populated organizer-only metrics")
    if any(config["information_boundary"].values()):
        errors.append("policy config permits hidden or organizer-only information")

    output_root.mkdir(parents=True, exist_ok=True)
    sequence_path = output_root / "method_family_sequence.csv"
    with sequence_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "sequence", "order", "experiment", "task", "method_family", "outcome",
            "ledger_status", "started_at_utc", "receipt_sha256",
        ])
        writer.writeheader()
        writer.writerows(sequence_rows)
    receipt: dict[str, object] = {
        "status": "VALID" if not errors else "FAIL",
        "experiment": "method_family_policy_audit_v1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": config["policy"],
        "two_failure_sequences_verified": len(config["two_failure_switches"]),
        "A_group_trigger_failures_verified": len(trigger_rows),
        "A_group_absorbed_experiment": absorbed["experiment"],
        "A_group_result": absorption["result"],
        "errors": errors,
        "information_boundary": {
            "hidden_labels_read_or_reconstructed": False,
            "private_scores_used": False,
            "organizer_only_metrics_inferred": False,
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {
            "method_family_policy_v1.json": _sha256(config_path),
            "experiment_ledger.csv": _sha256(ledger_path),
            **receipt_hashes,
        },
        "outputs": {"method_family_sequence.csv": _sha256(sequence_path)},
        "decision": "POLICY_SATISFIED_HOLD_CURRENT_FAMILIES" if not errors else "POLICY_EVIDENCE_INVALID",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    if errors:
        raise SystemExit(1)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--config", type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "method_family_policy_v1.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.traffic_root.resolve(), args.config.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
