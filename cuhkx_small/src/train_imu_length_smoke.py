#!/usr/bin/env python3
"""Train a leakage-guarded CUHK-X IMU-index smoke model.

This is deliberately a metadata-only engineering smoke.  It uses the five
organizer-published IMU row-count columns and four availability flags, never
opens test data, and cannot create a submission.  Its purpose is to verify the
subject-disjoint training, evaluation, and single-checkpoint pipeline while
raw IMU acquisition is blocked by storage or hosting limits.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from importlib import metadata
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, recall_score


EXPECTED_INDEX_SHA256 = (
    "b8899369d158c8fe6c8c20fce1bed21a8340026c541013b6c90f7cd5595b0f6b"
)
EXPECTED_SUBJECTS = set(range(1, 10)) | set(range(16, 25))
EXPECTED_CLASSES = set(range(40))
FOLDS = {
    "fold_0": {3, 6, 9, 18, 21, 24},
    "fold_1": {2, 5, 8, 17, 20, 23},
    "fold_2": {1, 4, 7, 16, 19, 22},
}
COUNT_COLUMNS = ["WTLA", "WTC", "WTRA", "WTRL", "WTLL"]
FLAG_COLUMNS = ["has_up", "has_down", "has_data_up", "has_data_down"]
FORBIDDEN_FEATURE_COLUMNS = {
    "activity_id",
    "activity_id_num",
    "user_id",
    "user_id_num",
    "identifier_id",
    "up_path",
    "down_path",
    "data_type",
}

# Frozen before the first training run on 2026-09-11.
GATE = {
    "required_subject_overlap_each_fold": 0,
    "required_clip_overlap_each_fold": 0,
    "minimum_fold_accuracy_gain_over_majority": 0.02,
    "minimum_mean_accuracy_gain_over_majority": 0.05,
    "minimum_mean_macro_recall": 0.10,
    "maximum_checkpoint_bytes_exclusive": 100_000_000,
    "required_checkpoint_files": 1,
}
BASE_SEED = 20260911


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(series: pd.Series) -> np.ndarray:
    normalized = series.astype(str).str.strip().str.lower()
    unexpected = sorted(set(normalized) - {"true", "false"})
    if unexpected:
        raise ValueError(f"Unexpected boolean values: {unexpected}")
    return (normalized == "true").to_numpy(dtype=np.float32)


def build_features(frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Create features from row counts and availability flags only."""
    counts = frame[COUNT_COLUMNS].to_numpy(dtype=np.float32)
    if not np.isfinite(counts).all() or (counts < 0).any():
        raise ValueError("IMU count columns must contain finite non-negative values")

    blocks = [counts, np.log1p(counts)]
    names = COUNT_COLUMNS.copy() + [f"log1p_{name}" for name in COUNT_COLUMNS]

    summaries = np.column_stack(
        [
            counts.sum(axis=1),
            counts.mean(axis=1),
            counts.std(axis=1),
            counts.min(axis=1),
            counts.max(axis=1),
            counts.max(axis=1) - counts.min(axis=1),
            (counts > 0).sum(axis=1),
        ]
    ).astype(np.float32)
    blocks.append(summaries)
    names.extend(
        [
            "count_total",
            "count_mean",
            "count_std",
            "count_min",
            "count_max",
            "count_range",
            "nonzero_device_count",
        ]
    )

    totals = np.maximum(counts.sum(axis=1, keepdims=True), 1.0)
    blocks.append((counts / totals).astype(np.float32))
    names.extend([f"share_{name}" for name in COUNT_COLUMNS])

    flags = np.column_stack([parse_bool(frame[name]) for name in FLAG_COLUMNS])
    blocks.append(flags)
    names.extend(FLAG_COLUMNS)

    if set(names) & FORBIDDEN_FEATURE_COLUMNS:
        raise AssertionError("Forbidden identifier or label leaked into features")
    features = np.column_stack(blocks).astype(np.float32)
    if features.shape[1] != len(names):
        raise AssertionError("Feature matrix/schema mismatch")
    return features, names


def make_model(seed: int) -> ExtraTreesClassifier:
    return ExtraTreesClassifier(
        n_estimators=256,
        max_depth=18,
        min_samples_leaf=2,
        max_features="sqrt",
        class_weight="balanced",
        random_state=seed,
        n_jobs=1,
    )


