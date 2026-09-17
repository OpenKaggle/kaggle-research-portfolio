#!/usr/bin/env python3
"""Regression checks for the V176 independent-corpus availability audit."""

from __future__ import annotations

import json
import pathlib
import sys


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from paper.tools.audit_v176_corpus_availability import (  # noqa: E402
    DECISION,
    EXPECTED_AGGREGATE,
    EXPECTED_CORPORA,
    STATUS,
    audit,
)


def main() -> None:
    original_read_text = pathlib.Path.read_text
    original_read_bytes = pathlib.Path.read_bytes

    def guarded_read_text(path: pathlib.Path, *args, **kwargs):
        assert "solutions" not in path.name
        return original_read_text(path, *args, **kwargs)

    def guarded_read_bytes(path: pathlib.Path, *args, **kwargs):
        assert "solutions" not in path.name
        return original_read_bytes(path, *args, **kwargs)

    pathlib.Path.read_text = guarded_read_text
    pathlib.Path.read_bytes = guarded_read_bytes
    try:
        result = audit(PROJECT_ROOT)
        repeated = audit(PROJECT_ROOT)
    finally:
        pathlib.Path.read_text = original_read_text
        pathlib.Path.read_bytes = original_read_bytes

    frozen_path = (
        PROJECT_ROOT
        / "paper/results/v176_independent_corpus_availability_audit_2026-09-09.json"
    )
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    assert result == repeated == frozen
    assert result["audit_status"] == STATUS
    assert result["current_decision"] == DECISION
    assert result["authorization_boundary"] == {
        "network_access_used": False,
        "kaggle_query_performed": False,
        "artifact_downloaded": False,
        "external_run_started": False,
        "submission_performed": False,
        "sealed_holdout_opened": False,
    }
    assert EXPECTED_AGGREGATE["tasks"] == 2080
    assert EXPECTED_AGGREGATE["outputs"] == 2563
    assert EXPECTED_CORPORA[-1] == {
        "stem": "arc-agi_concept",
        "tasks": 160,
        "outputs": 480,
    }
    assert all(result["eligibility_requirements"].values())
    print("v176 corpus availability regression passed")


if __name__ == "__main__":
    main()
