#!/usr/bin/env python3
"""Subject-disjoint OOF for nonvisual CUHK-X sensor specialists.

The script trains only on organizer-provided training labels (plus the HARn action
folder names), keeps subjects and clips intact, and never accesses hidden targets.
It emits audit-friendly OOF/test expert predictions and aggregate reports.  It does
not submit anything to Kaggle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier


SEED = 20260909
LABELS = "ABCD"
EXPECTED_USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    return {
        "hasitly": "hastily",
        "serioiusly": "seriously",
        "tensly": "tensely",
    }.get(text, text)


def answer_text(row: pd.Series) -> str:
    answer = str(row["answer"]).strip().upper()
    if len(answer) != 1 or answer not in LABELS:
        raise ValueError(f"Expected one answer label for {row['qa_id']}: {answer}")
    return norm(row[answer])


def user_from_path(path: str) -> int:
    match = re.search(r"(?:^|/)user(\d+)(?:/|$)", path, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"No subject in {path}")
    return int(match.group(1))


def harn_action_from_unit(unit: str) -> int:
    match = re.search(r"^Training/HARn/(\d+)_", unit)
    if not match:
        raise ValueError(f"No HARn action ID in {unit}")
    return int(match.group(1))


def harn_action_from_path(path: str) -> int:
    return harn_action_from_unit("Training/" + path)


def test_unit(path: str) -> str:
    match = re.search(r"large_model_track_test/LM_test_\d+", path)
    if not match:
        raise ValueError(f"No test clip key in {path}")
    return "Testing/" + match.group(0)


def classifier() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=240,
        max_features="sqrt",
        min_samples_leaf=1,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=SEED,
    )


def option_prediction(row: pd.Series, probability: np.ndarray, classes: np.ndarray) -> tuple[str, float]:
    by_class = {norm(label): float(score) for label, score in zip(classes, probability)}
    scores = np.asarray([by_class.get(norm(row[label]), 0.0) for label in LABELS])
    order = np.argsort(-scores, kind="stable")
    return LABELS[int(order[0])], float(scores[order[0]] - scores[order[1]])


def harn_maps(frame: pd.DataFrame) -> tuple[dict[str, Counter], dict[int, Counter]]:
    action_by_text: dict[str, Counter] = defaultdict(Counter)
    objects_by_action: dict[int, Counter] = defaultdict(Counter)
    for _, row in frame.iterrows():
        if row["source"] != "HARn" or row["category"] not in {"single", "object_interaction"}:
            continue
        action = harn_action_from_path(row["path"])
        text = answer_text(row)
        if row["category"] == "single":
            action_by_text[text][action] += 1
        else:
            objects_by_action[action][text] += 1
    return action_by_text, objects_by_action


def harn_prediction(
    row: pd.Series,
    probability: np.ndarray,
    classes: np.ndarray,
    action_by_text: dict[str, Counter],
    objects_by_action: dict[int, Counter],
) -> tuple[str, float]:
    by_action = {int(label): float(score) for label, score in zip(classes, probability)}
    scores = []
    for label in LABELS:
        text = norm(row[label])
        if row["category"] == "single":
            counts = action_by_text.get(text, Counter())
            score = sum(by_action.get(action, 0.0) * count for action, count in counts.items())
            score /= max(1, sum(counts.values()))
        elif row["category"] == "object_interaction":
            score = 0.0
            for action, objects in objects_by_action.items():
                if text in objects:
                    score += by_action.get(action, 0.0) * objects[text] / sum(objects.values())
        else:
            raise ValueError(f"Unsupported HARn category {row['category']}")
        scores.append(score)
    scores_array = np.asarray(scores)
    order = np.argsort(-scores_array, kind="stable")
    return LABELS[int(order[0])], float(scores_array[order[0]] - scores_array[order[1]])


class FeatureStore:
    def __init__(self, path: Path):
        data = np.load(path)
        self.units = data["units"].astype(str)
        self.imu = data["imu"].astype(np.float32)
        self.skeleton = data["skeleton"].astype(np.float32)
        self.index = {unit: index for index, unit in enumerate(self.units)}

    def combined(self, units: list[str]) -> np.ndarray:
        width = self.imu.shape[1] + self.skeleton.shape[1]
        result = np.full((len(units), width), np.nan, dtype=np.float32)
        for row, unit in enumerate(units):
            if unit in self.index:
                index = self.index[unit]
                result[row] = np.concatenate((self.imu[index], self.skeleton[index]))
        return result

    def skeleton_only(self, units: list[str]) -> np.ndarray:
        result = np.full((len(units), self.skeleton.shape[1]), np.nan, dtype=np.float32)
        for row, unit in enumerate(units):
            if unit in self.index:
                result[row] = self.skeleton[self.index[unit]]
        return result


def slice_metrics(frame: pd.DataFrame) -> dict:
    output = {}
    for (source, category), group in frame.groupby(["source", "category"]):
        by_user_parent = group.groupby("user")["parent_correct"].mean()
        by_user_expert = group.groupby("user")["expert_correct"].mean()
        disagree = group[group["prediction"] != group["parent_prediction"]]
        output[f"{source}/{category}"] = {
            "rows": int(len(group)),
            "parent_accuracy": float(group["parent_correct"].mean()),
            "expert_accuracy": float(group["expert_correct"].mean()),
            "parent_worst_subject": float(by_user_parent.min()),
            "expert_worst_subject": float(by_user_expert.min()),
            "disagreements": int(len(disagree)),
            "disagreement_parent_correct": int(disagree["parent_correct"].sum()),
            "disagreement_expert_correct": int(disagree["expert_correct"].sum()),
            "mean_confidence": float(group["confidence"].mean()),
            "fixed_threshold_overlays": {},
        }
        for threshold in (0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50):
            use = (group["prediction"] != group["parent_prediction"]) & (group["confidence"] >= threshold)
            overlay = group["parent_prediction"].where(~use, group["prediction"])
            correct = overlay == group["answer"]
            worst = correct.groupby(group["user"]).mean().min()
            output[f"{source}/{category}"]["fixed_threshold_overlays"][f"{threshold:.2f}"] = {
                "overrides": int(use.sum()),
                "accuracy": float(correct.mean()),
                "net_correct_vs_parent": int(correct.sum() - group["parent_correct"].sum()),
                "worst_subject_accuracy": float(worst),
            }
    return output


def main() -> None:
    campaign_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=campaign_root / "cache/nonvisual_features.npz")
    parser.add_argument("--train", type=Path, default=campaign_root / "data/raw/kaggle/training_qa.csv")
    parser.add_argument("--test", type=Path, default=campaign_root / "data/raw/kaggle/test_qa.csv")
    parser.add_argument(
        "--parent-oof", type=Path, default=campaign_root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    )
    parser.add_argument(
        "--parent-test", type=Path, default=campaign_root / "candidates/public_fususu_077777.csv"
    )
    parser.add_argument("--oof-output", type=Path, default=campaign_root / "artifacts/oof/nonvisual_sensor_oof.csv")
    parser.add_argument("--test-output", type=Path, default=campaign_root / "artifacts/predictions/nonvisual_sensor_test.csv")
    parser.add_argument("--model-dir", type=Path, default=campaign_root / "artifacts/models/nonvisual_rf_v1")
    parser.add_argument("--summary", type=Path, default=campaign_root / "reports/nonvisual_sensor_oof_summary.json")
    args = parser.parse_args()

    started = time.perf_counter()
    store = FeatureStore(args.features)
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(args.test, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    train["user"] = train["path"].map(user_from_path)
    if sorted(train["user"].unique().tolist()) != EXPECTED_USERS:
        raise ValueError("Unexpected subject manifest")
    parent_oof = pd.read_csv(args.parent_oof, dtype=str, keep_default_na=False)
    parent_oof = parent_oof[["qa_id", "prediction"]].rename(columns={"prediction": "parent_prediction"})

    hau_action = train[(train["source"] == "HAU") & (train["category"] == "single")].copy()
    hau_emotion = train[(train["source"] == "HAU") & (train["category"] == "emotion")].copy()
    if set(hau_action["path"]) != set(hau_emotion["path"]):
        raise ValueError("HAU action/emotion clip sets differ")
    hau_units = ["Training/" + path for path in hau_action["path"]]
    hau_x = store.combined(hau_units)
    hau_users = hau_action["user"].astype(int).to_numpy()
    hau_action_y = hau_action.apply(answer_text, axis=1).to_numpy()
    emotion_by_path = dict(zip(hau_emotion["path"], hau_emotion.apply(answer_text, axis=1)))
    hau_emotion_y = np.asarray([emotion_by_path[path] for path in hau_action["path"]])

    harn_units_mask = np.char.startswith(store.units, "Training/HARn/")
    harn_units = store.units[harn_units_mask].tolist()
    harn_x = store.skeleton[harn_units_mask]
    harn_y = np.asarray([harn_action_from_unit(unit) for unit in harn_units])
    harn_users = np.asarray([user_from_path(unit) for unit in harn_units])

    outputs = []
    for held_user in EXPECTED_USERS:
        print(f"fold user{held_user}", flush=True)
        hau_fit = hau_users != held_user
        action_model = classifier().fit(hau_x[hau_fit], hau_action_y[hau_fit])
        emotion_model = classifier().fit(hau_x[hau_fit], hau_emotion_y[hau_fit])
        for category, model in (("single", action_model), ("emotion", emotion_model)):
            rows = train[(train["source"] == "HAU") & (train["category"] == category) & (train["user"] == held_user)]
            units = ["Training/" + path for path in rows["path"]]
            probabilities = model.predict_proba(store.combined(units))
            for probability, (_, row) in zip(probabilities, rows.iterrows()):
                prediction, confidence = option_prediction(row, probability, model.classes_)
                outputs.append(
                    {"qa_id": row["qa_id"], "source": "HAU", "category": category, "user": held_user,
                     "answer": row["answer"], "prediction": prediction, "confidence": confidence}
                )

        harn_fit = harn_users != held_user
        harn_model = classifier().fit(harn_x[harn_fit], harn_y[harn_fit])
        mapping_fit = train[train["user"] != held_user]
        action_by_text, objects_by_action = harn_maps(mapping_fit)
        rows = train[
            (train["source"] == "HARn")
            & (train["category"].isin(["single", "object_interaction"]))
            & (train["user"] == held_user)
        ]
        units = ["Training/" + path for path in rows["path"]]
        probabilities = harn_model.predict_proba(store.skeleton_only(units))
        for probability, (_, row) in zip(probabilities, rows.iterrows()):
            prediction, confidence = harn_prediction(
                row, probability, harn_model.classes_, action_by_text, objects_by_action
            )
            outputs.append(
                {"qa_id": row["qa_id"], "source": "HARn", "category": row["category"], "user": held_user,
                 "answer": row["answer"], "prediction": prediction, "confidence": confidence}
            )

    oof = pd.DataFrame(outputs).merge(parent_oof, on="qa_id", how="left", validate="one_to_one")
    if oof["parent_prediction"].eq("").any() or oof["qa_id"].duplicated().any():
        raise ValueError("Invalid OOF merge")
    oof["expert_correct"] = oof["prediction"] == oof["answer"]
    oof["parent_correct"] = oof["parent_prediction"] == oof["answer"]
    metrics = slice_metrics(oof)

    # Fit final specialists on all available organizer training data and persist them.
    final_hau_action = classifier().fit(hau_x, hau_action_y)
    final_hau_emotion = classifier().fit(hau_x, hau_emotion_y)
    final_harn = classifier().fit(harn_x, harn_y)
    action_by_text, objects_by_action = harn_maps(train)
    test_outputs = []
    for source, categories, model, modality in (
        ("HAU", ["single"], final_hau_action, "combined"),
        ("HAU", ["emotion"], final_hau_emotion, "combined"),
        ("HARn", ["single", "object_interaction"], final_harn, "skeleton"),
    ):
        rows = test[(test["source"] == source) & (test["category"].isin(categories))]
        units = [test_unit(path) for path in rows["path"]]
        values = store.combined(units) if modality == "combined" else store.skeleton_only(units)
        probabilities = model.predict_proba(values)
        for probability, (_, row) in zip(probabilities, rows.iterrows()):
            if source == "HAU":
                prediction, confidence = option_prediction(row, probability, model.classes_)
            else:
                prediction, confidence = harn_prediction(
                    row, probability, model.classes_, action_by_text, objects_by_action
                )
            test_outputs.append(
                {"qa_id": row["qa_id"], "source": source, "category": row["category"],
                 "prediction": prediction, "confidence": confidence, "sensor_unit": test_unit(row["path"]),
                 "sensor_present": test_unit(row["path"]) in store.index}
            )
    test_predictions = pd.DataFrame(test_outputs)
    parent_test = pd.read_csv(args.parent_test, dtype=str, keep_default_na=False)
    test_predictions = test_predictions.merge(
        parent_test.rename(columns={"prediction": "parent_prediction"}), on="qa_id", how="left", validate="one_to_one"
    )

    args.oof_output.parent.mkdir(parents=True, exist_ok=True)
    args.test_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_dir.mkdir(parents=True, exist_ok=True)
    oof.to_csv(args.oof_output, index=False)
    test_predictions.to_csv(args.test_output, index=False)
    model_paths = {
        "hau_action": args.model_dir / "hau_action.joblib",
        "hau_emotion": args.model_dir / "hau_emotion.joblib",
        "harn_action": args.model_dir / "harn_action.joblib",
    }
    joblib.dump(final_hau_action, model_paths["hau_action"])
    joblib.dump(final_hau_emotion, model_paths["hau_emotion"])
    joblib.dump(final_harn, model_paths["harn_action"])

    summary = {
        "experiment": "nonvisual_rf_v1_subject_leave_one_out",
        "seed": SEED,
        "validation": "18-fold leave-one-subject-out; clips intact",
        "feature_source": "official LMT_(IMU,Radar,Skeleton).zip; IMU + Skeleton for HAU, Skeleton for HARn",
        "radar_used": False,
        "train_sha256": sha256(args.train),
        "feature_cache_sha256": sha256(args.features),
        "parent_oof_sha256": sha256(args.parent_oof),
        "parent_test_sha256": sha256(args.parent_test),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
        "model": {"type": "RandomForestClassifier", "n_estimators": 240, "max_features": "sqrt", "class_weight": "balanced_subsample"},
        "covered_oof_rows": int(len(oof)),
        "covered_test_rows": int(len(test_predictions)),
        "metrics": metrics,
        "test_disagreements_vs_frozen_077777": test_predictions.groupby(["source", "category"]).apply(
            lambda frame: int((frame["prediction"] != frame["parent_prediction"]).sum()), include_groups=False
        ).to_dict(),
        "model_sha256": {name: sha256(path) for name, path in model_paths.items()},
        "runtime_seconds": time.perf_counter() - started,
    }
    # JSON cannot encode tuple dictionary keys.
    summary["test_disagreements_vs_frozen_077777"] = {
        "/".join(key): value for key, value in summary["test_disagreements_vs_frozen_077777"].items()
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
