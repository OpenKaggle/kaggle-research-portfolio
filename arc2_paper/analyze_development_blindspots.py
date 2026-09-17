#!/usr/bin/env python3
"""Diagnose the two shared misses from the frozen 48-task development run.

The rules in this file were derived after inspecting development labels.  They
are therefore diagnostic candidates, not held-out evidence and not production
selector inputs.  The corpus audit detaches test solutions until after each
fixed rule has been selected from demonstrations alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Callable


SOURCE_ROOT = Path(__file__).resolve().parent / "public_assets/trm_source"
sys.path.insert(0, str(SOURCE_ROOT))
from blindspot_exact_overlay import (  # noqa: E402
    RULES,
    apply_overlay,
    reconstruct_centered_square_perimeters,
    reconstruct_centered_square_perimeters_with_trace,
    scale_by_distinct_color_count,
)

Grid = list[list[int]]
Rule = Callable[[Grid], Grid | None]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shape(grid: Grid | None) -> list[int] | None:
    return None if grid is None else [len(grid), len(grid[0])]


def _all_training_pairs_match(task: dict[str, Any], rule: Rule) -> bool:
    return all(rule(pair["input"]) == pair["output"] for pair in task["train"])


def audit_source_corpus(
    challenges: dict[str, dict[str, Any]],
    solutions: dict[str, list[Grid]],
    rules: dict[str, Rule],
) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for rule_name, rule in rules.items():
        selected: list[dict[str, Any]] = []
        for task_id, task in sorted(challenges.items()):
            if len(task["train"]) < 2 or not _all_training_pairs_match(task, rule):
                continue
            predictions = [rule(case["input"]) for case in task["test"]]
            targets = solutions[task_id]
            correctness = [prediction == target for prediction, target in zip(predictions, targets, strict=True)]
            selected.append(
                {
                    "task_id": task_id,
                    "test_outputs": len(targets),
                    "correct_outputs": sum(correctness),
                    "all_test_outputs_correct": all(correctness),
                    "prediction_shapes": [shape(prediction) for prediction in predictions],
                }
            )
        report[rule_name] = {
            "selected_tasks": len(selected),
            "selected_outputs": sum(item["test_outputs"] for item in selected),
            "correct_selected_outputs": sum(item["correct_outputs"] for item in selected),
            "incorrect_selected_outputs": sum(item["test_outputs"] - item["correct_outputs"] for item in selected),
            "tasks": selected,
        }
    return report


def _scale_factor(source: Grid, candidate: Grid) -> int | None:
    for factor in range(1, 11):
        expected = []
        for row in source:
            expanded = [value for value in row for _ in range(factor)]
            expected.extend(expanded[:] for _ in range(factor))
        if candidate == expected:
            return factor
    return None


def _hamming(first: Grid, second: Grid) -> int | None:
    if shape(first) != shape(second):
        return None
    return sum(a != b for row_a, row_b in zip(first, second) for a, b in zip(row_a, row_b))


def score_submission(
    submission: dict[str, list[dict[str, Grid]]],
    solutions: dict[str, list[Grid]],
) -> dict[str, Any]:
    hits: set[str] = set()
    attempt_1_hits: set[str] = set()
    attempt_2_incremental_hits: set[str] = set()
    task_hits: dict[str, list[bool]] = {}
    for task_id, targets in solutions.items():
        task_hits[task_id] = []
        for output_index, target in enumerate(targets):
            row = submission[task_id][output_index]
            key = f"{task_id}_{output_index}"
            first = row["attempt_1"] == target
            second = row["attempt_2"] == target
            if first:
                attempt_1_hits.add(key)
            if second and not first:
                attempt_2_incremental_hits.add(key)
            if first or second:
                hits.add(key)
            task_hits[task_id].append(first or second)
    return {
        "hits": hits,
        "solved_outputs": len(hits),
        "total_outputs": sum(len(values) for values in solutions.values()),
        "solved_tasks": sum(all(values) for values in task_hits.values()),
        "total_tasks": len(task_hits),
        "attempt_1_exact_outputs": len(attempt_1_hits),
        "attempt_2_incremental_outputs": len(attempt_2_incremental_hits),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    task_dir = root / "evaluator_only/development_stable_v2/tasks"
    nvarc_path = root / "kaggle_runs/development_stable_v2/nvarc_kgmon.json"
    challenge_path = root / "official/competition_files/arc-agi_training_challenges.json"
    solution_path = root / "official/competition_files/arc-agi_training_solutions.json"
    development_challenge_path = root / "kaggle_runs/development_stable_v2/benchmark_challenges.json"
    development_solution_path = root / "kaggle_runs/development_stable_v2/benchmark_solutions.json"
    development_base_path = root / "kaggle_runs/development_stable_v2/nvarc_kgmon.json"
    output_dir = root / "artifacts/development_blindspots_v1"
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks = {
        task_id: json.loads((task_dir / f"{task_id}.json").read_text(encoding="utf-8"))
        for task_id in ("d4b1c2b1", "4290ef0e")
    }
    nvarc = json.loads(nvarc_path.read_text(encoding="utf-8"))
    challenges = json.loads(challenge_path.read_text(encoding="utf-8"))
    solutions = json.loads(solution_path.read_text(encoding="utf-8"))

    rules: dict[str, Rule] = {
        "scale_by_distinct_color_count": scale_by_distinct_color_count,
        "reconstruct_centered_square_perimeters": reconstruct_centered_square_perimeters,
    }
    corpus_audit = audit_source_corpus(challenges, solutions, rules)

    development_challenges = json.loads(development_challenge_path.read_text(encoding="utf-8"))
    development_base = json.loads(development_base_path.read_text(encoding="utf-8"))
    overlay_variants = {
        "scale_only": ("scale_by_distinct_color_count",),
        "perimeter_only": ("reconstruct_centered_square_perimeters",),
        "combined_v176": tuple(RULES),
    }
    generated_submissions: dict[str, dict[str, Any]] = {}
    generated_receipts: dict[str, dict[str, Any]] = {}
    generated_paths: dict[str, dict[str, Path]] = {}
    for variant, enabled_rules in overlay_variants.items():
        submission, receipt = apply_overlay(
            development_challenges, development_base, enabled_rules
        )
        submission_path = output_dir / f"submission_{variant}.json"
        receipt_path = output_dir / f"selector_receipt_{variant}.json"
        submission_path.write_text(
            json.dumps(submission, separators=(",", ":")), encoding="utf-8"
        )
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        generated_submissions[variant] = submission
        generated_receipts[variant] = receipt
        generated_paths[variant] = {
            "submission": submission_path,
            "receipt": receipt_path,
        }

    # The candidate submissions and selector receipts above are complete before
    # evaluator-only development solutions are loaded for scoring.
    development_solutions = json.loads(
        development_solution_path.read_text(encoding="utf-8")
    )
    base_score = score_submission(development_base, development_solutions)
    variant_scores: dict[str, Any] = {}
    for variant, submission in generated_submissions.items():
        score = score_submission(submission, development_solutions)
        variant_scores[variant] = {
            **{key: value for key, value in score.items() if key != "hits"},
            "gain_outputs": sorted(score["hits"] - base_score["hits"]),
            "harm_outputs": sorted(base_score["hits"] - score["hits"]),
            "changed_attempt_2_outputs": generated_receipts[variant][
                "changed_attempt_2_outputs"
            ],
            "ambiguous_outputs_abstained": generated_receipts[variant][
                "ambiguous_outputs_abstained"
            ],
            "submission_sha256": sha256(generated_paths[variant]["submission"]),
            "selector_receipt_sha256": sha256(generated_paths[variant]["receipt"]),
        }
    development_overlay_ablation = {
        "split": "frozen_public_training_development_48_tasks_50_outputs",
        "post_hoc": True,
        "test_solutions_detached_until_after_candidate_generation": True,
        "base": {key: value for key, value in base_score.items() if key != "hits"},
        "variants": variant_scores,
        "interpretation": (
            "The +1/+1/+2 deltas are diagnostic development fit after inspecting the two misses. "
            "They establish complementarity and implementation behavior, not generalization."
        ),
    }
    ablation_path = output_dir / "development_overlay_ablation.json"
    ablation_path.write_text(
        json.dumps(development_overlay_ablation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    d4_task = tasks["d4b1c2b1"]
    d4_input = d4_task["test"][0]["input"]
    d4_target = d4_task["test"][0]["output"]
    d4_attempts = nvarc["d4b1c2b1"][0]
    frame_task = tasks["4290ef0e"]
    frame_input = frame_task["test"][0]["input"]
    frame_target = frame_task["test"][0]["output"]
    frame_attempts = nvarc["4290ef0e"][0]
    frame_prediction, frame_trace = reconstruct_centered_square_perimeters_with_trace(frame_input)

    report = {
        "status": "diagnostic_only_post_hoc_development_analysis",
        "external_actions_performed": False,
        "sealed_holdout_opened": False,
        "production_selector_modified": False,
        "accuracy_claim_allowed": False,
        "source_corpus_audit_interpretation": (
            "Rules were written after these public-training development labels were inspected; "
            "source-corpus precision measures consistency and false firing only, not unseen-task generalization."
        ),
        "blindspots": {
            "d4b1c2b1_0": {
                "bucket": ["counting", "geometry", "scaling"],
                "rule_hypothesis": "nearest-neighbor scale factor equals the number of distinct input colors",
                "training_pairs": len(d4_task["train"]),
                "training_pairs_exact": sum(
                    scale_by_distinct_color_count(pair["input"]) == pair["output"]
                    for pair in d4_task["train"]
                ),
                "test_palette_size": len({value for row in d4_input for value in row}),
                "target_shape": shape(d4_target),
                "diagnostic_prediction_exact": scale_by_distinct_color_count(d4_input) == d4_target,
                "nvarc": {
                    "attempt_1_shape": shape(d4_attempts["attempt_1"]),
                    "attempt_1_scale_factor": _scale_factor(d4_input, d4_attempts["attempt_1"]),
                    "attempt_2_shape": shape(d4_attempts["attempt_2"]),
                    "attempt_2_scale_factor": _scale_factor(d4_input, d4_attempts["attempt_2"]),
                    "error": "both attempts preserve the macro-grid but infer factors 4 and 3 instead of palette size 5",
                },
                "minimal_counterexample": {
                    "input": [[1, 2]],
                    "expected": [[1, 1, 2, 2], [1, 1, 2, 2]],
                    "paired_control_input": [[1, 1]],
                    "paired_control_expected": [[1, 1]],
                    "purpose": "separates palette-count scaling from a fixed scale tied only to input dimensions",
                },
                "falsifiers": [
                    "any demonstration whose output is not an exact nearest-neighbor expansion",
                    "any demonstration whose inferred row/column scale differs from its palette size",
                    "an inferred output dimension above the ARC 30-cell limit",
                ],
            },
            "4290ef0e_0": {
                "bucket": ["object", "topology", "symmetry", "composition"],
                "rule_hypothesis": (
                    "assign every non-background color to a distinct concentric square radius, "
                    "complete its observed perimeter fragments by two axial reflections, and choose "
                    "the bijection requiring minimum center extrapolation outside the source canvas"
                ),
                "training_pairs": len(frame_task["train"]),
                "training_pairs_exact": sum(
                    reconstruct_centered_square_perimeters(pair["input"]) == pair["output"]
                    for pair in frame_task["train"]
                ),
                "target_shape": shape(frame_target),
                "diagnostic_prediction_exact": frame_prediction == frame_target,
                "trace": frame_trace,
                "nvarc": {
                    "attempt_1_shape": shape(frame_attempts["attempt_1"]),
                    "attempt_2_shape": shape(frame_attempts["attempt_2"]),
                    "attempt_2_hamming_cells": _hamming(frame_attempts["attempt_2"], frame_target),
                    "attempt_2_center": frame_attempts["attempt_2"][5][5],
                    "target_center": frame_target[5][5],
                    "error": (
                        "attempt 2 gets the 11x11 size and bilateral symmetry but treats the isolated "
                        "component of color 6 as a center marker even though color 6 has four cells globally; "
                        "this shifts the inner radius assignment"
                    ),
                },
                "minimal_counterexample": {
                    "same_color_components": {"l_tromino_cells": 3, "isolated_cells": 1, "global_cells": 4},
                    "correct_center_predicate": "a center marker must be a globally singleton color, not merely a singleton component",
                    "expected_effect": "background remains at radius zero; the four cells are completed on a nonzero square perimeter",
                },
                "falsifiers": [
                    "a foreground color cannot be embedded on any candidate Chebyshev-radius perimeter",
                    "radii 1..R do not admit a bijection across ring colors",
                    "minimum outside-center penalty leaves multiple distinct completed outputs",
                    "a demonstration output differs from the centered reflection closure",
                ],
            },
        },
        "source_corpus_audit": {
            "dataset": "official Kaggle ARC-AGI training challenges/solutions (1000 tasks)",
            "tasks": len(challenges),
            "test_solutions_detached_until_after_demo_only_selection": True,
            "rules": corpus_audit,
        },
        "development_overlay_ablation": {
            **development_overlay_ablation,
            "artifact_sha256": sha256(ablation_path),
        },
        "provenance": {
            "development_source_receipt": sha256(root / "evaluator_only/development_stable_v2/SOURCE_RECEIPT.json"),
            "nvarc_submission": sha256(nvarc_path),
            "training_challenges": sha256(challenge_path),
            "training_solutions": sha256(solution_path),
            "development_challenges": sha256(development_challenge_path),
            "development_solutions": sha256(development_solution_path),
            "development_base_submission": sha256(development_base_path),
            "analysis_script": sha256(Path(__file__)),
            "overlay_module": sha256(SOURCE_ROOT / "blindspot_exact_overlay.py"),
        },
        "decision": "keep_isolated_until_preregistered_and_prospectively_tested; do_not_open_sealed_holdout",
    }
    output_path = output_dir / "blindspot_analysis.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "sha256": sha256(output_path), **report["source_corpus_audit"]}, indent=2))


if __name__ == "__main__":
    main()
