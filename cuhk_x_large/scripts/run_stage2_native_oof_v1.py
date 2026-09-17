#!/usr/bin/env python3
"""Validate a full CUHK-X Stage2-native owned system without test answers.

The semantic base is implemented in this file and fitted only on each fold's 17
training subjects.  It never loads a public notebook, public test prediction, or
fixed 682-row answer vector.  Existing owned sensor OOF artifacts are added only
under the frozen gates in the preregistered protocol.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import platform
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


LABELS = "ABCD"
USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]
FIRST_HALF = set(USERS[:9])
SECOND_HALF = set(USERS[9:])
EXPECTED = {
    "train": "2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc",
    "features": "a8ed7d5925977dabd18b4b55a2beecb02a8a7435ce0773268a41d188cefdd661",
    "rf_oof": "8054484a387472f04336d6c37fe77c4b9ae442484940538f6aaa777a71f5b7b7",
    "et_oof": "c89c06f082d3214331ab39f8b14bb922899769b1ad7108b6b25ceaab298e8259",
    "harn_visual": "e31e3b7c6f3799f8dd179e01577409ae45721b06d33e37c6f80b8366534021e2",
    "test_visual": "041d7163fd3225509206b9fe722b592cc7f1d9b73a3a6da419b73ef47d7447c3",
    "qwen": "6f2156b299b448eb9e184f8b9775ef07d4c270de940a668b5d509da9248db5a4",
}


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


def atoms(value: object) -> tuple[str, ...]:
    return tuple(norm(piece) for piece in str(value).split(",") if piece.strip())


def extract_user(path: str) -> int:
    match = re.search(r"(?:^|/)user(\d+)(?:/|$)", path, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"No subject in {path}")
    return int(match.group(1))


def valid_prediction(category: str, value: str) -> bool:
    if category in {"single", "combination", "emotion", "object_interaction"}:
        return len(value) == 1 and value in LABELS
    if category == "multi":
        return bool(value) and value == "".join(sorted(set(value))) and set(value) <= set(LABELS)
    if category == "sequence":
        return len(value) == 4 and set(value) == set(LABELS)
    return False


class OwnedSemanticDecoder:
    """Fold-fitted semantic/clip decoder with semantic, not letter, tie-breaks."""

    def __init__(self, smoothing: float = 8.0, support_weight: float = 1.0):
        self.smoothing = smoothing
        self.support_weight = support_weight
        self.option_ok: Counter[tuple[str, str, str]] = Counter()
        self.option_n: Counter[tuple[str, str, str]] = Counter()
        self.slice_ok: Counter[tuple[str, str]] = Counter()
        self.slice_n: Counter[tuple[str, str]] = Counter()
        self.option_set_memory: dict[tuple[str, str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
        self.multi_sizes: dict[tuple[str, str], Counter[int]] = defaultdict(Counter)
        self.before: Counter[tuple[str, str]] = Counter()

    def fit(self, frame: pd.DataFrame) -> "OwnedSemanticDecoder":
        for _, row in frame.iterrows():
            source = str(row["source"])
            category = str(row["category"])
            answer = str(row["answer"])
            values = [str(row[label]) for label in LABELS]
            option_set = tuple(sorted(norm(value) for value in values))
            slice_key = (source, category)
            if category != "sequence":
                for label, value in zip(LABELS, values):
                    key = (source, category, norm(value))
                    self.option_n[key] += 1
                    self.slice_n[slice_key] += 1
                    if label in answer:
                        self.option_ok[key] += 1
                        self.slice_ok[slice_key] += 1
            if category == "multi":
                self.multi_sizes[slice_key][len(answer)] += 1
            elif category == "sequence":
                if len(answer) != 4 or set(answer) != set(LABELS):
                    raise ValueError("Invalid training sequence")
                ordered = [norm(row[label]) for label in answer]
                for left_index, left in enumerate(ordered):
                    for right in ordered[left_index + 1 :]:
                        self.before[(left, right)] += 1
            else:
                for label in answer:
                    if label in LABELS:
                        self.option_set_memory[(source, category, option_set)][norm(row[label])] += 1
        return self

    def _logit(self, row: pd.Series, value: str) -> float:
        slice_key = (str(row["source"]), str(row["category"]))
        base = self.slice_ok[slice_key] / max(1, self.slice_n[slice_key])
        key = (slice_key[0], slice_key[1], norm(value))
        probability = (self.option_ok[key] + self.smoothing * base) / (
            self.option_n[key] + self.smoothing
        )
        probability = min(max(probability, 1e-6), 1.0 - 1e-6)
        return math.log(probability / (1.0 - probability))

    def _sequence(self, row: pd.Series) -> str:
        best_score = -math.inf
        best_semantics: tuple[str, ...] | None = None
        best_labels = ""
        for permutation in itertools.permutations(LABELS):
            semantics = tuple(norm(row[label]) for label in permutation)
            score = 0.0
            for left_index, left in enumerate(semantics):
                for right in semantics[left_index + 1 :]:
                    forward = self.before[(left, right)]
                    backward = self.before[(right, left)]
                    score += math.log((forward + 1.5) / (forward + backward + 3.0))
            # A semantic tuple tie-break remains invariant when letters are permuted.
            if score > best_score or (score == best_score and (best_semantics is None or semantics > best_semantics)):
                best_score = score
                best_semantics = semantics
                best_labels = "".join(permutation)
        return best_labels

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        output: dict[str, str] = {}
        for _, group in frame.groupby("path", sort=True):
            support: Counter[str] = Counter()
            for _, row in group.iterrows():
                if row["source"] == "HAU" and row["category"] in {"single", "multi", "combination", "sequence"}:
                    for label in LABELS:
                        if row["category"] == "combination":
                            support.update(atoms(row[label]))
                        else:
                            support.update([norm(row[label])])
            for _, row in group.iterrows():
                category = str(row["category"])
                if category == "sequence":
                    output[str(row["qa_id"])] = self._sequence(row)
                    continue
                values = [str(row[label]) for label in LABELS]
                option_set = tuple(sorted(norm(value) for value in values))
                memory = self.option_set_memory[(str(row["source"]), category, option_set)]
                scored: list[tuple[float, str, str]] = []
                for label, value in zip(LABELS, values):
                    own = Counter(atoms(value) if category == "combination" else [norm(value)])
                    external = sum(max(0, support[atom] - own[atom]) for atom in own)
                    score = self._logit(row, value) + math.log1p(memory[norm(value)]) + self.support_weight * external
                    scored.append((score, norm(value), label))
                # Highest score, then lexicographically highest semantic value.
                ranked = sorted(scored, key=lambda item: (item[0], item[1]), reverse=True)
                if category == "multi":
                    sizes = self.multi_sizes[(str(row["source"]), category)]
                    size = max(sizes, key=lambda count: (sizes[count], -count)) if sizes else 1
                    selected = {item[2] for item in ranked[:size]}
                    output[str(row["qa_id"])] = "".join(label for label in LABELS if label in selected)
                else:
                    output[str(row["qa_id"])] = ranked[0][2]
        result = frame["qa_id"].map(output)
        if result.isna().any():
            raise ValueError("Owned decoder missed rows")
        return result.astype(str)


def remap_prediction(value: str, old_to_new: dict[str, str], category: str) -> str:
    mapped = "".join(old_to_new[label] for label in value)
    return mapped if category == "sequence" else "".join(sorted(mapped))


def permute_frame(frame: pd.DataFrame, permutation: tuple[str, ...]) -> tuple[pd.DataFrame, dict[str, str], dict[str, str]]:
    changed = frame.copy()
    new_to_old = dict(zip(LABELS, permutation))
    old_to_new = {old: new for new, old in new_to_old.items()}
    old_values = changed[list(LABELS)].copy()
    for new_label, old_label in new_to_old.items():
        changed[new_label] = old_values[old_label]
    changed["answer"] = [
        remap_prediction(value, old_to_new, category)
        for value, category in zip(frame["answer"], frame["category"])
    ]
    return changed, new_to_old, old_to_new


def base_oof(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series(index=frame.index, dtype=str)
    for user in USERS:
        fit = frame["user"] != user
        valid = ~fit
        decoder = OwnedSemanticDecoder().fit(frame[fit])
        result.loc[valid] = decoder.predict(frame[valid]).to_numpy()
    if result.isna().any():
        raise ValueError("OOF base has missing rows")
    return result


def apply_owned_overlays(
    frame: pd.DataFrame,
    base_prediction: pd.Series,
    rf_by_id: dict[str, str],
    et_by_id: dict[str, str],
    et_present_by_id: dict[str, bool],
    skeleton_present_by_path: dict[str, bool],
) -> tuple[pd.Series, pd.Series]:
    prediction = base_prediction.copy()
    source = pd.Series("semantic_base", index=frame.index, dtype=str)
    for index, row in frame.iterrows():
        qa_id = str(row["qa_id"])
        if row["source"] == "HARn" and row["category"] == "single" and skeleton_present_by_path[str(row["path"])]:
            value = rf_by_id.get(qa_id, "")
            if value in LABELS:
                prediction.at[index] = value
                source.at[index] = "owned_harn_skeleton_rf"
        elif row["source"] == "HAU" and row["category"] == "emotion":
            rf = rf_by_id.get(qa_id, "")
            et = et_by_id.get(qa_id, "")
            if et_present_by_id.get(qa_id, False) and rf == et and et in LABELS:
                prediction.at[index] = et
                source.at[index] = "owned_hau_emotion_et_rf_consensus"
    return prediction, source


def metrics(frame: pd.DataFrame, prediction_column: str) -> dict[str, object]:
    correct = frame[prediction_column] == frame["answer"]
    base_correct = frame["semantic_base_prediction"] == frame["answer"]
    delta = correct.astype(int) - base_correct.astype(int)
    by_subject = {
        str(int(user)): {
            "rows": int(len(group)),
            "base_accuracy": float((group["semantic_base_prediction"] == group["answer"]).mean()),
            "system_accuracy": float((group[prediction_column] == group["answer"]).mean()),
            "net_gain": int(
                (group[prediction_column] == group["answer"]).sum()
                - (group["semantic_base_prediction"] == group["answer"]).sum()
            ),
        }
        for user, group in frame.groupby("user", sort=True)
    }
    by_category = {
        f"{source}/{category}": {
            "rows": int(len(group)),
            "base_accuracy": float((group["semantic_base_prediction"] == group["answer"]).mean()),
            "system_accuracy": float((group[prediction_column] == group["answer"]).mean()),
            "net_gain": int(
                (group[prediction_column] == group["answer"]).sum()
                - (group["semantic_base_prediction"] == group["answer"]).sum()
            ),
        }
        for (source, category), group in frame.groupby(["source", "category"], sort=True)
    }
    return {
        "rows": int(len(frame)),
        "semantic_base_correct": int(base_correct.sum()),
        "semantic_base_accuracy": float(base_correct.mean()),
        "system_correct": int(correct.sum()),
        "system_accuracy": float(correct.mean()),
        "net_gain": int(delta.sum()),
        "accuracy_gain": float(delta.mean()),
        "changed_vs_base": int((frame[prediction_column] != frame["semantic_base_prediction"]).sum()),
        "by_subject": by_subject,
        "by_category": by_category,
    }


def main() -> None:
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    paths = {
        "train": root / "data/raw/kaggle/training_qa.csv",
        "features": root / "cache/nonvisual_features.npz",
        "rf_oof": root / "artifacts/oof/nonvisual_sensor_oof.csv",
        "et_oof": root / "artifacts/oof/emotion_pairwise_extratrees_oof.csv",
        "harn_visual": root / "cache/harn_visual_manifest.json",
        "test_visual": root / "cache/test_visual_manifest.json",
        "qwen": root / "reports/qwen3_vl_4b_mlx_model_manifest.json",
    }
    protocol_path = root / "reports/stage2_native_v1_preregistered_protocol.json"
    oof_path = root / "artifacts/oof/stage2_native_v1_oof.csv"
    report_path = root / "reports/stage2_native_v1_oof_validation.json"
    for name, path in paths.items():
        if sha256(path) != EXPECTED[name]:
            raise ValueError(f"Frozen {name} hash mismatch")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN_BEFORE_OWNED_DECODER_OOF":
        raise ValueError("Protocol is not frozen")

    frame = pd.read_csv(paths["train"], encoding="utf-8-sig", dtype=str, keep_default_na=False)
    frame["user"] = frame["path"].map(extract_user)
    if len(frame) != 4087 or frame["qa_id"].duplicated().any() or frame["path"].nunique() != 1333:
        raise ValueError("Training row/clip invariant failed")
    if sorted(frame["user"].unique().tolist()) != USERS or frame.groupby("path")["user"].nunique().max() != 1:
        raise ValueError("Subject/clip grouping invariant failed")

    rf = pd.read_csv(paths["rf_oof"], dtype=str, keep_default_na=False)
    rf_by_id = rf.set_index("qa_id")["prediction"].to_dict()
    et = pd.read_csv(paths["et_oof"], dtype=str, keep_default_na=False)
    et_by_id = et.set_index("qa_id")["prediction"].to_dict()
    et_present_by_id = et.set_index("qa_id")["sensor_present"].str.lower().eq("true").to_dict()
    with np.load(paths["features"]) as cache:
        units = cache["units"].astype(str)
        skeleton = cache["skeleton"]
        unit_index = {unit: index for index, unit in enumerate(units)}
        skeleton_present_by_path = {
            path: (
                "Training/" + path in unit_index
                and bool(np.isfinite(skeleton[unit_index["Training/" + path]]).any())
            )
            for path in frame["path"].unique()
        }

    frame["semantic_base_prediction"] = base_oof(frame)
    frame["stage2_prediction"], frame["prediction_source"] = apply_owned_overlays(
        frame,
        frame["semantic_base_prediction"],
        rf_by_id,
        et_by_id,
        et_present_by_id,
        skeleton_present_by_path,
    )
    frame["semantic_base_correct"] = frame["semantic_base_prediction"] == frame["answer"]
    frame["stage2_correct"] = frame["stage2_prediction"] == frame["answer"]
    frame["invalid"] = [
        not valid_prediction(category, prediction)
        for category, prediction in zip(frame["category"], frame["stage2_prediction"])
    ]

    summary = metrics(frame, "stage2_prediction")
    halves = {}
    for name, users in (("first_nine", FIRST_HALF), ("second_nine", SECOND_HALF)):
        subset = frame[frame["user"].isin(users)]
        halves[name] = {
            "rows": int(len(subset)),
            "net_gain": int(subset["stage2_correct"].sum() - subset["semantic_base_correct"].sum()),
            "base_accuracy": float(subset["semantic_base_correct"].mean()),
            "system_accuracy": float(subset["stage2_correct"].mean()),
        }
    emotion = frame[
        (frame["source"] == "HAU")
        & (frame["category"] == "emotion")
        & (frame["stage2_prediction"] != frame["semantic_base_prediction"])
    ]
    emotion_gate = {
        "rows": int(len(emotion)),
        "system_correct": int(emotion["stage2_correct"].sum()),
        "system_accuracy": float(emotion["stage2_correct"].mean()),
        "base_correct": int(emotion["semantic_base_correct"].sum()),
        "base_accuracy": float(emotion["semantic_base_correct"].mean()),
        "net_gain": int(emotion["stage2_correct"].sum() - emotion["semantic_base_correct"].sum()),
    }

    original = frame.set_index("qa_id")["stage2_prediction"]
    category_by_id = frame.set_index("qa_id")["category"].astype(str).to_dict()
    training_qa_ids = set(category_by_id)
    permutation_mismatches = 0
    permutation_checks = 0
    for permutation in itertools.permutations(LABELS):
        permuted, new_to_old, old_to_new = permute_frame(frame, permutation)
        permuted_base = base_oof(permuted)
        permuted_rf = {
            qa_id: remap_prediction(value, old_to_new, category_by_id[qa_id])
            for qa_id, value in rf_by_id.items()
            if qa_id in training_qa_ids
        }
        permuted_et = {
            qa_id: remap_prediction(value, old_to_new, "emotion")
            for qa_id, value in et_by_id.items()
        }
        permuted_prediction, _ = apply_owned_overlays(
            permuted,
            permuted_base,
            permuted_rf,
            permuted_et,
            et_present_by_id,
            skeleton_present_by_path,
        )
        inverted = pd.Series(
            [
                remap_prediction(value, new_to_old, category)
                for value, category in zip(permuted_prediction, permuted["category"])
            ],
            index=permuted["qa_id"],
            dtype=str,
        )
        aligned = inverted.reindex(original.index)
        permutation_mismatches += int((aligned != original).sum())
        permutation_checks += len(frame)

    harn_manifest = json.loads(paths["harn_visual"].read_text(encoding="utf-8"))
    test_manifest = json.loads(paths["test_visual"].read_text(encoding="utf-8"))
    qwen_manifest = json.loads(paths["qwen"].read_text(encoding="utf-8"))
    visual_readiness = {
        "harn_visual_files": len(harn_manifest),
        "harn_visual_units": len({item["unit"] for item in harn_manifest}),
        "test_visual_files": len(test_manifest),
        "test_visual_units": len({item["unit"] for item in test_manifest}),
        "qwen_repo": qwen_manifest["repo_id"],
        "qwen_revision": qwen_manifest["revision"],
        "qwen_files": len(qwen_manifest["files"]),
        "core_prediction_effect": False,
    }

    harn_single_accuracy = summary["by_category"]["HARn/single"]["system_accuracy"]
    worst_subject_net = min(value["net_gain"] for value in summary["by_subject"].values())
    invalid = int(frame["invalid"].sum())
    gate_checks = {
        "full_system_accuracy_at_least_0_60": summary["system_accuracy"] >= 0.60,
        "gain_vs_semantic_base_at_least_0_03": summary["accuracy_gain"] >= 0.03,
        "first_subject_half_positive": halves["first_nine"]["net_gain"] > 0,
        "second_subject_half_positive": halves["second_nine"]["net_gain"] > 0,
        "worst_subject_net_nonnegative": worst_subject_net >= 0,
        "harn_single_accuracy_at_least_0_75": harn_single_accuracy >= 0.75,
        "hau_emotion_disagreements_at_least_100": emotion_gate["rows"] >= 100,
        "hau_emotion_accuracy_at_least_0_60": emotion_gate["system_accuracy"] >= 0.60,
        "hau_emotion_base_accuracy_at_most_0_40": emotion_gate["base_accuracy"] <= 0.40,
        "permutation_mismatches_zero": permutation_mismatches == 0,
        "invalid_zero": invalid == 0,
    }
    passed = all(gate_checks.values())
    decision = "PASS_CORE_ALLOW_NETWORK_FREE_TEST_BUILD" if passed else "REJECT_NO_TEST_NO_CANDIDATE_NO_SUBMISSION"

    oof_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    frame[
        [
            "qa_id", "source", "path", "category", "user", "answer",
            "semantic_base_prediction", "stage2_prediction", "prediction_source",
            "semantic_base_correct", "stage2_correct", "invalid",
        ]
    ].to_csv(oof_path, index=False)
    report = {
        "experiment": "stage2_native_owned_full_system_v1",
        "decision": decision,
        "passed": passed,
        "test_qa_read": False,
        "test_prediction_written": False,
        "candidate_csv_written": False,
        "submission_performed": False,
        "validation": {
            "design": "18-fold subject-disjoint LOSO; 4087 rows; 1333 intact clips",
            "summary": summary,
            "subject_halves": halves,
            "worst_subject_net_gain": worst_subject_net,
            "hau_emotion_consensus_disagreements": emotion_gate,
            "invalid_predictions": invalid,
        },
        "counterfactuals": {
            "semantic_base_ablation_accuracy": summary["semantic_base_accuracy"],
            "sensor_overlay_gain": summary["accuracy_gain"],
            "option_permutation": {
                "permutations": 24,
                "checks": permutation_checks,
                "mismatches": permutation_mismatches,
            },
        },
        "visual_qwen_readiness": visual_readiness,
        "gate": {"checks": gate_checks, "all_required": True, "passed": passed},
        "artifacts": {
            "protocol": str(protocol_path.relative_to(root)),
            "protocol_sha256": sha256(protocol_path),
            "oof": str(oof_path.relative_to(root)),
            "oof_sha256": sha256(oof_path),
            "code": str(Path(__file__).relative_to(root)),
            "code_sha256": sha256(Path(__file__)),
            "inputs": {name: sha256(path) for name, path in paths.items()},
        },
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
