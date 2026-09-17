#!/usr/bin/env python3
"""Regression checks for the historical V3 holdout-integrity finding."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from paper.tools.audit_v3_holdout_integrity import (  # noqa: E402
    DECISION,
    STATUS,
    audit,
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    original_read_text = pathlib.Path.read_text
    original_read_bytes = pathlib.Path.read_bytes

    def guarded_read_text(path: pathlib.Path, *args, **kwargs):
        assert path.name != "arc-agi_training_solutions.json"
        return original_read_text(path, *args, **kwargs)

    def guarded_read_bytes(path: pathlib.Path, *args, **kwargs):
        assert path.name != "arc-agi_training_solutions.json"
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
        PROJECT_ROOT / "paper/results/v3_holdout_integrity_audit_2026-09-09.json"
    )
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))

    assert result == repeated == frozen
    assert result["audit_status"] == STATUS
    assert result["decision"] == DECISION
    assert result["external_actions_performed"] is False
    assert result["holdout_solutions_read_by_this_audit"] is False
    assert result["holdout_task_ids_disclosed"] is False
    assert result["historical_facts"] == {
        "source_audit_task_universe": 1000,
        "source_audit_loaded_all_training_solutions": True,
        "source_audit_selected_tasks": 2,
        "selected_tasks_all_in_development": True,
        "development_preregistration_embeds_source_audit_result": True,
        "holdout_preregistration_pairs_that_development_candidate": True,
    }
    assert result["derived_holdout"] == {
        "tasks": 48,
        "outputs": 49,
        "task_id_set_sha256": (
            "f773c6318e99281d2fb49aed126f7febf297ab5a15059fc3493b40f3ff948718"
        ),
        "disjoint_from_development": True,
        "v176_selected_tasks": 0,
        "v176_behavior_known_before_holdout_run": "always abstains on this slice",
    }
    assert result["provenance"]["audit_tool"]["sha256"] == sha256(
        PROJECT_ROOT / "paper/tools/audit_v3_holdout_integrity.py"
    )
    assert not any(
        "arc-agi_training_solutions.json" in str(value)
        for value in result["provenance"].values()
    )
    print("v3 holdout integrity regression passed")


if __name__ == "__main__":
    main()
