#!/usr/bin/env python3
"""Subject-disjoint pairwise sensor model for HAU multi-answer questions."""

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
THRESHOLDS = tuple(np.arange(0.30, 0.701, 0.05).round(2))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


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
    targets: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    rows = []
    y = []
    for feature, (_, row) in zip(features, frame.iterrows()):
        positives = set(str(row["answer"])) if targets else set()
        for label in LABELS:
            onehot = np.zeros(len(option_index), dtype=np.float32)
            onehot[option_index[norm(row[label])]] = 1.0
            rows.append(np.concatenate((feature, onehot)))
            if targets:
                y.append(int(label in positives))
    return np.asarray(rows, dtype=np.float32), np.asarray(y, dtype=np.int8) if targets else None


def decode(probabilities: np.ndarray, threshold: float) -> tuple[list[str], list[float]]:
    matrix = probabilities.reshape(-1, 4)
    predictions = []
    confidence = []
    for scores in matrix:
        chosen = [index for index, score in enumerate(scores) if score >= threshold]
        if not chosen:
            chosen = [int(np.argmax(scores))]
        predictions.append("".join(LABELS[index] for index in chosen))
        confidence.append(float(np.min(np.abs(scores - threshold))))
    return predictions, confidence


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
    oof_path = root / "artifacts/oof/multi_pairwise_xgb_oof.csv"
    test_output_path = root / "artifacts/predictions/multi_pairwise_xgb_test.csv"
    model_path = root / "artifacts/models/multi_pairwise_xgb_v1.joblib"
    summary_path = root / "reports/multi_pairwise_xgb_summary.json"
    started = time.perf_counter()

    data = np.load(feature_path)
    units = data["units"].astype(str)
    unit_index = {unit: index for index, unit in enumerate(units)}
    imu = data["imu"].astype(np.float32)[:, motion_columns()]
    skeleton = data["skeleton"].astype(np.float32)
    features = np.concatenate((imu, skeleton), axis=1)
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    frame = train[(train["source"] == "HAU") & (train["category"] == "multi")].copy()
    frame["user"] = frame["path"].str.extract(r"user(\d+)").astype(int)
    if sorted(frame["user"].unique().tolist()) != USERS:
        raise ValueError("Unexpected subjects")
    option_values = sorted({norm(value) for value in frame[list(LABELS)].to_numpy().ravel()})
    option_index = {value: position for position, value in enumerate(option_values)}

    def features_for(paths: list[str], testing: bool = False) -> tuple[np.ndarray, np.ndarray]:
        result = np.full((len(paths), features.shape[1]), np.nan, dtype=np.float32)
        present = np.zeros(len(paths), dtype=bool)
        for row, path in enumerate(paths):
            unit = test_unit(path) if testing else "Training/" + path
            if unit in unit_index:
                result[row] = features[unit_index[unit]]
                present[row] = True
        return result, present

    x, sensor_present = features_for(frame["path"].tolist())
    if not sensor_present.all():
        raise ValueError("Missing training sensor features")
    fold_probabilities = []
    for held_user in USERS:
        print(f"fold user{held_user}", flush=True)
        fit = frame["user"].to_numpy() != held_user
        valid = ~fit
        fit_x, fit_y = expand(x[fit], frame[fit], option_index, targets=True)
        estimator = model().fit(fit_x, fit_y)
        valid_x, _ = expand(x[valid], frame[valid], option_index, targets=False)
        probability = estimator.predict_proba(valid_x)[:, 1].reshape(-1, 4)
        rows = frame[valid]
        for index, (_, row) in enumerate(rows.iterrows()):
            fold_probabilities.append(
                {
                    "qa_id": row["qa_id"],
                    "user": held_user,
                    "answer": row["answer"],
                    **{f"prob_{label}": float(probability[index, offset]) for offset, label in enumerate(LABELS)},
                }
            )
    oof = pd.DataFrame(fold_probabilities)
    parent_oof = pd.read_csv(parent_oof_path, dtype=str, keep_default_na=False)[["qa_id", "prediction"]]
    oof = oof.merge(
        parent_oof.rename(columns={"prediction": "parent_prediction"}),
        on="qa_id",
        how="left",
        validate="one_to_one",
    )
    probability_matrix = oof[[f"prob_{label}" for label in LABELS]].to_numpy()
    threshold_metrics = {}
    for threshold in THRESHOLDS:
        predictions, confidence = decode(probability_matrix, float(threshold))
        correct = pd.Series(predictions, index=oof.index) == oof["answer"]
        by_user = correct.groupby(oof["user"]).mean()
        threshold_metrics[f"{threshold:.2f}"] = {
            "accuracy": float(correct.mean()),
            "correct": int(correct.sum()),
            "worst_subject_accuracy": float(by_user.min()),
            "mean_confidence": float(np.mean(confidence)),
        }
    selected_threshold = max(
        THRESHOLDS,
        key=lambda value: (
            threshold_metrics[f"{value:.2f}"]["accuracy"],
            threshold_metrics[f"{value:.2f}"]["worst_subject_accuracy"],
            -abs(value - 0.5),
        ),
    )
    predictions, confidence = decode(probability_matrix, float(selected_threshold))
    oof["prediction"] = predictions
    oof["confidence"] = confidence
    oof["correct"] = oof["prediction"] == oof["answer"]
    oof["parent_correct"] = oof["parent_prediction"] == oof["answer"]

    overlays = {}
    parent_correct = int(oof["parent_correct"].sum())
    for gate in (0.00, 0.02, 0.05, 0.10, 0.15, 0.20):
        use = (oof["prediction"] != oof["parent_prediction"]) & (oof["confidence"] >= gate)
        fused = oof["parent_prediction"].where(~use, oof["prediction"])
        correct = fused == oof["answer"]
        overlays[f"{gate:.2f}"] = {
            "overrides": int(use.sum()),
            "accuracy": float(correct.mean()),
            "net_correct_vs_parent": int(correct.sum() - parent_correct),
            "worst_subject_accuracy": float(correct.groupby(oof["user"]).mean().min()),
        }

    full_x, full_y = expand(x, frame, option_index, targets=True)
    final_model = model().fit(full_x, full_y)
    test_frame = test[(test["source"] == "HAU") & (test["category"] == "multi")].copy()
    test_x, test_present = features_for(test_frame["path"].tolist(), testing=True)
    expanded_test, _ = expand(test_x, test_frame, option_index, targets=False)
    test_probability = final_model.predict_proba(expanded_test)[:, 1]
    test_predictions, test_confidence = decode(test_probability, float(selected_threshold))
    test_output = pd.DataFrame(
        {
            "qa_id": test_frame["qa_id"].to_numpy(),
            "prediction": test_predictions,
            "confidence": test_confidence,
            "sensor_present": test_present,
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
    joblib.dump(
        {
            "model": final_model,
            "option_index": option_index,
            "feature_columns": {"imu": motion_columns(), "skeleton": "all"},
            "threshold": float(selected_threshold),
        },
        model_path,
        compress=3,
    )
    by_user = oof.groupby("user")["correct"].mean()
    summary = {
        "experiment": "hau_multi_pairwise_option_xgb_v1",
        "seed": SEED,
        "validation": "18-fold leave-one-subject-out; one row per clip/category; exact string-match metric",
        "rows": int(len(oof)),
        "feature_count": int(features.shape[1]),
        "feature_set": "305 IMU motion features + 650 skeleton summary features",
        "option_vocab_count": len(option_index),
        "threshold_selection": "maximize OOF exact-match accuracy, then worst-subject accuracy, then closeness to 0.5 over fixed grid",
        "threshold_metrics": threshold_metrics,
        "selected_threshold": float(selected_threshold),
        "overall_accuracy": float(oof["correct"].mean()),
        "parent_accuracy": float(oof["parent_correct"].mean()),
        "worst_subject_accuracy": float(by_user.min()),
        "by_user": {str(user): float(value) for user, value in by_user.items()},
        "fixed_confidence_overlays": overlays,
        "test_rows": int(len(test_output)),
        "test_sensor_present": int(test_output["sensor_present"].sum()),
        "test_disagreements_vs_parent": int((test_output["prediction"] != test_output["parent_prediction"]).sum()),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "xgboost": xgboost.__version__,
        },
        "inputs": {
            "training_qa_sha256": sha256(train_path),
            "feature_cache_sha256": sha256(feature_path),
            "parent_oof_sha256": sha256(parent_oof_path),
            "parent_test_sha256": sha256(parent_test_path),
        },
        "outputs": {
            "oof_sha256": sha256(oof_path),
            "test_predictions_sha256": sha256(test_output_path),
            "model_sha256": sha256(model_path),
        },
        "code_sha256": sha256(Path(__file__)),
        "runtime_seconds": time.perf_counter() - started,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"summary_sha256={sha256(summary_path)}")


if __name__ == "__main__":
    main()
