#!/usr/bin/env python3
"""Enforce D-30/D-14/D-7/D-3 evidence deadlines and post-freeze activity policy."""

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
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def parse_milestones(config: dict[str, object]) -> dict[str, datetime]:
    milestones = {
        name: datetime.fromisoformat(value) for name, value in config["milestones"].items()
    }
    if any(value.tzinfo is None for value in milestones.values()):
        raise ValueError("all lifecycle milestones must include a timezone")
    if list(milestones.values()) != sorted(milestones.values()):
        raise ValueError("lifecycle milestones are not chronological")
    return milestones


def lifecycle_phase(at: datetime, milestones: dict[str, datetime]) -> str:
    if at.tzinfo is None:
        raise ValueError("lifecycle timestamp must include a timezone")
    if at < milestones["D30"]:
        return "RESEARCH_BEFORE_D30"
    if at < milestones["D14"]:
        return "D30_BASELINES_COMPLETE"
    if at < milestones["D7"]:
        return "D14_CANDIDATE_FROZEN"
    if at < milestones["D3"]:
        return "D7_REPRODUCTION_ONLY"
    if at < milestones["deadline"]:
        return "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"
    return "CLOSED"


def classify_experiment(experiment: str, policy: dict[str, object]) -> str:
    for category, prefixes in policy["category_prefixes"].items():
        if any(experiment.startswith(prefix) for prefix in prefixes):
            return category
    return "research_or_candidate"


