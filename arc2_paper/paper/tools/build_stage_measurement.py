#!/usr/bin/env python3
"""Build evaluator-side measurements from a completed labeled V3 run.

The frozen Kaggle notebook emits raw benchmark artifacts.  This local-only
tool turns those artifacts into the exact measurement object consumed by
``build_stage_receipt.py``.  It never invokes Kaggle, never changes a
submission, and classifies tasks from demonstrations only (never test labels).
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime
import hashlib
import json
import pathlib
import sys
from typing import Any

try:
    from paper.tools.audit_three_stage_pipeline import audit
    from paper.tools.build_stage_receipt import contract_root
except ModuleNotFoundError:  # Direct execution from paper/tools.
    from audit_three_stage_pipeline import audit  # type: ignore
    from build_stage_receipt import contract_root  # type: ignore


LABELED_STAGES = {"private_development", "sealed_holdout"}
ALL_STAGES = {*LABELED_STAGES, "competition_rerun"}
FAMILY_BUCKETS = (
    "geometry",
    "object",
    "color",
    "topology",
    "counting",
    "composition",
    "search",
)
REQUIRED_RUN_FILES = {
    "run_manifest": "run_manifest.json",
    "challenges": "benchmark_challenges.json",
    "solutions": "benchmark_solutions.json",
    "input_manifest": "benchmark_manifest.json",
    "anchor": "nvarc_kgmon.json",
    "submission": "submission.json",
    "report": "ab-benchmark-report.json",
    "finalized_receipt": "analysis/benchmark_receipt.json",
}
FORMAT_GUARDS = {
    "validated",
    "task_keys_exact",
    "output_counts_exact",
    "exactly_two_attempts",
    "rectangular_grids",
    "dimensions_1_to_30",
    "colors_0_to_9",
}
COMPETITION_OBSERVATION_FIELDS = {
    "schema_version",
    "observation_mode",
    "kernel_slug",
    "notebook_version",
    "authoritative_kernel_status",
    "raw_kernel_status",
    "status_verified_at_cst",
    "artifacts_downloaded",
    "submission_id",
    "submission_status",
    "leaderboard_score",
    "score_scope",
    "score_observed_at",
    "started_at_cst",
    "completed_at_cst",
    "wall_seconds",
    "peak_memory_mb",
    "failed_task_ids",
    "timed_out_task_ids",
    "notebook_sha256",
    "submission_sha256",
    "input_manifest_sha256",
    "run_log_sha256",
    "kernel_metadata_sha256",
    "public_leaderboard_used_for_selection",
    "claim_boundary",
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise ValueError(f"{label} fields differ: missing={missing}, extra={extra}")
    return value


def parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def validate_grid(grid: Any, label: str) -> list[list[int]]:
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        raise ValueError(f"{label}: height must be 1..30")
    if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
        raise ValueError(f"{label}: width must be 1..30")
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        raise ValueError(f"{label}: grid must be rectangular")
    if any(
        type(value) is not int or not 0 <= value <= 9
        for row in grid
        for value in row
    ):
        raise ValueError(f"{label}: colors must be integers 0..9")
    return grid


def validate_challenges(challenges: dict[str, Any]) -> None:
    if not challenges:
        raise ValueError("challenge set is empty")
    for task_id, task in challenges.items():
        if (
            not isinstance(task_id, str)
            or len(task_id) != 8
            or any(value not in "0123456789abcdef" for value in task_id)
        ):
            raise ValueError(f"invalid task id: {task_id!r}")
        if not isinstance(task, dict) or set(task) != {"train", "test"}:
            raise ValueError(f"{task_id}: challenge fields must be train/test")
        if not isinstance(task["train"], list) or not task["train"]:
            raise ValueError(f"{task_id}: training demonstrations are missing")
        if not isinstance(task["test"], list) or not task["test"]:
            raise ValueError(f"{task_id}: test inputs are missing")
        for index, pair in enumerate(task["train"]):
            if not isinstance(pair, dict) or set(pair) != {"input", "output"}:
                raise ValueError(f"{task_id}:train:{index}: invalid pair")
            validate_grid(pair["input"], f"{task_id}:train:{index}:input")
            validate_grid(pair["output"], f"{task_id}:train:{index}:output")
        for index, pair in enumerate(task["test"]):
            if not isinstance(pair, dict) or set(pair) != {"input"}:
                raise ValueError(
                    f"{task_id}:test:{index}: classifier input must not contain labels"
                )
            validate_grid(pair["input"], f"{task_id}:test:{index}:input")


def validate_solutions(
    challenges: dict[str, Any], solutions: dict[str, Any]
) -> int:
    if set(solutions) != set(challenges):
        raise ValueError("solution task IDs differ from challenge task IDs")
    outputs = 0
    for task_id, task in challenges.items():
        rows = solutions[task_id]
        if not isinstance(rows, list) or len(rows) != len(task["test"]):
            raise ValueError(f"{task_id}: solution output count mismatch")
        for index, grid in enumerate(rows):
            validate_grid(grid, f"{task_id}:solution:{index}")
            outputs += 1
    return outputs


def validate_submission(
    challenges: dict[str, Any], submission: dict[str, Any], label: str
) -> dict[str, bool]:
    if set(submission) != set(challenges):
        raise ValueError(f"{label}: task keys differ from challenge")
    for task_id, task in challenges.items():
        rows = submission[task_id]
        if not isinstance(rows, list) or len(rows) != len(task["test"]):
            raise ValueError(f"{label}:{task_id}: output count mismatch")
        for index, attempts in enumerate(rows):
            if not isinstance(attempts, dict) or set(attempts) != {
                "attempt_1",
                "attempt_2",
            }:
                raise ValueError(f"{label}:{task_id}:{index}: attempt keys invalid")
            for attempt, grid in attempts.items():
                validate_grid(grid, f"{label}:{task_id}:{index}:{attempt}")
    return {guard: True for guard in sorted(FORMAT_GUARDS)}


def background(grid: list[list[int]]) -> int:
    counts = Counter(value for row in grid for value in row)
    return min(counts, key=lambda value: (-counts[value], value))


def component_count(grid: list[list[int]], connectivity: int = 4) -> int:
    height, width = len(grid), len(grid[0])
    bg = background(grid)
    remaining = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if grid[row][col] != bg
    }
    offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        offsets += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    count = 0
    while remaining:
        count += 1
        queue = deque([remaining.pop()])
        while queue:
            row, col = queue.popleft()
            for drow, dcol in offsets:
                neighbor = (row + drow, col + dcol)
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    queue.append(neighbor)
    return count


def occupied_mask(grid: list[list[int]]) -> tuple[tuple[bool, ...], ...]:
    bg = background(grid)
    return tuple(tuple(value != bg for value in row) for row in grid)


def contains_subgrid(big: list[list[int]], small: list[list[int]]) -> bool:
    big_h, big_w = len(big), len(big[0])
    small_h, small_w = len(small), len(small[0])
    if small_h > big_h or small_w > big_w:
        return False
    return any(
        all(
            big[top + row][left : left + small_w] == small[row]
            for row in range(small_h)
        )
        for top in range(big_h - small_h + 1)
        for left in range(big_w - small_w + 1)
    )


def has_separator(grid: list[list[int]]) -> bool:
    height, width = len(grid), len(grid[0])
    row_bars = any(len(set(row)) == 1 for row in grid[1:-1])
    col_bars = any(
        len({grid[row][col] for row in range(height)}) == 1
        for col in range(1, width - 1)
    )
    return row_bars or col_bars


def is_count_encoded(
    input_grid: list[list[int]], output_grid: list[list[int]]
) -> bool:
    out_h, out_w = len(output_grid), len(output_grid[0])
    out_area = out_h * out_w
    if out_area > 30:
        return False
    bg = background(input_grid)
    counts = {
        component_count(input_grid, 4),
        component_count(input_grid, 8),
        len({value for row in input_grid for value in row if value != bg}),
    }
    counts.discard(0)
    return bool({out_h, out_w, out_area} & counts)


def primary_family(task: dict[str, Any]) -> str:
    """Assign one demonstration-only primary bucket with frozen precedence."""

    pairs = [(pair["input"], pair["output"]) for pair in task["train"]]
    if all(is_count_encoded(source, target) for source, target in pairs):
        return "counting"

    same_shape = all(
        (len(source), len(source[0])) == (len(target), len(target[0]))
        for source, target in pairs
    )
    if same_shape and all(
        occupied_mask(source) == occupied_mask(target) for source, target in pairs
    ) and any(source != target for source, target in pairs):
        return "color"

    if all(
        len(target) * len(target[0]) < len(source) * len(source[0])
        and contains_subgrid(source, target)
        for source, target in pairs
    ):
        return "object"

    if all(has_separator(source) for source, _ in pairs) or all(
        len(target) * len(target[0]) > len(source) * len(source[0])
        for source, target in pairs
    ):
        return "composition"

    if not same_shape:
        return "geometry"

    if any(
        component_count(source, 4) != component_count(target, 4)
        for source, target in pairs
    ):
        return "topology"

    return "search"


def relative_path(root: pathlib.Path, path: pathlib.Path, label: str) -> str:
    path = path.resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError(f"{label} must be inside the project root") from error


def verify_finalized_artifacts(run_dir: pathlib.Path, receipt: dict[str, Any]) -> None:
    artifacts = receipt.get("artifact_files")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("finalized receipt has no artifact_files manifest")
    for raw, record in artifacts.items():
        relative = pathlib.PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe finalized artifact path: {raw!r}")
        path = (run_dir / pathlib.Path(*relative.parts)).resolve()
        try:
            path.relative_to(run_dir)
        except ValueError as error:
            raise ValueError(f"finalized artifact escapes run directory: {raw!r}") from error
        if not path.is_file() or not isinstance(record, dict):
            raise ValueError(f"finalized artifact is missing: {raw!r}")
        if record.get("bytes") != path.stat().st_size or record.get("sha256") != digest(path):
            raise ValueError(f"finalized artifact drifted: {raw!r}")


def inspect_labeled_run(
    run_dir: pathlib.Path,
    stage: str,
    expected_tasks: int,
    expected_outputs: int,
    expected_method_policy: str = "agreement_exact_v176",
) -> dict[str, Any]:
    """Inspect raw artifacts without consulting or mutating the pipeline contract."""

    if stage not in LABELED_STAGES:
        raise ValueError(f"unsupported labeled stage: {stage!r}")
    run_dir = run_dir.resolve()
    paths = {
        name: run_dir / relative for name, relative in REQUIRED_RUN_FILES.items()
    }
    payloads = {name: load_object(path, name) for name, path in paths.items()}
    run_manifest = payloads["run_manifest"]
    challenges = payloads["challenges"]
    solutions = payloads["solutions"]
    input_manifest = payloads["input_manifest"]
    anchor = payloads["anchor"]
    method = payloads["submission"]
    report = payloads["report"]
    finalized = payloads["finalized_receipt"]

    if run_manifest.get("status") != "COMPLETE":
        raise ValueError("run manifest is not authoritatively COMPLETE")
    if finalized.get("authoritative_kernel_status") != "COMPLETE":
        raise ValueError("finalized receipt is not authoritatively COMPLETE")
    validate_challenges(challenges)
    outputs = validate_solutions(challenges, solutions)
    format_guards = validate_submission(challenges, method, "submission")
    validate_submission(challenges, anchor, "anchor")
    if len(challenges) != expected_tasks or outputs != expected_outputs:
        raise ValueError(
            "run scope differs from the stage contract: "
            f"tasks={len(challenges)}/{expected_tasks}, outputs={outputs}/{expected_outputs}"
        )

    manifest_rows = input_manifest.get("tasks")
    if not isinstance(manifest_rows, list) or {
        row.get("task_id") for row in manifest_rows if isinstance(row, dict)
    } != set(challenges):
        raise ValueError("input manifest task IDs differ from challenge task IDs")
    if len(manifest_rows) != len(challenges):
        raise ValueError("input manifest contains duplicate or invalid task rows")

    policy_scores = report.get("policy_scores")
    if not isinstance(policy_scores, dict) or expected_method_policy not in policy_scores:
        raise ValueError(
            f"A/B report is missing frozen method policy {expected_method_policy!r}"
        )
    if "kgmon" not in policy_scores:
        raise ValueError("A/B report is missing the frozen kgmon anchor")

    failed_ids_raw = finalized.get("nvarc", {}).get("failed_tasks")
    timed_out_raw = finalized.get("nvarc", {}).get("timed_out_tasks")
    if not isinstance(failed_ids_raw, list) or not all(
        isinstance(value, str) for value in failed_ids_raw
    ):
        raise ValueError("finalized failed-task IDs are invalid")
    if not isinstance(timed_out_raw, list) or not all(
        isinstance(value, str) for value in timed_out_raw
    ):
        raise ValueError("finalized timeout IDs are invalid")
    failed_ids = set(failed_ids_raw)
    if not failed_ids <= set(challenges) or not set(timed_out_raw) <= set(challenges):
        raise ValueError("finalized failure IDs are outside the benchmark")

    family_coverage = {
        bucket: {
            "correctness_available": True,
            "tasks": 0,
            "method_solved": 0,
            "anchor_solved": 0,
            "delta": 0,
            "failed_tasks": 0,
        }
        for bucket in FAMILY_BUCKETS
    }
    method_exact = 0
    anchor_exact = 0
    attempt_1_exact = 0
    attempt_2_incremental = 0
    attempt_1_changed = 0
    per_task: dict[str, dict[str, Any]] = {}
    for task_id, task in challenges.items():
        family = primary_family(task)
        method_hits: list[bool] = []
        anchor_hits: list[bool] = []
        for output_index, expected in enumerate(solutions[task_id]):
            method_row = method[task_id][output_index]
            anchor_row = anchor[task_id][output_index]
            method_a1 = method_row["attempt_1"] == expected
            method_a2 = method_row["attempt_2"] == expected
            anchor_hit = expected in (
                anchor_row["attempt_1"],
                anchor_row["attempt_2"],
            )
            method_hit = method_a1 or method_a2
            method_exact += int(method_hit)
            anchor_exact += int(anchor_hit)
            attempt_1_exact += int(method_a1)
            attempt_2_incremental += int(not method_a1 and method_a2)
            attempt_1_changed += int(
                method_row["attempt_1"] != anchor_row["attempt_1"]
            )
            method_hits.append(method_hit)
            anchor_hits.append(anchor_hit)
        row = family_coverage[family]
        row["tasks"] += 1
        row["method_solved"] += int(all(method_hits))
        row["anchor_solved"] += int(all(anchor_hits))
        row["failed_tasks"] += int(task_id in failed_ids)
        per_task[task_id] = {
            "family": family,
            "outputs": len(method_hits),
            "method_solved": all(method_hits),
            "anchor_solved": all(anchor_hits),
            "runtime_failed": task_id in failed_ids,
        }
    for row in family_coverage.values():
        row["delta"] = row["method_solved"] - row["anchor_solved"]

    direct_scores = {
        "method": method_exact,
        "anchor": anchor_exact,
    }
    report_scores = {
        "method": policy_scores[expected_method_policy].get("solved_outputs"),
        "anchor": policy_scores["kgmon"].get("solved_outputs"),
    }
    finalized_scores = {
        "method": finalized.get("selection_policy", {}).get("method_solved_outputs"),
        "anchor": finalized.get("selection_policy", {}).get("anchor_solved_outputs"),
    }
    if report_scores != direct_scores or finalized_scores != direct_scores:
        raise ValueError(
            "direct score disagrees with report/finalized receipt: "
            f"direct={direct_scores}, report={report_scores}, finalized={finalized_scores}"
        )
    if attempt_1_exact + attempt_2_incremental != method_exact:
        raise ValueError("attempt score decomposition is inconsistent")

    started_raw = run_manifest.get("started_at_cst")
    completed_raw = finalized.get("completed_at_cst")
    started = parse_timestamp(started_raw, "started_at_cst")
    completed = parse_timestamp(completed_raw, "completed_at_cst")
    if completed <= started:
        raise ValueError("completed timestamp does not follow started timestamp")
    wall = finalized.get("kernel_wall_upper_bound_seconds")
    peak = finalized.get("peak_memory_mb")
    if not isinstance(wall, (int, float)) or wall <= 0:
        raise ValueError("finalized wall time is invalid")
    if not isinstance(peak, (int, float)) or peak <= 0:
        raise ValueError("finalized peak memory is missing or invalid")
    if abs(float(wall) - (completed - started).total_seconds()) > 1e-9:
        raise ValueError("finalized wall time disagrees with run timestamps")

    hard_gates = finalized.get("hard_gates")
    if not isinstance(hard_gates, dict):
        raise ValueError("finalized hard gates are missing")
    unfinished = finalized.get("nvarc", {}).get("unfinished_tasks")
    incomplete = finalized.get("nvarc", {}).get("incomplete_decode_tasks")
    trm = finalized.get("trm")
    if not isinstance(unfinished, list) or not isinstance(incomplete, list):
        raise ValueError("finalized completion diagnostics are missing")
    if not isinstance(trm, dict) or type(trm.get("available")) is not bool:
        raise ValueError("finalized TRM availability is missing")
    derived_hard_gates = {
        "full_coverage": not unfinished,
        "zero_timeouts": not timed_out_raw,
        "all_decodes_complete": not incomplete,
        "all_submission_schemas_valid": True,
        "within_six_hour_cap": float(wall) <= 6 * 3600,
        "trm_available": trm["available"],
        "method_gain_at_least_one_output": method_exact - anchor_exact >= 1,
        "attempt_1_unchanged": attempt_1_changed == 0,
    }
    for key, expected in derived_hard_gates.items():
        if hard_gates.get(key) is not expected:
            raise ValueError(f"finalized hard gate disagrees with source evidence: {key}")
    operational = all(
        derived_hard_gates[key]
        for key in (
            "full_coverage",
            "zero_timeouts",
            "all_decodes_complete",
            "all_submission_schemas_valid",
            "within_six_hour_cap",
            "trm_available",
            "attempt_1_unchanged",
        )
    )
    non_degradation = method_exact >= anchor_exact
    if stage == "private_development":
        all_passed = operational and derived_hard_gates[
            "method_gain_at_least_one_output"
        ]
        gates = {"all_passed": all_passed, "promote_to_holdout": all_passed}
    else:
        all_passed = operational and non_degradation
        gates = {
            "all_passed": all_passed,
            "non_degradation_vs_anchor": non_degradation,
        }

    verify_finalized_artifacts(run_dir, finalized)
    return {
        "started_at": started_raw,
        "completed_at": completed_raw,
        "metrics": {
            "tasks": len(challenges),
            "outputs": outputs,
            "local_labels_available": True,
            "method_exact_outputs": method_exact,
            "anchor_exact_outputs": anchor_exact,
            "attempt_1_exact_outputs": attempt_1_exact,
            "attempt_2_incremental_outputs": attempt_2_incremental,
            "method_accuracy": method_exact / outputs,
            "anchor_accuracy": anchor_exact / outputs,
            "delta_vs_anchor": (method_exact - anchor_exact) / outputs,
        },
        "family_coverage": family_coverage,
        "runtime": {
            "wall_seconds": wall,
            "peak_memory_mb": peak,
            "failed_tasks": len(failed_ids),
            "failure_rate": len(failed_ids) / len(challenges),
            "timed_out_task_ids": sorted(timed_out_raw),
        },
        "submission_format": format_guards,
        "gates": gates,
        "task_family_assignments": per_task,
        "source_paths": paths,
        "source_sha256": {name: digest(path) for name, path in paths.items()},
        "notebook_sha256": run_manifest.get("notebook_sha256"),
        "method_policy": expected_method_policy,
    }


def frozen_builder(
    root: pathlib.Path, contract: dict[str, Any]
) -> tuple[pathlib.Path, dict[str, Any]]:
    binding = contract.get("stage_measurement_builder")
    if not isinstance(binding, dict):
        raise ValueError("contract measurement-builder binding is missing")
    path = (root / str(binding.get("path"))).resolve()
    if (
        not path.is_file()
        or digest(path) != binding.get("sha256")
        or digest(pathlib.Path(__file__).resolve()) != binding.get("sha256")
    ):
        raise ValueError("running measurement builder differs from the frozen binding")
    return path, binding


def project_input(root: pathlib.Path, raw: pathlib.Path, label: str) -> pathlib.Path:
    path = raw.resolve()
    relative_path(root, path, label)
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path


def validate_task_ids(values: Any, known: set[str], label: str) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"{label} must be a list of task IDs")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} contains duplicates")
    if any(
        len(value) != 8 or any(char not in "0123456789abcdef" for char in value)
        for value in values
    ):
        raise ValueError(f"{label} contains an invalid task ID")
    if not set(values) <= known:
        raise ValueError(f"{label} contains a task outside the challenge")
    return sorted(values)


def inspect_competition_run(
    challenge_path: pathlib.Path,
    submission_path: pathlib.Path,
    input_manifest_path: pathlib.Path,
    kernel_metadata_path: pathlib.Path,
    run_log_path: pathlib.Path,
    observation_path: pathlib.Path,
    notebook_path: pathlib.Path,
    expected_tasks: int,
    expected_outputs: int,
) -> dict[str, Any]:
    """Build hidden-label-safe operational evidence from captured run files."""

    challenges = load_object(challenge_path, "competition challenge")
    validate_challenges(challenges)
    outputs = sum(len(task["test"]) for task in challenges.values())
    if len(challenges) != expected_tasks or outputs != expected_outputs:
        raise ValueError(
            "competition scope differs from the stage contract: "
            f"tasks={len(challenges)}/{expected_tasks}, outputs={outputs}/{expected_outputs}"
        )
    submission = load_object(submission_path, "competition submission")
    format_guards = validate_submission(challenges, submission, "submission")
    metadata = load_object(kernel_metadata_path, "kernel metadata")
    observation = exact_keys(
        load_object(observation_path, "competition observation"),
        COMPETITION_OBSERVATION_FIELDS,
        "competition observation",
    )

    if observation.get("schema_version") != 1:
        raise ValueError("competition observation schema_version must be 1")
    if observation.get("observation_mode") != "READ_ONLY_KAGGLE_SUBMISSION_RECEIPT":
        raise ValueError("competition observation mode is invalid")
    if observation.get("authoritative_kernel_status") != "COMPLETE":
        raise ValueError("competition kernel is not authoritatively COMPLETE")
    raw_status = observation.get("raw_kernel_status")
    if not isinstance(raw_status, str) or "complete" not in raw_status.lower():
        raise ValueError("raw kernel status does not contain COMPLETE")
    if observation.get("artifacts_downloaded") is not True:
        raise ValueError("competition artifacts must be downloaded before measurement")
    if observation.get("submission_status") != "complete":
        raise ValueError("Kaggle submission is not complete")
    submission_id = observation.get("submission_id")
    if not isinstance(submission_id, (str, int)) or not str(submission_id).strip():
        raise ValueError("Kaggle submission ID is missing")
    score = observation.get("leaderboard_score")
    if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
        raise ValueError("Kaggle leaderboard score is invalid")
    if observation.get("score_scope") not in {
        "public_leaderboard",
        "private_leaderboard",
        "final",
    }:
        raise ValueError("Kaggle score scope is invalid")
    if type(observation.get("notebook_version")) is not int or observation[
        "notebook_version"
    ] < 1:
        raise ValueError("Kaggle notebook version is invalid")
    kernel_slug = observation.get("kernel_slug")
    if not isinstance(kernel_slug, str) or not kernel_slug.strip():
        raise ValueError("Kaggle kernel slug is missing")
    if metadata.get("id") != kernel_slug:
        raise ValueError("kernel metadata ID differs from the observed kernel slug")
    if metadata.get("code_file") != notebook_path.name:
        raise ValueError("kernel metadata code_file differs from the frozen notebook")
    if metadata.get("enable_internet") is not False:
        raise ValueError("competition notebook must have internet disabled")
    if metadata.get("enable_gpu") is not True:
        raise ValueError("competition notebook must have GPU enabled")
    if observation.get("public_leaderboard_used_for_selection") is not False:
        raise ValueError("leaderboard-driven policy selection is forbidden")
    claim = observation.get("claim_boundary")
    if not isinstance(claim, str) or not claim.strip():
        raise ValueError("competition observation claim boundary is missing")

    started_raw = observation.get("started_at_cst")
    completed_raw = observation.get("completed_at_cst")
    verified_raw = observation.get("status_verified_at_cst")
    score_raw = observation.get("score_observed_at")
    started = parse_timestamp(started_raw, "started_at_cst")
    completed = parse_timestamp(completed_raw, "completed_at_cst")
    verified = parse_timestamp(verified_raw, "status_verified_at_cst")
    score_observed = parse_timestamp(score_raw, "score_observed_at")
    if not started < completed <= verified or score_observed < completed:
        raise ValueError("competition observation timestamps are out of order")
    wall = observation.get("wall_seconds")
    peak = observation.get("peak_memory_mb")
    if not isinstance(wall, (int, float)) or wall <= 0:
        raise ValueError("competition wall time is invalid")
    if abs(float(wall) - (completed - started).total_seconds()) > 1e-9:
        raise ValueError("competition wall time disagrees with timestamps")
    if not isinstance(peak, (int, float)) or peak <= 0:
        raise ValueError("competition peak memory is missing or invalid")

    known_ids = set(challenges)
    failed_ids = validate_task_ids(
        observation.get("failed_task_ids"), known_ids, "failed_task_ids"
    )
    timed_out_ids = validate_task_ids(
        observation.get("timed_out_task_ids"), known_ids, "timed_out_task_ids"
    )
    if not set(timed_out_ids) <= set(failed_ids):
        raise ValueError("timed-out tasks must be included in failed tasks")

    source_paths = {
        "challenge": challenge_path,
        "submission": submission_path,
        "input_manifest": input_manifest_path,
        "kernel_metadata": kernel_metadata_path,
        "run_log": run_log_path,
        "submission_receipt": observation_path,
        "notebook": notebook_path,
    }
    expected_hash_fields = {
        "notebook": "notebook_sha256",
        "submission": "submission_sha256",
        "input_manifest": "input_manifest_sha256",
        "run_log": "run_log_sha256",
        "kernel_metadata": "kernel_metadata_sha256",
    }
    for name, path in source_paths.items():
        if not path.is_file():
            raise ValueError(f"competition source is missing: {name}")
        hash_field = expected_hash_fields.get(name)
        if hash_field is not None and observation.get(hash_field) != digest(path):
            raise ValueError(f"competition source hash mismatch: {name}")

    family_coverage = {
        bucket: {
            "correctness_available": False,
            "tasks": 0,
            "method_solved": None,
            "anchor_solved": None,
            "delta": None,
            "failed_tasks": 0,
        }
        for bucket in FAMILY_BUCKETS
    }
    assignments: dict[str, dict[str, Any]] = {}
    for task_id, task in challenges.items():
        family = primary_family(task)
        family_coverage[family]["tasks"] += 1
        family_coverage[family]["failed_tasks"] += int(task_id in failed_ids)
        assignments[task_id] = {
            "family": family,
            "outputs": len(task["test"]),
            "runtime_failed": task_id in failed_ids,
        }

    metrics = {
        "tasks": len(challenges),
        "outputs": outputs,
        "local_labels_available": False,
        "method_exact_outputs": None,
        "anchor_exact_outputs": None,
        "attempt_1_exact_outputs": None,
        "attempt_2_incremental_outputs": None,
        "method_accuracy": None,
        "anchor_accuracy": None,
        "delta_vs_anchor": None,
    }
    return {
        "started_at": started_raw,
        "completed_at": completed_raw,
        "metrics": metrics,
        "family_coverage": family_coverage,
        "runtime": {
            "wall_seconds": wall,
            "peak_memory_mb": peak,
            "failed_tasks": len(failed_ids),
            "failure_rate": len(failed_ids) / len(challenges),
            "timed_out_task_ids": timed_out_ids,
        },
        "submission_format": format_guards,
        "gates": {"all_passed": float(wall) <= 11.5 * 3600},
        "kaggle": {
            "submission_id": submission_id,
            "leaderboard_score": score,
            "submission_status": "complete",
            "score_scope": observation["score_scope"],
            "notebook_version": observation["notebook_version"],
            "kernel_slug": kernel_slug,
            "score_observed_at": score_raw,
            "submission_receipt_path": observation_path,
        },
        "task_family_assignments": assignments,
        "source_paths": source_paths,
        "source_sha256": {name: digest(path) for name, path in source_paths.items()},
    }


def build_measurement(
    contract_path: pathlib.Path,
    stage: str,
    run_dir: pathlib.Path,
    experiment_id: str,
    artifact_manifest_output: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = contract_path.resolve()
    pipeline = audit(contract_path)
    if not pipeline["passes"]:
        raise ValueError(
            "pipeline contract does not pass before measurement construction: "
            + json.dumps(pipeline["violations"], sort_keys=True)
        )
    if stage not in LABELED_STAGES:
        raise ValueError(f"unsupported stage: {stage!r}")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("experiment_id must be non-empty")
    contract = load_object(contract_path, "contract")
    stage_contract = contract.get("stages", {}).get(stage)
    if not isinstance(stage_contract, dict) or stage_contract.get("state") != "RUNNING":
        raise ValueError(f"{stage} must be RUNNING before measurement construction")
    root = contract_root(contract_path, contract)
    notebook_binding = stage_contract.get("notebook")
    if not isinstance(notebook_binding, dict):
        raise ValueError("stage notebook binding is missing")
    notebook_path = (root / str(notebook_binding.get("path"))).resolve()
    if not notebook_path.is_file() or digest(notebook_path) != notebook_binding.get("sha256"):
        raise ValueError("frozen stage notebook is missing or has drifted")

    inspected = inspect_labeled_run(
        run_dir,
        stage,
        int(stage_contract["expected_tasks"]),
        int(stage_contract["expected_outputs"]),
    )
    if inspected["notebook_sha256"] != notebook_binding["sha256"]:
        raise ValueError("run manifest notebook hash differs from frozen stage notebook")
    artifact_manifest_output = artifact_manifest_output.resolve()
    artifact_relative = relative_path(
        root, artifact_manifest_output, "artifact manifest output"
    )
    source_paths = {
        name: relative_path(root, path, f"source {name}")
        for name, path in inspected["source_paths"].items()
    }
    builder_path, _ = frozen_builder(root, contract)
    manifest = {
        "schema_version": 1,
        "artifact_status": "completed_labeled_stage_measurement_sources",
        "stage": stage,
        "experiment_id": experiment_id,
        "contract": {
            "path": relative_path(root, contract_path, "contract"),
            "sha256_at_measurement": digest(contract_path),
        },
        "measurement_builder": {
            "path": relative_path(root, builder_path, "measurement builder"),
            "sha256": digest(builder_path),
        },
        "family_classifier": {
            "version": "demonstration_primary_family_v1",
            "uses_test_outputs": False,
            "precedence": [
                "counting",
                "color",
                "object",
                "composition",
                "geometry",
                "topology",
            ],
            "fallback": "search",
            "task_assignments": inspected["task_family_assignments"],
        },
        "method_policy": inspected["method_policy"],
        "source_paths": source_paths,
        "source_sha256": inspected["source_sha256"],
        "claim_boundary": (
            "This manifest binds evaluator-side measurement inputs. Family labels "
            "are deterministic operational buckets from demonstrations, not ground-truth "
            "ARC concept annotations and not selector features."
        ),
    }
    measurement = {
        "experiment_id": experiment_id,
        "started_at": inspected["started_at"],
        "completed_at": inspected["completed_at"],
        "metrics": inspected["metrics"],
        "family_coverage": inspected["family_coverage"],
        "runtime": inspected["runtime"],
        "submission_format": inspected["submission_format"],
        "gates": inspected["gates"],
        "artifact_paths": {
            "notebook": relative_path(root, notebook_path, "notebook"),
            "input_manifest": source_paths["input_manifest"],
            "submission": source_paths["submission"],
            "artifact_manifest": artifact_relative,
        },
    }
    return measurement, manifest


def build_competition_measurement(
    contract_path: pathlib.Path,
    experiment_id: str,
    challenge_path: pathlib.Path,
    submission_path: pathlib.Path,
    input_manifest_path: pathlib.Path,
    kernel_metadata_path: pathlib.Path,
    run_log_path: pathlib.Path,
    observation_path: pathlib.Path,
    artifact_manifest_output: pathlib.Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = contract_path.resolve()
    pipeline = audit(contract_path)
    if not pipeline["passes"]:
        raise ValueError(
            "pipeline contract does not pass before measurement construction: "
            + json.dumps(pipeline["violations"], sort_keys=True)
        )
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ValueError("experiment_id must be non-empty")
    contract = load_object(contract_path, "contract")
    stage = "competition_rerun"
    stage_contract = contract.get("stages", {}).get(stage)
    if not isinstance(stage_contract, dict) or stage_contract.get("state") != "RUNNING":
        raise ValueError("competition_rerun must be RUNNING before measurement construction")
    root = contract_root(contract_path, contract)
    notebook_binding = stage_contract.get("notebook")
    if not isinstance(notebook_binding, dict):
        raise ValueError("competition stage notebook binding is missing")
    notebook_path = project_input(
        root, root / str(notebook_binding.get("path")), "competition notebook"
    )
    if digest(notebook_path) != notebook_binding.get("sha256"):
        raise ValueError("frozen competition notebook has drifted")
    inputs = {
        "challenge": challenge_path,
        "submission": submission_path,
        "input_manifest": input_manifest_path,
        "kernel_metadata": kernel_metadata_path,
        "run_log": run_log_path,
        "submission_receipt": observation_path,
    }
    inputs = {
        name: project_input(root, path, name) for name, path in inputs.items()
    }
    inspected = inspect_competition_run(
        inputs["challenge"],
        inputs["submission"],
        inputs["input_manifest"],
        inputs["kernel_metadata"],
        inputs["run_log"],
        inputs["submission_receipt"],
        notebook_path,
        int(stage_contract["expected_tasks"]),
        int(stage_contract["expected_outputs"]),
    )
    artifact_manifest_output = artifact_manifest_output.resolve()
    artifact_relative = relative_path(
        root, artifact_manifest_output, "artifact manifest output"
    )
    source_paths = {
        name: relative_path(root, path, f"source {name}")
        for name, path in inspected["source_paths"].items()
    }
    builder_path, _ = frozen_builder(root, contract)
    observation_schema_binding = contract.get("competition_observation_schema")
    if not isinstance(observation_schema_binding, dict):
        raise ValueError("competition observation-schema binding is missing")
    observation_schema_path = project_input(
        root,
        root / str(observation_schema_binding.get("path")),
        "competition observation schema",
    )
    if digest(observation_schema_path) != observation_schema_binding.get("sha256"):
        raise ValueError("competition observation schema has drifted")
    manifest = {
        "schema_version": 1,
        "artifact_status": "completed_competition_stage_measurement_sources",
        "stage": stage,
        "experiment_id": experiment_id,
        "contract": {
            "path": relative_path(root, contract_path, "contract"),
            "sha256_at_measurement": digest(contract_path),
        },
        "measurement_builder": {
            "path": relative_path(root, builder_path, "measurement builder"),
            "sha256": digest(builder_path),
        },
        "competition_observation_schema": {
            "path": relative_path(
                root, observation_schema_path, "competition observation schema"
            ),
            "sha256": digest(observation_schema_path),
        },
        "family_classifier": {
            "version": "demonstration_primary_family_v1",
            "uses_test_outputs": False,
            "correctness_available": False,
            "precedence": [
                "counting",
                "color",
                "object",
                "composition",
                "geometry",
                "topology",
            ],
            "fallback": "search",
            "task_assignments": inspected["task_family_assignments"],
        },
        "source_paths": source_paths,
        "source_sha256": inspected["source_sha256"],
        "claim_boundary": (
            "Hidden competition labels are unavailable. This manifest binds only "
            "operational coverage/failure evidence, submission format, runtime, "
            "artifact identity, and the Kaggle-returned aggregate score."
        ),
    }
    kaggle = dict(inspected["kaggle"])
    kaggle["submission_receipt_path"] = source_paths["submission_receipt"]
    measurement = {
        "experiment_id": experiment_id,
        "started_at": inspected["started_at"],
        "completed_at": inspected["completed_at"],
        "metrics": inspected["metrics"],
        "family_coverage": inspected["family_coverage"],
        "runtime": inspected["runtime"],
        "submission_format": inspected["submission_format"],
        "gates": inspected["gates"],
        "artifact_paths": {
            "notebook": source_paths["notebook"],
            "input_manifest": source_paths["input_manifest"],
            "submission": source_paths["submission"],
            "artifact_manifest": artifact_relative,
        },
        "kaggle": kaggle,
    }
    return measurement, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--stage", choices=sorted(ALL_STAGES), required=True)
    parser.add_argument("--run-dir", type=pathlib.Path)
    parser.add_argument("--challenge", type=pathlib.Path)
    parser.add_argument("--submission", type=pathlib.Path)
    parser.add_argument("--input-manifest", type=pathlib.Path)
    parser.add_argument("--kernel-metadata", type=pathlib.Path)
    parser.add_argument("--run-log", type=pathlib.Path)
    parser.add_argument("--competition-observation", type=pathlib.Path)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--artifact-manifest-output", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.stage in LABELED_STAGES:
            if args.run_dir is None:
                raise ValueError("--run-dir is required for a labeled stage")
            measurement, manifest = build_measurement(
                args.contract,
                args.stage,
                args.run_dir,
                args.experiment_id,
                args.artifact_manifest_output,
            )
        else:
            competition_inputs = {
                "--challenge": args.challenge,
                "--submission": args.submission,
                "--input-manifest": args.input_manifest,
                "--kernel-metadata": args.kernel_metadata,
                "--run-log": args.run_log,
                "--competition-observation": args.competition_observation,
            }
            missing = [name for name, value in competition_inputs.items() if value is None]
            if missing:
                raise ValueError(
                    "competition_rerun is missing required inputs: " + ", ".join(missing)
                )
            measurement, manifest = build_competition_measurement(
                args.contract,
                args.experiment_id,
                args.challenge,
                args.submission,
                args.input_manifest,
                args.kernel_metadata,
                args.run_log,
                args.competition_observation,
                args.artifact_manifest_output,
            )
        args.artifact_manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.artifact_manifest_output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(measurement, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "output": str(args.output),
                    "measurement_sha256": digest(args.output),
                    "artifact_manifest": str(args.artifact_manifest_output),
                    "artifact_manifest_sha256": digest(args.artifact_manifest_output),
                    "gates": measurement["gates"],
                },
                sort_keys=True,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
