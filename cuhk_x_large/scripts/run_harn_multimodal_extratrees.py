#!/usr/bin/env python3
"""Fixed multimodal ExtraTrees ablation for the official HARn sensor data.

Model selection uses only subject-disjoint training folds. Missing modalities are
reported explicitly and are never eligible for a test-time override. Test labels
are neither present nor inferred.
"""

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

from run_sensor_oof import (
    EXPECTED_USERS,
    LABELS,
    FeatureStore,
    harn_action_from_unit,
    harn_maps,
    harn_prediction,
    test_unit,
    user_from_path,
)


SEED = 20260909
TREES = 240
BASE_MODALITIES = ("imu", "radar", "skeleton")
VARIANTS = ("imu", "radar", "skeleton", "early_fusion", "late_fusion")


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def classifier() -> ExtraTreesClassifier:
    return ExtraTreesClassifier(
        n_estimators=TREES,
        max_features="sqrt",
        min_samples_leaf=1,
        class_weight="balanced",
        n_jobs=-1,
        random_state=SEED,
    )


def feature_matrix(store: FeatureStore, variant: str) -> np.ndarray:
    if variant in BASE_MODALITIES:
        return getattr(store, variant)
    if variant == "early_fusion":
        return np.concatenate((store.imu, store.radar, store.skeleton), axis=1)
    raise ValueError(f"No direct feature matrix for {variant}")


def row_present(store: FeatureStore, index: int, variant: str) -> bool:
    if variant in BASE_MODALITIES:
        return bool(np.isfinite(getattr(store, variant)[index]).any())
    if variant in {"early_fusion", "late_fusion"}:
        return any(np.isfinite(getattr(store, modality)[index]).any() for modality in BASE_MODALITIES)
    raise ValueError(variant)


def aligned_probability(model: ExtraTreesClassifier, values: np.ndarray, classes: np.ndarray) -> np.ndarray:
    probability = model.predict_proba(values)
    aligned = np.zeros((len(values), len(classes)), dtype=np.float64)
    positions = {int(label): index for index, label in enumerate(classes)}
    for source, label in enumerate(model.classes_):
        aligned[:, positions[int(label)]] = probability[:, source]
    return aligned


def score_frame(frame: pd.DataFrame, category: str) -> dict[str, object]:
    subset = frame[frame["category"] == category].copy()
    eligible = subset[subset["sensor_present"]].copy()
    if eligible.empty:
        raise ValueError(f"No eligible {category} rows")
    eligible["correct"] = eligible["prediction"] == eligible["answer"]
    by_user = eligible.groupby("user")["correct"].mean()
    use = eligible["prediction"] != eligible["parent_prediction"]
    changed = eligible[use]
    return {
        "rows": int(len(subset)),
        "sensor_present_rows": int(len(eligible)),
        "coverage": float(len(eligible) / len(subset)),
        "expert_accuracy": float(eligible["correct"].mean()),
        "worst_subject_accuracy": float(by_user.min()),
        "best_subject_accuracy": float(by_user.max()),
        "disagreements_vs_parent": int(use.sum()),
        "disagreement_expert_correct": int((changed["prediction"] == changed["answer"]).sum()),
        "disagreement_parent_correct": int((changed["parent_prediction"] == changed["answer"]).sum()),
    }


