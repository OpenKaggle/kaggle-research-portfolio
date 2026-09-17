#!/usr/bin/env python3
"""Regression checks for policy-injected, file-hashed stage receipts."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    build_complete_contract,
    normalized_receipt,
    sha256,
    write_json,
)
from paper.tools.build_stage_receipt import build_receipt  # noqa: E402


def prepare_artifacts(root: pathlib.Path, stage: str) -> dict[str, str]:
    paths = {"notebook": root / f"{stage}.ipynb"}
    for name in ("input_manifest", "submission", "artifact_manifest"):
        path = root / f"{stage}-{name}.json"
        write_json(path, {"stage": stage, "artifact": name})
        paths[name] = path
    return {key: path.relative_to(root).as_posix() for key, path in paths.items()}


def measurement(
    root: pathlib.Path,
    stage: str,
    completed_at: str,
) -> dict:
    receipt = normalized_receipt(stage, completed_at, sha256(root / f"{stage}.ipynb"))
    payload = {
        key: copy.deepcopy(receipt[key])
        for key in (
            "experiment_id",
            "started_at",
            "completed_at",
            "metrics",
            "family_coverage",
            "runtime",
            "submission_format",
            "gates",
        )
    }
    payload["artifact_paths"] = prepare_artifacts(root, stage)
    if stage == "competition_rerun":
        submission_receipt = root / "kaggle-submission-receipt.json"
        write_json(submission_receipt, {"submission": "123456", "score": 0.42})
        payload["kaggle"] = {
            key: receipt["kaggle"][key]
            for key in (
                "submission_id",
                "leaderboard_score",
                "submission_status",
                "score_scope",
                "notebook_version",
                "kernel_slug",
                "score_observed_at",
            )
        }
        payload["kaggle"]["submission_receipt_path"] = submission_receipt.relative_to(
            root
        ).as_posix()
    return payload


def set_running(contract: dict, stage: str) -> None:
    contract["status"] = "ACTIVE_NOT_COMPLETE"
    order = ("private_development", "sealed_holdout", "competition_rerun")
    index = order.index(stage)
    for earlier in order[:index]:
        contract["stages"][earlier]["state"] = "COMPLETE"
    contract["stages"][stage]["state"] = "RUNNING"
    contract["stages"][stage]["receipt"] = None
    for later in order[index + 1 :]:
        contract["stages"][later]["state"] = "NOT_AUTHORIZED"
        contract["stages"][later]["receipt"] = None
        contract["stages"][later]["authorization"] = None


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arc2-stage-builder-") as raw:
        root = pathlib.Path(raw)
        contract_path, contract, _ = build_complete_contract(root)

        development_contract = copy.deepcopy(contract)
        set_running(development_contract, "private_development")
        write_json(contract_path, development_contract)
        development_measurement = root / "development-measurement.json"
        write_json(
            development_measurement,
            measurement(
                root,
                "private_development",
                "2026-09-09T01:00:00+00:00",
            ),
        )
        built = build_receipt(
            contract_path, "private_development", development_measurement
        )
        stage_contract = development_contract["stages"]["private_development"]
        assert built["hypothesis"] == stage_contract["hypothesis"]
        assert built["single_changed_factor"] == stage_contract["single_changed_factor"]
        assert built["artifacts"]["notebook_sha256"] == stage_contract["notebook"]["sha256"]
        assert built["public_leaderboard_used_for_selection"] is False

        competition_contract = copy.deepcopy(contract)
        set_running(competition_contract, "competition_rerun")
        write_json(contract_path, competition_contract)
        competition_measurement = root / "competition-measurement.json"
        write_json(
            competition_measurement,
            measurement(
                root,
                "competition_rerun",
                "2026-09-09T03:00:00+00:00",
            ),
        )
        built = build_receipt(contract_path, "competition_rerun", competition_measurement)
        reference = competition_contract["stages"]["competition_rerun"][
            "score_reference"
        ]
        assert built["kaggle"]["reference_score"] == reference["score"]
        assert abs(built["kaggle"]["delta_vs_reference"] + 0.43) < 1e-12
        assert built["metrics"]["method_exact_outputs"] is None
        assert built["kaggle"]["submission_receipt_sha256"] == sha256(
            root / "kaggle-submission-receipt.json"
        )

        wrong_notebook = json.loads(competition_measurement.read_text(encoding="utf-8"))
        alternate = root / "alternate.ipynb"
        alternate.write_text("{\"different\": true}\n", encoding="utf-8")
        wrong_notebook["artifact_paths"]["notebook"] = alternate.name
        wrong_notebook_path = root / "wrong-notebook.json"
        write_json(wrong_notebook_path, wrong_notebook)
        try:
            build_receipt(contract_path, "competition_rerun", wrong_notebook_path)
        except ValueError as error:
            assert "notebook path differs" in str(error)
        else:
            raise AssertionError("alternate notebook was accepted")

        extra_field = json.loads(competition_measurement.read_text(encoding="utf-8"))
        extra_field["manual_override"] = True
        extra_field_path = root / "extra-field.json"
        write_json(extra_field_path, extra_field)
        try:
            build_receipt(contract_path, "competition_rerun", extra_field_path)
        except ValueError as error:
            assert "extra=['manual_override']" in str(error)
        else:
            raise AssertionError("unregistered measurement field was accepted")

        hidden_correctness = json.loads(
            competition_measurement.read_text(encoding="utf-8")
        )
        hidden_correctness["metrics"]["method_exact_outputs"] = 8
        hidden_correctness_path = root / "hidden-correctness.json"
        write_json(hidden_correctness_path, hidden_correctness)
        try:
            build_receipt(contract_path, "competition_rerun", hidden_correctness_path)
        except ValueError as error:
            assert "competition_per_output_correctness_forbidden" in str(error)
        else:
            raise AssertionError("fabricated hidden correctness was accepted")

    try:
        build_receipt(
            ROOT / "paper/manifests/three_stage_pipeline_v1.json",
            "private_development",
            ROOT / "does-not-exist.json",
        )
    except ValueError as error:
        assert "must be RUNNING" in str(error)
    else:
        raise AssertionError("current unauthorized development stage was accepted")

    print("stage receipt builder regression passed")


if __name__ == "__main__":
    main()
