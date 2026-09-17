#!/usr/bin/env python3
"""Validate a CUHK-X Large Model Track submission against official local files."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path


LABELS = "ABCD"
SINGLE_CATEGORIES = {"single", "combination", "emotion", "object_interaction"}


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def valid_prediction(value: str, category: str) -> bool:
    if not value or any(char not in LABELS for char in value):
        return False
    if len(set(value)) != len(value):
        return False
    if category in SINGLE_CATEGORIES:
        return len(value) == 1
    if category == "multi":
        return 1 <= len(value) <= 4 and value == "".join(sorted(value))
    if category == "sequence":
        return len(value) == 4 and set(value) == set(LABELS)
    return False


def file_hash(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def main() -> None:
    campaign_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument(
        "--test", type=Path, default=campaign_root / "data/raw/kaggle/test_qa.csv"
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=campaign_root / "data/raw/kaggle/sample_submission.csv",
    )
    args = parser.parse_args()

    sample_columns, sample_rows = read_csv(args.sample)
    test_columns, test_rows = read_csv(args.test)
    submission_columns, submission_rows = read_csv(args.submission)
    assert sample_columns == ["qa_id", "prediction"]
    assert submission_columns == sample_columns, submission_columns
    assert len(submission_rows) == len(test_rows) == len(sample_rows) == 682

    expected_ids = [row["qa_id"] for row in test_rows]
    received_ids = [row["qa_id"] for row in submission_rows]
    assert received_ids == expected_ids, "Submission IDs/order do not match test_qa.csv"
    assert len(set(received_ids)) == len(received_ids), "Duplicate qa_id"

    invalid = [
        row["qa_id"]
        for row, test_row in zip(submission_rows, test_rows)
        if not valid_prediction(row["prediction"].strip().upper(), test_row["category"])
    ]
    assert not invalid, f"Invalid category grammar for IDs: {invalid[:10]}"

    category_counts = Counter(row["category"] for row in test_rows)
    print(f"PASS rows={len(submission_rows)} columns={submission_columns}")
    print("categories=" + ",".join(f"{key}:{value}" for key, value in sorted(category_counts.items())))
    print(f"md5={file_hash(args.submission, 'md5')}")
    print(f"sha256={file_hash(args.submission, 'sha256')}")


if __name__ == "__main__":
    main()

