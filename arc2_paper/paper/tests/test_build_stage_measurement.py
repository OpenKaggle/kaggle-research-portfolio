#!/usr/bin/env python3
"""Real-artifact replay and synthetic end-to-end stage measurement checks."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    binding,
    build_complete_contract,
    sha256,
    write_json,
)
from paper.tools.build_stage_measurement import (  # noqa: E402
    FAMILY_BUCKETS,
    build_competition_measurement,
    build_measurement,
    inspect_labeled_run,
)
from paper.tools.build_stage_receipt import build_receipt  # noqa: E402


def grid(value: int) -> list[list[int]]:
    return [[value]]


def artifact_record(path: pathlib.Path) -> dict[str, int | str]:
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def write_synthetic_run(
    run_dir: pathlib.Path,
    notebook_sha256: str,
) -> None:
    run_dir.mkdir(parents=True)
    task_ids = [f"{index:08x}" for index in range(7)]
    challenges = {
        task_id: {
            "train": [{"input": grid(index + 1), "output": grid(index + 1)}],
            "test": [{"input": grid(index + 1)}],
        }
        for index, task_id in enumerate(task_ids)
    }
    solutions = {task_id: [grid(index + 1)] for index, task_id in enumerate(task_ids)}
    anchor = {}
    method = {}
    for index, task_id in enumerate(task_ids):
        expected = grid(index + 1)
        wrong = grid((index + 2) % 10)
        anchor[task_id] = [
            {"attempt_1": wrong, "attempt_2": expected if index else wrong}
        ]
        method[task_id] = [{"attempt_1": wrong, "attempt_2": expected}]

    write_json(run_dir / "benchmark_challenges.json", challenges)
    write_json(run_dir / "benchmark_solutions.json", solutions)
    write_json(
        run_dir / "benchmark_manifest.json",
        {
            "seed": "fixture",
            "selection": "fixture",
            "quartile_counts": {"q1": 2, "q2": 2, "q3": 2, "q4": 1},
            "tasks": [{"task_id": task_id} for task_id in task_ids],
        },
    )
    write_json(run_dir / "nvarc_kgmon.json", anchor)
    write_json(run_dir / "submission.json", method)
    write_json(
        run_dir / "ab-benchmark-report.json",
        {
            "benchmark_tasks": 7,
            "total_outputs": 7,
            "policy_scores": {
                "kgmon": {"solved_outputs": 6, "total_outputs": 7},
                "agreement_exact_v176": {"solved_outputs": 7, "total_outputs": 7},
            },
        },
    )
    write_json(
        run_dir / "run_manifest.json",
        {
            "status": "COMPLETE",
            "started_at_cst": "2026-09-09T10:00:00+08:00",
            "completed_at_cst": "2026-09-09T10:01:40+08:00",
            "notebook_sha256": notebook_sha256,
        },
    )
    artifact_names = (
        "benchmark_challenges.json",
        "benchmark_solutions.json",
        "benchmark_manifest.json",
        "nvarc_kgmon.json",
        "submission.json",
        "ab-benchmark-report.json",
    )
    artifact_files = {
        name: artifact_record(run_dir / name) for name in artifact_names
    }
    (run_dir / "analysis").mkdir()
    write_json(
        run_dir / "analysis/benchmark_receipt.json",
        {
            "authoritative_kernel_status": "COMPLETE",
            "completed_at_cst": "2026-09-09T10:01:40+08:00",
            "kernel_wall_upper_bound_seconds": 100,
            "peak_memory_mb": 1024,
            "nvarc": {
                "unfinished_tasks": [],
                "timed_out_tasks": [],
                "incomplete_decode_tasks": [],
                "failed_tasks": [],
            },
            "trm": {"available": True, "marker": {}},
            "selection_policy": {
                "method_solved_outputs": 7,
                "anchor_solved_outputs": 6,
            },
            "hard_gates": {
                "full_coverage": True,
                "zero_timeouts": True,
                "all_decodes_complete": True,
                "all_submission_schemas_valid": True,
                "within_six_hour_cap": True,
                "trm_available": True,
                "method_gain_at_least_one_output": True,
                "attempt_1_unchanged": True,
                "all_passed": True,
            },
            "artifact_files": artifact_files,
        },
    )


def write_synthetic_competition(
    root: pathlib.Path,
    notebook_path: pathlib.Path,
) -> dict[str, pathlib.Path]:
    task_ids = [f"{index:08x}" for index in range(3)]
    challenges = {
        task_id: {
            "train": [{"input": grid(index + 1), "output": grid(index + 1)}],
            "test": [{"input": grid(index + 1)}],
        }
        for index, task_id in enumerate(task_ids)
    }
    submission = {
        task_id: [{"attempt_1": grid(index + 1), "attempt_2": grid(0)}]
        for index, task_id in enumerate(task_ids)
    }
    paths = {
        "challenge": root / "competition/challenges.json",
        "submission": root / "competition/submission.json",
        "input_manifest": root / "competition/input-manifest.json",
        "kernel_metadata": root / "competition/kernel-metadata.json",
        "run_log": root / "competition/run.log",
        "observation": root / "competition/submission-receipt.json",
    }
    paths["challenge"].parent.mkdir()
    write_json(paths["challenge"], challenges)
    write_json(paths["submission"], submission)
    write_json(paths["input_manifest"], {"scope": "synthetic hidden test"})
    write_json(
        paths["kernel_metadata"],
        {
            "id": "owner/frozen-v3",
            "code_file": notebook_path.name,
            "enable_gpu": True,
            "enable_internet": False,
        },
    )
    paths["run_log"].write_text("COMPLETE\nsubmission emitted\n", encoding="utf-8")
    write_json(
        paths["observation"],
        {
            "schema_version": 1,
            "observation_mode": "READ_ONLY_KAGGLE_SUBMISSION_RECEIPT",
            "kernel_slug": "owner/frozen-v3",
            "notebook_version": 7,
            "authoritative_kernel_status": "COMPLETE",
            "raw_kernel_status": 'status "complete"',
            "status_verified_at_cst": "2026-09-09T12:01:42+08:00",
            "artifacts_downloaded": True,
            "submission_id": "987654",
            "submission_status": "complete",
            "leaderboard_score": 0.42,
            "score_scope": "public_leaderboard",
            "score_observed_at": "2026-09-09T12:01:41+08:00",
            "started_at_cst": "2026-09-09T12:00:00+08:00",
            "completed_at_cst": "2026-09-09T12:01:40+08:00",
            "wall_seconds": 100,
            "peak_memory_mb": 2048,
            "failed_task_ids": ["00000002"],
            "timed_out_task_ids": ["00000002"],
            "notebook_sha256": sha256(notebook_path),
            "submission_sha256": sha256(paths["submission"]),
            "input_manifest_sha256": sha256(paths["input_manifest"]),
            "run_log_sha256": sha256(paths["run_log"]),
            "kernel_metadata_sha256": sha256(paths["kernel_metadata"]),
            "public_leaderboard_used_for_selection": False,
            "claim_boundary": "Aggregate score only; hidden labels unavailable.",
        },
    )
    return paths


def main() -> None:
    stable_v2 = ROOT / "kaggle_runs/development_stable_v2"
    replay = inspect_labeled_run(
        stable_v2,
        "private_development",
        48,
        50,
        expected_method_policy="agreement_merge",
    )
    assert replay["metrics"]["method_exact_outputs"] == 48
    assert replay["metrics"]["anchor_exact_outputs"] == 48
    assert replay["metrics"]["attempt_1_exact_outputs"] == 47
    assert replay["metrics"]["attempt_2_incremental_outputs"] == 1
    assert replay["runtime"]["failed_tasks"] == 1
    assert replay["runtime"]["timed_out_task_ids"] == ["e619ca6e"]
    assert replay["gates"] == {
        "all_passed": False,
        "promote_to_holdout": False,
    }
    assert set(replay["family_coverage"]) == set(FAMILY_BUCKETS)
    assert sum(row["tasks"] for row in replay["family_coverage"].values()) == 48

    with tempfile.TemporaryDirectory(prefix="arc2-stage-measurement-") as raw:
        root = pathlib.Path(raw)
        contract_path, contract, _ = build_complete_contract(root)
        contract = copy.deepcopy(contract)
        contract["status"] = "ACTIVE_NOT_COMPLETE"
        development = contract["stages"]["private_development"]
        development["state"] = "RUNNING"
        development["receipt"] = None
        development["expected_tasks"] = 7
        development["expected_outputs"] = 7
        for stage in ("sealed_holdout", "competition_rerun"):
            contract["stages"][stage]["state"] = "NOT_AUTHORIZED"
            contract["stages"][stage]["receipt"] = None
            contract["stages"][stage]["authorization"] = None
        write_json(contract_path, contract)

        run_dir = root / "run"
        write_synthetic_run(run_dir, development["notebook"]["sha256"])
        measurement, manifest = build_measurement(
            contract_path,
            "private_development",
            run_dir,
            "fixture-development-v3",
            root / "generated/artifact-manifest.json",
        )
        assert measurement["metrics"]["delta_vs_anchor"] == 1 / 7
        assert measurement["gates"] == {
            "all_passed": True,
            "promote_to_holdout": True,
        }
        assert manifest["family_classifier"]["uses_test_outputs"] is False
        assert len(manifest["family_classifier"]["task_assignments"]) == 7

        artifact_manifest = root / "generated/artifact-manifest.json"
        artifact_manifest.parent.mkdir()
        write_json(artifact_manifest, manifest)
        measurement_path = root / "generated/measurement.json"
        write_json(measurement_path, measurement)
        receipt = build_receipt(
            contract_path,
            "private_development",
            measurement_path,
        )
        assert receipt["metrics"]["method_exact_outputs"] == 7
        assert receipt["gates"]["promote_to_holdout"] is True
        assert receipt["artifacts"]["artifact_manifest_sha256"] == sha256(
            artifact_manifest
        )

        leaked = json.loads(
            (run_dir / "benchmark_challenges.json").read_text(encoding="utf-8")
        )
        leaked["00000000"]["test"][0]["output"] = [[1]]
        write_json(run_dir / "benchmark_challenges.json", leaked)
        try:
            inspect_labeled_run(run_dir, "private_development", 7, 7)
        except ValueError as error:
            assert "must not contain labels" in str(error)
        else:
            raise AssertionError("test-output leakage was accepted")

    with tempfile.TemporaryDirectory(prefix="arc2-competition-measurement-") as raw:
        root = pathlib.Path(raw)
        contract_path, contract, _ = build_complete_contract(root)
        contract = copy.deepcopy(contract)
        contract["status"] = "ACTIVE_NOT_COMPLETE"
        competition = contract["stages"]["competition_rerun"]
        competition["state"] = "RUNNING"
        competition["receipt"] = None
        competition["expected_tasks"] = 3
        competition["expected_outputs"] = 3
        write_json(contract_path, contract)
        notebook_path = root / competition["notebook"]["path"]
        paths = write_synthetic_competition(root, notebook_path)
        measurement, manifest = build_competition_measurement(
            contract_path,
            "fixture-competition-v3",
            paths["challenge"],
            paths["submission"],
            paths["input_manifest"],
            paths["kernel_metadata"],
            paths["run_log"],
            paths["observation"],
            root / "competition/artifact-manifest.json",
        )
        assert measurement["metrics"]["local_labels_available"] is False
        assert all(
            measurement["metrics"][key] is None
            for key in (
                "method_exact_outputs",
                "anchor_exact_outputs",
                "attempt_1_exact_outputs",
                "attempt_2_incremental_outputs",
                "method_accuracy",
                "anchor_accuracy",
                "delta_vs_anchor",
            )
        )
        assert measurement["runtime"]["failure_rate"] == 1 / 3
        assert measurement["kaggle"]["submission_id"] == "987654"
        assert manifest["family_classifier"]["correctness_available"] is False
        assert sum(
            row["tasks"] for row in measurement["family_coverage"].values()
        ) == 3
        assert sum(
            row["failed_tasks"] for row in measurement["family_coverage"].values()
        ) == 1

        artifact_manifest = root / "competition/artifact-manifest.json"
        write_json(artifact_manifest, manifest)
        measurement_path = root / "competition/measurement.json"
        write_json(measurement_path, measurement)
        receipt = build_receipt(
            contract_path,
            "competition_rerun",
            measurement_path,
        )
        assert receipt["kaggle"]["leaderboard_score"] == 0.42
        assert abs(receipt["kaggle"]["delta_vs_reference"] + 0.43) < 1e-12
        assert receipt["metrics"]["method_exact_outputs"] is None

        observation = json.loads(paths["observation"].read_text(encoding="utf-8"))
        observation["hidden_correct_outputs"] = 2
        write_json(paths["observation"], observation)
        try:
            build_competition_measurement(
                contract_path,
                "fixture-competition-v3-extra",
                paths["challenge"],
                paths["submission"],
                paths["input_manifest"],
                paths["kernel_metadata"],
                paths["run_log"],
                paths["observation"],
                root / "competition/extra-artifact-manifest.json",
            )
        except ValueError as error:
            assert "extra=['hidden_correct_outputs']" in str(error)
        else:
            raise AssertionError("hidden competition correctness was accepted")

    print("stage measurement builder regression passed")


if __name__ == "__main__":
    main()
