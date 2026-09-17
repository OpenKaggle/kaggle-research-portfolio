#!/usr/bin/env python3
"""Build and audit deterministic CUHK-X subject-disjoint validation folds.

This script consumes only the organizer-published IMU index.  It does not read
test samples, infer labels, train a model, or write files.  Its JSON output is a
data-readiness receipt for a later human-reviewed training run.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


FOLDS = {
    "fold_0": {3, 6, 9, 18, 21, 24},
    "fold_1": {2, 5, 8, 17, 20, 23},
    "fold_2": {1, 4, 7, 16, 19, 22},
}
EXPECTED_SUBJECTS = set(range(1, 10)) | set(range(16, 25))
EXPECTED_CLASSES = set(range(40))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment(subject: int) -> str:
    return "env_users_01_09" if subject <= 9 else "env_users_16_24"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("index_csv", type=Path)
    parser.add_argument(
        "--payload-root",
        type=Path,
        default=None,
        help="Optional extracted HAR/data root; used only for readiness checks.",
    )
    args = parser.parse_args()

    with args.index_csv.open(newline="", encoding="utf-8") as handle:
        raw_rows = list(csv.DictReader(handle))

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    duplicate_keys: list[str] = []
    for row in raw_rows:
        subject = int(row["user_id_num"])
        label = int(row["activity_id_num"])
        clip_key = f'{row["activity_id"]}/{row["user_id"]}/{row["identifier_id"]}'
        if clip_key in seen:
            duplicate_keys.append(clip_key)
        seen.add(clip_key)
        payload_ready = False
        if args.payload_root is not None:
            up = args.payload_root / row["up_path"]
            down = args.payload_root / row["down_path"]
            payload_ready = up.is_file() and down.is_file()
        rows.append(
            {
                "clip_key": clip_key,
                "subject": subject,
                "label": label,
                "environment": environment(subject),
                "payload_ready": payload_ready,
                "has_up": row["has_up"].lower() == "true",
                "has_down": row["has_down"].lower() == "true",
                "has_data_up": row["has_data_up"].lower() == "true",
                "has_data_down": row["has_data_down"].lower() == "true",
            }
        )

    subjects = {int(row["subject"]) for row in rows}
    classes = {int(row["label"]) for row in rows}
    assert subjects == EXPECTED_SUBJECTS, (subjects, EXPECTED_SUBJECTS)
    assert classes == EXPECTED_CLASSES, (classes, EXPECTED_CLASSES)
    assert not duplicate_keys, duplicate_keys[:5]
    held_out_union = set().union(*FOLDS.values())
    assert held_out_union == EXPECTED_SUBJECTS
    assert sum(len(users) for users in FOLDS.values()) == len(EXPECTED_SUBJECTS)

    fold_reports: dict[str, object] = {}
    for fold_name, valid_subjects in FOLDS.items():
        train = [row for row in rows if int(row["subject"]) not in valid_subjects]
        valid = [row for row in rows if int(row["subject"]) in valid_subjects]
        train_subjects = {int(row["subject"]) for row in train}
        actual_valid_subjects = {int(row["subject"]) for row in valid}
        train_clips = {str(row["clip_key"]) for row in train}
        valid_clips = {str(row["clip_key"]) for row in valid}
        assert train_subjects.isdisjoint(actual_valid_subjects)
        assert train_clips.isdisjoint(valid_clips)
        assert actual_valid_subjects == valid_subjects

        counts = Counter(int(row["label"]) for row in valid)
        env_counts = Counter(str(row["environment"]) for row in valid)
        train_counts = Counter(int(row["label"]) for row in train)
        majority_label, majority_support = max(
            train_counts.items(), key=lambda item: (item[1], -item[0])
        )
        majority_correct = [int(row["label"]) == majority_label for row in valid]
        per_subject_majority_accuracy = {}
        for subject in sorted(actual_valid_subjects):
            mask = [int(row["subject"]) == subject for row in valid]
            correct = [ok for ok, keep in zip(majority_correct, mask) if keep]
            per_subject_majority_accuracy[str(subject)] = sum(correct) / len(correct)
        per_environment_majority_accuracy = {}
        for env in sorted(env_counts):
            mask = [str(row["environment"]) == env for row in valid]
            correct = [ok for ok, keep in zip(majority_correct, mask) if keep]
            per_environment_majority_accuracy[env] = sum(correct) / len(correct)
        fold_reports[fold_name] = {
            "train_clips": len(train),
            "valid_clips": len(valid),
            "train_subjects": sorted(train_subjects),
            "valid_subjects": sorted(actual_valid_subjects),
            "subject_overlap": 0,
            "clip_overlap": 0,
            "valid_environment_counts": dict(sorted(env_counts.items())),
            "valid_class_min": min(counts.values()),
            "valid_class_max": max(counts.values()),
            "valid_classes_present": len(counts),
            "valid_missing_classes": sorted(EXPECTED_CLASSES - set(counts)),
            "majority_baseline": {
                "train_majority_label": majority_label,
                "train_majority_support": majority_support,
                "valid_accuracy": sum(majority_correct) / len(majority_correct),
                "valid_macro_recall": (
                    1.0 / len(counts) if majority_label in counts else 0.0
                ),
                "valid_per_subject_accuracy": per_subject_majority_accuracy,
                "valid_per_environment_accuracy": per_environment_majority_accuracy,
            },
        }

    report = {
        "status": "SPLITS_VALID_PAYLOAD_BLOCKED"
        if not all(bool(row["payload_ready"]) for row in rows)
        else "SPLITS_AND_PAYLOAD_VALID",
        "source": str(args.index_csv),
        "source_sha256": sha256(args.index_csv),
        "rows": len(rows),
        "subjects": sorted(subjects),
        "classes": len(classes),
        "payload_ready_clips": sum(bool(row["payload_ready"]) for row in rows),
        "index_missing_up": sum(not bool(row["has_up"]) for row in rows),
        "index_missing_down": sum(not bool(row["has_down"]) for row in rows),
        "index_empty_up": sum(not bool(row["has_data_up"]) for row in rows),
        "index_empty_down": sum(not bool(row["has_data_down"]) for row in rows),
        "folds": fold_reports,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
