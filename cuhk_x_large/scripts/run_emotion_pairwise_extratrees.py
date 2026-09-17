#!/usr/bin/env python3
"""Subject-disjoint ExtraTrees option-ranking specialist for HAU emotion."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from run_emotion_pairwise_xgb import (
    LABELS,
    SEED,
    USERS,
    expand,
    motion_columns,
    norm,
    rank_rows,
    test_unit,
)


XGB_THRESHOLD = 0.05


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def model() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            (
                "classifier",
                ExtraTreesClassifier(
                    n_estimators=500,
                    max_features="sqrt",
                    min_samples_leaf=2,
                    class_weight="balanced",
                    n_jobs=-1,
                    random_state=SEED,
                ),
            ),
        ]
    )


def gate_metrics(frame: pd.DataFrame, use: pd.Series, prediction_column: str) -> dict[str, object]:
    chosen = frame[use].copy()
    chosen["expert_correct"] = chosen[prediction_column] == chosen["answer"]
    chosen["parent_correct"] = chosen["parent_prediction"] == chosen["answer"]
    chosen["delta"] = chosen["expert_correct"].astype(int) - chosen["parent_correct"].astype(int)
    by_user_delta = chosen.groupby("user")["delta"].sum()
    overlay = frame["parent_prediction"].where(~use, frame[prediction_column])
    overlay_correct = overlay == frame["answer"]
    return {
        "rows": int(len(chosen)),
        "expert_correct": int(chosen["expert_correct"].sum()),
        "expert_accuracy": float(chosen["expert_correct"].mean()) if len(chosen) else None,
        "parent_correct": int(chosen["parent_correct"].sum()),
        "parent_accuracy": float(chosen["parent_correct"].mean()) if len(chosen) else None,
        "net_correct_vs_parent": int(chosen["delta"].sum()),
        "subjects": int(chosen["user"].nunique()),
        "worst_represented_subject_net": int(by_user_delta.min()) if len(by_user_delta) else None,
        "by_user_net": {str(int(user)): int(value) for user, value in by_user_delta.items()},
        "overlay_accuracy": float(overlay_correct.mean()),
        "overlay_worst_subject_accuracy": float(
            overlay_correct.groupby(frame["user"]).mean().min()
        ),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    feature_path = root / "cache/nonvisual_features.npz"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    parent_oof_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    parent_test_path = root / "candidates/public_fususu_077777.csv"
    graph_test_path = root / "artifacts/predictions/public_graph_test.csv"
    rf_oof_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    rf_test_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    xgb_oof_path = root / "artifacts/oof/emotion_pairwise_xgb_oof.csv"
    xgb_test_path = root / "artifacts/predictions/emotion_pairwise_xgb_test.csv"
    oof_path = root / "artifacts/oof/emotion_pairwise_extratrees_oof.csv"
    test_output_path = root / "artifacts/predictions/emotion_pairwise_extratrees_test.csv"
    model_path = root / "artifacts/models/emotion_pairwise_extratrees_v1.joblib"
    summary_path = root / "reports/emotion_pairwise_extratrees_summary.json"

    started = time.perf_counter()
    with np.load(feature_path) as data:
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
                present[row] = bool(np.isfinite(result[row]).any())
        return result, present

    x, train_present = features_for(frame["path"].tolist())
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
                    "sensor_present": train_present[valid],
                }
            )
        )
    oof = pd.concat(parts, ignore_index=True)
    parent_oof = pd.read_csv(parent_oof_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction"]
    ].rename(columns={"prediction": "parent_prediction"})
    oof = oof.merge(parent_oof, on="qa_id", validate="one_to_one")
    oof["correct"] = oof["prediction"] == oof["answer"]
    oof["parent_correct"] = oof["parent_prediction"] == oof["answer"]

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
        validate="one_to_one",
    )

    rf_oof = pd.read_csv(rf_oof_path, dtype=str, keep_default_na=False)
    rf_oof = rf_oof[(rf_oof["source"] == "HAU") & (rf_oof["category"] == "emotion")][
        ["qa_id", "prediction", "confidence"]
    ].rename(columns={"prediction": "rf_prediction", "confidence": "rf_confidence"})
    rf_oof["rf_confidence"] = rf_oof["rf_confidence"].astype(float)
    xgb_oof = pd.read_csv(xgb_oof_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction", "confidence"]
    ].rename(columns={"prediction": "xgb_prediction", "confidence": "xgb_confidence"})
    xgb_oof["xgb_confidence"] = xgb_oof["xgb_confidence"].astype(float)
    ensemble = (
        oof.rename(
            columns={"prediction": "et_prediction", "confidence": "et_confidence"}
        )
        .merge(rf_oof, on="qa_id", validate="one_to_one")
        .merge(xgb_oof, on="qa_id", validate="one_to_one")
    )
    differs_parent = lambda column: ensemble[column] != ensemble["parent_prediction"]
    gates = {
        "rf_xgb_existing": (
            (ensemble["rf_prediction"] == ensemble["xgb_prediction"])
            & differs_parent("rf_prediction")
            & (ensemble["xgb_confidence"] >= XGB_THRESHOLD)
        ),
        "rf_xgb_et_triple": (
            ensemble["sensor_present"]
            & (ensemble["rf_prediction"] == ensemble["xgb_prediction"])
            & (ensemble["rf_prediction"] == ensemble["et_prediction"])
            & differs_parent("rf_prediction")
            & (ensemble["xgb_confidence"] >= XGB_THRESHOLD)
        ),
        "et_xgb": (
            ensemble["sensor_present"]
            & (ensemble["et_prediction"] == ensemble["xgb_prediction"])
            & differs_parent("et_prediction")
            & (ensemble["xgb_confidence"] >= XGB_THRESHOLD)
        ),
        "et_rf": (
            ensemble["sensor_present"]
            & (ensemble["et_prediction"] == ensemble["rf_prediction"])
            & differs_parent("et_prediction")
        ),
    }
    gate_reports = {
        "rf_xgb_existing": gate_metrics(ensemble, gates["rf_xgb_existing"], "rf_prediction"),
        "rf_xgb_et_triple": gate_metrics(
            ensemble, gates["rf_xgb_et_triple"], "rf_prediction"
        ),
        "et_xgb": gate_metrics(ensemble, gates["et_xgb"], "et_prediction"),
        "et_rf": gate_metrics(ensemble, gates["et_rf"], "et_prediction"),
    }

    rf_test = pd.read_csv(rf_test_path, dtype=str, keep_default_na=False)
    rf_test = rf_test[(rf_test["source"] == "HAU") & (rf_test["category"] == "emotion")][
        ["qa_id", "prediction", "confidence", "sensor_present"]
    ].rename(
        columns={
            "prediction": "rf_prediction",
            "confidence": "rf_confidence",
            "sensor_present": "rf_present",
        }
    )
    rf_test["rf_present"] = rf_test["rf_present"].str.lower().eq("true")
    rf_test["rf_confidence"] = rf_test["rf_confidence"].astype(float)
    xgb_test = pd.read_csv(xgb_test_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction", "confidence", "sensor_present"]
    ].rename(
        columns={
            "prediction": "xgb_prediction",
            "confidence": "xgb_confidence",
            "sensor_present": "xgb_present",
        }
    )
    xgb_test["xgb_present"] = xgb_test["xgb_present"].str.lower().eq("true")
    xgb_test["xgb_confidence"] = xgb_test["xgb_confidence"].astype(float)
    graph_test = pd.read_csv(graph_test_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "graph_prediction"}
    )
    test_ensemble = (
        test_output.rename(
            columns={
                "prediction": "et_prediction",
                "confidence": "et_confidence",
                "sensor_present": "et_present",
            }
        )
        .merge(rf_test, on="qa_id", validate="one_to_one")
        .merge(xgb_test, on="qa_id", validate="one_to_one")
        .merge(graph_test, on="qa_id", validate="one_to_one")
    )
    common_test = (
        test_ensemble["et_present"]
        & test_ensemble["rf_present"]
        & test_ensemble["xgb_present"]
    )
    test_gates = {
        "rf_xgb_existing": common_test
        & (test_ensemble["rf_prediction"] == test_ensemble["xgb_prediction"])
        & (test_ensemble["rf_prediction"] != test_ensemble["parent_prediction"])
        & (test_ensemble["rf_prediction"] != test_ensemble["graph_prediction"])
        & (test_ensemble["xgb_confidence"] >= XGB_THRESHOLD),
        "rf_xgb_et_triple": common_test
        & (test_ensemble["rf_prediction"] == test_ensemble["xgb_prediction"])
        & (test_ensemble["rf_prediction"] == test_ensemble["et_prediction"])
        & (test_ensemble["rf_prediction"] != test_ensemble["parent_prediction"])
        & (test_ensemble["rf_prediction"] != test_ensemble["graph_prediction"])
        & (test_ensemble["xgb_confidence"] >= XGB_THRESHOLD),
        "et_xgb": common_test
        & (test_ensemble["et_prediction"] == test_ensemble["xgb_prediction"])
        & (test_ensemble["et_prediction"] != test_ensemble["parent_prediction"])
        & (test_ensemble["et_prediction"] != test_ensemble["graph_prediction"])
        & (test_ensemble["xgb_confidence"] >= XGB_THRESHOLD),
        "et_rf": common_test
        & (test_ensemble["et_prediction"] == test_ensemble["rf_prediction"])
        & (test_ensemble["et_prediction"] != test_ensemble["parent_prediction"])
        & (test_ensemble["et_prediction"] != test_ensemble["graph_prediction"]),
    }
    evidence_columns = [
        "qa_id", "parent_prediction", "graph_prediction", "rf_prediction", "rf_confidence",
        "xgb_prediction", "xgb_confidence", "et_prediction", "et_confidence",
    ]

    oof_path.parent.mkdir(parents=True, exist_ok=True)
    test_output_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    oof.to_csv(oof_path, index=False)
    test_output.to_csv(test_output_path, index=False)
    joblib.dump(
        {"model": final_model, "option_index": option_index, "motion_columns": motion_columns()},
        model_path,
        compress=3,
    )
    by_user = oof.groupby("user")["correct"].mean()
    fixed_threshold_overlays = {}
    for threshold in (0.00, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40):
        use = oof["sensor_present"] & (oof["prediction"] != oof["parent_prediction"]) & (
            oof["confidence"] >= threshold
        )
        fixed_threshold_overlays[f"{threshold:.2f}"] = gate_metrics(
            oof.rename(columns={"prediction": "et_prediction"}), use, "et_prediction"
        )
    summary = {
        "experiment": "hau_emotion_pairwise_option_ranking_extratrees_v1",
        "seed": SEED,
        "validation": "18-fold leave-one-subject-out; clips intact; fixed ExtraTrees configuration",
        "model": {
            "type": "fold-local median imputation + ExtraTreesClassifier",
            "n_estimators": 500,
            "max_features": "sqrt",
            "min_samples_leaf": 2,
            "class_weight": "balanced",
        },
        "rows": int(len(oof)),
        "sensor_present_rows": int(oof["sensor_present"].sum()),
        "feature_count": int(full_x.shape[1]),
        "option_vocab_count": len(option_index),
        "overall_accuracy": float(oof["correct"].mean()),
        "sensor_present_accuracy": float(oof.loc[oof["sensor_present"], "correct"].mean()),
        "parent_accuracy": float(oof["parent_correct"].mean()),
        "worst_subject_accuracy": float(by_user.min()),
        "best_subject_accuracy": float(by_user.max()),
        "by_user": {str(user): float(value) for user, value in by_user.items()},
        "fixed_threshold_overlays": fixed_threshold_overlays,
        "fixed_consensus_ablation": gate_reports,
        "test": {
            "sensor_present": int(test_output["sensor_present"].sum()),
            "prediction_distribution": test_output["prediction"].value_counts().sort_index().to_dict(),
            "gate_rows": {name: int(use.sum()) for name, use in test_gates.items()},
            "gate_evidence": {
                name: test_ensemble.loc[use, evidence_columns].to_dict(orient="records")
                for name, use in test_gates.items()
            },
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "inputs": {
            "training_qa_sha256": sha256(train_path),
            "test_qa_sha256": sha256(test_path),
            "feature_cache_sha256": sha256(feature_path),
            "parent_oof_sha256": sha256(parent_oof_path),
            "parent_test_sha256": sha256(parent_test_path),
            "graph_test_sha256": sha256(graph_test_path),
            "rf_oof_sha256": sha256(rf_oof_path),
            "rf_test_sha256": sha256(rf_test_path),
            "xgb_oof_sha256": sha256(xgb_oof_path),
            "xgb_test_sha256": sha256(xgb_test_path),
            "imported_xgb_code_sha256": sha256(root / "scripts/run_emotion_pairwise_xgb.py"),
            "code_sha256": sha256(Path(__file__)),
        },
        "outputs": {
            "oof_sha256": sha256(oof_path),
            "test_predictions_sha256": sha256(test_output_path),
            "model_sha256": sha256(model_path),
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"report_sha256={sha256(summary_path)}", flush=True)


if __name__ == "__main__":
    main()
