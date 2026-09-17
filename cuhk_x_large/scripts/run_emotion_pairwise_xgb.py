#!/usr/bin/env python3
"""Pairwise option-ranking XGBoost specialist for HAU emotion questions."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBClassifier


LABELS = "ABCD"
USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]
SEED = 20260909


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    return {"hasitly": "hastily", "serioiusly": "seriously", "tensly": "tensely"}.get(text, text)


def motion_columns() -> np.ndarray:
    columns = []
    for device in range(5):
        start = device * 131
        for statistic in range(7):
            columns.extend(range(start + statistic * 16, start + statistic * 16 + 6))
        columns.extend(range(start + 112, start + 131))
    return np.asarray(columns)


def model() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.70,
        min_child_weight=3,
        reg_lambda=3,
        n_jobs=-1,
        random_state=SEED,
        eval_metric="logloss",
    )


def expand(
    features: np.ndarray,
    frame: pd.DataFrame,
    option_index: dict[str, int],
    with_targets: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    rows = []
    targets = []
    for feature, (_, row) in zip(features, frame.iterrows()):
        for label in LABELS:
            onehot = np.zeros(len(option_index), dtype=np.float32)
            onehot[option_index[norm(row[label])]] = 1.0
            rows.append(np.concatenate((feature, onehot)))
            if with_targets:
                targets.append(int(label == row["answer"]))
    return np.asarray(rows, dtype=np.float32), np.asarray(targets, dtype=np.int8) if with_targets else None


def rank_rows(probability: np.ndarray) -> tuple[list[str], list[float]]:
    matrix = probability.reshape(-1, 4)
    predictions = []
    margins = []
    for scores in matrix:
        order = np.argsort(-scores, kind="stable")
        predictions.append(LABELS[int(order[0])])
        margins.append(float(scores[order[0]] - scores[order[1]]))
    return predictions, margins


def test_unit(path: str) -> str:
    match = re.search(r"large_model_track_test/LM_test_\d+", path)
    if not match:
        raise ValueError(path)
    return "Testing/" + match.group(0)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    feature_path = root / "cache/nonvisual_features.npz"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    parent_oof_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    parent_test_path = root / "candidates/public_fususu_077777.csv"
    oof_path = root / "artifacts/oof/emotion_pairwise_xgb_oof.csv"
    test_output_path = root / "artifacts/predictions/emotion_pairwise_xgb_test.csv"
    model_path = root / "artifacts/models/emotion_pairwise_xgb_v1.joblib"
    summary_path = root / "reports/emotion_pairwise_xgb_summary.json"

    started = time.perf_counter()
    data = np.load(feature_path)
    units = data["units"].astype(str)
    index = {unit: row for row, unit in enumerate(units)}
    imu = data["imu"].astype(np.float32)[:, motion_columns()]
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    frame = train[(train["source"] == "HAU") & (train["category"] == "emotion")].copy()
    frame["user"] = frame["path"].str.extract(r"user(\d+)").astype(int)
    if sorted(frame["user"].unique().tolist()) != USERS:
        raise ValueError("Unexpected subjects")
    option_values = sorted({norm(value) for value in frame[list(LABELS)].to_numpy().ravel()})
    option_index = {value: position for position, value in enumerate(option_values)}

    def features_for(paths: list[str], testing: bool = False) -> tuple[np.ndarray, np.ndarray]:
        result = np.full((len(paths), imu.shape[1]), np.nan, dtype=np.float32)
        present = np.zeros(len(paths), dtype=bool)
        for row, path in enumerate(paths):
            unit = test_unit(path) if testing else "Training/" + path
            if unit in index:
                result[row] = imu[index[unit]]
                present[row] = True
        return result, present

    x, _ = features_for(frame["path"].tolist())
    parts = []
    for held_user in USERS:
        print(f"fold user{held_user}", flush=True)
        fit = frame["user"].to_numpy() != held_user
        valid = ~fit
        train_x, train_y = expand(x[fit], frame[fit], option_index, with_targets=True)
        estimator = model().fit(train_x, train_y)
        valid_x, _ = expand(x[valid], frame[valid], option_index, with_targets=False)
        probability = estimator.predict_proba(valid_x)[:, 1]
        predictions, margins = rank_rows(probability)
        rows = frame[valid]
        parts.append(
            pd.DataFrame(
                {
                    "qa_id": rows["qa_id"].to_numpy(),
                    "user": held_user,
                    "answer": rows["answer"].to_numpy(),
                    "prediction": predictions,
                    "confidence": margins,
                }
            )
        )
    oof = pd.concat(parts, ignore_index=True)
    parent_oof = pd.read_csv(parent_oof_path, dtype=str, keep_default_na=False)[["qa_id", "prediction"]]
    parent_oof = parent_oof.rename(columns={"prediction": "parent_prediction"})
    oof = oof.merge(parent_oof, on="qa_id", how="left", validate="one_to_one")
    oof["correct"] = oof["prediction"] == oof["answer"]
    oof["parent_correct"] = oof["parent_prediction"] == oof["answer"]
    by_user = oof.groupby("user")["correct"].mean()

    gates = {}
    for threshold in (0.00, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40):
        use = (oof["prediction"] != oof["parent_prediction"]) & (oof["confidence"] >= threshold)
        fused = oof["parent_prediction"].where(~use, oof["prediction"])
        correct = fused == oof["answer"]
        gates[f"{threshold:.2f}"] = {
            "overrides": int(use.sum()),
            "accuracy": float(correct.mean()),
            "net_correct_vs_parent": int(correct.sum() - oof["parent_correct"].sum()),
            "worst_subject_accuracy": float(correct.groupby(oof["user"]).mean().min()),
        }

    full_x, full_y = expand(x, frame, option_index, with_targets=True)
    final_model = model().fit(full_x, full_y)
    test_frame = test[(test["source"] == "HAU") & (test["category"] == "emotion")].copy()
    test_x, sensor_present = features_for(test_frame["path"].tolist(), testing=True)
    expanded_test, _ = expand(test_x, test_frame, option_index, with_targets=False)
    test_probability = final_model.predict_proba(expanded_test)[:, 1]
    test_predictions, test_margins = rank_rows(test_probability)
    test_output = pd.DataFrame(
        {
            "qa_id": test_frame["qa_id"].to_numpy(),
            "prediction": test_predictions,
            "confidence": test_margins,
            "sensor_present": sensor_present,
        }
    )
    parent_test = pd.read_csv(parent_test_path, dtype=str, keep_default_na=False)
    test_output = test_output.merge(
        parent_test.rename(columns={"prediction": "parent_prediction"}),
        on="qa_id",
        how="left",
        validate="one_to_one",
    )

    oof_path.parent.mkdir(parents=True, exist_ok=True)
    test_output_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    oof.to_csv(oof_path, index=False)
    test_output.to_csv(test_output_path, index=False)
    joblib.dump({"model": final_model, "option_index": option_index, "motion_columns": motion_columns()}, model_path, compress=3)
    summary = {
        "experiment": "hau_emotion_pairwise_option_ranking_xgb_v1",
        "seed": SEED,
        "validation": "18-fold leave-one-subject-out; one clip per fold only",
        "rows": int(len(oof)),
        "feature_count": int(x.shape[1]),
        "option_vocab_count": len(option_index),
        "overall_accuracy": float(oof["correct"].mean()),
        "parent_accuracy": float(oof["parent_correct"].mean()),
        "worst_subject_accuracy": float(by_user.min()),
        "best_subject_accuracy": float(by_user.max()),
        "by_user": {str(user): float(value) for user, value in by_user.items()},
        "fixed_threshold_overlays": gates,
        "test_disagreements_vs_parent": int((test_output["prediction"] != test_output["parent_prediction"]).sum()),
        "test_sensor_present": int(test_output["sensor_present"].sum()),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "xgboost": xgboost.__version__},
        "data_sha256": sha256(train_path),
        "feature_cache_sha256": sha256(feature_path),
        "oof_sha256": sha256(oof_path),
        "test_predictions_sha256": sha256(test_output_path),
        "model_sha256": sha256(model_path),
        "runtime_seconds": time.perf_counter() - started,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
