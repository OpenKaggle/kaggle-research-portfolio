#!/usr/bin/env python3
"""Draft 2020-12 checks for the hidden-label-safe competition observation."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tools.build_stage_measurement import (  # noqa: E402
    COMPETITION_OBSERVATION_FIELDS,
)


SCHEMA = ROOT / "paper/schemas/competition_observation_v1.schema.json"
HASH = "a" * 64


def fixture() -> dict:
    return {
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
        "notebook_sha256": HASH,
        "submission_sha256": HASH,
        "input_manifest_sha256": HASH,
        "run_log_sha256": HASH,
        "kernel_metadata_sha256": HASH,
        "public_leaderboard_used_for_selection": False,
        "claim_boundary": "Aggregate score only; hidden labels unavailable.",
    }


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == COMPETITION_OBSERVATION_FIELDS
    assert set(schema["properties"]) == COMPETITION_OBSERVATION_FIELDS
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid = fixture()
    assert not list(validator.iter_errors(valid))

    hidden = copy.deepcopy(valid)
    hidden["hidden_correct_outputs"] = 2
    assert list(validator.iter_errors(hidden))

    selected = copy.deepcopy(valid)
    selected["public_leaderboard_used_for_selection"] = True
    assert list(validator.iter_errors(selected))

    running = copy.deepcopy(valid)
    running["authoritative_kernel_status"] = "RUNNING"
    assert list(validator.iter_errors(running))

    duplicate_timeout = copy.deepcopy(valid)
    duplicate_timeout["timed_out_task_ids"] = ["00000002", "00000002"]
    assert list(validator.iter_errors(duplicate_timeout))

    print("competition observation schema regression passed")


if __name__ == "__main__":
    main()
