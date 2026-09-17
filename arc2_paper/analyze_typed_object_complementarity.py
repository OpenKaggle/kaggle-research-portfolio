#!/usr/bin/env python3
"""Frozen post-run union audit for typed-object V1 versus the existing V175 family."""

from __future__ import annotations

import csv
import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "paper/manifests/typed_object_family_audit_v1.json"
TYPED_ROWS = ROOT / "artifacts/typed_object_family_audit_v1/per_output.csv"
V175_ROWS = ROOT / "artifacts/exact_rule_loo_training/per_output.csv"
OUTPUT = ROOT / "artifacts/typed_object_family_audit_v1/complementarity_vs_v175.json"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def truth(value: str) -> bool:
    if value not in {"True", "False"}:
        raise ValueError(f"expected canonical boolean, got {value!r}")
    return value == "True"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit_ids = set(manifest["audit"]["task_ids"])
    typed = {
        (row["task_id"], int(row["output_index"])): row
        for row in csv.DictReader(TYPED_ROWS.open(encoding="utf-8"))
    }
    v175 = {
        (row["task_id"], int(row["output_index"])): row
        for row in csv.DictReader(V175_ROWS.open(encoding="utf-8"))
        if row["task_id"] in audit_ids
    }
    if set(typed) != set(v175) or len(typed) != 197:
        raise ValueError("typed-object and V175 rows do not cover the same frozen audit outputs")

    typed_selected = {key for key, row in typed.items() if truth(row["selected"])}
    typed_correct = {key for key in typed_selected if truth(typed[key]["correct"])}
    v175_selected = {
        key for key, row in v175.items() if truth(row["direct_selected"])
    }
    v175_correct = {
        key for key in v175_selected if truth(v175[key]["direct_correct"])
    }
    overlap = typed_correct & v175_correct
    exclusive = typed_correct - v175_correct
    union = typed_correct | v175_correct
    incorrect = typed_selected - typed_correct
    if incorrect:
        raise ValueError("typed-object one-shot receipt and per-output rows disagree")

    report = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "analysis": "typed_object_correspondence_v1 versus frozen V175 direct selection",
        "data_boundary": "implementation-sealed grouped fold 0 exclusions; no rerun",
        "public_leaderboard_used_for_selection": False,
        "tasks": manifest["audit"]["task_count"],
        "outputs": len(typed),
        "typed_object_selected_outputs": len(typed_selected),
        "typed_object_correct_outputs": len(typed_correct),
        "typed_object_incorrect_outputs": len(incorrect),
        "v175_selected_outputs": len(v175_selected),
        "v175_correct_outputs": len(v175_correct),
        "overlap_correct_outputs": len(overlap),
        "typed_object_exclusive_outputs": len(exclusive),
        "union_correct_outputs": len(union),
        "union_gain_over_v175_outputs": len(union) - len(v175_correct),
        "overlap_rows": [
            {
                "task_id": task_id,
                "output_index": output_index,
                "typed_reason": typed[(task_id, output_index)]["reason"],
                "v175_reasons": v175[(task_id, output_index)]["selected_reasons"],
            }
            for task_id, output_index in sorted(overlap)
        ],
        "promotion_gates": {
            "at_least_one_new_family_exclusive": len(exclusive) >= 1,
            "paper_h1_at_least_three_incremental_outputs": len(exclusive) >= 3,
            "passes": len(exclusive) >= 3,
            "decision": "STOP_TYPED_OBJECT_V1_NO_INCREMENTAL_UNION",
        },
        "input_sha256": {
            "paper/manifests/typed_object_family_audit_v1.json": sha256(MANIFEST),
            "artifacts/typed_object_family_audit_v1/per_output.csv": sha256(TYPED_ROWS),
            "artifacts/exact_rule_loo_training/per_output.csv": sha256(V175_ROWS),
        },
        "limitations": [
            "V175 was authored against public corpora, so its 55 selected outputs are retrospective context rather than an unseen baseline.",
            "The typed-object code and one-shot result remain frozen; this post-run join cannot authorize tuning on the audit fold.",
            "The audit is not the private development stage, sealed holdout, public evaluation, or Kaggle test.",
        ],
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**report, "report_sha256": sha256(OUTPUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