def package_version_and_license(distribution: str) -> dict[str, str | None]:
    package = metadata.metadata(distribution)
    return {
        "version": metadata.version(distribution),
        "license_expression": package.get("License-Expression"),
        "license_field": package.get("License"),
        "homepage": package.get("Home-page"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("index_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    input_path = args.index_csv.resolve()
    output_dir = args.output_dir.resolve()
    input_hash = sha256(input_path)
    if input_hash != EXPECTED_INDEX_SHA256:
        raise ValueError(
            f"Unexpected organizer index hash: {input_hash}; "
            f"expected {EXPECTED_INDEX_SHA256}"
        )

    frame = pd.read_csv(input_path)
    required = set(COUNT_COLUMNS + FLAG_COLUMNS) | {
        "activity_id",
        "activity_id_num",
        "user_id",
        "user_id_num",
        "identifier_id",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    subjects = frame["user_id_num"].astype(int).to_numpy()
    labels = frame["activity_id_num"].astype(int).to_numpy()
    if set(subjects) != EXPECTED_SUBJECTS:
        raise ValueError("Unexpected training-subject set")
    if set(labels) != EXPECTED_CLASSES:
        raise ValueError("Unexpected class set")
    clip_keys = (
        frame["activity_id"].astype(str)
        + "/"
        + frame["user_id"].astype(str)
        + "/"
        + frame["identifier_id"].astype(str)
    ).to_numpy()
    if len(set(clip_keys)) != len(clip_keys):
        raise ValueError("Duplicate clip identifiers in organizer index")

    features, feature_names = build_features(frame)
    fold_reports: list[dict[str, object]] = []
    oof_predictions = np.full(len(frame), -1, dtype=np.int64)

    for fold_number, (fold_name, valid_subjects) in enumerate(FOLDS.items()):
        valid_mask = np.isin(subjects, sorted(valid_subjects))
        train_mask = ~valid_mask
        train_subjects = set(subjects[train_mask])
        actual_valid_subjects = set(subjects[valid_mask])
        subject_overlap = len(train_subjects & actual_valid_subjects)
        train_clips = set(clip_keys[train_mask])
        valid_clips = set(clip_keys[valid_mask])
        clip_overlap = len(train_clips & valid_clips)
        if actual_valid_subjects != valid_subjects:
            raise AssertionError(f"{fold_name} subject assignment changed")
        if subject_overlap or clip_overlap:
            raise AssertionError(f"{fold_name} leakage guard failed")

        train_labels = labels[train_mask]
        values, counts = np.unique(train_labels, return_counts=True)
        majority_label = int(values[np.argmax(counts)])
        majority_predictions = np.full(valid_mask.sum(), majority_label)
        majority_accuracy = float(
            accuracy_score(labels[valid_mask], majority_predictions)
        )
        majority_macro_recall = float(
            recall_score(
                labels[valid_mask],
                majority_predictions,
                labels=sorted(EXPECTED_CLASSES),
                average="macro",
                zero_division=0,
            )
        )

        model = make_model(BASE_SEED + fold_number)
        model.fit(features[train_mask], train_labels)
        predictions = model.predict(features[valid_mask]).astype(np.int64)
        oof_predictions[valid_mask] = predictions
        accuracy = float(accuracy_score(labels[valid_mask], predictions))
        macro_recall = float(
            recall_score(
                labels[valid_mask],
                predictions,
                labels=sorted(EXPECTED_CLASSES),
                average="macro",
                zero_division=0,
            )
        )
        per_subject_accuracy = {
            str(subject): float(
                accuracy_score(
                    labels[valid_mask & (subjects == subject)],
                    oof_predictions[valid_mask & (subjects == subject)],
                )
            )
            for subject in sorted(valid_subjects)
        }
        fold_reports.append(
            {
                "fold": fold_name,
                "train_clips": int(train_mask.sum()),
                "valid_clips": int(valid_mask.sum()),
                "train_subjects": sorted(int(value) for value in train_subjects),
                "valid_subjects": sorted(int(value) for value in valid_subjects),
                "subject_overlap": subject_overlap,
                "clip_overlap": clip_overlap,
                "accuracy": accuracy,
                "macro_recall": macro_recall,
                "majority_label": majority_label,
                "majority_accuracy": majority_accuracy,
                "majority_macro_recall": majority_macro_recall,
                "accuracy_gain_over_majority": accuracy - majority_accuracy,
                "per_subject_accuracy": per_subject_accuracy,
            }
        )

    if (oof_predictions < 0).any():
        raise AssertionError("Some training clips did not receive OOF predictions")

    mean_accuracy = float(np.mean([row["accuracy"] for row in fold_reports]))
    mean_macro_recall = float(
        np.mean([row["macro_recall"] for row in fold_reports])
    )
    mean_majority_accuracy = float(
        np.mean([row["majority_accuracy"] for row in fold_reports])
    )
    oof_accuracy = float(accuracy_score(labels, oof_predictions))
    oof_macro_recall = float(
        recall_score(
            labels,
            oof_predictions,
            labels=sorted(EXPECTED_CLASSES),
            average="macro",
            zero_division=0,
        )
    )

    final_model = make_model(BASE_SEED)
    final_model.fit(features, labels)
    checkpoint = {
        "format_version": 1,
        "purpose": "CUHK-X IMU-index metadata-only engineering smoke",
        "non_llm": True,
        "submission_eligible": False,
        "model": final_model,
        "feature_names": feature_names,
        "classes": sorted(EXPECTED_CLASSES),
        "input_index_sha256": input_hash,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "checkpoint.joblib"
    temporary_checkpoint = output_dir / "checkpoint.joblib.tmp"
    joblib.dump(checkpoint, temporary_checkpoint, compress=3)
    os.replace(temporary_checkpoint, checkpoint_path)
    checkpoint_size = checkpoint_path.stat().st_size
    checkpoint_hash = sha256(checkpoint_path)

    gate_checks = {
        "subject_overlap_each_fold": all(
            row["subject_overlap"] == GATE["required_subject_overlap_each_fold"]
            for row in fold_reports
        ),
        "clip_overlap_each_fold": all(
            row["clip_overlap"] == GATE["required_clip_overlap_each_fold"]
            for row in fold_reports
        ),
        "fold_accuracy_gain_over_majority": all(
            row["accuracy_gain_over_majority"]
            >= GATE["minimum_fold_accuracy_gain_over_majority"]
            for row in fold_reports
        ),
        "mean_accuracy_gain_over_majority": (
            mean_accuracy - mean_majority_accuracy
            >= GATE["minimum_mean_accuracy_gain_over_majority"]
        ),
        "mean_macro_recall": mean_macro_recall
        >= GATE["minimum_mean_macro_recall"],
        "checkpoint_size": checkpoint_size
        < GATE["maximum_checkpoint_bytes_exclusive"],
        "single_checkpoint_file": checkpoint_path.is_file(),
        "non_llm": True,
        "test_data_read": False,
        "submission_created": False,
    }
    passed = all(gate_checks.values())
    report = {
        "decision": "PROMOTE_TO_RAW_IMU_ACQUISITION" if passed else "REJECT",
        "submission_eligible": False,
        "submission_created": False,
        "test_data_read": False,
        "experiment_scope": (
            "Metadata-only IMU engineering smoke; not a competition candidate"
        ),
        "promotion_gate": GATE,
        "gate_checks": gate_checks,
        "source": {
            "path": str(input_path),
            "sha256": input_hash,
            "rows": len(frame),
            "subjects": sorted(int(value) for value in set(subjects)),
            "classes": len(set(labels)),
        },
        "features": {
            "count": len(feature_names),
            "names": feature_names,
            "forbidden_columns_excluded": sorted(FORBIDDEN_FEATURE_COLUMNS),
        },
        "model": {
            "family": "scikit-learn ExtraTreesClassifier",
            "parameters": final_model.get_params(),
            "pretrained_weights": False,
            "external_data": False,
            "non_llm": True,
        },
        "validation": {
            "protocol": "three fixed subject-disjoint and clip-disjoint folds",
            "folds": fold_reports,
            "mean_accuracy": mean_accuracy,
            "mean_macro_recall": mean_macro_recall,
            "mean_majority_accuracy": mean_majority_accuracy,
            "mean_accuracy_gain_over_majority": (
                mean_accuracy - mean_majority_accuracy
            ),
            "pooled_oof_accuracy": oof_accuracy,
            "pooled_oof_macro_recall": oof_macro_recall,
        },
        "checkpoint": {
            "files": [checkpoint_path.name],
            "count": 1,
            "bytes": checkpoint_size,
            "sha256": checkpoint_hash,
            "limit_bytes_exclusive": GATE["maximum_checkpoint_bytes_exclusive"],
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "dependency_provenance": {
            "scikit-learn": package_version_and_license("scikit-learn"),
            "joblib": package_version_and_license("joblib"),
        },
        "limitations": [
            "Features are organizer-published row counts, not raw IMU signals.",
            "No test archive or test feature was opened or generated.",
            "Passing this smoke only promotes selective raw-IMU acquisition; it does not authorize a Kaggle submission.",
        ],
    }
    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
