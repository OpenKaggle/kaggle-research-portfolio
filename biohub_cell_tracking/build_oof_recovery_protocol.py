#!/usr/bin/env python3
"""Build the one-epoch recovery protocol from frozen OOF telemetry."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_PARENT = ROOT / "artifacts" / "budgeted_embryo_oof.json"
DEFAULT_ACTIVITY = ROOT / "official" / "oof_runtime_activity.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "budgeted_embryo_oof_1ep_recovery.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(parent: dict, parent_sha256: str, activity: dict) -> dict:
    payload = json.loads(json.dumps(parent))
    latest = activity["latest_ui_observation"]
    seconds_per_batch = float(latest["median_seconds_per_batch"])
    batches_per_epoch = int(latest["batches_per_epoch"])
    folds = len(payload["folds"])

    # Use the slower observed fold-0 batch count for both directions. Prediction
    # gets a 2x multiplier, then setup/evaluation and a three-hour reserve are
    # added separately rather than hidden inside one optimistic factor.
    training_seconds = folds * batches_per_epoch * seconds_per_batch
    reference_inference_seconds = float(
        parent["runtime_budget"]["estimated_inference_seconds"]
    )
    inference_safety_factor = 2.0
    inference_seconds = reference_inference_seconds * inference_safety_factor
    setup_seconds = 600.0
    evaluation_seconds = 1800.0
    contingency_seconds = 3 * 3600.0
    projected_seconds = (
        training_seconds
        + inference_seconds
        + setup_seconds
        + evaluation_seconds
        + contingency_seconds
    )
    official_limit_seconds = 12 * 3600.0

    payload["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["protocol"] = "budgeted_leave_one_embryo_out_1ep_recovery"
    payload["purpose"] = (
        "runtime-corrected honest generalization and error diagnosis; "
        "not a direct proxy for BH-0001"
    )
    payload["recovery_parent"] = {
        "protocol_sha256": parent_sha256,
        "failed_budget_assumption": "12 epochs projected from nonrepresentative reference timing",
        "current_run_script_version_id": activity["script_version_id"],
        "activity_receipt_checked_at_utc": activity["checked_at_utc"],
        "launch_condition": "current 12-epoch kernel must be terminal",
    }
    payload["training"]["epochs"] = 1
    payload["runtime_budget"] = {
        "official_limit_hours": 12,
        "source": "authenticated official Kaggle UI telemetry from the active 12-epoch run",
        "observed_fold_0_batches_per_epoch": batches_per_epoch,
        "observed_median_seconds_per_batch": seconds_per_batch,
        "conservative_batches_per_epoch_each_fold": batches_per_epoch,
        "estimated_training_seconds_two_folds": training_seconds,
        "reference_inference_seconds_16_movies": reference_inference_seconds,
        "inference_safety_factor": inference_safety_factor,
        "estimated_inference_seconds": inference_seconds,
        "setup_seconds": setup_seconds,
        "evaluation_seconds": evaluation_seconds,
        "contingency_seconds": contingency_seconds,
        "estimated_total_seconds_with_reserve": projected_seconds,
        "estimated_total_hours_with_reserve": projected_seconds / 3600.0,
        "headroom_seconds": official_limit_seconds - projected_seconds,
        "headroom_hours": (official_limit_seconds - projected_seconds) / 3600.0,
        "passes_prelaunch_runtime_gate": projected_seconds < official_limit_seconds,
    }
    payload["limitations"] = [
        "Only one training epoch is used per embryo direction because live telemetry disproved the original 12-epoch budget.",
        "Only eight validation movies per embryo are fully inferred and scored.",
        "Checkpoint selection uses only the same-embryo monitor subset; the cross-embryo holdout does not participate in training or selection.",
        "Promotion requires directionally consistent results in both embryo directions; this reduced protocol cannot justify leaderboard-only tuning.",
    ]
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--activity", type=Path, default=DEFAULT_ACTIVITY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    parent = json.loads(args.parent.read_text(encoding="utf-8"))
    activity = json.loads(args.activity.read_text(encoding="utf-8"))
    payload = build(parent, sha256(args.parent), activity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    print(json.dumps(payload["runtime_budget"], indent=2))


if __name__ == "__main__":
    main()
