#!/usr/bin/env python3
"""Freeze P1's sole fresh verb/object/temporal + sensor-gating screen."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20260911
LABELS = "ABCD"
EXPECTED = {
    "train": "2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc",
    "features": "a8ed7d5925977dabd18b4b55a2beecb02a8a7435ce0773268a41d188cefdd661",
    "visual": "e31e3b7c6f3799f8dd179e01577409ae45721b06d33e37c6f80b8366534021e2",
    "model": "6f2156b299b448eb9e184f8b9775ef07d4c270de940a668b5d509da9248db5a4",
    "sensor_oof": "8054484a387472f04336d6c37fe77c4b9ae442484940538f6aaa777a71f5b7b7",
    "core_oof": "8cf9879a1e147456db67dffe3246bb108e2816170dc787347ce24e93a8f7d1b7",
    "core_report": "2f3caffe9e4aec49cd38ee722b1e3c403e6e009527703fbc1358cfd919bf5288",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def select_balanced(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    """Round-robin subjects, then stable hash; never inspect labels."""
    groups = {
        int(subject): group.assign(stable=group["qa_id"].map(stable_key)).sort_values(["stable", "qa_id"])
        for subject, group in frame.groupby("subject", sort=True)
    }
    positions = {subject: 0 for subject in groups}
    selected = []
    while len(selected) < count:
        progressed = False
        for subject in sorted(groups, key=lambda value: stable_key(str(value))):
            position = positions[subject]
            if position < len(groups[subject]):
                selected.append(groups[subject].iloc[position])
                positions[subject] += 1
                progressed = True
                if len(selected) == count:
                    break
        if not progressed:
            raise ValueError("Not enough eligible rows for frozen stratum")
    return pd.DataFrame(selected).drop(columns="stable")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = {
        "train": root / "data/raw/kaggle/training_qa.csv",
        "features": root / "cache/nonvisual_features.npz",
        "visual": root / "cache/harn_visual_manifest.json",
        "model": root / "reports/qwen3_vl_4b_mlx_model_manifest.json",
        "sensor_oof": root / "artifacts/oof/nonvisual_sensor_oof.csv",
        "core_oof": root / "artifacts/oof/stage2_native_v1_oof.csv",
        "core_report": root / "reports/stage2_native_v1_oof_validation.json",
    }
    manifest_path = root / "artifacts/manifests/p1_decomposed_sensor_fresh48_v1.csv"
    protocol_path = root / "reports/p1_decomposed_sensor_fresh48_v1_protocol.json"
    if manifest_path.exists() or protocol_path.exists():
        raise FileExistsError("Refusing to overwrite the frozen P1 screen")
    for name, path in paths.items():
        if sha256(path) != EXPECTED[name]:
            raise ValueError(f"Frozen {name} hash mismatch")

    core = pd.read_csv(paths["core_oof"], dtype=str, keep_default_na=False)
    core["base_correct"] = core["semantic_base_prediction"] == core["answer"]
    core["system_correct"] = core["stage2_prediction"] == core["answer"]
    by_subject = core.groupby("user")[["base_correct", "system_correct"]].mean()
    subject_delta = by_subject["system_correct"] - by_subject["base_correct"]
    category = core.groupby(["source", "category"])[["base_correct", "system_correct"]].sum()
    action_net = int(category.loc[("HARn", "single"), "system_correct"] - category.loc[("HARn", "single"), "base_correct"])
    object_net = int(category.loc[("HARn", "object_interaction"), "system_correct"] - category.loc[("HARn", "object_interaction"), "base_correct"])
    training_gate = {
        "subject_blocked_macro_gain": float(subject_delta.mean()),
        "subject_blocked_macro_gain_at_least_0_02": bool(subject_delta.mean() >= 0.02),
        "action_net_gain": action_net,
        "action_nonnegative": action_net >= 0,
        "object_net_gain": object_net,
        "object_nonnegative": object_net >= 0,
        "worst_subject_accuracy_delta": float(subject_delta.min()),
        "worst_subject_loss_no_worse_than_0_03": bool(subject_delta.min() >= -0.03),
        "invalid_zero": bool((core["invalid"].str.lower() == "false").all()),
    }
    if not all(
        training_gate[key]
        for key in (
            "subject_blocked_macro_gain_at_least_0_02",
            "action_nonnegative",
            "object_nonnegative",
            "worst_subject_loss_no_worse_than_0_03",
            "invalid_zero",
        )
    ):
        raise ValueError("P1 training-side gate did not authorize a fresh screen")

    excluded_ids: set[str] = set()
    excluded_paths: set[str] = set()
    exclusion_sources: list[dict[str, object]] = []
    registry_path = root / "reports/vlm_exposure_registry.jsonl"
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            excluded_ids.add(str(item["qa_id"]))
            excluded_paths.add(str(item["path"]))
    exclusion_sources.append({"path": str(registry_path.relative_to(root)), "sha256": sha256(registry_path)})
    for path in sorted((root / "artifacts/manifests").glob("*.csv")):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if "qa_id" in frame:
            excluded_ids.update(frame["qa_id"])
        if "path" in frame:
            excluded_paths.update(frame["path"])
        exclusion_sources.append({"path": str(path.relative_to(root)), "sha256": sha256(path)})
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("qa_id"):
                    excluded_ids.add(str(item["qa_id"]))
                if item.get("path"):
                    excluded_paths.add(str(item["path"]))
        exclusion_sources.append({"path": str(path.relative_to(root)), "sha256": sha256(path)})

    train = pd.read_csv(paths["train"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    eligible = train[(train["source"] == "HARn") & train["category"].isin(["single", "object_interaction"])].copy()
    eligible["subject"] = eligible["path"].str.extract(r"/user(\d+)/").astype(int)
    eligible["subject_half"] = np.where(eligible["subject"] <= 9, "first_nine", "second_nine")
    eligible = eligible[~eligible["qa_id"].isin(excluded_ids) & ~eligible["path"].isin(excluded_paths)]
    parts = []
    for task in ("single", "object_interaction"):
        for half in ("first_nine", "second_nine"):
            parts.append(select_balanced(eligible[(eligible["category"] == task) & (eligible["subject_half"] == half)], 12))
    selected = pd.concat(parts, ignore_index=True).sort_values("qa_id")
    if len(selected) != 48 or selected["qa_id"].duplicated().any() or selected["path"].duplicated().any():
        raise ValueError("P1 screen must contain 48 unique QA rows and clips")

    visual = json.loads(paths["visual"].read_text(encoding="utf-8"))
    lookup = {(item["unit"], item["modality"]): item for item in visual}
    records = []
    for row in selected.itertuples(index=False):
        item = lookup.get((row.path, "Depth"))
        if item is None:
            raise FileNotFoundError(f"No complete Depth video for {row.path}")
        video = root / "data/raw/visual_harn" / item["path"]
        if not video.is_file() or sha256(video) != item["sha256"]:
            raise ValueError(f"Video missing/hash mismatch: {video}")
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
    frozen = pd.DataFrame(records)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    frozen.to_csv(manifest_path, index=False)

    generic_prompt = (
        "Inspect the entire timestamped depth video and answer the multiple-choice question.\n"
        "Question: {question}\n{options}\n"
        "Return exactly: evidence=<brief visual evidence>; answer=<A|B|C|D>"
    )
    decomposed_prompt = (
        "Inspect the entire timestamped depth video. Separately identify the main action verb, the manipulated object or body target, and when the decisive motion occurs; then answer the multiple-choice question.\n"
        "Question: {question}\n{options}\n"
        "Return exactly: verb=<brief>; object=<brief or none>; temporal=<early|middle|late|throughout>; answer=<A|B|C|D>"
    )
    protocol = {
        "schema_version": 1,
        "experiment": "p1_decomposed_sensor_fresh48_v1",
        "status": "FROZEN_BEFORE_SOLE_FRESH_SCREEN",
        "independent_implementation": {
            "VideoGEM_inspiration": "action/verb/object prompt decomposition only; this is not an exact reproduction of VideoGEM",
            "TimeLogic_inspiration": "absolute-time wording and temporal evidence field only; this is not an exact reproduction of TimeLogic",
        },
        "training_side_gate": training_gate,
        "selection": {
            "labels_used": False,
            "prior_vlm_predictions_used": False,
            "rows": 48,
            "unique_clips": 48,
            "strata": {"single/first_nine": 12, "single/second_nine": 12, "object_interaction/first_nine": 12, "object_interaction/second_nine": 12},
            "manifest": str(manifest_path.relative_to(root)),
            "manifest_sha256": sha256(manifest_path),
            "excluded_qa_ids": len(excluded_ids),
            "excluded_clips": len(excluded_paths),
            "exclusion_sources": exclusion_sources,
        },
        "equal_budget_pair": {
            "model": "mlx-community/Qwen3-VL-4B-Instruct-4bit",
            "revision": "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b",
            "network": "disabled before model import/load",
            "same_video": True,
            "modality": "Depth",
            "fps_each": 1.0,
            "max_generation_tokens_each": 48,
            "temperature_each": 0.0,
            "generic_prompt": generic_prompt,
            "generic_prompt_sha256": hashlib.sha256(generic_prompt.encode()).hexdigest(),
            "decomposed_prompt": decomposed_prompt,
            "decomposed_prompt_sha256": hashlib.sha256(decomposed_prompt.encode()).hexdigest(),
        },
        "sensor_route": {
            "sensor_source": "subject-disjoint HARn RandomForest OOF",
            "single": "Start with VLM answer. If sensor confidence >=0.15 and sensor equals semantic base while disagreeing with VLM, veto to semantic base; sensor/VLM agreement remains that answer.",
            "object_interaction": "Start with semantic base. Promote the VLM answer only when sensor confidence >=0.05 and sensor agrees with VLM.",
            "thresholds_inherited_before_screen": {"single": 0.15, "object_interaction": 0.05},
        },
        "promotion_gate": {
            "candidate_vs_equal_budget_generic_subject_macro_gain_min": 0.02,
            "single_net_gain_min": 0,
            "object_net_gain_min": 0,
            "worst_subject_accuracy_delta_min": -0.03,
            "generic_invalid_max": 0,
            "decomposed_invalid_max": 0,
            "decomposed_evidence_schema_invalid_max": 0,
            "parent_disagreement_net_gain_min_exclusive": 0,
            "all_conditions_required": True,
        },
        "inputs": {name: [str(path.relative_to(root)), sha256(path)] for name, path in paths.items()},
        "release": {
            "pass": "Permit one separate network-free arbitrary-ID/clip P1 packaging run; no submission yet.",
            "failure": "REJECT P1, preserve the existing core Stage2-native candidate and finalist hedges, and do not probe the leaderboard.",
        },
    }
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"protocol": str(protocol_path), "protocol_sha256": sha256(protocol_path), "selection": protocol["selection"], "training_side_gate": training_gate}, indent=2))


if __name__ == "__main__":
    main()
