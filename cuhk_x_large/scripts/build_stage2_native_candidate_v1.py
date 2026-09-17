#!/usr/bin/env python3
"""Build a fully owned Stage2-native candidate from arbitrary QA rows and clips."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from run_stage2_native_oof_v1 import LABELS, OwnedSemanticDecoder, norm, valid_prediction


EXPECTED = {
    "train": "2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc",
    "test": "d694c7abc5a003d5c9048098880f0f77716fae0eb18d1c9fe9330e4e987320a5",
    "sample": "456905af98ce5257042f3779982e5b48e0ea248fcdf38eb79c9dd3e4f88a0a38",
    "features": "a8ed7d5925977dabd18b4b55a2beecb02a8a7435ce0773268a41d188cefdd661",
    "harn_model": "592673f9ea7da7770ca0e95388e4379798acf6450284bfc359340175ef93d611",
    "hau_emotion_model": "7f20c9b509b01e3ee79b45d620fd43b5b83caaa6c0bc75ba707abbec32e3400e",
    "emotion_et_model": "4af817095c602500db2ad6a8a7637ded103de7fbae5a24cdc3765dcf7dc81a42",
    "core_report": "2f3caffe9e4aec49cd38ee722b1e3c403e6e009527703fbc1358cfd919bf5288",
    "qwen_report": "4d093c43141963a4be9c19db35cdc11bef0251cacd0ed475f3b93435da0cae18",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def install_network_block() -> dict[str, object]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    original_socket = socket.socket

    class BlockedSocket(original_socket):
        def connect(self, address: object) -> None:
            raise RuntimeError(f"Network disabled for Stage2-native build: {address}")

        def connect_ex(self, address: object) -> int:
            raise RuntimeError(f"Network disabled for Stage2-native build: {address}")

    def blocked_connection(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network disabled for Stage2-native build")

    socket.socket = BlockedSocket
    socket.create_connection = blocked_connection
    try:
        socket.create_connection(("example.invalid", 443), timeout=0.01)
        probe_blocked = False
    except RuntimeError:
        probe_blocked = True
    return {
        "hf_hub_offline": os.environ["HF_HUB_OFFLINE"],
        "transformers_offline": os.environ["TRANSFORMERS_OFFLINE"],
        "socket_probe_blocked": probe_blocked,
    }


def resolve_feature_unit(path: str, available: set[str]) -> str | None:
    normalized = str(path).replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if parts and Path(parts[-1]).suffix:
        parts.pop()
    if parts and parts[-1].lower() in {"depth", "color", "rgb", "ir", "infrared"}:
        parts.pop()
    clip = "/".join(parts) if parts else normalized
    direct = [normalized, clip, "Testing/" + normalized, "Training/" + normalized, "Testing/" + clip, "Training/" + clip]
    for candidate in direct:
        if candidate in available:
            return candidate
    match = re.search(r"large_model_track_test/LM_test_\d+", path)
    if match and "Testing/" + match.group(0) in available:
        return "Testing/" + match.group(0)
    suffix_matches = [
        unit
        for unit in available
        if unit.endswith("/" + normalized)
        or unit.endswith("/" + clip)
        or clip.endswith("/" + unit)
    ]
    return suffix_matches[0] if len(suffix_matches) == 1 else None


def harn_action_from_path(path: str) -> int:
    match = re.search(r"^HARn/(\d+)_", path)
    if not match:
        raise ValueError(f"No HARn action ID in {path}")
    return int(match.group(1))


def answer_text(row: pd.Series) -> str:
    return norm(row[str(row["answer"])])


def harn_maps(train: pd.DataFrame) -> tuple[dict[str, Counter[int]], dict[int, Counter[str]]]:
    action_by_text: defaultdict[str, Counter[int]] = defaultdict(Counter)
    objects_by_action: defaultdict[int, Counter[str]] = defaultdict(Counter)
    for _, row in train[train["source"] == "HARn"].iterrows():
        action = harn_action_from_path(str(row["path"]))
        if row["category"] == "single":
            action_by_text[answer_text(row)][action] += 1
        elif row["category"] == "object_interaction":
            objects_by_action[action][answer_text(row)] += 1
    return dict(action_by_text), dict(objects_by_action)


def harn_prediction(
    row: pd.Series,
    probability: np.ndarray,
    classes: np.ndarray,
    maps: tuple[dict[str, Counter[int]], dict[int, Counter[str]]],
) -> tuple[str, bool]:
    action_by_text, objects_by_action = maps
    by_action = {int(label): float(score) for label, score in zip(classes, probability)}
    scores = []
    for label in LABELS:
        text = norm(row[label])
        if row["category"] == "single":
            counts = action_by_text.get(text, Counter())
            score = sum(by_action.get(action, 0.0) * count for action, count in counts.items()) / max(1, sum(counts.values()))
        else:
            score = sum(
                by_action.get(action, 0.0) * objects[text] / sum(objects.values())
                for action, objects in objects_by_action.items()
                if text in objects
            )
        scores.append(score)
    order = np.argsort(-np.asarray(scores), kind="stable")
    return LABELS[int(order[0])], max(scores) > 0.0


def option_prediction(row: pd.Series, probability: np.ndarray, classes: np.ndarray) -> tuple[str, bool]:
    by_class = {norm(label): float(score) for label, score in zip(classes, probability)}
    scores = np.asarray([by_class.get(norm(row[label]), 0.0) for label in LABELS])
    order = np.argsort(-scores, kind="stable")
    return LABELS[int(order[0])], bool(scores[order[0]] > 0.0)


def emotion_et_prediction(
    row: pd.Series,
    motion: np.ndarray,
    bundle: dict[str, object],
) -> tuple[str, bool]:
    option_index = bundle["option_index"]
    expanded = []
    supported = True
    for label in LABELS:
        onehot = np.zeros(len(option_index), dtype=np.float32)
        option = norm(row[label])
        if option not in option_index:
            supported = False
        else:
            onehot[option_index[option]] = 1.0
        expanded.append(np.concatenate((motion, onehot)))
    probability = bundle["model"].predict_proba(np.asarray(expanded, dtype=np.float32))[:, 1]
    order = np.argsort(-probability, kind="stable")
    return LABELS[int(order[0])], supported


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--input-qa", type=Path, default=None, help="Defaults to the official test QA; arbitrary QA IDs are allowed")
    parser.add_argument("--features", type=Path, default=None, help="Feature cache containing units matching input clip paths")
    parser.add_argument("--sample-order", type=Path, default=None, help="Optional two-column/order template; omission preserves input QA order")
    args = parser.parse_args()
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    if not args.output.is_absolute():
        args.output = root / args.output
    if not args.report.is_absolute():
        args.report = root / args.report
    official_mode = args.input_qa is None
    input_qa_path = args.input_qa or root / "data/raw/kaggle/test_qa.csv"
    feature_path = args.features or root / "cache/nonvisual_features.npz"
    sample_path = args.sample_order or (root / "data/raw/kaggle/sample_submission.csv" if official_mode else None)
    input_qa_path = input_qa_path if input_qa_path.is_absolute() else root / input_qa_path
    feature_path = feature_path if feature_path.is_absolute() else root / feature_path
    if sample_path is not None and not sample_path.is_absolute():
        sample_path = root / sample_path
    paths = {
        "train": root / "data/raw/kaggle/training_qa.csv",
        "input_qa": input_qa_path,
        "features": feature_path,
        "harn_model": root / "artifacts/models/nonvisual_rf_v1/harn_action.joblib",
        "hau_emotion_model": root / "artifacts/models/nonvisual_rf_v1/hau_emotion.joblib",
        "emotion_et_model": root / "artifacts/models/emotion_pairwise_extratrees_v1.joblib",
        "core_report": root / "reports/stage2_native_v1_oof_validation.json",
        "qwen_report": root / "reports/stage2_native_qwen_missing_sensor_v1_validation.json",
    }
    immutable_names = {"train", "harn_model", "hau_emotion_model", "emotion_et_model", "core_report", "qwen_report"}
    for name in immutable_names:
        path = paths[name]
        if sha256(path) != EXPECTED[name]:
            raise ValueError(f"Frozen {name} hash mismatch")
    if official_mode:
        if sha256(input_qa_path) != EXPECTED["test"] or sha256(feature_path) != EXPECTED["features"]:
            raise ValueError("Official QA/feature input hash mismatch")
        if sample_path is None or sha256(sample_path) != EXPECTED["sample"]:
            raise ValueError("Official sample-order hash mismatch")
    core_report = json.loads(paths["core_report"].read_text(encoding="utf-8"))
    qwen_report = json.loads(paths["qwen_report"].read_text(encoding="utf-8"))
    if not core_report["passed"] or qwen_report["passed"]:
        raise ValueError("Frozen promotion decisions do not permit this core-only build")
    network = install_network_block()
    if not network["socket_probe_blocked"]:
        raise RuntimeError("Network isolation failed")

    train = pd.read_csv(paths["train"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    input_qa = pd.read_csv(input_qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    required = {"qa_id", "source", "path", "category", "question", *LABELS}
    if not required.issubset(input_qa.columns) or input_qa["qa_id"].duplicated().any():
        raise ValueError("Input QA schema/ID invariant failed")
    if official_mode and len(input_qa) != 682:
        raise ValueError("Official test row count mismatch")
    base = OwnedSemanticDecoder().fit(train).predict(input_qa)
    prediction = pd.Series(base.to_numpy(), index=input_qa.index, dtype=str)
    source = pd.Series("owned_semantic_base", index=input_qa.index, dtype=str)

    with np.load(paths["features"]) as cache:
        units = cache["units"].astype(str)
        unit_index = {unit: index for index, unit in enumerate(units)}
        imu = cache["imu"].astype(np.float32)
        skeleton = cache["skeleton"].astype(np.float32)
    harn_model = joblib.load(paths["harn_model"])
    emotion_model = joblib.load(paths["hau_emotion_model"])
    et_bundle = joblib.load(paths["emotion_et_model"])
    harn_semantics = harn_maps(train)

    available_units = set(unit_index)
    for index, row in input_qa.iterrows():
        unit = resolve_feature_unit(str(row["path"]), available_units)
        if unit is None:
            continue
        feature_index = unit_index[unit]
        if row["source"] == "HARn" and row["category"] == "single":
            values = skeleton[feature_index]
            if not np.isfinite(values).any():
                continue
            probabilities = harn_model.predict_proba(values.reshape(1, -1))[0]
            candidate, supported = harn_prediction(row, probabilities, harn_model.classes_, harn_semantics)
            if supported:
                prediction.at[index] = candidate
                source.at[index] = "owned_harn_skeleton_rf"
        elif row["source"] == "HAU" and row["category"] == "emotion":
            combined = np.concatenate((imu[feature_index], skeleton[feature_index]))
            motion = imu[feature_index, np.asarray(et_bundle["motion_columns"], dtype=int)]
            if not np.isfinite(combined).any() or not np.isfinite(motion).any():
                continue
            rf_probability = emotion_model.predict_proba(combined.reshape(1, -1))[0]
            rf_prediction, rf_supported = option_prediction(row, rf_probability, emotion_model.classes_)
            et_prediction, et_supported = emotion_et_prediction(row, motion, et_bundle)
            if rf_supported and et_supported and rf_prediction == et_prediction:
                prediction.at[index] = rf_prediction
                source.at[index] = "owned_hau_emotion_et_rf_consensus"

    candidate = pd.DataFrame({"qa_id": input_qa["qa_id"], "prediction": prediction})
    if sample_path is not None:
        sample = pd.read_csv(sample_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        if set(input_qa["qa_id"]) != set(sample["qa_id"]):
            raise ValueError("Input QA/sample-order ID mismatch")
        candidate = sample[["qa_id"]].merge(candidate, on="qa_id", validate="one_to_one")
    categories = candidate.merge(input_qa[["qa_id", "category"]], on="qa_id", validate="one_to_one")
    invalid = sum(
        not valid_prediction(category, value)
        for category, value in zip(categories["category"], categories["prediction"])
    )
    if invalid:
        raise ValueError(f"Candidate contains {invalid} invalid predictions")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(args.output, index=False)
    report = {
        "experiment": "stage2_native_owned_candidate_v1",
        "network_isolation": network,
        "rows": int(len(candidate)),
        "unique_qa_ids": int(candidate["qa_id"].nunique()),
        "unique_input_clips": int(input_qa["path"].nunique()),
        "official_strict_mode": official_mode,
        "invalid_predictions": invalid,
        "fixed_third_party_test_vector_dependency": False,
        "qwen_prediction_effect": False,
        "prediction_source_counts": source.value_counts().sort_index().to_dict(),
        "output": str(args.output.relative_to(root)),
        "output_sha256": sha256(args.output),
        "inputs": {
            **{name: sha256(path) for name, path in paths.items()},
            **({"sample_order": sha256(sample_path)} if sample_path is not None else {}),
        },
        "code_sha256": sha256(Path(__file__)),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "runtime_seconds": time.perf_counter() - started,
        "submission": "NOT_ATTEMPTED",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
