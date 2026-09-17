#!/usr/bin/env python3
"""Audit whether the local evidence inventory contains an untouched V176 corpus."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
STATUS = "NO_VERIFIED_ELIGIBLE_ARC_AGI_2_GENERALIZATION_CORPUS"
DECISION = "PIVOT_V176_TO_SYSTEMS_NEGATIVE"
EXPECTED_CORPORA = [
    {"stem": "arc-agi_training", "tasks": 400, "outputs": 416},
    {"stem": "arc-agi_evaluation", "tasks": 400, "outputs": 419},
    {"stem": "arc-agi_training2", "tasks": 1000, "outputs": 1076},
    {"stem": "arc-agi_evaluation2", "tasks": 120, "outputs": 172},
    {"stem": "arc-agi_concept", "tasks": 160, "outputs": 480},
]
EXPECTED_AGGREGATE = {
    "tasks": 2080,
    "outputs": 2563,
    "fired_tasks": 753,
    "fired_outputs": 1103,
    "correct_fired_outputs": 1103,
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(root: pathlib.Path, relative: str) -> dict[str, str]:
    path = root / relative
    return {"path": relative, "sha256": sha256(path)}


def audit(root: pathlib.Path = PROJECT_ROOT) -> dict[str, Any]:
    root = root.resolve()
    readme_path = root / "public_assets/trm_source/README.md"
    source_path = (
        root
        / "public_assets/trm_source/receipts/exact-rule-heldout-benchmark-v175.json"
    )
    integrity_path = root / "paper/results/v3_holdout_integrity_audit_2026-09-09.json"

    source = json.loads(source_path.read_text(encoding="utf-8"))
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    readme = readme_path.read_text(encoding="utf-8")

    observed_corpora = [
        {
            "stem": item["stem"],
            "tasks": item["tasks"],
            "outputs": item["outputs"],
        }
        for item in source["datasets"]
    ]
    observed_aggregate = {
        key: source["aggregate"][key] for key in EXPECTED_AGGREGATE
    }
    if observed_corpora != EXPECTED_CORPORA:
        raise ValueError("historical corpus inventory drifted")
    if observed_aggregate != EXPECTED_AGGREGATE:
        raise ValueError("historical aggregate inventory drifted")
    if "ConceptARC at 480/480 outputs and 160/160 tasks" not in readme:
        raise ValueError("ConceptARC completeness statement missing")
    if integrity.get("audit_status") != "CONTAMINATED_FOR_V176_GENERALIZATION":
        raise ValueError("V3 holdout-integrity decision drifted")
    if integrity.get("holdout_solutions_read_by_this_audit") is not False:
        raise ValueError("holdout-integrity audit boundary drifted")

    return {
        "schema_version": 1,
        "checked_at_cst": "2026-09-09T21:45:00+08:00",
        "checked_at_utc": "2026-09-09T13:45:00+00:00",
        "audit_status": STATUS,
        "candidate_id": "conservative_exact_overlay_v3",
        "method": (
            "local provenance and prior-solution-access audit only; "
            "no network or Kaggle action"
        ),
        "eligibility_requirements": {
            "corpus_independently_created": True,
            "license_cleared": True,
            "solution_unavailable_during_method_construction": True,
            "target_distribution_comparability_justified": True,
            "task_and_content_overlap_zero": True,
            "one_shot_protocol_frozen_before_solution_access": True,
        },
        "local_source_evidence": {
            "audit_tool": binding(root, "paper/tools/audit_v176_corpus_availability.py"),
            "bundled_parent_readme": {
                **binding(root, "public_assets/trm_source/README.md"),
                "observed_fact": (
                    "The bundled source documents prior testing over official "
                    "ARC-AGI corpora, duplicate partitions, and ConceptARC."
                ),
            },
            "v175_five_corpus_receipt": {
                **binding(
                    root,
                    "public_assets/trm_source/receipts/"
                    "exact-rule-heldout-benchmark-v175.json",
                ),
                "aggregate": observed_aggregate,
                "corpora": observed_corpora,
            },
            "v3_holdout_integrity_receipt": binding(
                root, "paper/results/v3_holdout_integrity_audit_2026-09-09.json"
            ),
        },
        "adjudication": {
            "arc_agi_1_train_and_evaluation": (
                "INELIGIBLE: historically evaluated by the bundled parent"
            ),
            "arc_agi_2_train_and_evaluation": (
                "INELIGIBLE: historically evaluated by the bundled parent"
            ),
            "conceptarc": (
                "INELIGIBLE: historically evaluated to complete coverage"
            ),
            "one_d_arc_miniarc_community_or_synthetic": (
                "NOT_VERIFIED: target-distribution comparability is not established"
            ),
            "same_1000_task_repartition": (
                "INELIGIBLE: repartitioning cannot restore solution isolation"
            ),
        },
        "permitted_use_of_domain_shift_corpora": (
            "Only a preregistered domain-shift mechanistic stress test; never an "
            "ARC-AGI-2 Accuracy, Progress, Universality, or Novelty claim."
        ),
        "current_decision": DECISION,
        "positive_route_reopen_contract": {
            "required_before_acquisition_or_solution_view": [
                "new candidate and contract version",
                "solver, rules, metrics, inclusion, exclusion, and license frozen",
            ],
            "required_receipts": [
                "provenance and solution-access audit",
                "zero-overlap audit",
                "license receipt",
                "target-distribution comparability justification",
            ],
            "stop_conditions": [
                "any historical answer exposure",
                "any task or content overlap",
                "any holdout-driven tuning or rerun",
            ],
        },
        "authorization_boundary": {
            "network_access_used": False,
            "kaggle_query_performed": False,
            "artifact_downloaded": False,
            "external_run_started": False,
            "submission_performed": False,
            "sealed_holdout_opened": False,
        },
        "claim_boundary": (
            "No eligible untouched labeled corpus is verified in the current local "
            "inventory. This does not prove that none exists elsewhere."
        ),
    }


def main() -> None:
    try:
        result = audit()
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"passes": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
