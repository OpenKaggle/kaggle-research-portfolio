#!/usr/bin/env python3
"""Draft 2020-12 checks for normalized stage receipt v1."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator, FormatChecker


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import normalized_receipt  # noqa: E402


SCHEMA_PATH = ROOT / "paper/schemas/stage_receipt_v1.schema.json"
NOTEBOOK_SHA = "b" * 64


def assert_valid(validator: Draft202012Validator, payload: dict) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def assert_invalid(validator: Draft202012Validator, payload: dict) -> None:
    assert list(validator.iter_errors(payload))


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    fixtures = {
        "private_development": normalized_receipt(
            "private_development", "2026-09-09T01:00:00+00:00", NOTEBOOK_SHA
        ),
        "sealed_holdout": normalized_receipt(
            "sealed_holdout", "2026-09-09T02:00:00+00:00", NOTEBOOK_SHA
        ),
        "competition_rerun": normalized_receipt(
            "competition_rerun", "2026-09-09T03:00:00+00:00", NOTEBOOK_SHA
        ),
    }
    for payload in fixtures.values():
        assert_valid(validator, payload)

    fabricated_hidden = copy.deepcopy(fixtures["competition_rerun"])
    fabricated_hidden["metrics"]["method_exact_outputs"] = 8
    assert_invalid(validator, fabricated_hidden)

    fabricated_family = copy.deepcopy(fixtures["competition_rerun"])
    fabricated_family["family_coverage"]["geometry"]["method_solved"] = 1
    assert_invalid(validator, fabricated_family)

    missing_family = copy.deepcopy(fixtures["private_development"])
    del missing_family["family_coverage"]["search"]
    assert_invalid(validator, missing_family)

    score_out_of_range = copy.deepcopy(fixtures["competition_rerun"])
    score_out_of_range["kaggle"]["leaderboard_score"] = 1.01
    assert_invalid(validator, score_out_of_range)

    invalid_timestamp = copy.deepcopy(fixtures["competition_rerun"])
    invalid_timestamp["kaggle"]["score_observed_at"] = "not-a-timestamp"
    assert_invalid(validator, invalid_timestamp)

    unregistered_field = copy.deepcopy(fixtures["sealed_holdout"])
    unregistered_field["manual_override"] = True
    assert_invalid(validator, unregistered_field)

    print("stage receipt schema regression passed")


if __name__ == "__main__":
    main()
