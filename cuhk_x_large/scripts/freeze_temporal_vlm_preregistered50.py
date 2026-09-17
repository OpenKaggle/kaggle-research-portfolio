#!/usr/bin/env python3
"""Freeze a 50-row HAU temporal-VLM comparison before any new inference.

The selector is label-blind.  It snapshots every historical VLM log, excludes
both previously seen QA ids and previously seen clips, then selects five unique
clips (one per HAU task) for each of ten subjects.  The subject halves are
predefined by the dataset's numeric groups, not by results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SEED = 20260911
CATEGORIES = ("sequence", "combination", "multi", "single", "emotion")
ROWS_PER_CATEGORY = 10
LOGICAL_SELECTION = "artifacts/manifests/temporal_vlm_preregistered50.csv"
LOGICAL_PROTOCOL = "reports/temporal_vlm_preregistered50_protocol.json"
LOGICAL_RUNNER = "scripts/run_temporal_vlm_preregistered50.py"
MODEL_REPO = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
MODEL_REVISION = "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def numeric_subject(subject: str) -> int:
    return int(subject.removeprefix("user"))


def historical_vlm_inputs(root: Path) -> tuple[set[str], set[str], list[dict[str, object]]]:
    qa_ids: set[str] = set()
    clips: set[str] = set()
    artifacts: list[dict[str, object]] = []
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
            if clip.startswith(("HAU/", "HARn/")):
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


def choose_subjects(subjects: list[str], low: int, high: int, count: int) -> list[str]:
    group = [subject for subject in subjects if low <= numeric_subject(subject) <= high]
    chosen = sorted(group, key=stable_key)[:count]
    if len(chosen) != count:
        raise ValueError(f"Need {count} subjects in numeric range {low}-{high}; found {len(chosen)}")
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional staging directory. Logical project paths remain frozen in the protocol.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    parent_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    runner_path = root / LOGICAL_RUNNER
    if args.output_dir is None:
        selection_path = root / LOGICAL_SELECTION
        protocol_path = root / LOGICAL_PROTOCOL
    else:
        selection_path = args.output_dir / Path(LOGICAL_SELECTION).name
        protocol_path = args.output_dir / Path(LOGICAL_PROTOCOL).name
    if selection_path.exists() or protocol_path.exists():
        raise FileExistsError("Temporal-VLM preregistration is immutable and already exists")

    for required in (qa_path, parent_path, model_manifest_path, runner_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    historical_ids, historical_clips, historical_artifacts = historical_vlm_inputs(root)
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    eligible = qa[
        (qa["source"] == "HAU")
        & qa["category"].isin(CATEGORIES)
        & ~qa["qa_id"].isin(historical_ids)
        & ~qa["path"].isin(historical_clips)
        & ~qa["path"].str.contains("/user8/", regex=False)
    ].copy()
    eligible["subject"] = eligible["path"].str.extract(r"/(user\d+)/", expand=False)
    if eligible["subject"].isna().any():
        raise ValueError("Could not parse one or more HAU subjects")

    counts = eligible.groupby(["subject", "category"]).size().unstack(fill_value=0)
    candidate_subjects = [
        subject
        for subject, values in counts.iterrows()
        if all(int(values.get(category, 0)) >= 1 for category in CATEGORIES)
    ]
    half_a = choose_subjects(candidate_subjects, 1, 9, 5)
    half_b = choose_subjects(candidate_subjects, 16, 24, 5)
    subjects = half_a + half_b

    chosen: list[pd.Series] = []
    chosen_paths: set[str] = set()
    for subject in subjects:
        subject_rows = eligible[eligible["subject"] == subject]
        for category in CATEGORIES:
            candidates = subject_rows[
                (subject_rows["category"] == category)
                & ~subject_rows["path"].isin(chosen_paths)
            ].copy()
            candidates["stable_key"] = candidates["qa_id"].map(stable_key)
            candidates = candidates.sort_values(["stable_key", "qa_id"])
            if candidates.empty:
                raise ValueError(f"No unique fresh clip remains for {subject}/{category}")
            row = candidates.iloc[0]
            if row["qa_id"] in historical_ids or row["path"] in historical_clips:
                raise ValueError("Historical VLM input leaked into the frozen cohort")
            chosen.append(row)
            chosen_paths.add(str(row["path"]))

    selected = pd.DataFrame(chosen).reset_index(drop=True)
    if len(selected) != 50:
        raise ValueError(f"Expected 50 selected rows, got {len(selected)}")
    if selected["qa_id"].duplicated().any() or selected["path"].duplicated().any():
        raise ValueError("QA ids and clips must both be unique")
    if selected.groupby("category").size().to_dict() != {category: 10 for category in CATEGORIES}:
        raise ValueError("Category balance invariant failed")
    if selected.groupby("subject").size().tolist() != [5] * 10:
        raise ValueError("Subject balance invariant failed")

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction"]
    ].rename(columns={"prediction": "subject_disjoint_parent_prediction"})
    selected = selected.merge(parent, on="qa_id", validate="one_to_one")
    half_map = {subject: "A_user1_9" for subject in half_a} | {
        subject: "B_user16_24" for subject in half_b
    }
    frozen = pd.DataFrame(
        {
            "qa_id": selected["qa_id"],
            "category": selected["category"],
            "subject": selected["subject"],
            "subject_half": selected["subject"].map(half_map),
            "path": selected["path"],
            "expected_depth_relpath": selected["path"] + "/Depth/Depth.mp4",
            "subject_disjoint_parent_prediction": selected[
                "subject_disjoint_parent_prediction"
            ],
        }
    )
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    protocol_path.parent.mkdir(parents=True, exist_ok=True)
    frozen.to_csv(selection_path, index=False)

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != "apache-2.0"
    ):
        raise ValueError("Local model manifest does not match the preregistered model")

    protocol = {
        "schema_version": 1,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN_BEFORE_ANY_TEMPORAL_LOCALIZATION_OR_NEW_VLM_INFERENCE",
        "purpose": "question-driven coarse-localization to dense-frame sampling versus uniform sampling",
        "scientific_question": (
            "Does question-conditioned temporal localization improve exact HAU QA accuracy "
            "under the same model, coarse-context, fine-frame, and generation-token budget?"
        ),
        "freshness": {
            "historical_training_qa_ids": len(historical_ids),
            "historical_training_clips": len(historical_clips),
            "selected_qa_overlap_with_history": 0,
            "selected_clip_overlap_with_history": 0,
            "historical_artifacts_frozen_at_selection": historical_artifacts,
        },
        "selection_policy": {
            "labels_used_for_selection": False,
            "seed": SEED,
            "source": "HAU",
            "excluded_subject": "user8 (only HAU subject exposed in prior VLM runs)",
            "subject_halves": {
                "A_user1_9": half_a,
                "B_user16_24": half_b,
            },
            "rows_per_subject": 5,
            "rows_per_category": {category: ROWS_PER_CATEGORY for category in CATEGORIES},
            "clip_uniqueness": "all 50 paths unique",
            "tie_break": "stable SHA-256 of seed and qa_id",
            "comparator": "18-fold subject-disjoint public-graph OOF prediction",
        },
        "fixed_budget": {
            "model": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": "apache-2.0",
            "reason_for_instruct_not_thinking": (
                "Use the already pinned local model to isolate sampling as the only causal variable; "
                "a model change would confound this comparison."
            ),
            "coarse_frames": 8,
            "fine_frames_per_arm": 16,
            "coarse_generation_max_tokens": 64,
            "answer_generation_max_tokens_per_arm": 32,
            "temperature": 0.0,
            "arms": {
                "uniform": "16 fixed uniformly spaced fine frames",
                "localized": "16 chronological fine frames centered on up to two coarse indices selected from the question and options",
            },
            "fairness": (
                "Both arms receive the same shared 8-frame coarse localization call, one 16-frame "
                "answer video, the identical answer prompt, and 32 answer tokens. The uniform arm "
                "ignores the location indices but retains the same coarse-call allocation."
            ),
        },
        "metrics": {
            "primary": "localized minus uniform exact accuracy on sequence+combination+multi",
            "secondary": [
                "overall exact accuracy",
                "exact accuracy by all five tasks",
                "exact accuracy in both frozen subject halves",
                "localized accuracy where localized and subject-disjoint parent disagree",
                "invalid-output and implementation-failure rates",
                "runtime",
            ],
        },
        "precommitted_gate": {
            "implementation": "50/50 rows finish; zero read/inference failures; zero invalid answer outputs in either arm; at least 48/50 locator parses",
            "primary_temporal": "localized minus uniform >= 3 exact answers on the 30 sequence+combination+multi rows (>=10 percentage points)",
            "overall": "localized exact correctness is not below uniform",
            "task_stability": "sequence, combination, and multi each have nonnegative net correctness and at least two are strictly positive",
            "subject_half_stability": "localized has strictly positive net correctness in both frozen 25-row subject halves",
            "parent_disagreement": "at least 10 localized-parent disagreements; localized accuracy >=0.60 and parent accuracy <=0.40 on them",
            "operational": "experiment runtime after model load <=7200 seconds",
            "all_required": True,
            "candidate_if_pass": "validation-qualified only; a separate frozen full-test run is required before any candidate CSV",
            "candidate_if_fail": "NONE; reject the temporal-localization route without post-hoc cohort or threshold edits",
            "submission": "PROHIBITED in this experiment",
        },
        "frozen_rows": len(frozen),
        "selected_qa_ids": frozen["qa_id"].tolist(),
        "selected_clips": frozen["path"].tolist(),
        "category_distribution": dict(sorted(Counter(frozen["category"]).items())),
        "subject_distribution": dict(sorted(Counter(frozen["subject"]).items())),
        "subject_half_distribution": dict(sorted(Counter(frozen["subject_half"]).items())),
        "inputs": {
            "training_qa_sha256": sha256(qa_path),
            "subject_disjoint_parent_oof_sha256": sha256(parent_path),
            "model_manifest_sha256": sha256(model_manifest_path),
            "runner_sha256": sha256(runner_path),
            "freezer_sha256": sha256(Path(__file__)),
        },
        "selection_file": LOGICAL_SELECTION,
        "selection_file_sha256": sha256(selection_path),
    }
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(protocol, indent=2))
    print(f"selection_sha256={sha256(selection_path)}")
    print(f"protocol_sha256={sha256(protocol_path)}")


if __name__ == "__main__":
    main()
