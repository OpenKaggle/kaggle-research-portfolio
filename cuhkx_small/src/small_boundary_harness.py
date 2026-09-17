#!/usr/bin/env python3
"""Fail-closed CUHK-X Small research and release boundary checks.

The default command audits only preregistration, static inference policy, and
submission cadence.  It never reads competition test payloads and never makes
a submission.  ``validate_release_manifest`` is intentionally separate: a
candidate cannot pass it until real subject-disjoint evidence and a complete
single-checkpoint package exist.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "cuhkx_small/config/top5_preregistered_ladder.json"
DEFAULT_SUBMISSION_LOG = ROOT / "cuhkx_small/SUBMISSION_LOG.csv"
P2_SOURCE = ROOT / "cuhkx_small/src/train_p2_thermal_tsm.py"
WEIGHT_SUFFIXES = {".bin", ".ckpt", ".onnx", ".pt", ".pth", ".safetensors"}
NETWORK_IMPORT_ROOTS = {
    "aiohttp",
    "ftplib",
    "httpx",
    "requests",
    "socket",
    "urllib",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def natural_path_key(value: str) -> tuple[tuple[int, int | str], ...]:
    """Stable natural order that never depends on filesystem enumeration."""
    parts: list[tuple[int, int | str]] = []
    for token in re.split(r"(\d+)", value.casefold()):
        if not token:
            continue
        parts.append((0, int(token)) if token.isdigit() else (1, token))
    return tuple(parts)


def audit_split_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    duplicate_keys: list[str] = []
    key_counts = Counter(str(row.get("clip_key", "")) for row in rows)
    duplicate_keys = sorted(key for key, count in key_counts.items() if not key or count > 1)
    train = [row for row in rows if row.get("split") == "train"]
    valid = [row for row in rows if row.get("split") == "validation"]
    unknown_splits = sorted(
        {str(row.get("split")) for row in rows} - {"train", "validation"}
    )
    train_subjects = {int(row["subject"]) for row in train if "subject" in row}
    valid_subjects = {int(row["subject"]) for row in valid if "subject" in row}
    train_keys = {str(row["clip_key"]) for row in train if "clip_key" in row}
    valid_keys = {str(row["clip_key"]) for row in valid if "clip_key" in row}
    subject_overlap = sorted(train_subjects & valid_subjects)
    clip_overlap = sorted(train_keys & valid_keys)
    checks = {
        "nonempty_train": bool(train),
        "nonempty_validation": bool(valid),
        "known_splits_only": not unknown_splits,
        "unique_nonempty_clip_keys": not duplicate_keys,
        "zero_subject_overlap": not subject_overlap,
        "zero_clip_overlap": not clip_overlap,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "subject_overlap": subject_overlap,
        "clip_overlap": clip_overlap,
        "duplicate_or_empty_clip_keys": duplicate_keys,
        "unknown_splits": unknown_splits,
    }


def fit_train_robust_scale(values: list[list[float]], minimum_iqr: float) -> dict[str, Any]:
    if not values or not values[0]:
        raise ValueError("training sensor matrix must be nonempty")
    channels = len(values[0])
    if any(len(row) != channels for row in values):
        raise ValueError("ragged training sensor matrix")
    if any(not math.isfinite(float(value)) for row in values for value in row):
        raise ValueError("non-finite training sensor value")
    medians: list[float] = []
    iqrs: list[float] = []
    for channel in range(channels):
        column = sorted(float(row[channel]) for row in values)
        medians.append(statistics.median(column))
        quartiles = statistics.quantiles(column, n=4, method="inclusive") if len(column) > 1 else [column[0]] * 3
        iqrs.append(max(float(minimum_iqr), quartiles[2] - quartiles[0]))
    return {
        "fit_scope": "train_fold_only",
        "channels": channels,
        "median": medians,
        "iqr": iqrs,
        "minimum_iqr": float(minimum_iqr),
    }


def audit_sensor_batch(
    timestamps: list[float],
    values: list[list[float]],
    train_scale: dict[str, Any],
    maximum_absolute_robust_z: float,
    maximum_outlier_fraction: float,
) -> dict[str, Any]:
    expected_channels = int(train_scale.get("channels", 0))
    shape_ok = bool(values) and all(len(row) == expected_channels for row in values)
    finite = all(math.isfinite(float(stamp)) for stamp in timestamps) and all(
        math.isfinite(float(value)) for row in values for value in row
    )
    monotonic = len(timestamps) == len(values) and all(
        timestamps[index] < timestamps[index + 1]
        for index in range(len(timestamps) - 1)
    )
    fit_scope_ok = train_scale.get("fit_scope") == "train_fold_only"
    scale_shape_ok = (
        len(train_scale.get("median", [])) == expected_channels
        and len(train_scale.get("iqr", [])) == expected_channels
        and all(float(value) > 0 for value in train_scale.get("iqr", []))
    )
    outlier_fraction = 1.0
    if shape_ok and finite and scale_shape_ok:
        total = len(values) * expected_channels
        outliers = 0
        for row in values:
            for channel, value in enumerate(row):
                robust_z = abs(
                    (float(value) - float(train_scale["median"][channel]))
                    / float(train_scale["iqr"][channel])
                )
                outliers += robust_z > maximum_absolute_robust_z
        outlier_fraction = outliers / total
    checks = {
        "row_count_matches_timestamps": len(timestamps) == len(values) and bool(values),
        "strictly_increasing_finite_timestamps": monotonic and finite,
        "pinned_channel_count": shape_ok,
        "train_fold_only_scale": fit_scope_ok and scale_shape_ok,
        "scale_drift_within_preregistered_bound": outlier_fraction <= maximum_outlier_fraction,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "outlier_fraction": outlier_fraction,
    }


def audit_modality_contract(
    available: dict[str, bool],
    mask: dict[str, float],
    expected_modalities: list[str],
    supports_missing: bool,
) -> dict[str, Any]:
    expected = set(expected_modalities)
    keys_match = set(available) == expected and set(mask) == expected
    binary_mask = all(float(value) in {0.0, 1.0} for value in mask.values())
    mask_matches = keys_match and all(
        float(mask[name]) == (1.0 if available[name] else 0.0)
        for name in expected
    )
    missing_supported = supports_missing or all(available.get(name, False) for name in expected)
    checks = {
        "exact_expected_modalities": keys_match,
        "binary_availability_mask": binary_mask,
        "mask_matches_present_inputs": mask_matches,
        "missingness_explicitly_supported": missing_supported,
    }
    return {"passed": all(checks.values()), "checks": checks}


def audit_inference_sources(paths: Iterable[Path], forbidden_imports: Iterable[str]) -> dict[str, Any]:
    forbidden_roots = set(forbidden_imports) | NETWORK_IMPORT_ROOTS
    findings: list[str] = []
    checked: list[str] = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        checked.append(str(path.resolve()))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                root = module.split(".", 1)[0]
                if root in forbidden_roots:
                    findings.append(f"{path.name}:{getattr(node, 'lineno', 0)}:{module}")
    return {"passed": not findings, "checked": checked, "forbidden_imports": findings}


def audit_submission_cadence(path: Path, campaign_daily_maximum: int) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row.get("submission_id", "") for row in rows]
    valid_times = True
    dates: list[str] = []
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row["submitted_utc"].replace("Z", "+00:00"))
            valid_times &= stamp.tzinfo is not None and stamp.utcoffset() == timezone.utc.utcoffset(stamp)
            dates.append(stamp.date().isoformat())
        except (KeyError, ValueError):
            valid_times = False
    per_day = dict(sorted(Counter(dates).items()))
    checks = {
        "unique_nonempty_submission_ids": bool(ids) and all(ids) and len(ids) == len(set(ids)),
        "parseable_utc_timestamps": valid_times and len(dates) == len(rows),
        "campaign_daily_cap_respected": all(
            count <= campaign_daily_maximum for count in per_day.values()
        ),
    }
    return {"passed": all(checks.values()), "checks": checks, "per_day": per_day}


def validate_preregistration(config: dict[str, Any]) -> dict[str, Any]:
    required_boundaries = {
        "subject_disjoint",
        "clip_disjoint",
        "modality_missingness",
        "sensor_order",
        "scale_drift",
        "single_checkpoint",
        "static_no_llm_inference",
        "license_and_provenance",
        "offline_and_network",
        "submission_frequency",
    }
    boundaries = config.get("boundaries", {})
    ladder = config.get("ladder", [])
    ids = [row.get("id") for row in ladder]
    checks = {
        "schema_version": config.get("schema_version") == 1,
        "all_boundaries_present": required_boundaries <= set(boundaries),
        "exact_three_stage_ladder": ids
        == [
            "S1_THERMAL_TSM_TDN",
            "S2_CONDITIONAL_THERMAL_IMU_FUSION",
            "S3_TRAIN_ONLY_ROBUST_AUGMENTATION",
        ],
        "causal_predecessor_chain": len(ladder) == 3
        and ladder[0].get("predecessor") == "B0_THERMAL_TEMPORAL_MEAN"
        and ladder[1].get("predecessor") == ladder[0].get("id")
        and ladder[2].get("predecessor") == ladder[1].get("id"),
        "every_stage_has_fast_kill_promotion_and_attribution": len(ladder) == 3
        and all(
            row.get("fast_kill")
            and row.get("promotion")
            and row.get("causal_attribution")
            for row in ladder
        ),
        "single_checkpoint_strictly_below_100MB": boundaries.get("single_checkpoint", {}).get("learned_weight_files") == 1
        and int(boundaries.get("single_checkpoint", {}).get("int8_bytes_exclusive", 0)) == 100_000_000,
        "no_llm_and_no_network": boundaries.get("static_no_llm_inference", {}).get("uses_llm") is False
        and boundaries.get("offline_and_network", {}).get("network_allowed_at_inference") is False,
        "public_score_not_a_gate": config.get("top5_evidence_gate", {}).get("public_leaderboard_score_is_not_an_evidence_gate") is True,
        "top5_snapshot_ordered": float(config.get("public_leaderboard_snapshot", {}).get("top_5_score", 0))
        > float(config.get("public_leaderboard_snapshot", {}).get("top_6_score", 1)),
        "payload_blocked_release_rejected": config.get("current_decision")
        == "RESEARCH_READY_PAYLOAD_BLOCKED_RELEASE_REJECTED",
    }
    return {"passed": all(checks.values()), "checks": checks}


def validate_release_manifest(manifest: dict[str, Any], package_root: Path) -> dict[str, Any]:
    """Validate a future finalist package without inferring any competition label."""
    root = package_root.resolve()
    weight_names = manifest.get("learned_weight_files", [])
    checkpoint = root / weight_names[0] if len(weight_names) == 1 else root / "__missing__"
    quantization = manifest.get("quantization", "fp32")
    size_limit = 100_000_000 if quantization == "int8" else 95_000_000
    checkpoint_ok = checkpoint.is_file() and _within(checkpoint, root)
    checkpoint_hash_ok = checkpoint_ok and sha256(checkpoint) == manifest.get("checkpoint_sha256")
    enumerated_weights = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in WEIGHT_SUFFIXES
    )
    source_paths = [root / value for value in manifest.get("inference_sources", [])]
    source_paths_ok = bool(source_paths) and all(path.is_file() and _within(path, root) for path in source_paths)
    static_audit = (
        audit_inference_sources(source_paths, manifest.get("forbidden_import_roots", []))
        if source_paths_ok
        else {"passed": False, "checked": [], "forbidden_imports": ["missing source"]}
    )
    assets = manifest.get("asset_inventory", [])
    asset_checks: list[bool] = []
    for asset in assets:
        required = all(asset.get(field) for field in ("path", "public_url", "version", "license", "sha256"))
        path = root / str(asset.get("path", "__missing__"))
        local_ok = path.is_file() and _within(path, root) and sha256(path) == asset.get("sha256")
        asset_checks.append(required and local_ok and asset.get("status") == "APPROVED")
    output_hashes = manifest.get("deterministic_output_sha256", [])
    checks = {
        "single_enumerated_checkpoint": len(weight_names) == 1 and enumerated_weights == weight_names,
        "checkpoint_present_hash_matched": checkpoint_hash_ok,
        "checkpoint_strict_size_limit": checkpoint_ok and checkpoint.stat().st_size < size_limit,
        "int8_loss_gate": quantization != "int8"
        or float(manifest.get("int8_absolute_accuracy_loss", 1.0)) <= 0.005,
        "non_llm_family": manifest.get("uses_llm") is False
        and manifest.get("model_family") in {
            "convolutional_neural_network",
            "temporal_shift_module",
            "small_sensor_mlp",
        },
        "static_inference_offline_and_no_llm_imports": bool(static_audit["passed"]),
        "all_assets_approved_and_hash_matched": bool(assets) and all(asset_checks),
        "quarantine_excluded": all("public_mirror" not in value.casefold() for value in weight_names)
        and all("public_mirror" not in str(asset.get("path", "")).casefold() for asset in assets),
        "two_outputs_byte_identical": len(output_hashes) == 2
        and bool(output_hashes[0])
        and output_hashes[0] == output_hashes[1],
        "no_test_labels_or_network": manifest.get("test_labels_read") is False
        and manifest.get("network_allowed_at_inference") is False,
        "scientific_gate_passed": manifest.get("scientific_gate_passed") is True,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "checkpoint_bytes": checkpoint.stat().st_size if checkpoint_ok else None,
        "enumerated_weights": enumerated_weights,
        "static_source_audit": static_audit,
    }


def run_research_audit(config_path: Path, submission_log: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    preregistration = validate_preregistration(config)
    cadence = audit_submission_cadence(
        submission_log,
        int(config["boundaries"]["submission_frequency"]["campaign_daily_maximum"]),
    )
    static_source = audit_inference_sources(
        [P2_SOURCE],
        config["boundaries"]["static_no_llm_inference"]["forbidden_import_roots"],
    )
    research_pass = preregistration["passed"] and cadence["passed"] and static_source["passed"]
    return {
        "status": "PASS_RESEARCH_BOUNDARY_BLOCKED_DATA" if research_pass else "FAIL_RESEARCH_BOUNDARY",
        "passed": research_pass,
        "config_sha256": sha256(config_path),
        "submission_log_sha256": sha256(submission_log),
        "preregistration": preregistration,
        "submission_cadence": cadence,
        "static_p2_source": static_source,
        "transport_readiness": "BLOCKED_OFFICIAL_PAYLOAD",
        "scientific_gate": "NOT_RUN_REAL_PAYLOAD",
        "release_gate": "REJECT_NO_TEST_CANDIDATE",
        "test_labels_read": False,
        "submission_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--submission-log", type=Path, default=DEFAULT_SUBMISSION_LOG)
    args = parser.parse_args()
    report = run_research_audit(args.config.resolve(), args.submission_log.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
