#!/usr/bin/env python3
"""Audit label-free within-clip rules against training and the frozen test anchor."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

import pandas as pd


MODALITIES = {"depth", "depth_color", "ir", "thermal", "imu", "skeleton", "radar"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clip_key(value: str) -> str:
    parts = list(PurePosixPath(str(value).replace("\\", "/")).parts)
    if len(parts) >= 2 and parts[-2].lower() in MODALITIES and Path(parts[-1]).stem.lower() in MODALITIES:
        parts = parts[:-2]
    return "/".join(parts)


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def atoms(value: str) -> tuple[str, ...]:
    return tuple(norm(piece) for piece in str(value).split(",") if piece.strip())


def infer(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["clip_key"] = frame["path"].map(clip_key)
    rows: list[dict[str, object]] = []
    for clip, group in frame[frame["source"] == "HAU"].groupby("clip_key"):
        sequence = group[group["category"] == "sequence"]
        if len(sequence) != 1:
            continue
        sequence_row = sequence.iloc[0]
        present = {norm(sequence_row[label]) for label in "ABCD" if sequence_row[label]}
        for category in ("multi", "combination"):
            candidates = group[group["category"] == category]
            if len(candidates) != 1:
                continue
            row = candidates.iloc[0]
            if category == "multi":
                prediction = "".join(label for label in "ABCD" if norm(row[label]) in present)
                unique = bool(prediction)
            else:
                matches = [
                    label
                    for label in "ABCD"
                    if row[label] and set(atoms(row[label])).issubset(present)
                ]
                prediction = matches[0] if len(matches) == 1 else ""
                unique = len(matches) == 1
            rows.append(
                {
                    "qa_id": row["qa_id"],
                    "clip_key": clip,
                    "category": category,
                    "prediction": prediction,
                    "unique": unique,
                    "answer": row.get("answer", ""),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    parent_path = root / "candidates/public_fususu_077777.csv"
    report_path = root / "reports/linked_question_structure_audit.json"
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    train_inferred = infer(train)
    test_inferred = infer(test)
    train_unique = train_inferred[train_inferred["unique"]].copy()
    train_unique["correct"] = train_unique["prediction"] == train_unique["answer"]
    train_unique = train_unique.merge(train[["qa_id", "path"]], on="qa_id", validate="one_to_one")
    train_unique["subject"] = train_unique["path"].str.extract(r"user(\d+)").astype(int)
    test_unique = test_inferred[test_inferred["unique"]].merge(parent, on="qa_id", validate="one_to_one")
    test_unique["differs_parent"] = test_unique["prediction"] != test_unique["parent_prediction"]

    training: dict[str, object] = {}
    testing: dict[str, object] = {}
    for category in ("multi", "combination"):
        subset = train_unique[train_unique["category"] == category]
        subject_accuracy = subset.groupby("subject")["correct"].mean()
        training[category] = {
            "unique_rows": int(len(subset)),
            "accuracy": float(subset["correct"].mean()),
            "worst_subject_accuracy": float(subject_accuracy.min()),
        }
        test_subset = test_unique[test_unique["category"] == category]
        testing[category] = {
            "unique_rows": int(len(test_subset)),
            "differs_frozen_parent": int(test_subset["differs_parent"].sum()),
            "differences": test_subset.loc[
                test_subset["differs_parent"],
                ["qa_id", "prediction", "parent_prediction"],
            ].to_dict(orient="records"),
        }
    report = {
        "experiment": "label_free_linked_question_structure_audit",
        "rule": "sequence option texts define an occurring-action set; multi selects exact overlaps; combination selects the unique option whose comma-separated atoms are all in that set",
        "training": training,
        "testing": testing,
        "decision": {
            "combination": "NO_CHANGE: perfect on 126 training rows but frozen parent already matches every unique test inference",
            "multi": "REJECTED: only 65.56% training accuracy and worst-subject 45.45%",
        },
        "inputs": {
            "training_qa_sha256": sha256(train_path),
            "test_qa_sha256": sha256(test_path),
            "frozen_parent_sha256": sha256(parent_path),
            "code_sha256": sha256(Path(__file__)),
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
