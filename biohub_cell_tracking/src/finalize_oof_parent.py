#!/usr/bin/env python3
"""Finalize the original OOF only when completion and source are evidence-bound."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from finalize_oof import finalize, write_json
from validate_oof_receipt import sha256


OFFICIAL_STATUS_SOURCE = "Official Kaggle kernel status and execution log APIs"
OFFICIAL_ACTIVITY_SOURCE = "Official authenticated Kaggle Notebook UI Logs page"
ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_bound_parent(
    activity_path: Path,
    completion_status_path: Path,
    local_source_path: Path,
    remote_source_path: Path,
    metadata_path: Path,
    experiment_id: str,
) -> tuple[dict, dict]:
    required_paths = {
        "activity receipt": activity_path,
        "completion status": completion_status_path,
        "local source": local_source_path,
        "pulled-back source": remote_source_path,
        "metadata": metadata_path,
    }
    for label, path in required_paths.items():
        require(path.is_file(), f"{label} is missing")

    activity = json.loads(activity_path.read_text(encoding="utf-8"))
    completion = json.loads(completion_status_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    require(experiment_id == "BH-0002", "parent finalizer only accepts BH-0002")
    require(activity.get("source") == OFFICIAL_ACTIVITY_SOURCE, "activity receipt is not authenticated Kaggle UI evidence")
    require(completion.get("source") == OFFICIAL_STATUS_SOURCE, "completion status is not official Kaggle evidence")
    require(metadata.get("id") == activity.get("kernel"), "metadata kernel differs from activity receipt")
    require(completion.get("kernel") == activity.get("kernel"), "completion kernel differs from activity receipt")
    require(metadata.get("is_private") is True, "parent OOF kernel is not private")
    require(metadata.get("enable_gpu") is True, "parent OOF kernel did not use GPU")
    require(metadata.get("enable_internet") is False, "parent OOF kernel internet must be disabled")

    script_version_id = activity.get("script_version_id")
    run_url = activity.get("run_url")
    require(isinstance(script_version_id, int) and script_version_id > 0, "activity script version is invalid")
    expected_url = f"https://www.kaggle.com/code/{activity['kernel']}/edit/run/{script_version_id}"
    require(run_url == expected_url, "activity run URL does not bind the exact kernel version")
    require(str(completion.get("status", "")).upper() == "COMPLETE", "parent OOF run is not complete")
    require(completion.get("failure_message") is None, "completion status contains a failure")
    require(completion.get("log_api_error") is None, "completion status has a log API error")
    require(completion.get("script_version_id") == script_version_id, "completion status script version differs from activity receipt")
    require(completion.get("run_url") == run_url, "completion status run URL differs from activity receipt")

    local_hash = sha256(local_source_path)
    remote_hash = sha256(remote_source_path)
    require(local_hash == remote_hash, "pulled-back parent source differs from local source")
    return activity, completion


def finalize_parent(
    run_dir: Path,
    protocol_path: Path,
    activity_path: Path,
    completion_status_path: Path,
    local_source_path: Path,
    remote_source_path: Path,
    metadata_path: Path,
    validation_path: Path,
    analysis_path: Path,
    finalization_path: Path,
    binding_path: Path,
    ledger_path: Path,
    experiment_id: str = "BH-0002",
) -> tuple[dict, int]:
    activity, completion = validate_bound_parent(
        activity_path,
        completion_status_path,
        local_source_path,
        remote_source_path,
        metadata_path,
        experiment_id,
    )
    receipt_path = run_dir / "budgeted_oof_receipt.json"
    require(receipt_path.is_file(), "downloaded parent OOF receipt is missing")

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

    require(finalization.get("status") == "complete", "parent OOF finalization was not complete")
    require(finalization.get("experiment_id") == experiment_id, "finalized experiment differs from parent")
    require(finalization.get("ledger_updated") is True, "parent ledger was not updated")
    require(finalization.get("submission_recommendation") == "diagnostic_only_do_not_submit", "parent result is not diagnostic-only")

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    binding = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_parent_oof_finalization",
        "experiment_id": experiment_id,
        "kernel": activity["kernel"],
        "script_version_id": activity["script_version_id"],
        "run_url": activity["run_url"],
        "official_kernel_status": completion["status"],
        "activity_receipt_sha256": sha256(activity_path),
        "official_completion_status_sha256": sha256(completion_status_path),
        "protocol_sha256": sha256(protocol_path),
        "local_source_sha256": sha256(local_source_path),
        "pulled_remote_source_sha256": sha256(remote_source_path),
        "metadata_sha256": sha256(metadata_path),
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
    parser.add_argument("--protocol", type=Path, default=ROOT / "artifacts" / "budgeted_embryo_oof.json")
    parser.add_argument("--activity", type=Path, default=ROOT / "official" / "oof_runtime_activity.json")
    parser.add_argument("--completion-status", type=Path, default=ROOT / "official" / "oof_kernel_status.json")
    parser.add_argument("--local-source", type=Path, default=ROOT / "kernels" / "biohub_budgeted_embryo_oof" / "biohub-budgeted-embryo-oof.py")
    parser.add_argument("--remote-source", type=Path, default=ROOT / "kaggle_runs" / "BH-0002-source" / "biohub-budgeted-embryo-oof-v1.py")
    parser.add_argument("--metadata", type=Path, default=ROOT / "kernels" / "biohub_budgeted_embryo_oof" / "kernel-metadata.json")
    parser.add_argument("--validation-output", type=Path, default=ROOT / "artifacts" / "budgeted_oof_validation.json")
    parser.add_argument("--analysis-output", type=Path, default=ROOT / "artifacts" / "budgeted_oof_analysis.json")
    parser.add_argument("--finalization-output", type=Path, default=ROOT / "artifacts" / "budgeted_oof_finalization.json")
    parser.add_argument("--binding-output", type=Path, default=ROOT / "artifacts" / "budgeted_oof_finalization_binding.json")
    parser.add_argument("--ledger", type=Path, default=ROOT / "EXPERIMENT_LEDGER.csv")
    parser.add_argument("--experiment-id", default="BH-0002")
    args = parser.parse_args()
    report, exit_code = finalize_parent(
        args.run_dir,
        args.protocol,
        args.activity,
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
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
