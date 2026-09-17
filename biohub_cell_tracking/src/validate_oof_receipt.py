#!/usr/bin/env python3
"""Validate the completed budgeted embryo-OOF receipt before using its scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


OFFICIAL_METRIC_COMMIT = "075fc5f5a52d11077f9dc2b074644618f26939e2"
OFFICIAL_METRIC_HASHES = {
    "metrics.py": "cfdd596e3f8909cca14db0682889738b19ff75c3808b3773175aba9367ca7444",
    "division_metrics.py": "0635c38621a38f1eb4b55a302b4a817a88e9094930dfc2dab16faeeee60f4dc9",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def validate(receipt: dict, protocol: dict, protocol_sha256: str) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if receipt.get("status") != "complete":
        errors.append(f"receipt status is {receipt.get('status')!r}, expected 'complete'")
    if receipt.get("source_protocol_sha256") != protocol_sha256:
        errors.append("protocol SHA-256 mismatch")
    if receipt.get("official_metric_commit") != OFFICIAL_METRIC_COMMIT:
        errors.append("official metric commit mismatch")
    if receipt.get("official_metric_sha256") != OFFICIAL_METRIC_HASHES:
        errors.append("official metric source hashes mismatch")
    if receipt.get("ground_truth_scope") != "official train only":
        errors.append("ground-truth scope is not restricted to official train")
    if receipt.get("competition_test_accessed") is not False:
        errors.append("competition test access was not affirmatively false")
    if receipt.get("visible_test_copies_used_for_monitor_or_holdout") is not False:
        errors.append("visible-test exclusion was not affirmatively false")

    runtime = receipt.get("total_seconds")
    if not isinstance(runtime, (int, float)) or not math.isfinite(runtime):
        errors.append("total runtime is missing or non-finite")
    elif runtime >= 12 * 3600:
        errors.append(f"total runtime {runtime:.1f}s exceeds the 12-hour limit")

    expected_folds = {int(fold["fold"]): fold for fold in protocol["folds"]}
    actual_fold_rows = receipt.get("folds")
    if not isinstance(actual_fold_rows, list):
        errors.append("fold receipts are missing")
        actual_fold_rows = []
    actual_folds = {
        int(fold.get("fold", -1)): fold
        for fold in actual_fold_rows
        if isinstance(fold, dict)
    }
    if set(actual_folds) != set(expected_folds):
        errors.append(
            f"fold IDs mismatch: expected {sorted(expected_folds)}, got {sorted(actual_folds)}"
        )

    for fold_id, expected in expected_folds.items():
        actual = actual_folds.get(fold_id)
        if actual is None:
            continue
        expected_counts = {
            "train_datasets": len(expected["train"]),
            "monitor_datasets": len(expected["monitor"]),
            "holdout_datasets": len(expected["holdout"]),
        }
        for key, expected_value in expected_counts.items():
            if actual.get(key) != expected_value:
                errors.append(
                    f"fold {fold_id} {key} mismatch: {actual.get(key)} != {expected_value}"
                )
        if actual.get("seed") != expected["seed"]:
            errors.append(f"fold {fold_id} seed mismatch")
        if actual.get("train_embryo") != expected["train_embryo"]:
            errors.append(f"fold {fold_id} train embryo mismatch")
        if actual.get("holdout_embryo") != expected["validation_embryo"]:
            errors.append(f"fold {fold_id} holdout embryo mismatch")
        for key in ("weights_sha256", "train_log_sha256", "predict_log_sha256"):
            if not valid_hash(actual.get(key)):
                errors.append(f"fold {fold_id} has invalid {key}")
        summary = actual.get("holdout_summary")
        if not isinstance(summary, dict):
            errors.append(f"fold {fold_id} holdout summary missing")
        else:
            if summary.get("n") != len(expected["holdout"]):
                errors.append(f"fold {fold_id} scored sample count mismatch")
            score = summary.get("score")
            if not isinstance(score, (int, float)) or not math.isfinite(score):
                errors.append(f"fold {fold_id} score missing or non-finite")

    per_sample = receipt.get("per_sample")
    if not isinstance(per_sample, list):
        errors.append("per-sample metrics are missing")
        per_sample = []
    expected_pairs = {
        (int(fold["fold"]), dataset)
        for fold in protocol["folds"]
        for dataset in fold["holdout"]
    }
    actual_pairs = {
        (int(row.get("fold", -1)), row.get("dataset"))
        for row in per_sample
        if isinstance(row, dict)
    }
    if actual_pairs != expected_pairs:
        errors.append("per-sample fold/dataset coverage mismatch")
    if len(per_sample) != len(expected_pairs):
        errors.append(
            f"per-sample row count mismatch: {len(per_sample)} != {len(expected_pairs)}"
        )

    combined = receipt.get("combined_holdout_summary")
    if not isinstance(combined, dict):
        errors.append("combined holdout summary missing")
    else:
        if combined.get("n") != len(expected_pairs):
            errors.append("combined holdout sample count mismatch")
        score = combined.get("score")
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            errors.append("combined score missing or non-finite")

    fold_scores = [
        actual_folds[fold_id].get("holdout_summary", {}).get("score")
        for fold_id in sorted(actual_folds)
    ]
    if len(fold_scores) == 2 and all(
        isinstance(score, (int, float)) and math.isfinite(score)
        for score in fold_scores
    ):
        gap = abs(fold_scores[0] - fold_scores[1])
        if gap > 0.15:
            warnings.append(f"large embryo-direction score gap: {gap:.6f}")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "folds": len(actual_folds),
        "per_sample_rows": len(per_sample),
        "runtime_seconds": runtime,
        "combined_score": combined.get("score") if isinstance(combined, dict) else None,
        "fold_scores": fold_scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    report = validate(receipt, protocol, sha256(args.protocol))
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
