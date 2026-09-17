#!/usr/bin/env python3
"""Build a normalized, hash-bound receipt for one authorized completed stage.

The contract stage must already be RUNNING and the whole pipeline contract must
pass before this tool will read a measurement file. Hypothesis, single changed
factor, data split, candidate identity, score reference, and leaderboard-use
declaration are injected from frozen policy rather than accepted from the run.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

try:
    from paper.tools.audit_three_stage_pipeline import (
        STAGE_ORDER,
        audit,
        digest,
        validate_complete_receipt,
    )
except ModuleNotFoundError:  # Direct execution from paper/tools.
    from audit_three_stage_pipeline import (  # type: ignore
        STAGE_ORDER,
        audit,
        digest,
        validate_complete_receipt,
    )


COMMON_MEASUREMENT_FIELDS = {
    "experiment_id",
    "started_at",
    "completed_at",
    "metrics",
    "family_coverage",
    "runtime",
    "submission_format",
    "gates",
    "artifact_paths",
}
ARTIFACT_PATH_FIELDS = {
    "notebook",
    "input_manifest",
    "submission",
    "artifact_manifest",
}
KAGGLE_MEASUREMENT_FIELDS = {
    "submission_id",
    "leaderboard_score",
    "submission_status",
    "score_scope",
    "notebook_version",
    "kernel_slug",
    "score_observed_at",
    "submission_receipt_path",
}


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise ValueError(f"{label} fields differ: missing={missing}, extra={extra}")
    return value


def project_file(root: pathlib.Path, raw: Any, label: str) -> pathlib.Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty repository-relative path")
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} is unsafe: {raw!r}")
    path = (root / pathlib.Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} escapes project root: {raw!r}") from error
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {raw!r}")
    return path


def contract_root(contract_path: pathlib.Path, contract: dict[str, Any]) -> pathlib.Path:
    raw = contract.get("project_root")
    if not isinstance(raw, str) or not raw:
        raise ValueError("contract project_root is missing")
    return (contract_path.parent / raw).resolve()


def build_receipt(
    contract_path: pathlib.Path,
    stage: str,
    measurement_path: pathlib.Path,
) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    measurement_path = measurement_path.resolve()
    pipeline = audit(contract_path)
    if not pipeline["passes"]:
        raise ValueError(
            "pipeline contract does not pass before receipt construction: "
            + json.dumps(pipeline["violations"], sort_keys=True)
        )
    if stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage: {stage!r}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    stage_contract = contract["stages"][stage]
    if stage_contract.get("state") != "RUNNING" or stage_contract.get("receipt") is not None:
        raise ValueError(
            f"{stage} must be RUNNING with no terminal receipt before construction"
        )

    measurement = json.loads(measurement_path.read_text(encoding="utf-8"))
    expected_measurement = COMMON_MEASUREMENT_FIELDS | (
        {"kaggle"} if stage == "competition_rerun" else set()
    )
    measurement = exact_keys(measurement, expected_measurement, "measurement")
    artifact_paths = exact_keys(
        measurement["artifact_paths"], ARTIFACT_PATH_FIELDS, "artifact_paths"
    )

    root = contract_root(contract_path, contract)
    artifacts: dict[str, str] = {}
    for key in sorted(ARTIFACT_PATH_FIELDS):
        path = project_file(root, artifact_paths[key], f"artifact_paths.{key}")
        artifacts[f"{key}_sha256"] = digest(path)

    expected_notebook = stage_contract.get("notebook")
    if not isinstance(expected_notebook, dict):
        raise ValueError(f"{stage} has no frozen notebook binding")
    expected_notebook_path = project_file(
        root, expected_notebook.get("path"), f"{stage}.notebook"
    )
    provided_notebook_path = project_file(
        root, artifact_paths["notebook"], "artifact_paths.notebook"
    )
    if expected_notebook_path != provided_notebook_path:
        raise ValueError("measurement notebook path differs from the frozen stage notebook")
    if artifacts["notebook_sha256"] != expected_notebook.get("sha256"):
        raise ValueError("measurement notebook hash differs from the frozen stage notebook")

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "stage": stage,
        "candidate_id": contract["candidate_id"],
        "experiment_id": measurement["experiment_id"],
        "hypothesis": stage_contract["hypothesis"],
        "single_changed_factor": stage_contract["single_changed_factor"],
        "data_split": stage_contract["data_split"],
        "authoritative_status": "COMPLETE",
        "public_leaderboard_used_for_selection": contract["anti_tuning"][
            "public_leaderboard_used_for_policy_selection"
        ],
        "started_at": measurement["started_at"],
        "completed_at": measurement["completed_at"],
        "metrics": measurement["metrics"],
        "family_coverage": measurement["family_coverage"],
        "runtime": measurement["runtime"],
        "submission_format": measurement["submission_format"],
        "artifacts": artifacts,
        "gates": measurement["gates"],
    }

    if stage == "competition_rerun":
        measured_kaggle = exact_keys(
            measurement["kaggle"], KAGGLE_MEASUREMENT_FIELDS, "kaggle measurement"
        )
        submission_receipt = project_file(
            root,
            measured_kaggle["submission_receipt_path"],
            "kaggle.submission_receipt_path",
        )
        reference = stage_contract["score_reference"]
        score = measured_kaggle["leaderboard_score"]
        receipt["kaggle"] = {
            key: measured_kaggle[key]
            for key in KAGGLE_MEASUREMENT_FIELDS - {"submission_receipt_path"}
        }
        receipt["kaggle"].update(
            {
                "submission_receipt_sha256": digest(submission_receipt),
                "reference_name": reference["name"],
                "reference_score": reference["score"],
                "reference_scope": reference["scope"],
                "delta_vs_reference": float(score) - float(reference["score"]),
                "reference_receipt_sha256": reference["receipt_sha256"],
            }
        )

    violations: list[dict[str, Any]] = []
    validate_complete_receipt(
        receipt,
        stage,
        contract["candidate_id"],
        set(contract["required_family_buckets"]),
        stage_contract,
        violations,
    )
    if violations:
        raise ValueError(
            "constructed receipt failed normalized validation: "
            + json.dumps(violations, sort_keys=True)
        )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--stage", choices=STAGE_ORDER, required=True)
    parser.add_argument("--measurement", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        receipt = build_receipt(args.contract, args.stage, args.measurement)
        rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "output": str(args.output),
                    "receipt_sha256": digest(args.output),
                },
                sort_keys=True,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
