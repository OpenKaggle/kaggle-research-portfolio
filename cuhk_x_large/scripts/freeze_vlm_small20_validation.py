#!/usr/bin/env python3
"""Freeze a label-independent 20-question, subject-aware VLM validation screen."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SEED = 20260909
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


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    video_manifest_path = root / "cache/partial_visual_manifest.json"
    parent_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    selection_path = root / "artifacts/manifests/vlm_small20_validation.csv"
    protocol_path = root / "reports/vlm_small20_frozen_protocol.json"

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    video_manifest = json.loads(video_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, dict[str, object]]] = {}
    for item in video_manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item

    eligible = qa[
        (qa["source"] == "HARn")
        & qa["category"].isin(CATEGORIES)
        & qa["path"].isin(available)
    ].copy()
    eligible["subject"] = eligible["path"].str.extract(r"/(user\d+)/", expand=False)
    eligible["action"] = eligible["path"].str.split("/").str[1]
    subjects = sorted(
        [
            subject
            for subject, group in eligible.groupby("subject")
            if set(group["category"]) == set(CATEGORIES)
        ],
        key=stable_key,
    )[:SUBJECTS_TO_SELECT]
    if len(subjects) != SUBJECTS_TO_SELECT:
        raise ValueError("Insufficient subjects with both target categories")

    selected_rows: list[pd.Series] = []
    used_paths: set[str] = set()
    used_actions: set[str] = set()
    for subject in subjects:
        subject_rows = eligible[eligible["subject"] == subject]
        for category in CATEGORIES:
            candidates = subject_rows[subject_rows["category"] == category].copy()
            candidates["new_action"] = ~candidates["action"].isin(used_actions)
            candidates["new_path"] = ~candidates["path"].isin(used_paths)
            candidates["stable_key"] = candidates["qa_id"].map(stable_key)
            candidates = candidates.sort_values(
                ["new_path", "new_action", "stable_key", "qa_id"],
                ascending=[False, False, True, True],
            )
            row = candidates.iloc[0]
            selected_rows.append(row)
            used_paths.add(str(row["path"]))
            used_actions.add(str(row["action"]))

    selected = pd.DataFrame(selected_rows).reset_index(drop=True)
    if len(selected) != 20 or selected["qa_id"].duplicated().any():
        raise ValueError("Frozen selection row invariant failed")
    if selected.groupby("subject").size().tolist() != [2] * SUBJECTS_TO_SELECT:
        raise ValueError("Frozen subject balance invariant failed")
    if selected.groupby("category").size().to_dict() != {
        "object_interaction": 10,
        "single": 10,
    }:
        raise ValueError("Frozen task balance invariant failed")

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)
    parent = parent[["qa_id", "prediction"]].rename(
        columns={"prediction": "subject_disjoint_parent_prediction"}
    )
    selected = selected.merge(parent, on="qa_id", validate="one_to_one")
    rows = []
    modality_priority = ("Depth_Color", "IR", "Depth")
    for row in selected.itertuples(index=False):
        modality = next(name for name in modality_priority if name in available[row.path])
        video = available[row.path][modality]
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
        "status": "FROZEN_BEFORE_INFERENCE",
        "purpose": "fixed small-batch audit of the established one-video/one-question VLM path",
        "selection_policy": {
            "labels_used_for_selection": False,
            "seed": SEED,
            "eligible_source": "HARn",
            "eligible_categories": list(CATEGORIES),
            "subjects": subjects,
            "rows_per_subject": 2,
            "rows_per_category": {"single": 10, "object_interaction": 10},
            "tie_break": "stable SHA-256 order; prefer an unused clip and action",
            "subject_disjoint_statement": (
                "The zero-shot VLM has no task-data fitting. The frozen comparator prediction "
                "for every row comes from the 18-fold model that excluded that row's subject."
            ),
        },
        "precommitted_stop_rules": {
            "implementation_failure_rate": (
                "If read, inference, or parser implementation failures exceed 1/20 (5%), "
                "stop candidate evaluation and repair the pipeline before judging the model."
            ),
            "invalid_outputs": "Exclude invalid/empty outputs from scientific accuracy; report them separately.",
            "candidate_gate": (
                "Do not propose an override unless valid VLM evidence has positive net correctness "
                "versus the frozen subject-disjoint parent separately in both tasks, remains positive "
                "in both fixed five-subject halves, and maps to a label-free test-time rule."
            ),
            "submission": "This audit cannot submit automatically.",
        },
        "frozen_rows": len(frozen),
        "task_distribution": dict(sorted(Counter(frozen["category"]).items())),
        "subject_distribution": dict(sorted(Counter(frozen["subject"]).items())),
        "action_distribution": dict(sorted(Counter(frozen["action"]).items())),
        "selected_qa_ids": frozen["qa_id"].tolist(),
        "inputs": {
            "training_qa_sha256": sha256(qa_path),
            "partial_visual_manifest_sha256": sha256(video_manifest_path),
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
