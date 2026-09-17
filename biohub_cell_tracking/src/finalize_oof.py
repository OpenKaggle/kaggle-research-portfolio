#!/usr/bin/env python3
"""Validate, diagnose, and ledger a completed budgeted embryo-OOF run."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from analyze_oof import analyse
from validate_oof_receipt import sha256, validate


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def verify_downloaded_artifacts(
    receipt: dict, protocol: dict, protocol_path: Path, run_dir: Path, validation: dict
) -> dict:
    errors = list(validation["errors"])
    artifact_hashes: dict[str, str] = {}

    output_protocol_path = run_dir / "budgeted_oof_protocol.json"
    if not output_protocol_path.is_file():
        errors.append("downloaded output protocol is missing")
        output_protocol_match = False
    else:
        output_protocol_match = (
            json.loads(output_protocol_path.read_text(encoding="utf-8")) == protocol
        )
        artifact_hashes[output_protocol_path.name] = sha256(output_protocol_path)
        if not output_protocol_match:
            errors.append("downloaded output protocol does not match frozen protocol")

    receipt_folds = {
        int(row.get("fold", -1)): row
        for row in receipt.get("folds", [])
        if isinstance(row, dict)
    }
    for fold in protocol["folds"]:
        fold_id = int(fold["fold"])
        receipt_fold = receipt_folds.get(fold_id, {})
        for kind in ("train", "predict"):
            path = run_dir / f"fold_{fold_id}_{kind}.log"
            expected = receipt_fold.get(f"{kind}_log_sha256")
            if not path.is_file():
                errors.append(f"downloaded fold {fold_id} {kind} log is missing")
                continue
            actual = sha256(path)
            artifact_hashes[path.name] = actual
            if actual != expected:
                errors.append(f"downloaded fold {fold_id} {kind} log SHA-256 mismatch")

    validation = {
        **validation,
        "valid": not errors,
        "errors": errors,
        "downloaded_output_protocol_match": output_protocol_match,
        "downloaded_artifact_sha256": dict(sorted(artifact_hashes.items())),
        "frozen_protocol_sha256": sha256(protocol_path),
    }
    return validation


def update_ledger(
    ledger_path: Path,
    experiment_id: str,
    receipt: dict,
    analysis: dict,
    validation_hash: str,
    analysis_hash: str,
) -> None:
    with ledger_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise ValueError("experiment ledger has no header")
    matches = [row for row in rows if row["experiment_id"] == experiment_id]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one ledger row for {experiment_id}, found {len(matches)}"
        )

    row = matches[0]
    row["offline_score"] = f"{float(analysis['combined_holdout_score']):.9f}"
    row["runtime_seconds"] = f"{float(receipt['total_seconds']):.6f}"
    row["promotion_gate"] = "PASS: receipt+metric+split+logs; DIAGNOSTIC_ONLY"
    row["outcome"] = "OOF_VALIDATED_DIAGNOSTIC"
    marker = f"OOF validation SHA256 {validation_hash}; analysis SHA256 {analysis_hash}"
    if marker not in row["notes"]:
        row["notes"] = (
            f"{row['notes']}; {marker}; next single variable "
            f"{analysis['next_experiment']['single_variable']}"
        )

    temporary = ledger_path.with_name(f".{ledger_path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(ledger_path)


def finalize(
    run_dir: Path,
    protocol_path: Path,
    validation_path: Path,
    analysis_path: Path,
    finalization_path: Path,
    ledger_path: Path | None,
    experiment_id: str,
) -> tuple[dict, int]:
    receipt_path = run_dir / "budgeted_oof_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    validation = validate(receipt, protocol, sha256(protocol_path))
    validation = verify_downloaded_artifacts(
        receipt, protocol, protocol_path, run_dir, validation
    )
    write_json(validation_path, validation)

    analysis = analyse(receipt, protocol, validation)
    write_json(analysis_path, analysis)
    validation_hash = sha256(validation_path)
    analysis_hash = sha256(analysis_path)

    ledger_updated = False
    finalization_errors: list[str] = []
    if validation["valid"] and analysis["status"] == "complete_diagnostic":
        if ledger_path is not None:
            try:
                update_ledger(
                    ledger_path,
                    experiment_id,
                    receipt,
                    analysis,
                    validation_hash,
                    analysis_hash,
                )
                ledger_updated = True
            except (KeyError, OSError, ValueError) as error:
                finalization_errors.append(f"ledger update failed: {error}")
    else:
        finalization_errors.append("OOF evidence did not pass finalization gates")

    success = not finalization_errors
    finalization = {
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if success else "rejected",
        "experiment_id": experiment_id,
        "receipt_sha256": sha256(receipt_path),
        "protocol_sha256": sha256(protocol_path),
        "validation_sha256": validation_hash,
        "analysis_sha256": analysis_hash,
        "combined_holdout_score": analysis.get("combined_holdout_score"),
        "fold_scores": analysis.get("fold_scores"),
        "next_single_variable": analysis.get("next_experiment", {}).get(
            "single_variable"
        ),
        "submission_recommendation": analysis.get("submission_recommendation"),
        "ledger_updated": ledger_updated,
        "errors": finalization_errors,
    }
    write_json(finalization_path, finalization)
    return finalization, 0 if success else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_embryo_oof.json",
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_oof_validation.json",
    )
    parser.add_argument(
        "--analysis-output",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_oof_analysis.json",
    )
    parser.add_argument(
        "--finalization-output",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_oof_finalization.json",
    )
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "EXPERIMENT_LEDGER.csv"
    )
    parser.add_argument("--experiment-id", default="BH-0002")
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    report, exit_code = finalize(
        args.run_dir,
        args.protocol,
        args.validation_output,
        args.analysis_output,
        args.finalization_output,
        None if args.no_ledger else args.ledger,
        args.experiment_id,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
