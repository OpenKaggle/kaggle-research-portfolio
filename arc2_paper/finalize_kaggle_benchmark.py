#!/usr/bin/env python3
"""Seal a completed training-only Kaggle benchmark into one audit receipt."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from analyze_kaggle_benchmark import load_json, sha256, validate_submission


REQUIRED_ARTIFACTS = (
    "run_manifest.json",
    "benchmark_challenges.json",
    "benchmark_solutions.json",
    "benchmark_manifest.json",
    "nvarc_kgmon.json",
    "nvarc_portfolio.json",
    "nvarc_full_probmul_3.json",
    "nvarc_submission.json",
    "submission.json",
    "ab-benchmark-report.json",
)

SUBMISSION_NAMES = (
    "nvarc_kgmon.json",
    "nvarc_portfolio.json",
    "nvarc_full_probmul_3.json",
    "nvarc_submission.json",
    "trm_submission_early.json",
    "trm_submission_final.json",
    "benchmark_nvarc1_trm1.json",
    "submission.json",
)


def read_receipts(run_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(run_dir.glob("nvarc-receipt-rank*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from error
            required = {
                "rank",
                "task_id",
                "elapsed_seconds",
                "timed_out",
                "decode_batches_finished",
                "decode_batches_planned",
                "finished_at",
            }
            if not isinstance(record, dict) or not required <= set(record):
                raise ValueError(f"{path}:{line_number}: incomplete receipt")
            records.append(record)
    return records


def discover_peak_memory(run_dir: Path) -> tuple[int | None, list[str]]:
    pattern = re.compile(r"allocated\s+(\d+)MB", re.IGNORECASE)
    values: list[int] = []
    sources: list[str] = []
    for path in sorted(run_dir.rglob("*.log")):
        matches = [int(value) for value in pattern.findall(path.read_text(encoding="utf-8", errors="replace"))]
        if matches:
            values.extend(matches)
            sources.append(path.relative_to(run_dir).as_posix())
    return (max(values) if values else None), sources


def artifact_manifest(run_dir: Path, output_dir: Path) -> dict[str, dict[str, int | str]]:
    files = {}
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.is_relative_to(output_dir):
            continue
        relative = path.relative_to(run_dir).as_posix()
        if relative == "run_manifest.json":
            continue
        files[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--kernel-status", default="COMPLETE")
    parser.add_argument("--observed-peak-memory-mb", type=int)
    parser.add_argument("--completed-at-cst")
    args = parser.parse_args()

    if args.kernel_status.upper() != "COMPLETE":
        raise SystemExit("refusing to seal a benchmark whose authoritative kernel status is not COMPLETE")
    if not args.completed_at_cst:
        raise SystemExit("--completed-at-cst is required for a sealed runtime upper bound")
    if args.observed_peak_memory_mb is not None and args.observed_peak_memory_mb <= 0:
        raise SystemExit("observed peak memory must be positive")

    missing = [name for name in REQUIRED_ARTIFACTS if not (args.run_dir / name).is_file()]
    if missing:
        raise SystemExit(f"missing completed-run artifacts: {missing}")

    challenges = load_json(args.run_dir / "benchmark_challenges.json")
    solutions = load_json(args.run_dir / "benchmark_solutions.json")
    manifest = load_json(args.run_dir / "benchmark_manifest.json")
    report = load_json(args.run_dir / "ab-benchmark-report.json")
    run_manifest = load_json(args.run_dir / "run_manifest.json")
    if len(challenges) != 48:
        raise ValueError(f"expected the frozen 48-task benchmark, found {len(challenges)} tasks")
    if set(solutions) != set(challenges):
        raise ValueError("solution task IDs differ from challenge task IDs")
    if set(challenges) != {row["task_id"] for row in manifest.get("tasks", [])}:
        raise ValueError("benchmark manifest task IDs differ from challenge task IDs")
    if sorted(manifest.get("quartile_counts", {}).values()) != [12, 12, 12, 12]:
        raise ValueError("benchmark manifest does not contain 12 tasks per work quartile")

    completed_at = datetime.fromisoformat(args.completed_at_cst)
    started_at = datetime.fromisoformat(str(run_manifest["started_at_cst"]))
    if completed_at.tzinfo is None or started_at.tzinfo is None:
        raise ValueError("started/completed timestamps must include UTC offsets")
    kernel_wall_upper_bound_seconds = (completed_at - started_at).total_seconds()
    if kernel_wall_upper_bound_seconds <= 0:
        raise ValueError("completed timestamp precedes the recorded start")

    trm_available = bool(report.get("trm_available"))
    if trm_available:
        trm_required = (
            "trm_submission_early.json",
            "trm_submission_final.json",
            "benchmark_nvarc1_trm1.json",
            "selector-receipt.json",
        )
        trm_missing = [name for name in trm_required if not (args.run_dir / name).is_file()]
        if trm_missing:
            raise ValueError(f"TRM is reported available but its conditional artifacts are missing: {trm_missing}")

    submission_receipts = {}
    submissions = {}
    for name in SUBMISSION_NAMES:
        path = args.run_dir / name
        if not path.is_file():
            continue
        submission = load_json(path)
        validate_submission(challenges, submission, name)
        submissions[name] = submission
        submission_receipts[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    anchor = submissions["nvarc_kgmon.json"]
    method = submissions["submission.json"]
    attempt_1_changed_outputs = 0
    for task_id, anchor_rows in anchor.items():
        for output_index, anchor_row in enumerate(anchor_rows):
            if method[task_id][output_index]["attempt_1"] != anchor_row["attempt_1"]:
                attempt_1_changed_outputs += 1

    policy_scores = report.get("policy_scores", {})
    anchor_solved = int(policy_scores.get("kgmon", {}).get("solved_outputs", -1))
    method_policy_score_key = (
        "agreement_exact_v176"
        if "agreement_exact_v176" in policy_scores
        else "agreement_merge"
    )
    if method_policy_score_key not in policy_scores:
        raise ValueError("A/B report has no recognized final-method policy score")
    method_solved = int(policy_scores[method_policy_score_key].get("solved_outputs", -1))
    method_gain_outputs = method_solved - anchor_solved

    exact_overlay_receipt = None
    if method_policy_score_key == "agreement_exact_v176":
        exact_overlay_path = args.run_dir / "exact-overlay-receipt.json"
        if not exact_overlay_path.is_file():
            raise ValueError("V176 policy score exists but exact-overlay-receipt.json is missing")
        exact_overlay_receipt = load_json(exact_overlay_path)
        expected_rules = {
            "scale_by_distinct_color_count",
            "reconstruct_centered_square_perimeters",
        }
        expected_outputs = sum(len(task["test"]) for task in challenges.values())
        if (
            exact_overlay_receipt.get("solution_blind") is not True
            or set(exact_overlay_receipt.get("enabled_rules", [])) != expected_rules
            or int(exact_overlay_receipt.get("task_count", -1)) != len(challenges)
            or int(exact_overlay_receipt.get("test_output_count", -1)) != expected_outputs
            or len(exact_overlay_receipt.get("rows", [])) != expected_outputs
        ):
            raise ValueError("exact-overlay receipt disagrees with the frozen V176 policy or benchmark")
        exact_overlay_receipt = {
            **exact_overlay_receipt,
            "sha256": sha256(exact_overlay_path),
        }

    records = read_receipts(args.run_dir)
    counts = Counter(str(record["task_id"]) for record in records)
    duplicate_receipts = sorted(task_id for task_id, count in counts.items() if count != 1)
    unknown_receipts = sorted(set(counts) - set(challenges))
    unfinished = sorted(set(challenges) - set(counts))
    if duplicate_receipts or unknown_receipts:
        raise ValueError(
            f"invalid NVARC receipts: duplicate={duplicate_receipts}, unknown={unknown_receipts}"
        )

    timed_out = sorted(str(record["task_id"]) for record in records if record["timed_out"])
    incomplete_decode = sorted(
        str(record["task_id"])
        for record in records
        if int(record["decode_batches_finished"]) < int(record["decode_batches_planned"])
    )
    starts = [float(record["finished_at"]) - float(record["elapsed_seconds"]) for record in records]
    finishes = [float(record["finished_at"]) for record in records]
    nvarc_wall_seconds = max(finishes) - min(starts) if records else None
    occupied_seconds = sum(float(record["elapsed_seconds"]) for record in records)

    report_tasks = int(report.get("benchmark_tasks", -1))
    report_outputs = int(report.get("total_outputs", -1))
    actual_outputs = sum(len(task["test"]) for task in challenges.values())
    if report_tasks != len(challenges) or report_outputs != actual_outputs:
        raise ValueError("A/B report coverage disagrees with benchmark files")
    if int(report.get("nvarc_completed_tasks", -1)) != len(counts):
        raise ValueError("A/B report completion count disagrees with receipts")
    if sorted(report.get("nvarc_unfinished_tasks", [])) != unfinished:
        raise ValueError("A/B report unfinished task list disagrees with receipts")

    discovered_peak, memory_sources = discover_peak_memory(args.run_dir)
    peak_memory = max(
        value
        for value in (discovered_peak, args.observed_peak_memory_mb)
        if value is not None
    ) if discovered_peak is not None or args.observed_peak_memory_mb is not None else None

    output_dir = args.output_dir or args.run_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    files = artifact_manifest(args.run_dir, output_dir)
    failed_tasks = sorted(set(unfinished) | set(timed_out) | set(incomplete_decode))
    receipt = {
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "completed_at_cst": args.completed_at_cst,
        "kernel_wall_upper_bound_seconds": kernel_wall_upper_bound_seconds,
        "authoritative_kernel_status": "COMPLETE",
        "data_boundary": "public training-only frozen benchmark",
        "tasks": len(challenges),
        "outputs": actual_outputs,
        "valid_submission_artifacts": submission_receipts,
        "nvarc": {
            "completed_tasks": len(counts),
            "unfinished_tasks": unfinished,
            "timed_out_tasks": timed_out,
            "incomplete_decode_tasks": incomplete_decode,
            "failed_tasks": failed_tasks,
            "failure_rate": len(failed_tasks) / len(challenges),
            "gpu_occupied_seconds": occupied_seconds,
            "wall_seconds_from_receipts": nvarc_wall_seconds,
            "max_task_seconds": max((float(record["elapsed_seconds"]) for record in records), default=None),
        },
        "trm": {
            "available": trm_available,
            "marker": report.get("trm_marker"),
        },
        "peak_memory_mb": peak_memory,
        "peak_memory_log_sources": memory_sources,
        "policy_scores": policy_scores,
        "selection_policy": {
            "anchor": "nvarc_kgmon.json",
            "method": "submission.json",
            "method_policy_score_key": method_policy_score_key,
            "anchor_solved_outputs": anchor_solved,
            "method_solved_outputs": method_solved,
            "method_gain_outputs": method_gain_outputs,
            "attempt_1_changed_outputs": attempt_1_changed_outputs,
        },
        "exact_overlay": exact_overlay_receipt,
        "solver_union": {
            "nvarc_unique_outputs_vs_trm": report.get("nvarc_unique_outputs_vs_trm"),
            "trm_unique_outputs_vs_nvarc": report.get("trm_unique_outputs_vs_nvarc"),
            "overlap_outputs": report.get("nvarc_trm_overlap_outputs"),
            "oracle_outputs": report.get("nvarc_trm_oracle_outputs"),
            "oracle_accuracy": report.get("nvarc_trm_oracle_accuracy"),
        },
        "hard_gates": {
            "full_coverage": not unfinished,
            "zero_timeouts": not timed_out,
            "all_decodes_complete": not incomplete_decode,
            "all_submission_schemas_valid": True,
            "within_six_hour_cap": kernel_wall_upper_bound_seconds <= 6 * 3600,
            "trm_available": trm_available,
            "method_gain_at_least_one_output": method_gain_outputs >= 1,
            "attempt_1_unchanged": attempt_1_changed_outputs == 0,
        },
        "artifact_files": files,
    }
    receipt["hard_gates"]["all_passed"] = all(receipt["hard_gates"].values())
    receipt["promotion_decision"] = (
        "PROMOTE_TO_SEALED_HOLDOUT"
        if receipt["hard_gates"]["all_passed"]
        else "STOP_BEFORE_SEALED_HOLDOUT"
    )
    receipt_path = output_dir / "benchmark_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**receipt, "receipt_sha256": sha256(receipt_path)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
