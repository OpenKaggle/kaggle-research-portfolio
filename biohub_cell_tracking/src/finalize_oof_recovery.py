#!/usr/bin/env python3
"""Finalize recovery OOF only when its launch and completion are evidence-bound."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from finalize_oof import finalize, write_json
from validate_oof_receipt import sha256


OFFICIAL_STATUS_SOURCE = "Official Kaggle kernel status and execution log APIs"
ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_bound_recovery(
    protocol_path: Path,
    preflight_path: Path,
    launch_receipt_path: Path,
    launch_status_path: Path,
    completion_status_path: Path,
    local_source_path: Path,
    remote_source_path: Path,
    metadata_path: Path,
    experiment_id: str,
) -> tuple[dict, dict]:
    required_paths = {
        "protocol": protocol_path,
        "preflight": preflight_path,
        "launch receipt": launch_receipt_path,
        "launch status": launch_status_path,
        "completion status": completion_status_path,
        "local source": local_source_path,
        "pulled-back source": remote_source_path,
        "metadata": metadata_path,
    }
    for label, path in required_paths.items():
        require(path.is_file(), f"{label} is missing")

    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    launch = json.loads(launch_receipt_path.read_text(encoding="utf-8"))
    launch_status = json.loads(launch_status_path.read_text(encoding="utf-8"))
    completion = json.loads(completion_status_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    require(launch.get("status") == "accepted_recovery_launch", "recovery launch receipt is not accepted")
    require(launch.get("experiment_id") == experiment_id, "recovery launch experiment does not match")
    require(launch.get("competition_submission_authorized") is False, "recovery launch improperly authorizes submission")
    require(preflight.get("valid") is True, "recovery preflight is invalid")
    require(preflight.get("launch_allowed") is True, "recovery preflight did not authorize launch")
    require(preflight.get("terminal_evidence_valid") is True, "recovery preflight lacks terminal evidence")
    require(sha256(preflight_path) == launch.get("preflight_sha256"), "recovery preflight changed after launch")
    require(sha256(protocol_path) == preflight.get("protocol_sha256"), "recovery protocol differs from preflight")

    local_hash = sha256(local_source_path)
    remote_hash = sha256(remote_source_path)
    require(local_hash == remote_hash, "pulled-back recovery source differs from local source")
    require(local_hash == preflight.get("source_sha256"), "recovery source differs from preflight")
    require(local_hash == launch.get("local_source_sha256"), "recovery source differs from launch receipt")
    require(remote_hash == launch.get("pulled_remote_source_sha256"), "pulled-back source differs from launch receipt")
    require(sha256(metadata_path) == preflight.get("metadata_sha256"), "recovery metadata differs from preflight")
    require(sha256(metadata_path) == launch.get("metadata_sha256"), "recovery metadata differs from launch receipt")
    require(metadata.get("id") == launch.get("kernel"), "recovery metadata kernel differs from launch")
    require(metadata.get("is_private") is True, "recovery kernel is not private")
    require(metadata.get("enable_gpu") is True, "recovery kernel did not use GPU")
    require(metadata.get("enable_internet") is False, "recovery kernel internet must be disabled")

    require(sha256(launch_status_path) == launch.get("official_status_receipt_sha256"), "launch status receipt changed after launch")
    require(launch_status.get("source") == OFFICIAL_STATUS_SOURCE, "launch status is not official Kaggle evidence")
    require(launch_status.get("kernel") == launch.get("kernel"), "launch status kernel differs from launch receipt")
    require(str(launch_status.get("status", "")).upper() in {"RUNNING", "COMPLETE"}, "launch status is not live or complete")
    require(launch_status.get("failure_message") is None, "launch status contains a failure")

    script_version_id = launch.get("script_version_id")
    run_url = launch.get("run_url")
    require(isinstance(script_version_id, int) and script_version_id > 0, "launch script version is invalid")
    require(isinstance(run_url, str) and run_url, "launch run URL is missing")
    require(completion.get("source") == OFFICIAL_STATUS_SOURCE, "completion status is not official Kaggle evidence")
    require(completion.get("kernel") == launch.get("kernel"), "completion status kernel differs from launch receipt")
    require(str(completion.get("status", "")).upper() == "COMPLETE", "recovery run is not complete")
    require(completion.get("failure_message") is None, "completion status contains a failure")
    require(completion.get("log_api_error") is None, "completion status has a log API error")
    require(completion.get("script_version_id") == script_version_id, "completion status script version differs from launch")
    require(completion.get("run_url") == run_url, "completion status run URL differs from launch")

    return launch, completion


def finalize_recovery(
    run_dir: Path,
    protocol_path: Path,
    preflight_path: Path,
    launch_receipt_path: Path,
    launch_status_path: Path,
    completion_status_path: Path,
    local_source_path: Path,
    remote_source_path: Path,
    metadata_path: Path,
    validation_path: Path,
    analysis_path: Path,
    finalization_path: Path,
    binding_path: Path,
    ledger_path: Path,
    experiment_id: str = "BH-0003",
) -> tuple[dict, int]:
    launch, completion = validate_bound_recovery(
        protocol_path,
        preflight_path,
        launch_receipt_path,
        launch_status_path,
        completion_status_path,
        local_source_path,
        remote_source_path,
        metadata_path,
        experiment_id,
    )
    receipt_path = run_dir / "budgeted_oof_receipt.json"
    require(receipt_path.is_file(), "downloaded recovery OOF receipt is missing")

    finalization, exit_code = finalize(
        run_dir,
        protocol_path,
        validation_path,
        analysis_path,
        finalization_path,
        ledger_path,
        experiment_id,
    )
    if exit_code != 0:
        return finalization, exit_code

    require(finalization.get("status") == "complete", "recovery OOF finalization was not complete")
    require(finalization.get("experiment_id") == experiment_id, "finalized experiment differs from recovery")
    require(finalization.get("ledger_updated") is True, "recovery ledger was not updated")
    require(finalization.get("submission_recommendation") == "diagnostic_only_do_not_submit", "recovery result is not diagnostic-only")

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    binding = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_recovery_oof_finalization",
        "experiment_id": experiment_id,
        "kernel": launch["kernel"],
        "script_version_id": launch["script_version_id"],
        "run_url": launch["run_url"],
        "official_kernel_status": completion["status"],
        "launch_receipt_sha256": sha256(launch_receipt_path),
        "official_completion_status_sha256": sha256(completion_status_path),
        "preflight_sha256": sha256(preflight_path),
        "protocol_sha256": sha256(protocol_path),
        "local_source_sha256": sha256(local_source_path),
        "pulled_remote_source_sha256": sha256(remote_source_path),
        "oof_receipt_sha256": sha256(receipt_path),
        "validation_sha256": sha256(validation_path),
        "analysis_sha256": sha256(analysis_path),
        "finalization_sha256": sha256(finalization_path),
        "combined_holdout_score": analysis["combined_holdout_score"],
        "validation_valid": validation["valid"],
        "analysis_status": analysis["status"],
        "ledger_outcome": "OOF_VALIDATED_DIAGNOSTIC",
        "competition_submission_authorized": False,
        "promotion_authorized": False,
    }
    write_json(binding_path, binding)
    return binding, 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_embryo_oof_1ep_recovery.json",
    )
    parser.add_argument(
        "--preflight",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_preflight.json",
    )
    parser.add_argument(
        "--launch-receipt",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_launch.json",
    )
    parser.add_argument(
        "--launch-status",
        type=Path,
        default=ROOT / "official" / "oof_recovery_launch_status.json",
    )
    parser.add_argument(
        "--completion-status",
        type=Path,
        default=ROOT / "official" / "oof_recovery_kernel_status.json",
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
        "--validation-output",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_oof_1ep_recovery_validation.json",
    )
    parser.add_argument(
        "--analysis-output",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_oof_1ep_recovery_analysis.json",
    )
    parser.add_argument(
        "--finalization-output",
        type=Path,
        default=ROOT / "artifacts" / "budgeted_oof_1ep_recovery_finalization.json",
    )
    parser.add_argument(
        "--binding-output",
        type=Path,
        default=ROOT / "artifacts" / "oof_recovery_finalization_binding.json",
    )
    parser.add_argument(
        "--ledger", type=Path, default=ROOT / "EXPERIMENT_LEDGER.csv"
    )
    parser.add_argument("--experiment-id", default="BH-0003")
    args = parser.parse_args()
    try:
        report, exit_code = finalize_recovery(
            args.run_dir,
            args.protocol,
            args.preflight,
            args.launch_receipt,
            args.launch_status,
            args.completion_status,
            args.local_source,
            args.remote_source,
            args.metadata,
            args.validation_output,
            args.analysis_output,
            args.finalization_output,
            args.binding_output,
            args.ledger,
            args.experiment_id,
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        report = {
            "status": "rejected",
            "experiment_id": args.experiment_id,
            "error": str(error),
            "competition_submission_authorized": False,
        }
        exit_code = 1
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
