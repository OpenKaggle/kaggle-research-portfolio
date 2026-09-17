#!/usr/bin/env python3
"""Rebuild the frozen best submission from the pinned V32 anchor and public inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from compare_merged_submissions import compare
from concat_csv_parts import concatenate
from fix_v32_queue_horizon import fix
from odme_lambda_frontier import run as run_odme
from replace_task_rows import replace_task
from validate_submission import validate


TRAFFIC_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def _resolve(path: str) -> Path:
    return (TRAFFIC_ROOT / path).resolve()


def _expect_hash(path: Path, expected: str, label: str) -> str:
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _files_equal(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        while True:
            left_block = left_handle.read(8 * 1024 * 1024)
            right_block = right_handle.read(8 * 1024 * 1024)
            if left_block != right_block:
                return False
            if not left_block:
                return True


def _expect_diff(report: dict[str, object], config: dict[str, object]) -> None:
    best = config["current_best"]
    if report["changed_rows_by_task"] != best["expected_changed_rows_by_task_from_v32"]:
        raise ValueError(f"unexpected changed tasks: {report['changed_rows_by_task']}")
    if report["changed_cells_by_column"] != best["expected_changed_cells_by_column_from_v32"]:
        raise ValueError(f"unexpected changed columns: {report['changed_cells_by_column']}")


def run(
    release: Path,
    config_path: Path,
    output_root: Path,
    evidence_root: Path | None = None,
) -> dict[str, object]:
    started = time.perf_counter()
    config = json.loads(config_path.read_text())
    if any(config["information_boundary"].values()):
        raise ValueError("freeze config must prohibit every unavailable information source")
    key_path = release / "submission_key.csv"
    _expect_hash(key_path, config["submission_key_sha256"], "submission key")
    anchor = _resolve(config["anchor"]["merged_path"])
    source_queue = _resolve(config["anchor"]["queue_path"])
    canonical = _resolve(config["current_best"]["canonical_path"])
    _expect_hash(anchor, config["anchor"]["merged_sha256"], "V32 anchor")
    _expect_hash(source_queue, config["anchor"]["queue_sha256"], "V32 Queue source")
    _expect_hash(canonical, config["current_best"]["expected_sha256"], "canonical best")
    official_commit = subprocess.check_output(
        ["git", "-C", str(TRAFFIC_ROOT / "official"), "rev-parse", "HEAD"], text=True
    ).strip()
    if official_commit != config["official_code_commit"]:
        raise ValueError(
            f"official code commit mismatch: expected {config['official_code_commit']}, got {official_commit}"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    evidence_root = evidence_root or output_root
    evidence_root.mkdir(parents=True, exist_ok=True)
    queue_path = output_root / "queue_offbyone.csv"
    queue_receipt_path = output_root / "queue_offbyone_receipt.json"
    queue_receipt = fix(source_queue, queue_path, queue_receipt_path)
    if queue_receipt["rows_changed_1_to_0"] != config["queue"]["expected_rows_changed_1_to_0"]:
        raise ValueError("Queue fix changed an unexpected number of rows")
    _expect_hash(
        queue_path, config["queue"]["expected_natural_key_sha256"], "replayed Queue"
    )
    queue_merged = output_root / "queue_merged.csv"
    replace_task(anchor, key_path, queue_path, "queue", queue_merged)
    queue_diff = compare(anchor, queue_merged)
    if queue_diff["changed_rows_by_task"] != {"queue": 160}:
        raise ValueError(f"unexpected Queue replay diff: {queue_diff['changed_rows_by_task']}")

    odme_root = output_root / "odme"
    odme = config["odme"]
    odme_receipt = run_odme(
        release,
        odme_root,
        (float(odme["lambda"]),),
        ("validation", "private"),
        None,
        float(odme["lambda"]),
        float(odme["tolerance"]),
        float(odme["lsmr_tolerance"]),
        int(odme["max_iterations"]),
    )
    validation_odme = odme_root / "odme_validation_lambda_5.csv"
    private_odme = odme_root / "odme_private_lambda_5.csv"
    _expect_hash(validation_odme, odme["expected_validation_sha256"], "validation ODME")
    _expect_hash(private_odme, odme["expected_private_sha256"], "private ODME")
    combined_odme = output_root / "odme_lambda5.csv"
    odme_rows = concatenate([validation_odme, private_odme], combined_odme)
    _expect_hash(combined_odme, odme["expected_combined_sha256"], "combined ODME")

    rebuilt = output_root / "submission.csv"
    replace_task(queue_merged, key_path, combined_odme, "odme", rebuilt)
    validation = validate(rebuilt, key_path)
    if validation["rows"] != config["current_best"]["expected_rows"]:
        raise ValueError(f"unexpected rebuilt row count: {validation['rows']}")
    rebuilt_sha = _expect_hash(
        rebuilt, config["current_best"]["expected_sha256"], "rebuilt current best"
    )
    if not _files_equal(rebuilt, canonical):
        raise ValueError("rebuilt current best is not byte-identical to canonical artifact")
    lineage = compare(anchor, rebuilt)
    _expect_diff(lineage, config)

    report_paths = {
        "queue_diff.json": queue_diff,
        "current_best_validation.json": validation,
        "v32_to_rebuilt_diff.json": lineage,
    }
    for name, report in report_paths.items():
        (evidence_root / name).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    receipt: dict[str, object] = {
        "status": "REPRODUCED_BYTE_IDENTICAL",
        "experiment": "current_best_full_replay_v1",
        "config": str(config_path),
        "information_boundary": config["information_boundary"],
        "official_code_commit": official_commit,
        "queue_rows_changed_1_to_0": queue_receipt["rows_changed_1_to_0"],
        "odme_panel_splits": len(odme_receipt["panels"]) * len(odme_receipt["splits"]),
        "odme_rows": odme_rows,
        "whole_table_rows": validation["rows"],
        "changed_rows_by_task_from_v32": lineage["changed_rows_by_task"],
        "changed_cells_by_column_from_v32": lineage["changed_cells_by_column"],
        "rebuilt_sha256": rebuilt_sha,
        "canonical_sha256": _sha256(canonical),
        "byte_identical_to_canonical": True,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "outputs": {
            **{name: _sha256(evidence_root / name) for name in report_paths},
            "submission.csv": _sha256(rebuilt),
        },
        "decision": "FREEZE_REPLAY_PATH_VALID",
    }
    receipt_path = evidence_root / "current_best_full_replay_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=TRAFFIC_ROOT / "config" / "current_best_freeze_v1.json"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        help="Optional persistent destination for small reports and receipt while large replay files stay under output-root",
    )
    args = parser.parse_args()
    run(
        args.release_root.resolve(),
        args.config.resolve(),
        args.output_root.resolve(),
        args.evidence_root.resolve() if args.evidence_root else None,
    )


if __name__ == "__main__":
    main()
