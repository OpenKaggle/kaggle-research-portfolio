#!/usr/bin/env python3
"""Screen honest HAU emotion feature families with leave-one-subject-out CV."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


LABELS = "ABCD"
SEED = 20260909
USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    return {"hasitly": "hastily", "serioiusly": "seriously", "tensly": "tensely"}.get(text, text)


def prediction(row: pd.Series, probability: np.ndarray, classes: np.ndarray) -> str:
    scores = {norm(label): float(value) for label, value in zip(classes, probability)}
    return max(LABELS, key=lambda label: (scores.get(norm(row[label]), 0.0), -LABELS.index(label)))


def imu_columns(kind: str) -> np.ndarray:
    selected = []
    for device in range(5):
        start = device * 131
        if kind == "spectral":
            selected.extend(range(start + 112, start + 131))
        elif kind == "motion":
            for statistic in range(7):
                selected.extend(range(start + statistic * 16, start + statistic * 16 + 6))
            selected.extend(range(start + 112, start + 131))
        else:
            raise ValueError(kind)
    return np.asarray(selected)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    feature_path = root / "cache/nonvisual_features.npz"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    output_path = root / "reports/emotion_feature_ablation.json"
    data = np.load(feature_path)
    units = data["units"].astype(str)
    index = {unit: row for row, unit in enumerate(units)}
    imu = data["imu"].astype(np.float32)
    skeleton = data["skeleton"].astype(np.float32)
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    frame = train[(train["source"] == "HAU") & (train["category"] == "emotion")].copy()
    frame["user"] = frame["path"].str.extract(r"user(\d+)").astype(int)
    frame["target"] = frame.apply(lambda row: norm(row[row["answer"]]), axis=1)
    row_indices = np.asarray([index.get("Training/" + path, -1) for path in frame["path"]])

    all_imu = np.full((len(frame), imu.shape[1]), np.nan, dtype=np.float32)
    all_skeleton = np.full((len(frame), skeleton.shape[1]), np.nan, dtype=np.float32)
    present = row_indices >= 0
    all_imu[present] = imu[row_indices[present]]
    all_skeleton[present] = skeleton[row_indices[present]]
    motion = imu_columns("motion")
    spectral = imu_columns("spectral")
    configs = {
        "imu_all_sqrt": (all_imu, "sqrt", 1),
        "imu_motion_sqrt": (all_imu[:, motion], "sqrt", 1),
        "imu_spectral_sqrt": (all_imu[:, spectral], "sqrt", 1),
        "skeleton_sqrt": (all_skeleton, "sqrt", 1),
        "combined_sqrt": (np.concatenate((all_imu, all_skeleton), axis=1), "sqrt", 1),
        "imu_motion_mf025_leaf2": (all_imu[:, motion], 0.25, 2),
    }

    started = time.perf_counter()
    results = {}
    users = frame["user"].to_numpy()
    target = frame["target"].to_numpy()
    for name, (features, max_features, leaf) in configs.items():
        print(name, flush=True)
        parts = []
        for held_user in USERS:
            fit = users != held_user
            valid = ~fit
            model = RandomForestClassifier(
                n_estimators=120,
                max_features=max_features,
                min_samples_leaf=leaf,
                class_weight="balanced_subsample",
                n_jobs=-1,
                random_state=SEED,
            ).fit(features[fit], target[fit])
            probabilities = model.predict_proba(features[valid])
            rows = frame[valid]
            predictions = [prediction(row, probability, model.classes_) for probability, (_, row) in zip(probabilities, rows.iterrows())]
            parts.append(pd.DataFrame({"qa_id": rows["qa_id"], "user": held_user, "answer": rows["answer"], "prediction": predictions}))
        oof = pd.concat(parts, ignore_index=True)
        oof["correct"] = oof["prediction"] == oof["answer"]
        by_user = oof.groupby("user")["correct"].mean()
        results[name] = {
            "feature_count": int(features.shape[1]),
            "overall_accuracy": float(oof["correct"].mean()),
            "worst_subject_accuracy": float(by_user.min()),
            "best_subject_accuracy": float(by_user.max()),
            "by_user": {str(user): float(value) for user, value in by_user.items()},
        }
    report = {
        "experiment": "hau_emotion_feature_ablation_loso",
        "seed": SEED,
        "trees_per_fold": 120,
        "subjects": USERS,
        "rows": int(len(frame)),
        "train_sha256": sha256(train_path),
        "feature_cache_sha256": sha256(feature_path),
        "results": results,
        "runtime_seconds": time.perf_counter() - started,
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
