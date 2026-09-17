#!/usr/bin/env python3
"""Freeze a fresh 48-row HARn screen for the Stage2-native route."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SEED = 20260911
USERS_A = [1, 2, 3, 4, 5, 6, 7, 8, 9]
USERS_B = [16, 17, 18, 19, 20, 21, 22, 23, 24]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def stable(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    runner_path = root / "scripts/run_harn_stage2_native_v1.py"
    manifest_path = root / "cache/harn_visual_manifest.json"
    seen_ids: set[str] = set()
    seen_clips: set[str] = set()
    history = []
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        rows = 0
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            qa_id, clip = str(item.get("qa_id", "")), str(item.get("path", ""))
            if qa_id.startswith("training_"):
                seen_ids.add(qa_id)
            if clip.startswith("HARn/"):
                seen_clips.add(clip)
            rows += 1
        history.append({"path": str(path.relative_to(root)), "sha256": sha256(path), "rows": rows})
    manifest = json.loads(manifest_path.read_text())
    depth_units = {item["unit"] for item in manifest if item["modality"] == "Depth"}
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    frame = train[(train["source"] == "HARn") & train["path"].isin(depth_units) & ~train["qa_id"].isin(seen_ids) & ~train["path"].isin(seen_clips)].copy()
    frame["user"] = frame["path"].str.extract(r"/user(\d+)/", expand=False).astype(int)
    selected = []
    used_clips: set[str] = set()
    for user in USERS_A + USERS_B:
        rows = frame[(frame["user"] == user) & (frame["category"] == "single")].copy()
        rows["stable"] = rows["qa_id"].map(stable)
        rows = rows.sort_values(["stable", "qa_id"])
        for row in rows.itertuples(index=False):
            if row.path not in used_clips:
                selected.append(row)
                used_clips.add(row.path)
            if sum(int(item.user) == user and item.category == "single" for item in selected) == 2:
                break
    for half, users in (("A_user1_9", USERS_A), ("B_user16_24", USERS_B)):
        eligible_users = []
        for user in users:
            rows = frame[(frame["user"] == user) & (frame["category"] == "object_interaction") & ~frame["path"].isin(used_clips)].copy()
            if not rows.empty:
                eligible_users.append(user)
        chosen_users = sorted(eligible_users, key=lambda value: stable(f"object-user{value}"))[:6]
        if len(chosen_users) != 6:
            raise ValueError(f"Insufficient fresh object subjects in {half}")
        for user in chosen_users:
            rows = frame[(frame["user"] == user) & (frame["category"] == "object_interaction") & ~frame["path"].isin(used_clips)].copy()
            rows["stable"] = rows["qa_id"].map(stable)
            row = rows.sort_values(["stable", "qa_id"]).iloc[0]
            selected.append(row)
            used_clips.add(row["path"])
    chosen = pd.DataFrame(selected)
    chosen["subject"] = "user" + chosen["user"].astype(str)
    chosen["subject_half"] = np.where(chosen["user"].isin(USERS_A), "A_user1_9", "B_user16_24")
    frozen = chosen[["qa_id", "source", "category", "path", "subject", "subject_half"]].sort_values(["subject_half", "subject", "category", "qa_id"]).reset_index(drop=True)
    if len(frozen) != 48 or frozen["qa_id"].nunique() != 48 or frozen["path"].nunique() != 48:
        raise ValueError("Fresh48 invariant failed")
    if frozen["category"].value_counts().to_dict() != {"single": 36, "object_interaction": 12}:
        raise ValueError("Fresh48 task balance failed")
    if frozen["subject_half"].value_counts().to_dict() != {"A_user1_9": 24, "B_user16_24": 24}:
        raise ValueError("Fresh48 half balance failed")
    out = args.output_dir or root
    selection_path = out / "harn_stage2_native48.csv" if args.output_dir else root / "artifacts/manifests/harn_stage2_native48.csv"
    protocol_path = out / "harn_stage2_native48_protocol.json" if args.output_dir else root / "reports/harn_stage2_native48_protocol.json"
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    frozen.to_csv(selection_path, index=False)
    inputs = {
        "train_sha256": sha256(train_path),
        "test_sha256": sha256(root / "data/raw/kaggle/test_qa.csv"),
        "sample_sha256": sha256(root / "data/raw/kaggle/sample_submission.csv"),
        "sensor_oof_sha256": sha256(root / "artifacts/oof/harn_multimodal_extratrees_oof.csv"),
        "model_manifest_sha256": sha256(root / "reports/qwen3_vl_4b_mlx_model_manifest.json"),
        "sensor_model_sha256": sha256(root / "artifacts/models/harn_multimodal_extratrees/selected.joblib"),
        "feature_cache_sha256": sha256(root / "cache/nonvisual_features.npz"),
        "harn_visual_manifest_sha256": sha256(manifest_path),
        "test_visual_manifest_sha256": sha256(root / "cache/test_visual_manifest.json"),
        "exposure_registry_sha256": sha256(root / "artifacts/manifests/vlm_exposure_registry.jsonl"),
        "runner_sha256": sha256(runner_path),
    }
    protocol = {
        "schema_version": 1,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_FRESH48_VLM_OR_TEST_NATIVE_INFERENCE",
        "history": {"training_qa_ids": len(seen_ids), "harn_clips": len(seen_clips), "artifacts": history},
        "selection": {"seed": SEED, "labels_used": False, "rows": 48, "unique_clips": 48, "tasks": {"single": 36, "object_interaction": 12}, "subject_halves": {"A_user1_9": 24, "B_user16_24": 24}},
        "route": {"single": "sensor unless VLM+base jointly veto; all-different needs sensor margin >=0.15", "object_interaction": "sensor only when VLM agrees and margin >=0.05; otherwise owned base", "vlm": {"model": "mlx-community/Qwen3-VL-4B-Instruct-4bit", "revision": "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b", "fixed_frames": 8, "max_tokens": 8}},
        "gates": {"network": "socket blocked and no network client/URL in runner", "implementation": ">=47/48 valid VLM, zero inference/read errors", "equal_budget": "exactly 8 uniformly sampled frames and max 8 output tokens for every row", "subject_macro": ">=+2 percentage points versus owned base", "worst_subject": "degradation no worse than 3 percentage points", "overall": ">=+6/48 exact versus owned base", "single": ">=+6/36 exact", "object": "nonnegative", "halves": "strictly positive net in both fixed halves", "changed": ">=10 rows, candidate accuracy >=0.75, base accuracy <=0.40", "all_required": True, "test_policy": "do not open test VLM or create candidate until all gates pass", "submission": "prohibited"},
        "inputs": inputs,
        "selection_sha256": sha256(selection_path),
        "selected_qa_ids": frozen["qa_id"].tolist(),
        "selected_clips": frozen["path"].tolist(),
    }
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    print(json.dumps(protocol, indent=2))
    print("selection_sha256", sha256(selection_path))
    print("protocol_sha256", sha256(protocol_path))


if __name__ == "__main__":
    import numpy as np
    main()
