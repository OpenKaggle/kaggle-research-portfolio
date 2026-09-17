#!/usr/bin/env python3
"""Freeze 20 genuinely unseen HARn QA/clip pairs for subject-clustered VLM validation."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SEED = 20260910
CATEGORIES = ("single", "object_interaction")
SUBJECTS_TO_SELECT = 10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def historical_vlm_inputs(root: Path) -> tuple[set[str], set[str], list[dict[str, object]]]:
    qa_ids: set[str] = set()
    clips: set[str] = set()
    artifacts = []
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        rows = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            qa_id = str(item.get("qa_id", ""))
            clip = str(item.get("path", ""))
            if qa_id.startswith("training_"):
                qa_ids.add(qa_id)
            if clip.startswith("HARn/"):
                clips.add(clip)
            rows += 1
        artifacts.append(
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256(path),
                "rows": rows,
            }
        )
    return qa_ids, clips, artifacts


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    visual_manifest_path = root / "cache/harn_visual_manifest.json"
    parent_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    selection_path = root / "artifacts/manifests/vlm_fresh20_validation.csv"
    protocol_path = root / "reports/vlm_fresh20_frozen_protocol.json"
    if selection_path.exists() or protocol_path.exists():
        raise FileExistsError("Fresh20 protocol is immutable and already exists")

    historical_ids, historical_clips, historical_artifacts = historical_vlm_inputs(root)
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    visual_manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, dict[str, object]]] = {}
    for item in visual_manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item
    eligible = qa[
        (qa["source"] == "HARn")
        & qa["category"].isin(CATEGORIES)
        & qa["path"].isin(available)
        & ~qa["qa_id"].isin(historical_ids)
        & ~qa["path"].isin(historical_clips)
    ].copy()
    eligible["subject"] = eligible["path"].str.extract(r"/(user\d+)/", expand=False)
    eligible["action"] = eligible["path"].str.split("/").str[1]
    eligible_counts = eligible.groupby(["subject", "category"]).size().unstack(fill_value=0)
    candidate_subjects = [
        subject
        for subject, values in eligible_counts.iterrows()
        if all(int(values.get(category, 0)) > 0 for category in CATEGORIES)
    ]
    subjects = sorted(candidate_subjects, key=stable_key)[:SUBJECTS_TO_SELECT]
    if len(subjects) != SUBJECTS_TO_SELECT:
        raise ValueError("Fewer than 10 subjects have fresh rows in both tasks")

    selected_rows: list[pd.Series] = []
    used_paths: set[str] = set()
    used_actions: set[str] = set()
    for subject in subjects:
        subject_rows = eligible[eligible["subject"] == subject]
        for category in CATEGORIES:
            candidates = subject_rows[subject_rows["category"] == category].copy()
            candidates["new_path"] = ~candidates["path"].isin(used_paths)
            candidates["new_action"] = ~candidates["action"].isin(used_actions)
            candidates["stable_key"] = candidates["qa_id"].map(stable_key)
            candidates = candidates.sort_values(
                ["new_path", "new_action", "stable_key", "qa_id"],
                ascending=[False, False, True, True],
            )
            row = candidates.iloc[0]
            if row["qa_id"] in historical_ids or row["path"] in historical_clips:
                raise ValueError("Historical VLM input leaked into fresh selection")
            selected_rows.append(row)
            used_paths.add(str(row["path"]))
            used_actions.add(str(row["action"]))

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    if len(selected) != 20 or selected["qa_id"].duplicated().any() or selected["path"].duplicated().any():
        raise ValueError("Fresh selection uniqueness invariant failed")
    if selected.groupby("subject").size().tolist() != [2] * SUBJECTS_TO_SELECT:
        raise ValueError("Fresh selection subject balance invariant failed")
    if selected.groupby("category").size().to_dict() != {
        "object_interaction": 10,
        "single": 10,
    }:
        raise ValueError("Fresh selection task balance invariant failed")

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction"]
    ].rename(columns={"prediction": "subject_disjoint_parent_prediction"})
    selected = selected.merge(parent, on="qa_id", validate="one_to_one")
    rows = []
    for row in selected.itertuples(index=False):
        modality = next(name for name in ("Depth_Color", "IR", "Depth") if name in available[row.path])
        video = available[row.path][modality]
        video_path = root / "data/raw/visual_harn" / video["path"]
        if not video_path.is_file() or sha256(video_path) != video["sha256"]:
            raise ValueError(f"Fresh selected video failed file/hash check: {row.path}")
        rows.append(
            {
                "qa_id": row.qa_id,
                "category": row.category,
                "subject": row.subject,
                "action": row.action,
                "path": row.path,
                "modality": modality,
                "video_manifest_sha256": video["sha256"],
                "subject_disjoint_parent_prediction": row.subject_disjoint_parent_prediction,
            }
        )
    frozen = pd.DataFrame(rows)
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    frozen.to_csv(selection_path, index=False)
    protocol = {
        "schema_version": 1,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_FIRST_EVER_VLM_INFERENCE",
        "purpose": "fresh one-video/one-question subject-clustered validation screen",
        "freshness": {
            "eligible_qa_and_clip_both_unseen": int(len(eligible)),
            "historical_training_qa_ids": len(historical_ids),
            "historical_harn_clips": len(historical_clips),
            "selected_qa_overlap_with_history": 0,
            "selected_clip_overlap_with_history": 0,
            "historical_artifacts_frozen_at_selection": historical_artifacts,
        },
        "selection_policy": {
            "labels_used_for_selection": False,
            "seed": SEED,
            "subjects": subjects,
            "rows_per_subject": 2,
            "rows_per_category": {"single": 10, "object_interaction": 10},
            "tie_break": "stable SHA-256; prefer globally unused clip and action",
            "comparator": "18-fold OOF parent prediction excluding each row's subject",
        },
        "precommitted_gate": {
            "implementation": "more than 1/20 read or inference failures stops and requires repair",
            "primary": "one-sided exact sign test over non-tied subject deltas p <= 0.05",
            "hard_subject_stop": "any subject with negative aggregate delta rejects promotion",
            "task_stability": "single and object_interaction must each have positive net correctness",
            "cohort_stability": "both pre-frozen five-subject halves must have positive net correctness",
            "next_step_if_pass": "larger fresh subject-disjoint validation only",
            "submission": "prohibited",
        },
        "frozen_rows": len(frozen),
        "task_distribution": dict(sorted(Counter(frozen["category"]).items())),
        "subject_distribution": dict(sorted(Counter(frozen["subject"]).items())),
        "action_distribution": dict(sorted(Counter(frozen["action"]).items())),
        "selected_qa_ids": frozen["qa_id"].tolist(),
        "selected_clips": frozen["path"].tolist(),
        "inputs": {
            "training_qa_sha256": sha256(qa_path),
            "harn_visual_manifest_sha256": sha256(visual_manifest_path),
            "subject_disjoint_parent_oof_sha256": sha256(parent_path),
        },
        "selection_file": str(selection_path.relative_to(root)),
        "selection_file_sha256": sha256(selection_path),
        "code_sha256": sha256(Path(__file__)),
    }
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(protocol, indent=2))
    print(f"protocol_sha256={sha256(protocol_path)}")


if __name__ == "__main__":
    main()
