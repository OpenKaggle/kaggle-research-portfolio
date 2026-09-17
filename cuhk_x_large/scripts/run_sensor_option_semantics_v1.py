#!/usr/bin/env python3
"""Fail-closed LOSO validation for a tri-modal sensor--option semantics branch.

This result-bearing script reads training labels, the frozen feature cache, and an
owned subject-disjoint parent OOF only.  It cannot read test_qa, create a test
prediction, create a candidate CSV, or submit to Kaggle.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import platform
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


LABELS = "ABCD"
USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]
FIRST_HALF = set(USERS[:9])
SECOND_HALF = set(USERS[9:])
MODALITIES = ("imu", "radar", "skeleton")
SEED = 20260911
EXPECTED = {
    "training_qa": "2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc",
    "feature_cache": "a8ed7d5925977dabd18b4b55a2beecb02a8a7435ce0773268a41d188cefdd661",
    "parent_oof": "8054484a387472f04336d6c37fe77c4b9ae442484940538f6aaa777a71f5b7b7",
}

ADJECTIVE = {
    "absentmindedly": "absent-minded",
    "anxiously": "anxious",
    "attentively": "attentive",
    "briskly": "brisk",
    "calmly": "calm",
    "carefully": "careful",
    "casually": "casual",
    "cautiously": "cautious",
    "comfortably": "comfortable",
    "confidently": "confident",
    "contently": "content",
    "deliberately": "deliberate",
    "diligently": "diligent",
    "eagerly": "eager",
    "earnestly": "earnest",
    "evenly": "even",
    "firmly": "firm",
    "forcefully": "forceful",
    "frantically": "frantic",
    "gently": "gentle",
    "gracefully": "graceful",
    "hastily": "hasty",
    "hurriedly": "hurried",
    "impatiently": "impatient",
    "intently": "intent",
    "joyfully": "joyful",
    "lazily": "lazy",
    "leisurely": "leisurely",
    "lightly": "light",
    "methodically": "methodical",
    "meticulously": "meticulous",
    "naturally": "natural",
    "neatly": "neat",
    "nervously": "nervous",
    "orderly": "orderly",
    "patiently": "patient",
    "peacefully": "peaceful",
    "precisely": "precise",
    "quickly": "quick",
    "quietly": "quiet",
    "rapidly": "rapid",
    "relaxedly": "relaxed",
    "restlessly": "restless",
    "seriously": "serious",
    "slowly": "slow",
    "smoothly": "smooth",
    "softly": "soft",
    "soothingly": "soothing",
    "steadily": "steady",
    "swiftly": "swift",
    "tensely": "tense",
    "thoroughly": "thorough",
    "unhurriedly": "unhurried",
    "urgently": "urgent",
}


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def basic_norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def norm(value: object) -> str:
    text = basic_norm(value)
    text = {
        "hasitly": "hastily",
        "serioiusly": "seriously",
        "tensly": "tensely",
    }.get(text, text)
    reverse = {rewrite(option): option for option in ADJECTIVE}
    return reverse.get(text, text)


def rewrite(option: str) -> str:
    adjective = ADJECTIVE[option]
    article = "an" if adjective[0] in "aeiou" else "a"
    return f"in {article} {adjective} manner"


def motion_columns() -> np.ndarray:
    columns: list[int] = []
    for device in range(5):
        start = device * 131
        for statistic in range(7):
            columns.extend(range(start + statistic * 16, start + statistic * 16 + 6))
        columns.extend(range(start + 112, start + 131))
    result = np.asarray(columns, dtype=int)
    if len(result) != 305:
        raise AssertionError("Frozen IMU motion-column width changed")
    return result


def user_from_path(path: str) -> int:
    match = re.search(r"(?:^|/)user(\d+)(?:/|$)", path, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"No subject in {path}")
    return int(match.group(1))


def environment_stratum(path: str) -> str:
    trial = path.rsplit("/", 1)[-1]
    match = re.fullmatch(r"(\d+)-(\d+)-(\d+)", trial)
    if not match:
        raise ValueError(f"Unexpected HAU trial token: {path}")
    prefix = int(match.group(1))
    if prefix in {1, 2}:
        return "trial_prefix_1_2"
    if prefix in {3, 4, 5}:
        return "trial_prefix_3_5"
    if prefix in {6, 7}:
        return "trial_prefix_6_7"
    raise ValueError(f"Unexpected HAU trial prefix: {path}")


def estimator() -> Pipeline:
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            (
                "classifier",
                ExtraTreesClassifier(
                    n_estimators=320,
                    max_features="sqrt",
                    min_samples_leaf=2,
                    class_weight="balanced",
                    n_jobs=-1,
                    random_state=SEED,
                ),
            ),
        ]
    )


def feature_rows(
    sensor: np.ndarray,
    frame: pd.DataFrame,
    option_index: dict[str, int],
    targets: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    rows: list[np.ndarray] = []
    y: list[int] = []
    for sensor_row, (_, qa) in zip(sensor, frame.iterrows()):
        for label in LABELS:
            option = norm(qa[label])
            if option not in option_index:
                raise ValueError(f"Unknown canonical option {option!r}")
            onehot = np.zeros(len(option_index), dtype=np.float32)
            onehot[option_index[option]] = 1.0
            rows.append(np.concatenate((sensor_row, onehot)))
            if targets:
                y.append(int(label == qa["answer"]))
    return np.asarray(rows, dtype=np.float32), np.asarray(y, dtype=np.int8) if targets else None


def score_rows(model: Pipeline, sensor: np.ndarray, frame: pd.DataFrame, option_index: dict[str, int]) -> np.ndarray:
    expanded, _ = feature_rows(sensor, frame, option_index, targets=False)
    return model.predict_proba(expanded)[:, 1].reshape(-1, 4)


def top_labels(scores: np.ndarray, frame: pd.DataFrame) -> list[str]:
    """Choose by score, breaking exact ties by canonical semantics, never letter."""
    output: list[str] = []
    for score_row, (_, qa) in zip(scores, frame.iterrows()):
        best = float(np.max(score_row))
        tied = [label for label, score in zip(LABELS, score_row) if float(score) == best]
        output.append(min(tied, key=lambda label: semantic_for_label(qa, label)))
    return output


def majority(predictions: list[str]) -> str | None:
    counts = Counter(predictions)
    option, count = counts.most_common(1)[0]
    return option if count >= 2 else None


def semantic_for_label(row: pd.Series, label: str) -> str:
    return norm(row[label])


def permuted_frame(frame: pd.DataFrame, permutation: tuple[str, ...]) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    changed = frame.copy()
    reverse_maps: list[dict[str, str]] = []
    for index, (_, row) in enumerate(frame.iterrows()):
        values = {new: row[old] for new, old in zip(LABELS, permutation)}
        for label in LABELS:
            changed.iat[index, changed.columns.get_loc(label)] = values[label]
        reverse_maps.append({old: new for new, old in zip(LABELS, permutation)})
    return changed, reverse_maps


def rewritten_frame(frame: pd.DataFrame) -> pd.DataFrame:
    changed = frame.copy()
    for label in LABELS:
        changed[label] = changed[label].map(lambda value: rewrite(norm(value)))
    return changed


def accuracy_metrics(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {
            "rows": 0,
            "candidate_correct": 0,
            "candidate_accuracy": None,
            "parent_correct": 0,
            "parent_accuracy": None,
            "net_correct_vs_parent": 0,
        }
    return {
        "rows": int(len(frame)),
        "candidate_correct": int(frame["candidate_correct"].sum()),
        "candidate_accuracy": float(frame["candidate_correct"].mean()),
        "parent_correct": int(frame["parent_correct"].sum()),
        "parent_accuracy": float(frame["parent_correct"].mean()),
        "net_correct_vs_parent": int(frame["candidate_correct"].sum() - frame["parent_correct"].sum()),
    }


def main() -> None:
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    feature_path = root / "cache/nonvisual_features.npz"
    parent_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    protocol_path = root / "reports/sensor_option_semantics_v1_preregistered_protocol.json"
    oof_path = root / "artifacts/oof/sensor_option_semantics_v1_oof.csv"
    report_path = root / "reports/sensor_option_semantics_v1_validation.json"

    for name, path in (("training_qa", train_path), ("feature_cache", feature_path), ("parent_oof", parent_path)):
        actual = sha256(path)
        if actual != EXPECTED[name]:
            raise ValueError(f"Frozen {name} hash mismatch: {actual}")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN_BEFORE_RESULT_BEARING_RUN":
        raise ValueError("Protocol is not frozen")
    if protocol["scope"]["test_qa_may_be_read_before_gate"]:
        raise ValueError("Protocol unexpectedly permits test access")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    full_hau = train[train["source"] == "HAU"].copy()
    full_hau["user"] = full_hau["path"].map(user_from_path)
    if full_hau.groupby("path")["user"].nunique().max() != 1:
        raise ValueError("A HAU clip crosses subjects")
    frame = full_hau[full_hau["category"] == "emotion"].copy()
    frame["environment_stratum"] = frame["path"].map(environment_stratum)
    if sorted(frame["user"].unique().tolist()) != USERS:
        raise ValueError("Expected exactly 18 released subjects")
    if frame["qa_id"].duplicated().any() or frame["path"].duplicated().any():
        raise ValueError("Expected one HAU emotion QA per intact clip")

    option_values = sorted({norm(value) for value in frame[list(LABELS)].to_numpy().ravel()})
    if set(option_values) != set(ADJECTIVE):
        raise ValueError(f"Frozen semantic vocabulary mismatch: {sorted(set(option_values) ^ set(ADJECTIVE))}")
    option_index = {value: index for index, value in enumerate(option_values)}
    rewritten = rewritten_frame(frame)
    if any(norm(rewritten.iloc[row][label]) != norm(frame.iloc[row][label]) for row in range(len(frame)) for label in LABELS):
        raise ValueError("Synonym rewrite does not round-trip to frozen semantics")

    with np.load(feature_path) as cache:
        units = cache["units"].astype(str)
        unit_index = {unit: index for index, unit in enumerate(units)}
        feature_store = {
            "imu": cache["imu"].astype(np.float32)[:, motion_columns()],
            "radar": cache["radar"].astype(np.float32),
            "skeleton": cache["skeleton"].astype(np.float32),
        }
    row_indices = []
    for path in frame["path"]:
        unit = "Training/" + path
        if unit not in unit_index:
            raise ValueError(f"Sensor cache lacks {unit}")
        row_indices.append(unit_index[unit])
    features = {name: values[row_indices] for name, values in feature_store.items()}
    present = {name: np.isfinite(values).any(axis=1) for name, values in features.items()}

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)
    parent = parent[(parent["source"] == "HAU") & (parent["category"] == "emotion")][
        ["qa_id", "user", "answer", "prediction"]
    ].rename(columns={"prediction": "owned_parent_prediction", "answer": "parent_answer", "user": "parent_user"})
    if len(parent) != len(frame):
        raise ValueError("Owned parent slice coverage mismatch")
    frame = frame.merge(parent, on="qa_id", validate="one_to_one")
    if not (frame["answer"] == frame["parent_answer"]).all():
        raise ValueError("Owned parent label mismatch")
    if not (frame["user"].astype(int) == frame["parent_user"].astype(int)).all():
        raise ValueError("Owned parent subject mismatch")
    if not frame["owned_parent_prediction"].isin(list(LABELS)).all():
        raise ValueError("Owned parent contains invalid predictions")

    modality_prediction = {name: np.empty(len(frame), dtype="<U1") for name in MODALITIES}
    synonym_prediction = {name: np.empty(len(frame), dtype="<U1") for name in MODALITIES}
    modality_margin = {name: np.zeros(len(frame), dtype=np.float64) for name in MODALITIES}
    permutation_mismatches = 0
    permutation_checks = 0
    synonym_mismatches = 0
    synonym_checks = 0
    fold_receipts: list[dict[str, object]] = []

    for held_user in USERS:
        print(f"fold user{held_user}", flush=True)
        fit = frame["user"].to_numpy(dtype=int) != held_user
        valid = ~fit
        valid_positions = np.flatnonzero(valid)
        fold_scores: dict[str, np.ndarray] = {}
        fold_rewrite_scores: dict[str, np.ndarray] = {}
        for modality in MODALITIES:
            x_fit, y_fit = feature_rows(features[modality][fit], frame[fit], option_index, targets=True)
            model = estimator().fit(x_fit, y_fit)
            scores = score_rows(model, features[modality][valid], frame[valid], option_index)
            rewrite_scores = score_rows(model, features[modality][valid], rewritten[valid], option_index)
            fold_scores[modality] = scores
            fold_rewrite_scores[modality] = rewrite_scores
            labels = top_labels(scores, frame[valid])
            rewrite_labels = top_labels(rewrite_scores, rewritten[valid])
            modality_prediction[modality][valid_positions] = labels
            synonym_prediction[modality][valid_positions] = rewrite_labels
            ordered = np.sort(scores, axis=1)
            modality_margin[modality][valid_positions] = ordered[:, -1] - ordered[:, -2]

        held = frame[valid]
        original_candidate_semantics: list[str] = []
        rewrite_candidate_semantics: list[str] = []
        for local_index, (_, row) in enumerate(held.iterrows()):
            originals = [
                semantic_for_label(row, top_labels(fold_scores[name], held)[local_index])
                for name in MODALITIES
            ]
            rewritten_semantics = [
                semantic_for_label(row, top_labels(fold_rewrite_scores[name], rewritten[valid])[local_index])
                for name in MODALITIES
            ]
            parent_semantic = semantic_for_label(row, row["owned_parent_prediction"])
            original_candidate_semantics.append(majority(originals) or parent_semantic)
            rewrite_candidate_semantics.append(majority(rewritten_semantics) or parent_semantic)
        mismatch = sum(a != b for a, b in zip(original_candidate_semantics, rewrite_candidate_semantics))
        synonym_mismatches += mismatch
        synonym_checks += len(held)

        for permutation in itertools.permutations(LABELS):
            permuted, reverse_maps = permuted_frame(held, permutation)
            semantic_predictions: dict[str, list[str]] = {}
            score_columns = [LABELS.index(old_label) for old_label in permutation]
            for modality in MODALITIES:
                # Each option is scored independently.  Permuting answer positions is
                # therefore exactly a column reindex of the already computed scores.
                scores = fold_scores[modality][:, score_columns]
                labels = top_labels(scores, permuted)
                semantic_predictions[modality] = [
                    semantic_for_label(row, label) for (_, row), label in zip(permuted.iterrows(), labels)
                ]
            for local_index, (_, original_row) in enumerate(held.iterrows()):
                candidate_semantic = majority([semantic_predictions[name][local_index] for name in MODALITIES])
                if candidate_semantic is None:
                    remapped_parent = reverse_maps[local_index][original_row["owned_parent_prediction"]]
                    candidate_semantic = semantic_for_label(permuted.iloc[local_index], remapped_parent)
                permutation_mismatches += int(candidate_semantic != original_candidate_semantics[local_index])
                permutation_checks += 1

        fold_receipts.append(
            {
                "held_user": held_user,
                "fit_rows": int(fit.sum()),
                "validation_rows": int(valid.sum()),
                "fit_subjects": sorted(frame.loc[fit, "user"].astype(int).unique().tolist()),
                "validation_subjects": [held_user],
                "fit_validation_clip_overlap": int(
                    len(set(frame.loc[fit, "path"]) & set(frame.loc[valid, "path"]))
                ),
            }
        )

    output = frame[
        ["qa_id", "path", "user", "environment_stratum", "answer", "owned_parent_prediction"]
    ].copy()
    for modality in MODALITIES:
        output[f"{modality}_present"] = present[modality]
        output[f"{modality}_prediction"] = modality_prediction[modality]
        output[f"{modality}_margin"] = modality_margin[modality]
        output[f"{modality}_synonym_prediction"] = synonym_prediction[modality]
    consensus = []
    candidate = []
    eligible = []
    for _, row in output.iterrows():
        all_present = all(bool(row[f"{name}_present"]) for name in MODALITIES)
        voted = majority([row[f"{name}_prediction"] for name in MODALITIES]) if all_present else None
        consensus.append(voted or "")
        candidate.append(voted or row["owned_parent_prediction"])
        eligible.append(voted is not None)
    output["tri_modal_consensus_prediction"] = consensus
    output["consensus_eligible"] = eligible
    output["candidate_prediction"] = candidate
    output["disagrees_owned_parent"] = output["candidate_prediction"] != output["owned_parent_prediction"]
    output["candidate_correct"] = output["candidate_prediction"] == output["answer"]
    output["parent_correct"] = output["owned_parent_prediction"] == output["answer"]
    output["invalid"] = ~output["candidate_prediction"].isin(list(LABELS))

    disagreements = output[output["disagrees_owned_parent"]].copy()
    disagreement_metrics = accuracy_metrics(disagreements)
    halves = {
        "first_nine": accuracy_metrics(disagreements[disagreements["user"].astype(int).isin(FIRST_HALF)]),
        "second_nine": accuracy_metrics(disagreements[disagreements["user"].astype(int).isin(SECOND_HALF)]),
    }
    environments = {
        str(name): accuracy_metrics(group)
        for name, group in disagreements.groupby("environment_stratum", sort=True)
    }
    by_subject = {
        str(int(user)): accuracy_metrics(group)
        for user, group in disagreements.groupby("user", sort=True)
    }
    modality_metrics = {}
    for modality in MODALITIES:
        correct = output[f"{modality}_prediction"] == output["answer"]
        modality_metrics[modality] = {
            "rows": int(len(output)),
            "present_rows": int(output[f"{modality}_present"].sum()),
            "accuracy_all_rows": float(correct.mean()),
            "accuracy_present_rows": float(correct[output[f"{modality}_present"]].mean()),
        }

    invalid = int(output["invalid"].sum())
    gate_checks = {
        "disagreements_at_least_30": disagreement_metrics["rows"] >= 30,
        "candidate_accuracy_at_least_0_60": (
            disagreement_metrics["candidate_accuracy"] is not None
            and disagreement_metrics["candidate_accuracy"] >= 0.60
        ),
        "parent_accuracy_at_most_0_40": (
            disagreement_metrics["parent_accuracy"] is not None
            and disagreement_metrics["parent_accuracy"] <= 0.40
        ),
        "first_subject_half_positive": halves["first_nine"]["net_correct_vs_parent"] > 0,
        "second_subject_half_positive": halves["second_nine"]["net_correct_vs_parent"] > 0,
        "invalid_zero": invalid == 0,
        "permutation_mismatches_zero": permutation_mismatches == 0,
        "synonym_mismatches_zero": synonym_mismatches == 0,
    }
    promoted = all(gate_checks.values())
    decision = "PROMOTE_TO_SEPARATE_TEST_BUILD_REVIEW" if promoted else "REJECT_NO_TEST_NO_SUBMISSION"

    oof_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(oof_path, index=False)
    report = {
        "experiment": "sensor_option_semantics_triad_v1",
        "decision": decision,
        "promoted": promoted,
        "test_qa_read": False,
        "test_prediction_written": False,
        "candidate_csv_written": False,
        "submission_performed": False,
        "validation": {
            "design": "18-fold subject-disjoint LOSO; one intact clip per HAU emotion row; fold-local fitting",
            "rows": int(len(output)),
            "subjects": sorted(output["user"].astype(int).unique().tolist()),
            "folds": fold_receipts,
            "modalities": modality_metrics,
            "consensus_eligible_rows": int(output["consensus_eligible"].sum()),
            "owned_parent": {
                "definition": "nonvisual_sensor_oof.csv prediction on HAU/emotion; imported parent_prediction column excluded",
                "overall_accuracy": float(output["parent_correct"].mean()),
            },
            "candidate_overall_accuracy": float(output["candidate_correct"].mean()),
            "disagreements": disagreement_metrics,
            "subject_halves": halves,
            "by_subject_on_disagreements": by_subject,
            "environment_proxy_on_disagreements": environments,
            "environment_proxy_caveat": "Released metadata calls x-y-z a trial; prefix bins are recording-condition proxies, not organizer-provided environment labels.",
            "invalid_predictions": invalid,
        },
        "counterfactual_audits": {
            "option_permutation": {
                "permutations_per_row": 24,
                "evaluation": "exact column reindex of independently computed option scores",
                "semantic_checks": permutation_checks,
                "semantic_mismatches": permutation_mismatches,
            },
            "synonym_rewrite": {
                "rewrite_form": "in a/an <adjective> manner",
                "semantic_checks": synonym_checks,
                "semantic_mismatches": synonym_mismatches,
                "vocabulary_size": len(ADJECTIVE),
            },
        },
        "promotion_gate": {
            "checks": gate_checks,
            "all_conditions_required": True,
            "passed": promoted,
        },
        "artifacts": {
            "protocol": str(protocol_path.relative_to(root)),
            "protocol_sha256": sha256(protocol_path),
            "oof": str(oof_path.relative_to(root)),
            "oof_sha256": sha256(oof_path),
            "code": str(Path(__file__).relative_to(root)),
            "code_sha256": sha256(Path(__file__)),
            "training_qa_sha256": sha256(train_path),
            "feature_cache_sha256": sha256(feature_path),
            "owned_parent_oof_sha256": sha256(parent_path),
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "seed": SEED,
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
