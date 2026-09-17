#!/usr/bin/env python3
"""Draft 2020-12 checks for the one-stage authorization receipt."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tools.authorize_stage import AUTHORIZATION_FIELDS  # noqa: E402


SCHEMA = ROOT / "paper/schemas/stage_authorization_v1.schema.json"
HASH = "a" * 64


def fixture() -> dict:
    return {
        "schema_version": 1,
        "candidate_id": "conservative_exact_overlay_v3",
        "stage": "private_development",
        "decision": "AUTHORIZE_ONE_STAGE_RUN",
        "authorized": True,
        "authorized_by_user": True,
        "authorized_at": "2026-09-09T00:40:00+00:00",
        "contract_sha256_before": HASH,
        "notebook": {
            "path": "candidate_notebooks/example/example.ipynb",
            "sha256": HASH,
        },
        "allowed_external_action": (
            "KAGGLE_RUN_PRIVATE_DEVELOPMENT_ONCE_AND_READ_TERMINAL_ARTIFACTS"
        ),
        "one_run_only": True,
        "read_terminal_evidence_after_run": True,
        "public_leaderboard_used_for_selection": False,
        "future_stages_authorized": False,
        "claim_boundary": "One stage only; no future stage is authorized.",
    }


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == AUTHORIZATION_FIELDS
    assert set(schema["properties"]) == AUTHORIZATION_FIELDS
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid = fixture()
    assert not list(validator.iter_errors(valid))

    future = copy.deepcopy(valid)
    future["future_stages_authorized"] = True
    assert list(validator.iter_errors(future))

    multiple = copy.deepcopy(valid)
    multiple["one_run_only"] = False
    assert list(validator.iter_errors(multiple))

    leaderboard_selection = copy.deepcopy(valid)
    leaderboard_selection["public_leaderboard_used_for_selection"] = True
    assert list(validator.iter_errors(leaderboard_selection))

    naive_time = copy.deepcopy(valid)
    naive_time["authorized_at"] = "2026-09-09T00:40:00"
    assert list(validator.iter_errors(naive_time))

    extra = copy.deepcopy(valid)
    extra["submit_without_receipt"] = True
    assert list(validator.iter_errors(extra))

    print("stage authorization schema regression passed")


if __name__ == "__main__":
    main()