def experiment_policy_violations(
    rows: list[dict[str, str]],
    as_of: datetime,
    milestones: dict[str, datetime],
    policy: dict[str, object],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for row in rows:
        try:
            started = datetime.fromisoformat(row["started_at_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            violations.append(
                {
                    "kind": "experiment",
                    "name": row.get("experiment", "MISSING"),
                    "started_at_utc": row.get("started_at_utc", "MISSING"),
                    "phase": "INVALID_TIMESTAMP",
                    "category": "unknown",
                    "reason": "timestamp is missing naive or invalid",
                }
            )
            continue
        if started.tzinfo is None:
            violations.append(
                {
                    "kind": "experiment",
                    "name": row.get("experiment", "MISSING"),
                    "started_at_utc": row.get("started_at_utc", "MISSING"),
                    "phase": "INVALID_TIMESTAMP",
                    "category": "unknown",
                    "reason": "timestamp is missing naive or invalid",
                }
            )
            continue
        if started > as_of or started < milestones["D14"]:
            continue
        phase = lifecycle_phase(started, milestones)
        category = classify_experiment(row["experiment"], policy)
        allowed = set(policy["allowed_categories"][phase])
        reason = None
        if category not in allowed:
            reason = f"{category} is not allowed in {phase}"
        elif category == "bugfix" and not row["status"].startswith(policy["bugfix_status_prefix"]):
            reason = "bugfix name lacks a BUGFIX status"
        elif category == "final_selection" and row["status"] != policy["final_selection_status"]:
            reason = "final-selection row lacks FINAL_SELECTED status"
        if reason:
            violations.append(
                {
                    "kind": "experiment",
                    "name": row["experiment"],
                    "started_at_utc": row["started_at_utc"],
                    "phase": phase,
                    "category": category,
                    "reason": reason,
                }
            )
    return violations


def submission_policy_violations(
    rows: list[dict[str, str]],
    as_of: datetime,
    milestones: dict[str, datetime],
    policy: dict[str, object],
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for row in rows:
        try:
            submitted = datetime.fromisoformat(row["submitted_at_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            submitted = None
        if submitted is None or submitted.tzinfo is None:
            violations.append(
                {
                    "kind": "submission",
                    "name": row.get("experiment", "MISSING"),
                    "started_at_utc": row.get("submitted_at_utc", "MISSING"),
                    "phase": "INVALID_TIMESTAMP",
                    "category": "unknown",
                    "reason": "submission timestamp is missing naive or invalid",
                }
            )
            continue
        if submitted > as_of or submitted < milestones["D14"]:
            continue
        phase = lifecycle_phase(submitted, milestones)
        category = classify_experiment(row["experiment"], policy)
        allowed_bugfix_submission = (
            phase == "D3_BUGFIX_AND_FINAL_SELECTION_ONLY" and category == "bugfix"
        )
        if not allowed_bugfix_submission:
            violations.append(
                {
                    "kind": "submission",
                    "name": row["experiment"],
                    "started_at_utc": row["submitted_at_utc"],
                    "phase": phase,
                    "category": category,
                    "reason": "new Kaggle receipt after candidate freeze is allowed only for a D-3 bugfix",
                }
            )
    return violations


def policy_probes(
    milestones: dict[str, datetime], policy: dict[str, object]
) -> dict[str, bool]:
    def row(name: str, at: datetime, status: str = "COMPLETE") -> dict[str, str]:
        return {"experiment": name, "started_at_utc": at.isoformat(), "status": status}

    d14 = milestones["D14"]
    d7 = milestones["D7"]
    d3 = milestones["D3"]
    deadline = milestones["deadline"]
    before_deadline = deadline.replace(microsecond=0)
    tuning_d14 = experiment_policy_violations(
        [row("new_candidate_tuning", d14)], before_deadline, milestones, policy
    )
    tuning_d7 = experiment_policy_violations(
        [row("new_candidate_tuning", d7)], before_deadline, milestones, policy
    )
    reproduction_d7 = experiment_policy_violations(
        [row("current_best_full_replay_D7", d7, "REPRODUCED")],
        before_deadline,
        milestones,
        policy,
    )
    model_d3 = experiment_policy_violations(
        [row("ordinary_model_after_D3", d3)], before_deadline, milestones, policy
    )
    bugfix_d3 = experiment_policy_violations(
        [row("bugfix_schema_guard", d3, "BUGFIX_VALID")], before_deadline, milestones, policy
    )
    final_d3 = experiment_policy_violations(
        [row("final_submission_selection", d3, "FINAL_SELECTED")],
        before_deadline,
        milestones,
        policy,
    )
    submission_base = {
        "competition": "probe",
        "source": "probe",
        "submission_id": "1",
        "filename": "probe.csv",
        "sha256": "0" * 64,
        "public_score": "0",
        "private_score": "",
        "status": "COMPLETE",
        "conclusion": "probe",
    }
    frozen_submission = submission_policy_violations(
        [
            {
                **submission_base,
                "experiment": "new_candidate_tuning",
                "submitted_at_utc": d14.isoformat(),
            }
        ],
        before_deadline,
        milestones,
        policy,
    )
    bugfix_submission = submission_policy_violations(
        [
            {
                **submission_base,
                "experiment": "bugfix_schema_guard",
                "submitted_at_utc": d3.isoformat(),
            }
        ],
        before_deadline,
        milestones,
        policy,
    )
    return {
        "post_D14_candidate_tuning_rejected": len(tuning_d14) == 1,
        "post_D7_candidate_tuning_rejected": len(tuning_d7) == 1,
        "post_D7_reproduction_allowed": reproduction_d7 == [],
        "post_D3_ordinary_model_rejected": len(model_d3) == 1,
        "post_D3_bugfix_allowed": bugfix_d3 == [],
        "post_D3_final_selection_allowed": final_d3 == [],
        "post_D14_new_submission_rejected": len(frozen_submission) == 1,
        "post_D3_bugfix_submission_allowed": bugfix_submission == [],
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run(
    traffic_root: Path,
    config_path: Path,
    as_of: datetime,
    output_root: Path,
) -> dict[str, object]:
    started = time.perf_counter()
    if output_root.exists():
        raise ValueError("lifecycle policy output root already exists; use a new path")
    if as_of.tzinfo is None:
        raise ValueError("--as-of must include a timezone")
    config = json.loads(config_path.read_text())
    milestones = parse_milestones(config)
    artifacts = traffic_root / "artifacts"
    experiment_path = artifacts / "experiment_ledger.csv"
    submission_path = artifacts / "submission_ledger.csv"
    status_path = artifacts / "campaign_status.json"
    experiments = _read_csv(experiment_path)
    submissions = _read_csv(submission_path)
    status = json.loads(status_path.read_text())
    errors: list[str] = []
    input_hashes: dict[str, str] = {
        config_path.name: _sha256(config_path),
        "experiment_ledger.csv": _sha256(experiment_path),
        "submission_ledger.csv": _sha256(submission_path),
        "campaign_status.json": _sha256(status_path),
        "src/lifecycle_policy_audit.py": _sha256(Path(__file__).resolve()),
    }
    if any(status["lifecycle"][name] != config["milestones"][name] for name in ("D30", "D14", "D7", "D3")):
        errors.append("campaign status milestones disagree with lifecycle policy")
    if status["deadline_asia_shanghai"] != config["milestones"]["deadline"]:
        errors.append("campaign deadline disagrees with lifecycle policy")
    frozen = config["frozen_candidate"]
    if (
        status["current_best"]["submission_id"] != frozen["submission_id"]
        or status["current_best"]["sha256"] != frozen["sha256"]
    ):
        errors.append("current best disagrees with the D-14 frozen candidate")

    evidence_rows: list[dict[str, object]] = []
    for evidence in config["deadline_evidence"]:
        matches = [row for row in experiments if row["experiment"] == evidence["experiment"]]
        valid = len(matches) == 1
        ledger_started = None
        if valid:
            ledger_started = datetime.fromisoformat(matches[0]["started_at_utc"].replace("Z", "+00:00"))
            expected_ledger_status = evidence.get("ledger_status", evidence.get("status"))
            valid = (
                ledger_started.tzinfo is not None
                and ledger_started <= milestones[evidence["milestone"]]
                and matches[0]["status"] == expected_ledger_status
                and matches[0]["sha256"] == evidence["receipt_sha256"]
            )
        receipt_path = traffic_root / evidence["receipt_path"]
        receipt_sha = _sha256(receipt_path) if receipt_path.is_file() else "MISSING"
        input_hashes[evidence["receipt_path"]] = receipt_sha
        receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
        expected_receipt_status = evidence.get("receipt_status", evidence.get("status"))
        valid = valid and receipt_sha == evidence["receipt_sha256"] and receipt.get("status") == expected_receipt_status
        if not valid:
            errors.append(f"{evidence['milestone']} deadline evidence is invalid or late")
        evidence_rows.append(
            {
                "milestone": evidence["milestone"],
                "deadline": milestones[evidence["milestone"]].isoformat(),
                "experiment": evidence["experiment"],
                "ledger_started_at": ledger_started.isoformat() if ledger_started else "MISSING",
                "receipt_sha256": receipt_sha,
                "status": "PASS" if valid else "FAIL",
            }
        )

    experiment_violations = experiment_policy_violations(experiments, as_of, milestones, config)
    submission_violations = submission_policy_violations(submissions, as_of, milestones, config)
    probes = policy_probes(milestones, config)
    if experiment_violations:
        errors.append(f"{len(experiment_violations)} post-freeze experiment policy violations")
    if submission_violations:
        errors.append(f"{len(submission_violations)} post-freeze submission policy violations")
    if not all(probes.values()):
        errors.append("one or more lifecycle enforcement probes failed")
    if any(config["information_boundary"].values()):
        errors.append("lifecycle policy permits unavailable information")

    output_root.mkdir(parents=True)
    evidence_output = output_root / "deadline_evidence.csv"
    with evidence_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0]))
        writer.writeheader()
        writer.writerows(evidence_rows)
    violation_output = output_root / "lifecycle_violations.csv"
    violation_fields = ["kind", "name", "started_at_utc", "phase", "category", "reason"]
    with violation_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=violation_fields)
        writer.writeheader()
        writer.writerows([*experiment_violations, *submission_violations])
    matrix_output = output_root / "lifecycle_policy_matrix.csv"
    matrix_rows = [
        {
            "phase": phase,
            "allowed_categories": ";".join(categories),
            "new_kaggle_submission_rule": (
                "documented bugfix only" if phase == "D3_BUGFIX_AND_FINAL_SELECTION_ONLY" else "forbidden"
            ),
        }
        for phase, categories in config["allowed_categories"].items()
    ]
    with matrix_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix_rows[0]))
        writer.writeheader()
        writer.writerows(matrix_rows)
    receipt: dict[str, object] = {
        "status": "VALID" if not errors else "FAIL",
        "experiment": "lifecycle_policy_audit_v1",
        "as_of": as_of.isoformat(),
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": lifecycle_phase(as_of, milestones),
        "deadline_evidence_verified": sum(row["status"] == "PASS" for row in evidence_rows),
        "post_freeze_experiment_violations": experiment_violations,
        "post_freeze_submission_violations": submission_violations,
        "enforcement_probes": probes,
        "errors": errors,
        "frozen_candidate": frozen,
        "information_boundary": {
            "hidden_labels_read_or_reconstructed": False,
            "private_scores_used": False,
            "organizer_only_metrics_inferred": False,
            "external_action_performed": False,
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": input_hashes,
        "outputs": {
            evidence_output.name: _sha256(evidence_output),
            violation_output.name: _sha256(violation_output),
            matrix_output.name: _sha256(matrix_output),
        },
        "decision": "LIFECYCLE_GATES_ENFORCED",
    }
    receipt_path = output_root / "lifecycle_policy_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "lifecycle_policy_v1.json",
    )
    parser.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(
        args.traffic_root.resolve(), args.config.resolve(), args.as_of, args.output_root.resolve()
    )
    if receipt["status"] != "VALID":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