def agreement_gate(frame: pd.DataFrame, rf: pd.DataFrame, category: str) -> dict[str, object]:
    subset = frame[frame["category"] == category].merge(
        rf[["qa_id", "prediction"]].rename(columns={"prediction": "rf_prediction"}),
        on="qa_id",
        validate="one_to_one",
    )
    agree = subset["sensor_present"] & (subset["prediction"] == subset["rf_prediction"])
    agreed = subset[agree].copy()
    override = agreed[agreed["prediction"] != agreed["parent_prediction"]].copy()
    return {
        "agreement_rows": int(len(agreed)),
        "agreement_accuracy": float((agreed["prediction"] == agreed["answer"]).mean()),
        "override_rows": int(len(override)),
        "override_expert_correct": int((override["prediction"] == override["answer"]).sum()),
        "override_parent_correct": int((override["parent_prediction"] == override["answer"]).sum()),
        "override_net_correct_vs_parent": int(
            (override["prediction"] == override["answer"]).sum()
            - (override["parent_prediction"] == override["answer"]).sum()
        ),
        "override_worst_subject_net": int(
            override.assign(
                delta=(override["prediction"] == override["answer"]).astype(int)
                - (override["parent_prediction"] == override["answer"]).astype(int)
            ).groupby("user")["delta"].sum().min()
        ) if len(override) else 0,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    feature_path = root / "cache/nonvisual_features.npz"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    parent_oof_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    parent_test_path = root / "candidates/public_fususu_077777.csv"
    rf_oof_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    oof_path = root / "artifacts/oof/harn_multimodal_extratrees_oof.csv"
    test_output_path = root / "artifacts/predictions/harn_multimodal_extratrees_test.csv"
    model_path = root / "artifacts/models/harn_multimodal_extratrees/selected.joblib"
    report_path = root / "reports/harn_multimodal_extratrees_summary.json"
    started = time.perf_counter()

    store = FeatureStore(feature_path)
    with np.load(feature_path) as data:
        store.radar = data["radar"].astype(np.float32)
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    train["user"] = train["path"].map(user_from_path)
    parent_oof = pd.read_csv(parent_oof_path, dtype=str, keep_default_na=False)[["qa_id", "prediction"]]
    parent_oof = parent_oof.rename(columns={"prediction": "parent_prediction"})
    parent_test = pd.read_csv(parent_test_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    rf_oof = pd.read_csv(rf_oof_path, dtype=str, keep_default_na=False)

    harn_mask = np.char.startswith(store.units, "Training/HARn/")
    harn_indices = np.flatnonzero(harn_mask)
    harn_units = store.units[harn_mask]
    action_y = np.asarray([harn_action_from_unit(unit) for unit in harn_units], dtype=int)
    users = np.asarray([user_from_path(unit) for unit in harn_units], dtype=int)
    if sorted(np.unique(users).tolist()) != EXPECTED_USERS:
        raise ValueError("Unexpected HARn training subjects")
    classes = np.asarray(sorted(np.unique(action_y).tolist()), dtype=int)

    direct_variants = (*BASE_MODALITIES, "early_fusion")
    oof_probability = {
        variant: np.zeros((len(harn_units), len(classes)), dtype=np.float64)
        for variant in VARIANTS
    }
    for held_user in EXPECTED_USERS:
        print(f"fold user{held_user}", flush=True)
        fit = users != held_user
        hold = ~fit
        fold_models: dict[str, ExtraTreesClassifier] = {}
        for variant in direct_variants:
            values = feature_matrix(store, variant)[harn_indices]
            model = classifier().fit(values[fit], action_y[fit])
            fold_models[variant] = model
            oof_probability[variant][hold] = aligned_probability(model, values[hold], classes)
        oof_probability["late_fusion"][hold] = np.mean(
            [oof_probability[modality][hold] for modality in BASE_MODALITIES], axis=0
        )

    action_metrics: dict[str, object] = {}
    qa_frames: dict[str, pd.DataFrame] = {}
    action_position = {unit: index for index, unit in enumerate(harn_units)}
    harn_qa = train[
        (train["source"] == "HARn") & train["category"].isin(["single", "object_interaction"])
    ].copy()
    harn_qa = harn_qa.merge(parent_oof, on="qa_id", validate="one_to_one")
    mappings = {held: harn_maps(train[train["user"] != held]) for held in EXPECTED_USERS}

    for variant in VARIANTS:
        action_present = np.asarray(
            [row_present(store, int(index), variant) for index in harn_indices], dtype=bool
        )
        action_pred = classes[oof_probability[variant].argmax(axis=1)]
        by_user = {
            int(user): float((action_pred[(users == user) & action_present] == action_y[(users == user) & action_present]).mean())
            for user in EXPECTED_USERS
            if ((users == user) & action_present).any()
        }
        action_metrics[variant] = {
            "rows": int(len(action_y)),
            "sensor_present_rows": int(action_present.sum()),
            "accuracy": float((action_pred[action_present] == action_y[action_present]).mean()),
            "worst_subject_accuracy": float(min(by_user.values())),
            "by_user": by_user,
        }
        records = []
        for _, row in harn_qa.iterrows():
            unit = "Training/" + row["path"]
            if unit not in action_position:
                records.append(
                    {
                        "qa_id": row["qa_id"],
                        "source": "HARn",
                        "category": row["category"],
                        "user": int(row["user"]),
                        "answer": row["answer"],
                        "prediction": "",
                        "confidence": 0.0,
                        "sensor_present": False,
                        "parent_prediction": row["parent_prediction"],
                        "variant": variant,
                    }
                )
                continue
            position = action_position[unit]
            store_index = int(harn_indices[position])
            present = row_present(store, store_index, variant)
            action_by_text, objects_by_action = mappings[int(row["user"])]
            prediction, confidence = harn_prediction(
                row,
                oof_probability[variant][position],
                classes,
                action_by_text,
                objects_by_action,
            )
            records.append(
                {
                    "qa_id": row["qa_id"],
                    "source": "HARn",
                    "category": row["category"],
                    "user": int(row["user"]),
                    "answer": row["answer"],
                    "prediction": prediction,
                    "confidence": confidence,
                    "sensor_present": present,
                    "parent_prediction": row["parent_prediction"],
                    "variant": variant,
                }
            )
        qa_frames[variant] = pd.DataFrame(records)

    variant_metrics = {}
    for variant, frame in qa_frames.items():
        variant_metrics[variant] = {
            "single": score_frame(frame, "single"),
            "object_interaction": score_frame(frame, "object_interaction"),
            "rf_agreement": {
                category: agreement_gate(frame, rf_oof, category)
                for category in ("single", "object_interaction")
            },
        }

    eligible_variants = [
        variant
        for variant in VARIANTS
        if variant_metrics[variant]["single"]["coverage"] >= 0.90
    ]
    selected = max(
        eligible_variants,
        key=lambda variant: (
            variant_metrics[variant]["single"]["expert_accuracy"],
            variant_metrics[variant]["single"]["worst_subject_accuracy"],
            variant_metrics[variant]["object_interaction"]["expert_accuracy"],
            variant,
        ),
    )
    selected_oof = qa_frames[selected].copy()
    oof_path.parent.mkdir(parents=True, exist_ok=True)
    selected_oof.to_csv(oof_path, index=False)

    final_models: dict[str, ExtraTreesClassifier] = {}
    needed = BASE_MODALITIES if selected == "late_fusion" else (selected,)
    for variant in needed:
        values = feature_matrix(store, variant)[harn_indices]
        final_models[variant] = classifier().fit(values, action_y)

    harn_test = test[
        (test["source"] == "HARn") & test["category"].isin(["single", "object_interaction"])
    ].merge(parent_test, on="qa_id", validate="one_to_one")
    action_by_text, objects_by_action = harn_maps(train)
    test_records = []
    for _, row in harn_test.iterrows():
        unit = test_unit(row["path"])
        if unit not in store.index:
            test_records.append(
                {
                    "qa_id": row["qa_id"], "source": "HARn", "category": row["category"],
                    "prediction": "", "confidence": 0.0, "sensor_unit": unit,
                    "sensor_present": False, "parent_prediction": row["parent_prediction"],
                    "variant": selected,
                }
            )
            continue
        index = store.index[unit]
        present = row_present(store, index, selected)
        if selected == "late_fusion":
            probability = np.mean(
                [aligned_probability(final_models[m], getattr(store, m)[[index]], classes)[0] for m in BASE_MODALITIES],
                axis=0,
            )
        else:
            probability = aligned_probability(
                final_models[selected], feature_matrix(store, selected)[[index]], classes
            )[0]
        prediction, confidence = harn_prediction(
            row, probability, classes, action_by_text, objects_by_action
        )
        test_records.append(
            {
                "qa_id": row["qa_id"], "source": "HARn", "category": row["category"],
                "prediction": prediction, "confidence": confidence, "sensor_unit": unit,
                "sensor_present": present, "parent_prediction": row["parent_prediction"],
                "variant": selected,
            }
        )
    test_predictions = pd.DataFrame(test_records)
    test_output_path.parent.mkdir(parents=True, exist_ok=True)
    test_predictions.to_csv(test_output_path, index=False)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"selected": selected, "classes": classes, "models": final_models}, model_path)

    report = {
        "experiment": "harn_multimodal_extratrees_fixed_ablation_v1",
        "seed": SEED,
        "validation": "18-fold leave-one-subject-out; sensor units and QA clips intact",
        "selection_rule": "among fixed variants with >=90% HARn-single coverage (the organizer supplement omits 50/562 referenced HARn QA rows), maximize single QA accuracy; tie-break worst-subject, object accuracy, then name",
        "model": {
            "type": "ExtraTreesClassifier",
            "n_estimators": TREES,
            "max_features": "sqrt",
            "min_samples_leaf": 1,
            "class_weight": "balanced",
        },
        "action_metrics": action_metrics,
        "variant_metrics": variant_metrics,
        "selected_variant": selected,
        "test": {
            "rows": int(len(test_predictions)),
            "sensor_present_rows": int(test_predictions["sensor_present"].sum()),
            "by_category": {
                category: {
                    "rows": int(len(group)),
                    "sensor_present_rows": int(group["sensor_present"].sum()),
                    "disagreements_vs_parent": int(
                        (group["sensor_present"] & (group["prediction"] != group["parent_prediction"])).sum()
                    ),
                }
                for category, group in test_predictions.groupby("category")
            },
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "inputs": {
            "feature_cache_sha256": sha256(feature_path),
            "training_qa_sha256": sha256(train_path),
            "test_qa_sha256": sha256(test_path),
            "parent_oof_sha256": sha256(parent_oof_path),
            "parent_test_sha256": sha256(parent_test_path),
            "rf_oof_sha256": sha256(rf_oof_path),
            "code_sha256": sha256(Path(__file__)),
        },
        "artifacts": {
            "selected_oof_sha256": sha256(oof_path),
            "test_predictions_sha256": sha256(test_output_path),
            "model_sha256": sha256(model_path),
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
