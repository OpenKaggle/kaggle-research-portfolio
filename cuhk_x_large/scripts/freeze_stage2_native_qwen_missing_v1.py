#!/usr/bin/env python3
"""Freeze the label-independent all-missing-skeleton HARn/single VLM cohort."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


TRAIN_SHA = "2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc"
FEATURE_SHA = "a8ed7d5925977dabd18b4b55a2beecb02a8a7435ce0773268a41d188cefdd661"
VISUAL_SHA = "e31e3b7c6f3799f8dd179e01577409ae45721b06d33e37c6f80b8366534021e2"
MODEL_SHA = "6f2156b299b448eb9e184f8b9775ef07d4c270de940a668b5d509da9248db5a4"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    feature_path = root / "cache/nonvisual_features.npz"
    visual_path = root / "cache/harn_visual_manifest.json"
    model_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    manifest_path = root / "artifacts/manifests/stage2_native_qwen_missing_sensor_v1.csv"
    protocol_path = root / "reports/stage2_native_qwen_missing_sensor_v1_protocol.json"
    if protocol_path.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite an already frozen cohort")
    expected = {
        train_path: TRAIN_SHA,
        feature_path: FEATURE_SHA,
        visual_path: VISUAL_SHA,
        model_path: MODEL_SHA,
    }
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise ValueError(f"Frozen input hash mismatch: {path}")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    with np.load(feature_path) as cache:
        units = cache["units"].astype(str)
        skeleton = cache["skeleton"]
        unit_index = {unit: index for index, unit in enumerate(units)}
        eligible = train[(train["source"] == "HARn") & (train["category"] == "single")].copy()
        eligible["sensor_present"] = [
            "Training/" + path in unit_index
            and bool(np.isfinite(skeleton[unit_index["Training/" + path]]).any())
            for path in eligible["path"]
        ]
    selected = eligible[~eligible["sensor_present"]].copy()
    selected["subject"] = selected["path"].str.extract(r"/user(\d+)/").astype(int)
    selected["subject_half"] = np.where(selected["subject"] <= 9, "first_nine", "second_nine")

    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    lookup = {(item["unit"], item["modality"]): item for item in visual}
    records = []
    for row in selected.sort_values("qa_id").itertuples(index=False):
        item = lookup.get((row.path, "Depth"))
        if item is None:
            raise FileNotFoundError(f"No Depth video for {row.path}")
        video = root / "data/raw/visual_harn" / item["path"]
        if not video.is_file() or sha256(video) != item["sha256"]:
            raise ValueError(f"Video missing or hash mismatch: {video}")
        records.append(
            {
                "qa_id": row.qa_id,
                "source": row.source,
                "category": row.category,
                "path": row.path,
                "subject": int(row.subject),
                "subject_half": row.subject_half,
                "modality": "Depth",
                "video_relative_path": str(video.relative_to(root)),
                "video_sha256": item["sha256"],
            }
        )
    cohort = pd.DataFrame(records)
    if len(cohort) != 40 or cohort["qa_id"].duplicated().any() or cohort["path"].duplicated().any():
        raise ValueError("Expected exactly 40 unique all-missing-skeleton rows/clips")

    historical_ids: set[str] = set()
    historical_logs: list[dict[str, str]] = []
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        historical_logs.append({"path": str(path.relative_to(root)), "sha256": sha256(path)})
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                historical_ids.add(str(json.loads(line).get("qa_id", "")))
    cohort["historically_observed_by_any_vlm"] = cohort["qa_id"].isin(historical_ids)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cohort.to_csv(manifest_path, index=False)
    prompt = (
        "Classify the main human action shown in the video.\n"
        "{question}\n{options}\n"
        "Reply with exactly one capital letter from A/B/C/D. Do not add punctuation or explanation."
    )
    protocol = {
        "schema_version": 1,
        "experiment": "stage2_native_qwen_missing_sensor_v1",
        "status": "FROZEN_BEFORE_QWEN_INFERENCE",
        "selection": {
            "rule": "Every official training HARn/single row whose frozen skeleton feature row has no finite value; labels and prior VLM predictions are not used.",
            "rows": int(len(cohort)),
            "clips": int(cohort["path"].nunique()),
            "subject_halves": cohort["subject_half"].value_counts().sort_index().to_dict(),
            "historically_observed_rows": int(cohort["historically_observed_by_any_vlm"].sum()),
            "historically_unobserved_rows": int((~cohort["historically_observed_by_any_vlm"]).sum()),
            "manifest": str(manifest_path.relative_to(root)),
            "manifest_sha256": sha256(manifest_path),
        },
        "inference": {
            "model": "mlx-community/Qwen3-VL-4B-Instruct-4bit",
            "revision": "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b",
            "license": "apache-2.0",
            "network": "disabled before model import/load",
            "modality": "Depth",
            "fps": 1.0,
            "temperature": 0.0,
            "max_tokens": 8,
            "prompt_template": prompt,
            "prompt_template_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        },
        "gate": {
            "minimum_rows": 30,
            "valid_rate_min": 1.0,
            "accuracy_min": 0.6,
            "both_subject_halves_accuracy_min": 0.5,
            "must_not_reduce_core_oof_accuracy": True,
            "all_conditions_required": True,
        },
        "history_audit": historical_logs,
        "inputs": {str(path.relative_to(root)): digest for path, digest in expected.items()},
        "prohibited": [
            "Reading historical VLM predictions to choose cohort rows or prompt",
            "Using Fresh20 as a selector",
            "Reading test QA or producing a test prediction before this gate passes",
        ],
    }
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"protocol": str(protocol_path), "protocol_sha256": sha256(protocol_path), **protocol["selection"]}, indent=2))


if __name__ == "__main__":
    main()
