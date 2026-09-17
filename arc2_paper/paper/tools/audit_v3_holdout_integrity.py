#!/usr/bin/env python3
"""Audit whether the frozen V3 holdout can support a generalization claim.

The audit never reads the training-solution file.  It reconstructs the second
work-stratified 48-task slice from public challenge inputs, then compares only
task identities with the already-frozen full-corpus V176 audit.  That historical
audit did read all 1,000 training solutions before the holdout preregistration
embedded its result, so the same 48 tasks cannot be called sealed evidence for
the V176 overlay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from typing import Any


SEED = "arc2026-ab-v2-work-stratified"
STATUS = "CONTAMINATED_FOR_V176_GENERALIZATION"
DECISION = "BLOCK_V3_HOLDOUT_PROMOTION_UNTIL_NEW_UNTOUCHED_HOLDOUT"


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(root: pathlib.Path, path: pathlib.Path) -> dict[str, str]:
    resolved = path.resolve()
    return {
        "path": resolved.relative_to(root.resolve()).as_posix(),
        "sha256": digest(resolved),
    }


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cells(grid: Any) -> int:
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
        return 0
    return len(grid) * len(grid[0])


def estimated_work(task: dict[str, Any]) -> tuple[int, int, int, int]:
    train_input = sum(cells(pair["input"]) for pair in task["train"])
    train_output = sum(cells(pair["output"]) for pair in task["train"])
    test_input = sum(cells(case["input"]) for case in task["test"])
    ratios = sorted(
        cells(pair["output"]) / max(1, cells(pair["input"]))
        for pair in task["train"]
    )
    output_ratio = ratios[len(ratios) // 2] if ratios else 1.0
    estimated_test_output = round(test_input * output_ratio)
    token_work = 16 * (train_input + train_output) + 8 * estimated_test_output
    return token_work, estimated_test_output, train_input + train_output, test_input


def derive_holdout_ids(challenges: dict[str, Any]) -> list[str]:
    ordered = sorted(challenges, key=lambda key: (estimated_work(challenges[key]), key))
    quartiles = [
        ordered[index * len(ordered) // 4 : (index + 1) * len(ordered) // 4]
        for index in range(4)
    ]
    selected: list[str] = []
    for quartile_index, quartile_ids in enumerate(quartiles):
        deterministic = sorted(
            quartile_ids,
            key=lambda task_id: hashlib.sha256(
                f"{SEED}:{quartile_index}:{task_id}".encode("utf-8")
            ).digest(),
        )
        selected.extend(deterministic[12:24])
    return selected


def audit(root: pathlib.Path) -> dict[str, Any]:
    root = root.resolve()
    paths = {
        "audit_tool": pathlib.Path(__file__),
        "source_audit": root
        / "artifacts/development_blindspots_v1/blindspot_analysis.json",
        "source_analysis": root / "analyze_development_blindspots.py",
        "development_manifest": root
        / "kaggle_runs/development_stable_v2/benchmark_manifest.json",
        "training_challenges": root
        / "official/competition_files/arc-agi_training_challenges.json",
        "development_preregistration": root
        / "candidate_notebooks/conservative_exact_overlay_v3/preregistration.json",
        "holdout_preregistration": root
        / "candidate_notebooks/conservative_exact_overlay_v3_holdout/preregistration.json",
        "holdout_notebook": root
        / "candidate_notebooks/conservative_exact_overlay_v3_holdout/arc2-conservative-exact-overlay-v3-holdout.ipynb",
        "overlay_module": root / "public_assets/trm_source/blindspot_exact_overlay.py",
    }
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError(f"required {name} file is missing: {path}")

    source_audit = load_json(paths["source_audit"])
    development_manifest = load_json(paths["development_manifest"])
    challenges = load_json(paths["training_challenges"])
    development_preregistration = load_json(paths["development_preregistration"])
    holdout_preregistration = load_json(paths["holdout_preregistration"])
    analysis_source = paths["source_analysis"].read_text(encoding="utf-8")
    holdout_notebook = load_json(paths["holdout_notebook"])
    holdout_notebook_source = "\n".join(
        cell.get("source", "")
        for cell in holdout_notebook.get("cells", [])
        if isinstance(cell, dict) and isinstance(cell.get("source", ""), str)
    )

    if len(challenges) != 1000:
        raise ValueError("training challenge universe is not the expected 1,000 tasks")
    source_corpus = source_audit.get("source_corpus_audit")
    if not isinstance(source_corpus, dict) or source_corpus.get("tasks") != len(challenges):
        raise ValueError("historical source audit does not cover the full task universe")
    provenance = source_audit.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("historical source audit provenance is missing")
    if provenance.get("training_challenges") != digest(paths["training_challenges"]):
        raise ValueError("historical source audit challenge hash has drifted")
    historical_solution_hash = provenance.get("training_solutions")
    if not isinstance(historical_solution_hash, str) or len(historical_solution_hash) != 64:
        raise ValueError("historical training-solution hash is missing")
    for fragment in (
        'solutions = json.loads(solution_path.read_text(encoding="utf-8"))',
        "corpus_audit = audit_source_corpus(challenges, solutions, rules)",
    ):
        if fragment not in analysis_source:
            raise ValueError("historical analysis no longer proves full-solution scoring")

    rules = source_corpus.get("rules")
    if not isinstance(rules, dict) or set(rules) != {
        "scale_by_distinct_color_count",
        "reconstruct_centered_square_perimeters",
    }:
        raise ValueError("historical V176 rule audit is incomplete")
    selected_ids = {
        row["task_id"]
        for rule in rules.values()
        for row in rule.get("tasks", [])
        if isinstance(row, dict) and isinstance(row.get("task_id"), str)
    }
    if len(selected_ids) != 2:
        raise ValueError("historical selected-task count changed")

    manifest_rows = development_manifest.get("tasks")
    if not isinstance(manifest_rows, list):
        raise ValueError("development manifest tasks are missing")
    development_ids = {
        row["task_id"]
        for row in manifest_rows
        if isinstance(row, dict) and isinstance(row.get("task_id"), str)
    }
    if len(development_ids) != 48 or not selected_ids <= development_ids:
        raise ValueError("historical selected tasks are not confined to development")

    holdout_ids = derive_holdout_ids(challenges)
    holdout_set = set(holdout_ids)
    if len(holdout_ids) != 48 or len(holdout_set) != 48:
        raise ValueError("derived holdout is not exactly 48 unique tasks")
    if development_ids & holdout_set:
        raise ValueError("derived holdout overlaps development")
    holdout_outputs = sum(len(challenges[task_id]["test"]) for task_id in holdout_ids)
    if holdout_outputs != 49:
        raise ValueError("derived holdout output scope changed")
    if selected_ids & holdout_set:
        raise ValueError("historical audit unexpectedly selected a holdout task")

    for fragment in (
        f'benchmark_seed = "{SEED}"',
        "deterministic_order[tasks_per_quartile:2 * tasks_per_quartile]",
    ):
        if fragment not in holdout_notebook_source:
            raise ValueError("holdout notebook selection algorithm has drifted")
    safety = development_preregistration.get("source_corpus_safety_control")
    if not isinstance(safety, dict) or safety.get("dataset") != (
        "1000 official public-training tasks"
    ):
        raise ValueError("development preregistration omits the full-corpus audit")
    if holdout_preregistration.get("paired_development_preregistration") != (
        "../conservative_exact_overlay_v3/preregistration.json"
    ):
        raise ValueError("holdout preregistration is not paired to the audited candidate")

    holdout_id_hash = hashlib.sha256(
        "\n".join(sorted(holdout_ids)).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "result_type": "historical_holdout_integrity_audit",
        "candidate_id": "conservative_exact_overlay_v3",
        "audit_status": STATUS,
        "decision": DECISION,
        "external_actions_performed": False,
        "holdout_solutions_read_by_this_audit": False,
        "holdout_task_ids_disclosed": False,
        "historical_facts": {
            "source_audit_task_universe": len(challenges),
            "source_audit_loaded_all_training_solutions": True,
            "source_audit_selected_tasks": len(selected_ids),
            "selected_tasks_all_in_development": True,
            "development_preregistration_embeds_source_audit_result": True,
            "holdout_preregistration_pairs_that_development_candidate": True,
        },
        "derived_holdout": {
            "tasks": len(holdout_ids),
            "outputs": holdout_outputs,
            "task_id_set_sha256": holdout_id_hash,
            "disjoint_from_development": True,
            "v176_selected_tasks": 0,
            "v176_behavior_known_before_holdout_run": "always abstains on this slice",
        },
        "provenance": {
            **{name: binding(root, path) for name, path in paths.items()},
            "historical_training_solutions_sha256": historical_solution_hash,
        },
        "permitted_claims": [
            "execution/runtime evidence for the unchanged parent",
            "format and artifact-integrity evidence",
        ],
        "forbidden_claims": [
            "sealed-holdout evidence for V176 overlay contribution",
            "new-task generalization of the two V176 rules",
            "Progress or Novelty from this 48-task slice",
        ],
        "claim_boundary": (
            "The historical full-corpus solution audit made V176 coverage on the "
            "later paired 48-task slice knowable before its run. The slice remains "
            "unrun, and this audit reads no holdout solutions, but it is not sealed "
            "method-generalization evidence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args()
    print(json.dumps(audit(args.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
