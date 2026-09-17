#!/usr/bin/env python3
"""Measure exact-rule coverage and exclusivity against a frozen NVARC anchor."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parent
    exact_path = root / "artifacts" / "exact_rule_loo_development_stable_v2" / "per_output.csv"
    paired_path = root / "kaggle_runs" / "development_stable_v2" / "analysis" / "paired_results.csv"
    output_path = (
        root / "artifacts" / "exact_rule_loo_development_stable_v2"
        / "complementarity_vs_nvarc.json"
    )

    exact_rows = {
        (row["task_id"], int(row["output_index"])): row
        for row in csv.DictReader(exact_path.open(encoding="utf-8"))
    }
    paired_rows = {
        (row["task_id"], int(row["output_index"])): row
        for row in csv.DictReader(paired_path.open(encoding="utf-8"))
    }
    if set(exact_rows) != set(paired_rows) or len(exact_rows) != 50:
        raise ValueError("exact-rule and NVARC rows must cover the same frozen 50 outputs")

    selected = {
        key for key, row in exact_rows.items() if row["direct_selected"].lower() == "true"
    }
    exact_correct = {
        key for key in selected if exact_rows[key]["direct_correct"].lower() == "true"
    }
    anchor_correct = {
        key for key, row in paired_rows.items() if int(row["anchor_pass2"]) == 1
    }
    exclusive = exact_correct - anchor_correct
    overlap = exact_correct & anchor_correct
    oracle = exact_correct | anchor_correct
    missed_by_both = set(exact_rows) - oracle

    family_fields = (
        "shape_family",
        "color_family",
        "component_family",
        "structural_change_axes",
    )
    family_coverage: dict[str, dict[str, dict[str, int]]] = {}
    for field in family_fields:
        rows: dict[str, dict[str, int]] = defaultdict(
            lambda: {"outputs": 0, "selected": 0, "correct": 0, "exclusive": 0}
        )
        for key, paired in paired_rows.items():
            value = paired[field]
            rows[value]["outputs"] += 1
            rows[value]["selected"] += int(key in selected)
            rows[value]["correct"] += int(key in exact_correct)
            rows[value]["exclusive"] += int(key in exclusive)
        family_coverage[field] = dict(sorted(rows.items()))

    reason_counts = Counter()
    for key in selected:
        for reason in filter(None, exact_rows[key]["selected_reasons"].split("|")):
            reason_counts[reason] += 1

    report = {
        "data_boundary": "frozen 48-task public-training development; labels evaluator-only",
        "tasks": len({task_id for task_id, _ in exact_rows}),
        "outputs": len(exact_rows),
        "anchor": "NVARC KGMon pass@2",
        "exact_rule_policy": "one unique grid among rules passing every leave-one-demonstration-out fold",
        "anchor_correct_outputs": len(anchor_correct),
        "exact_rule_selected_outputs": len(selected),
        "exact_rule_correct_selected_outputs": len(exact_correct),
        "exact_rule_direct_precision": len(exact_correct) / len(selected) if selected else None,
        "overlap_correct_outputs": len(overlap),
        "exact_rule_exclusive_outputs": len(exclusive),
        "oracle_correct_outputs": len(oracle),
        "oracle_gain_over_anchor_outputs": len(oracle) - len(anchor_correct),
        "missed_by_both": [
            {"task_id": task_id, "output_index": output_index}
            for task_id, output_index in sorted(missed_by_both)
        ],
        "selected_reason_counts": dict(sorted(reason_counts.items())),
        "family_coverage": family_coverage,
        "promotion_gate": {
            "requires_at_least_one_exclusive_output": True,
            "passes": len(exclusive) >= 1,
            "decision": (
                "KEEP_FOR_SEALED_VALIDATION"
                if exclusive
                else "STOP_EXACT_RULE_FAMILY_NO_COMPLEMENTARITY"
            ),
        },
        "limitations": [
            "The rule library was authored against public corpora; its direct precision here is not an unseen-task generalization estimate.",
            "Only exclusive/oracle gain is used for the solver-family decision.",
            "No sealed-holdout or public-evaluation label was accessed.",
        ],
        "input_sha256": {
            exact_path.relative_to(root).as_posix(): sha256(exact_path),
            paired_path.relative_to(root).as_posix(): sha256(paired_path),
        },
    }
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**report, "report_sha256": sha256(output_path)}, indent=2))


if __name__ == "__main__":
    main()
