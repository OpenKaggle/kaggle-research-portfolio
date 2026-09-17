#!/usr/bin/env python3
"""Backfill missing legacy resource evidence through deterministic replays.

Original ledger cells remain untouched.  This records current-machine replay
measurements separately, including an expected failure replay for lambda=1.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _measure(
    label: str,
    commands: list[list[str]],
    log_path: Path,
    *,
    expect_failure: bool = False,
) -> dict[str, object]:
    started = time.perf_counter()
    peak_bytes = 0
    exits: list[int] = []
    with log_path.open("w", encoding="utf-8") as log:
        for command in commands:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
            tracked = psutil.Process(process.pid)
            while process.poll() is None:
                try:
                    # Every measured command is the Python worker itself.  Do
                    # not enumerate the process table: macOS sandboxing blocks
                    # that sysctl even though the known child PID is readable.
                    peak_bytes = max(peak_bytes, tracked.memory_info().rss)
                except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                    pass
                time.sleep(0.02)
            exits.append(int(process.returncode))
            if process.returncode and not expect_failure:
                raise RuntimeError(f"{label} command failed with exit {process.returncode}")
    failed = any(code != 0 for code in exits)
    if expect_failure != failed:
        raise RuntimeError(
            f"{label}: expected_failure={expect_failure}, observed exit codes={exits}"
        )
    return {
        "label": label,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": peak_bytes / (1024 * 1024),
        "exit_codes": exits,
        "expected_failure": expect_failure,
        "log": str(log_path),
    }


def coverage(backfills: list[dict[str, object]]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for row in backfills:
        for field in row["covers_legacy_fields"]:
            result.add((str(row["experiment"]), str(field)))
    return result


def run(traffic_root: Path, release: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    python = sys.executable
    src = traffic_root / "src"
    artifacts = traffic_root / "artifacts"
    public = traffic_root / "public_notebooks" / "traffic_flow_bench_pipeline_v32" / "output"
    key = release / "submission_key.csv"
    anchor = public / "submission.csv"
    queue_source = public / "queue_submission.csv"
    current_best = artifacts / "odme_lambda5_v1" / "submission.csv"
    output_root.mkdir(parents=True, exist_ok=True)
    measurements: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="traffic_resource_replay_", dir="/tmp") as temp_name:
        temp = Path(temp_name)

        anchor_report = temp / "anchor_validation.json"
        anchor_measure = _measure(
            "v32_anchor_validation",
            [[python, str(src / "validate_submission.py"), "--submission", str(anchor),
              "--key", str(key), "--report", str(anchor_report)]],
            output_root / "v32_anchor_validation.log",
        )
        anchor_result = json.loads(anchor_report.read_text())
        if anchor_result["sha256"] != "7673146d855a153ee56e90ea5afd5dd5431299420d3e803df5e73396e7611e0c":
            raise ValueError("V32 replay SHA mismatch")
        anchor_measure.update(
            experiment="v32_public_anchor",
            covers_legacy_fields=["peak_memory_mb"],
            replay_output_sha256=anchor_result["sha256"],
        )
        measurements.append(anchor_measure)

        queue_natural = temp / "queue_offbyone.csv"
        queue_measure = _measure(
            "queue_natural_fix",
            [[python, str(src / "fix_v32_queue_horizon.py"), "--source", str(queue_source),
              "--output", str(queue_natural), "--receipt", str(temp / "queue_receipt.json")]],
            output_root / "queue_natural_fix.log",
        )
        queue_sha = _sha256(queue_natural)
        if queue_sha != "54ed12c7936ce386947077bcee0c0fb22ea716bc53a10028306c4e05e7a830ac":
            raise ValueError("Queue natural replay SHA mismatch")
        queue_measure.update(
            experiment="queue_offbyone_v1_natural",
            covers_legacy_fields=["peak_memory_mb"],
            replay_output_sha256=queue_sha,
        )
        measurements.append(queue_measure)

        queue_merged = temp / "queue_merged.csv"
        queue_merged_validation = temp / "queue_merged_validation.json"
        queue_merged_diff = temp / "queue_merged_diff.json"
        merged_measure = _measure(
            "queue_merged_build_and_validation",
            [
                [python, str(src / "replace_task_rows.py"), "--anchor", str(anchor),
                 "--key", str(key), "--replacement", str(queue_natural), "--task", "queue",
                 "--output", str(queue_merged)],
                [python, str(src / "compare_merged_submissions.py"), "--anchor", str(anchor),
                 "--candidate", str(queue_merged), "--expect-task", "queue",
                 "--expect-column", "queue_pred", "--expect-changed-rows", "160",
                 "--report", str(queue_merged_diff)],
                [python, str(src / "validate_submission.py"), "--submission", str(queue_merged),
                 "--key", str(key), "--report", str(queue_merged_validation)],
            ],
            output_root / "queue_merged_build_and_validation.log",
        )
        merged_sha = json.loads(queue_merged_validation.read_text())["sha256"]
        if merged_sha != "7e5c790f917bfb112d572aeab520edc611174c3a98b68ce23190a06c297521da":
            raise ValueError("Queue merged replay SHA mismatch")
        merged_measure.update(
            experiment="queue_offbyone_v1_merged",
            covers_legacy_fields=["runtime_seconds", "peak_memory_mb"],
            replay_output_sha256=merged_sha,
        )
        measurements.append(merged_measure)

        release_report = temp / "public_release_audit.json"
        release_measure = _measure(
            "public_release_audit",
            [[python, str(src / "audit_public_release.py"), "--release-root", str(release),
              "--output", str(release_report)]],
            output_root / "public_release_audit.log",
        )
        release_result = json.loads(release_report.read_text())
        if release_result["status"] != "VALID" or release_result["errors"]:
            raise ValueError("public release replay audit failed")
        release_measure.update(
            experiment="public_release_audit",
            covers_legacy_fields=["peak_memory_mb"],
            replay_output_sha256=_sha256(release_report),
        )
        measurements.append(release_measure)

        lineage_diff = temp / "lineage_diff.json"
        lineage_validation = temp / "lineage_validation.json"
        lineage_measure = _measure(
            "current_best_lineage",
            [
                [python, str(src / "compare_merged_submissions.py"), "--anchor", str(anchor),
                 "--candidate", str(current_best), "--expect-changed-rows", "70868",
                 "--report", str(lineage_diff)],
                [python, str(src / "validate_submission.py"), "--submission", str(current_best),
                 "--key", str(key), "--report", str(lineage_validation)],
            ],
            output_root / "current_best_lineage.log",
        )
        lineage_result = json.loads(lineage_diff.read_text())
        if lineage_result["changed_rows_by_task"] != {"queue": 160, "odme": 70708}:
            raise ValueError("current-best lineage replay mismatch")
        lineage_measure.update(
            experiment="current_best_lineage_audit_v1",
            covers_legacy_fields=["peak_memory_mb"],
            replay_output_sha256=json.loads(lineage_validation.read_text())["sha256"],
        )
        measurements.append(lineage_measure)

        lambda1_measure = _measure(
            "lambda1_expected_numerical_failure",
            [[python, str(src / "odme_lambda_frontier.py"), "--release-root", str(release),
              "--output-root", str(temp / "lambda1"), "--lambda", "1",
              "--control-lambda", "5", "--panel", "D7_I10_E", "--split", "validation",
              "--tolerance", "1e-8", "--lsmr-tolerance", "1e-8",
              "--max-iterations", "300"]],
            output_root / "lambda1_expected_failure.log",
            expect_failure=True,
        )
        lambda1_log = (output_root / "lambda1_expected_failure.log").read_text()
        if "matrix-free ODME solve failed" not in lambda1_log:
            raise ValueError("lambda=1 did not reproduce the expected numerical failure")
        lambda1_measure.update(
            experiment="odme_lambda1_vs5_numerical_gate",
            covers_legacy_fields=["peak_memory_mb"],
            replay_output_sha256=None,
        )
        measurements.append(lambda1_measure)

    backfill_path = output_root / "legacy_resource_backfill.csv"
    columns = [
        "experiment", "covers_legacy_fields", "runtime_seconds", "peak_memory_mb",
        "expected_failure", "exit_codes", "replay_output_sha256", "log",
    ]
    with backfill_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for measurement in measurements:
            writer.writerow(
                {
                    column: json.dumps(measurement[column])
                    if isinstance(measurement.get(column), (list, dict))
                    else measurement.get(column)
                    for column in columns
                }
            )
    expected_coverage = {
        ("v32_public_anchor", "peak_memory_mb"),
        ("queue_offbyone_v1_natural", "peak_memory_mb"),
        ("queue_offbyone_v1_merged", "runtime_seconds"),
        ("queue_offbyone_v1_merged", "peak_memory_mb"),
        ("public_release_audit", "peak_memory_mb"),
        ("odme_lambda1_vs5_numerical_gate", "peak_memory_mb"),
        ("current_best_lineage_audit_v1", "peak_memory_mb"),
    }
    observed_coverage = coverage(measurements)
    if observed_coverage != expected_coverage:
        raise ValueError(f"resource backfill coverage mismatch: {observed_coverage}")
    receipt: dict[str, object] = {
        "status": "COMPLETE_REPLAY_BACKFILL",
        "experiment": "legacy_resource_replay_v1",
        "interpretation": "Measurements describe deterministic replays on the current machine. They do not pretend to be measurements captured during the original historical runs.",
        "covered_legacy_fields": [f"{experiment}:{field}" for experiment, field in sorted(observed_coverage)],
        "measurements": measurements,
        "hidden_labels_or_target_truth_read": False,
        "lambda1_policy": "Expected numerical failure replay only; no candidate, score comparison, or family reopening.",
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": max(float(row["peak_memory_mb"]) for row in measurements),
        "outputs": {backfill_path.name: _sha256(backfill_path)},
    }
    receipt_path = output_root / "legacy_resource_replay_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.traffic_root.resolve(), args.release_root.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
