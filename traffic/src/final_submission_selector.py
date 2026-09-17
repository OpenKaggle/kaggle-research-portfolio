#!/usr/bin/env python3
"""Time-gated internal selector for the final TrafficFlowBench submission."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from evidence_registry import register_final_selection


ALLOWED_D3_STATUS_PREFIXES = ("BUGFIX", "FINAL_SELECT", "REPRODUCED", "READY")
MAX_LIVE_AS_OF_AGE_SECONDS = 15 * 60
MAX_LIVE_AS_OF_FUTURE_SKEW_SECONDS = 60
MAX_D3_READINESS_AGE_SECONDS = 15 * 60


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def select_best(rows: list[dict[str, str]]) -> dict[str, str]:
    eligible = [
        row for row in rows
        if row["status"] == "COMPLETE" and row["public_score"].strip()
    ]
    if not eligible:
        raise ValueError("submission ledger has no completed scored candidate")
    return max(
        eligible,
        key=lambda row: (float(row["public_score"]), row["submitted_at_utc"], int(row["submission_id"])),
    )


def completed_submission(rows: list[dict[str, str]], submission_id: int) -> dict[str, str]:
    matches = [row for row in rows if int(row["submission_id"]) == submission_id]
    if len(matches) != 1:
        raise ValueError(f"submission ledger must contain exactly one row for {submission_id}")
    if matches[0]["status"] != "COMPLETE":
        raise ValueError(f"submission {submission_id} is not complete")
    return matches[0]


def selection_decision(as_of: datetime, d3: datetime, dry_run: bool, submission_id: int) -> str:
    if as_of >= d3 and not dry_run:
        return f"SELECT_FINAL_SUBMISSION_{submission_id}"
    if as_of < d3:
        return f"PREVIEW_SUBMISSION_{submission_id}_WAIT_UNTIL_D3"
    return f"PREVIEW_SUBMISSION_{submission_id}_D3_REACHED_RERUN_WITHOUT_DRY_RUN"


def validate_live_timestamp(as_of: datetime, now: datetime) -> float:
    if as_of.tzinfo is None or now.tzinfo is None:
        raise ValueError("live timestamp validation requires timezone-aware datetimes")
    age_seconds = (now.astimezone(timezone.utc) - as_of.astimezone(timezone.utc)).total_seconds()
    if age_seconds < -MAX_LIVE_AS_OF_FUTURE_SKEW_SECONDS:
        raise ValueError("--as-of is ahead of the live system clock; final selection is refused")
    if age_seconds > MAX_LIVE_AS_OF_AGE_SECONDS:
        raise ValueError("--as-of is stale relative to the live system clock; final selection is refused")
    return age_seconds


def validate_readiness_for_selection(
    readiness: dict[str, object], as_of: datetime, d3: datetime, dry_run: bool
) -> float | None:
    if dry_run:
        if readiness["status"] != "READY" or readiness["checks_failed"] != 0:
            raise ValueError("campaign readiness is not clean")
        return None

    readiness_as_of = datetime.fromisoformat(str(readiness["as_of"]))
    if readiness_as_of.tzinfo is None:
        raise ValueError("D-3 readiness timestamp must include a timezone")
    readiness_age = (as_of.astimezone(timezone.utc) - readiness_as_of.astimezone(timezone.utc)).total_seconds()
    if readiness_as_of < d3:
        raise ValueError("final selection requires a D-3 readiness receipt")
    if readiness_age < 0 or readiness_age > MAX_D3_READINESS_AGE_SECONDS:
        raise ValueError("D-3 readiness receipt is stale or later than final selection")
    if readiness["phase"] != "D3_BUGFIX_AND_FINAL_SELECTION_ONLY":
        raise ValueError("readiness receipt is not in the D-3 selection phase")
    if readiness["status"] == "READY":
        if readiness["checks_failed"] != 0:
            raise ValueError("READY receipt contains failed checks")
    elif readiness["status"] == "READY_FOR_FINAL_SELECTION":
        failures = readiness.get("failures", [])
        if (
            readiness["checks_failed"] != 1
            or len(failures) != 1
            or failures[0].get("requirement") != "D3_final_selection_control"
        ):
            raise ValueError("preselection readiness contains failures beyond pending final selection")
    else:
        raise ValueError("campaign is not ready for final selection")
    return readiness_age


def late_experiment_violations(
    rows: list[dict[str, str]], d3: datetime, as_of: datetime
) -> list[dict[str, str]]:
    violations = []
    for row in rows:
        started = datetime.fromisoformat(row["started_at_utc"].replace("Z", "+00:00"))
        if d3 <= started <= as_of and not row["status"].startswith(ALLOWED_D3_STATUS_PREFIXES):
            violations.append(
                {
                    "experiment": row["experiment"],
                    "started_at_utc": row["started_at_utc"],
                    "status": row["status"],
                }
            )
    return violations


def run(
    traffic_root: Path,
    as_of: datetime,
    output_root: Path,
    dry_run: bool,
    now: datetime | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    receipt_path = output_root / "final_submission_selection_receipt.json"
    if receipt_path.exists():
        if dry_run:
            raise ValueError("output root already contains a selector receipt; use a new path")
        existing = json.loads(receipt_path.read_text())
        register_final_selection(traffic_root, receipt_path)
        print(json.dumps(existing, indent=2))
        return existing
    if as_of.tzinfo is None:
        raise ValueError("--as-of must include a timezone")
    live_now = now or datetime.now(timezone.utc)
    if live_now.tzinfo is None:
        raise ValueError("system clock must be timezone-aware")
    artifacts = traffic_root / "artifacts"
    status = json.loads((artifacts / "campaign_status.json").read_text())
    d3 = datetime.fromisoformat(status["lifecycle"]["D3"])
    deadline = datetime.fromisoformat(status["deadline_asia_shanghai"])
    if as_of >= deadline:
        raise ValueError("final selector cannot run at or after the competition deadline")
    live_clock_age_seconds: float | None = None
    if not dry_run:
        live_clock_age_seconds = validate_live_timestamp(as_of, live_now)
        if live_now < d3:
            raise ValueError(f"final selection is forbidden before D-3 ({d3.isoformat()}); use --dry-run")
        if live_now >= deadline:
            raise ValueError("final selector cannot run at or after the competition deadline")

    with (artifacts / "submission_ledger.csv").open(newline="", encoding="utf-8") as handle:
        submissions = list(csv.DictReader(handle))
    with (artifacts / "experiment_ledger.csv").open(newline="", encoding="utf-8") as handle:
        experiments = list(csv.DictReader(handle))
    selected = select_best(submissions)
    declared = status["current_best"]
    if selected["experiment"] != declared["experiment"]:
        raise ValueError("highest completed ledger candidate disagrees with campaign experiment")
    if int(selected["submission_id"]) != int(declared["submission_id"]):
        raise ValueError("highest completed ledger candidate disagrees with campaign current_best")
    if float(selected["public_score"]) != float(declared["public_score"]):
        raise ValueError("selected public score disagrees with campaign current_best")

    candidate_path = traffic_root / declared["artifact_path"]
    candidate_sha = _sha256(candidate_path)
    if candidate_sha != selected["sha256"] or candidate_sha != declared["sha256"]:
        raise ValueError("selected candidate artifact SHA disagrees with ledger or status")

    fallback_id = int(status["current_candidate"]["fallback_submission_id"])
    fallback = completed_submission(submissions, fallback_id)
    fallback_path = traffic_root / status["current_candidate"]["fallback_artifact_path"]
    fallback_sha = _sha256(fallback_path)
    if fallback_sha != fallback["sha256"] or fallback_sha != status["current_candidate"]["parent_sha256"]:
        raise ValueError("fallback artifact SHA disagrees with ledger or status")

    lineage_path = artifacts / "current_best_lineage_audit_v1" / "current_best_lineage_receipt.json"
    replay_path = artifacts / "current_best_full_replay_v1" / "current_best_full_replay_receipt.json"
    readiness_path = traffic_root / status["lifecycle"]["readiness"]["receipt_path"]
    lineage_sha = _sha256(lineage_path)
    replay_sha = _sha256(replay_path)
    readiness_sha = _sha256(readiness_path)
    if lineage_sha != status["current_candidate"]["lineage_audit"]["receipt_sha256"]:
        raise ValueError("lineage receipt SHA disagrees with frozen campaign status")
    if replay_sha != status["current_candidate"]["full_replay"]["receipt_sha256"]:
        raise ValueError("full replay receipt SHA disagrees with frozen campaign status")
    if readiness_sha != status["lifecycle"]["readiness"]["receipt_sha256"]:
        raise ValueError("readiness receipt SHA disagrees with frozen campaign status")
    lineage = json.loads(lineage_path.read_text())
    replay = json.loads(replay_path.read_text())
    readiness = json.loads(readiness_path.read_text())
    if lineage["status"] != "VALID_FROZEN":
        raise ValueError("candidate lineage is not frozen-valid")
    if lineage["current_best"]["sha256"] != candidate_sha:
        raise ValueError("lineage receipt candidate SHA disagrees with selected artifact")
    if replay["status"] != "REPRODUCED_BYTE_IDENTICAL" or not replay["byte_identical_to_canonical"]:
        raise ValueError("candidate full replay is not byte-identical")
    if replay["rebuilt_sha256"] != candidate_sha or replay["canonical_sha256"] != candidate_sha:
        raise ValueError("full replay candidate SHA disagrees with selected artifact")
    readiness_age_seconds = validate_readiness_for_selection(readiness, as_of, d3, dry_run)
    violations = late_experiment_violations(experiments, d3, as_of)
    if violations:
        raise ValueError(f"non-bugfix experiments exist after D-3: {violations}")

    selection_final = not dry_run
    input_hashes = {
        "submission_ledger.csv": _sha256(artifacts / "submission_ledger.csv"),
        "experiment_ledger.csv": _sha256(artifacts / "experiment_ledger.csv"),
        "campaign_status.json": _sha256(artifacts / "campaign_status.json"),
        "lineage_receipt.json": _sha256(lineage_path),
        "full_replay_receipt.json": _sha256(replay_path),
        "readiness_receipt.json": _sha256(readiness_path),
    }
    receipt: dict[str, object] = {
        "status": "FINAL_SELECTED" if selection_final else "PREVIEW_READY_NOT_FINAL",
        "experiment": (
            "final_submission_selection"
            if selection_final
            else output_root.name
            if output_root.name.startswith("final_submission_preview_")
            else "final_submission_preview"
        ),
        "as_of": as_of.isoformat(),
        "executed_at_utc": live_now.astimezone(timezone.utc).isoformat(),
        "D3": d3.isoformat(),
        "deadline": deadline.isoformat(),
        "dry_run": dry_run,
        "selection_final": selection_final,
        "clock_gate": {
            "live_clock_enforced": not dry_run,
            "max_as_of_age_seconds": MAX_LIVE_AS_OF_AGE_SECONDS,
            "max_future_skew_seconds": MAX_LIVE_AS_OF_FUTURE_SKEW_SECONDS,
            "observed_as_of_age_seconds": live_clock_age_seconds,
            "max_D3_readiness_age_seconds": MAX_D3_READINESS_AGE_SECONDS,
            "observed_D3_readiness_age_seconds": readiness_age_seconds,
        },
        "selected": {
            "submission_id": int(selected["submission_id"]),
            "experiment": selected["experiment"],
            "public_score": float(selected["public_score"]),
            "sha256": candidate_sha,
            "artifact_path": declared["artifact_path"],
            "status": selected["status"],
        },
        "fallback": {
            "submission_id": fallback_id,
            "experiment": fallback["experiment"],
            "public_score": float(fallback["public_score"]),
            "sha256": fallback_sha,
            "artifact_path": status["current_candidate"]["fallback_artifact_path"],
            "status": fallback["status"],
            "reason": "previous completed Queue-only parent retained as a rollback receipt",
        },
        "evidence": {
            "lineage_status": lineage["status"],
            "full_replay_status": replay["status"],
            "readiness_status": readiness["status"],
            "late_experiment_violations": violations,
            "candidate_artifact_sha_verified_now": True,
            "fallback_artifact_sha_verified_now": True,
            "evidence_receipt_shas_verified_now": True,
        },
        "information_boundary": {
            "private_score_used": False,
            "hidden_labels_read_or_reconstructed": False,
            "organizer_only_metrics_inferred": False,
        },
        "external_kaggle_action_performed": False,
        "internal_selection_complete": selection_final,
        "campaign_goal_complete": False,
        "campaign_goal_boundary": "A D-3 internal selection receipt is necessary but does not by itself certify final external state or the complete campaign objective.",
        "decision": selection_decision(as_of, d3, dry_run, int(selected["submission_id"])),
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": input_hashes,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    if selection_final:
        register_final_selection(traffic_root, receipt_path)
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.traffic_root.resolve(), args.as_of, args.output_root.resolve(), args.dry_run)


if __name__ == "__main__":
    main()
