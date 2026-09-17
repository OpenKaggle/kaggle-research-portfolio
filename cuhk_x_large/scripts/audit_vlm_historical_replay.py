#!/usr/bin/env python3
"""Classify Small20 as a deterministic replay and freeze further VLM promotion work."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def exact_positive_sign_p(positive: int, negative: int) -> float | None:
    discordant = positive + negative
    if discordant == 0:
        return None
    return sum(math.comb(discordant, k) for k in range(positive, discordant + 1)) / (2**discordant)


def comparison(frame: pd.DataFrame) -> dict[str, object]:
    vlm_correct = int(frame["vlm_correct"].sum())
    parent_correct = int(frame["parent_correct"].sum())
    by_subject = (
        frame.groupby("subject")[["vlm_correct", "parent_correct"]]
        .sum()
        .astype(int)
    )
    by_subject["net_correct"] = by_subject["vlm_correct"] - by_subject["parent_correct"]
    positive = int((by_subject["net_correct"] > 0).sum())
    negative = int((by_subject["net_correct"] < 0).sum())
    ties = int((by_subject["net_correct"] == 0).sum())
    return {
        "rows": int(len(frame)),
        "vlm_correct": vlm_correct,
        "parent_correct": parent_correct,
        "net_correct": vlm_correct - parent_correct,
        "vlm_accuracy": vlm_correct / len(frame) if len(frame) else None,
        "parent_accuracy": parent_correct / len(frame) if len(frame) else None,
        "subject_units": int(len(by_subject)),
        "positive_subjects": positive,
        "negative_subjects": negative,
        "tied_subjects": ties,
        "one_sided_exact_positive_sign_p": exact_positive_sign_p(positive, negative),
        "by_subject": {
            subject: {
                "rows": int((frame["subject"] == subject).sum()),
                "vlm_correct": int(values["vlm_correct"]),
                "parent_correct": int(values["parent_correct"]),
                "net_correct": int(values["net_correct"]),
            }
            for subject, values in by_subject.iterrows()
        },
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    replay_path = root / "artifacts/vlm/qwen3_vl_4b_small20_frozen_v1.jsonl"
    prior_paths = [
        root / "artifacts/vlm/qwen3_vl_4b_zero_shot_full122_v1.jsonl",
        root / "artifacts/vlm/qwen3_vl_4b_zero_shot_object66_v1.jsonl",
    ]
    protocol_path = root / "reports/vlm_small20_frozen_protocol.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    visual_manifest_path = root / "cache/partial_visual_manifest.json"
    parent_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    sensor_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    output_path = root / "reports/vlm_historical_replay_and_freeze_audit.json"

    replay = pd.read_json(replay_path, lines=True, dtype=False)
    prior = pd.concat(
        [pd.read_json(path, lines=True, dtype=False) for path in prior_paths],
        ignore_index=True,
    )
    if replay["qa_id"].duplicated().any() or len(replay) != 20:
        raise ValueError("Small20 replay must contain 20 unique rows")
    paired = replay.merge(prior, on="qa_id", suffixes=("_replay", "_prior"), validate="one_to_one")
    if len(paired) != 20:
        raise ValueError("Every Small20 row must exist in the historical VLM artifacts")
    consistency_fields = ["prediction", "raw_output", "prompt_sha256", "video_sha256"]
    consistency = {
        field: int((paired[f"{field}_replay"] == paired[f"{field}_prior"]).sum())
        for field in consistency_fields
    }

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction"]
    ].rename(columns={"prediction": "parent_prediction"})
    sensor = pd.read_csv(sensor_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction", "confidence"]
    ].rename(columns={"prediction": "sensor_prediction"})
    historical = prior.merge(parent, on="qa_id", validate="one_to_one").merge(
        sensor,
        on="qa_id",
        validate="one_to_one",
    )
    historical["vlm_correct"] = historical["prediction"].eq(historical["answer"])
    historical["parent_correct"] = historical["parent_prediction"].eq(historical["answer"])
    historical["sensor_agreement_parent_disagreement"] = (
        historical["prediction"].eq(historical["sensor_prediction"])
        & historical["prediction"].ne(historical["parent_prediction"])
    )
    direct_by_task = {
        task: comparison(group)
        for task, group in historical.groupby("category")
    }
    agreement_by_task = {
        task: comparison(group[group["sensor_agreement_parent_disagreement"]])
        for task, group in historical.groupby("category")
    }

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    available_units = {item["unit"] for item in json.loads(visual_manifest_path.read_text())}
    eligible = qa[
        (qa["source"] == "HARn")
        & qa["category"].isin(["single", "object_interaction"])
        & qa["path"].isin(available_units)
    ].copy()
    prior_pairs = set(zip(prior["qa_id"], prior["path"]))
    unseen = eligible[
        ~eligible.apply(lambda row: (row["qa_id"], row["path"]) in prior_pairs, axis=1)
    ]

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    report = {
        "audit": "VLM historical replay, post-hoc task/subject taxonomy, and hard freeze",
        "small20_classification": "PASS_ONLY_AS_REPRODUCIBILITY_PIPELINE_SMOKE",
        "small20_performance_evidence_decision": "REJECT_AS_NEW_PERFORMANCE_OR_PROMOTION_EVIDENCE",
        "reason": (
            "All 20 QA/clip pairs were inferred before the Small20 protocol in the historical "
            "full122/object66 runs with identical prompts and video inputs."
        ),
        "small20": {
            "protocol_sha256": sha256(protocol_path),
            "selection_sha256": protocol["selection_file_sha256"],
            "rows": len(replay),
            "unique_qa_ids": int(replay["qa_id"].nunique()),
            "prior_overlap_rows": len(paired),
            "prior_overlap_fraction": len(paired) / len(replay),
            "field_consistency_counts_out_of_20": consistency,
            "exact_prediction_replay_rate": consistency["prediction"] / 20,
            "invalid_or_empty_outputs": int(replay["prediction"].eq("").sum()),
            "implementation_failures": int(replay["failure_type"].isin(["read_error", "inference_error"]).sum()),
            "retry_rows": 0,
            "scientific_accuracy_reuse_prohibited": True,
        },
        "fresh_validation_availability": {
            "eligible_recovered_rows": int(len(eligible)),
            "previously_inferred_qa_clip_pairs": int(len(prior_pairs)),
            "eligible_never_inferred_qa_clip_pairs": int(len(unseen)),
            "required_for_new_screen": 20,
            "new_screen_possible": len(unseen) >= 20,
        },
        "historical_post_hoc_taxonomy_only": {
            "warning": (
                "These rows were already inspected. Results may generate future hypotheses only; "
                "they cannot define, select, promote, or submit a router."
            ),
            "direct_vlm_vs_subject_disjoint_parent_by_task_and_subject": direct_by_task,
            "existing_sensor_agreement_parent_disagreement_by_task_and_subject": agreement_by_task,
        },
        "future_fresh_screen_gate": {
            "unit_of_independence": "subject",
            "primary": "one-sided exact sign test over non-tied subject deltas, p <= 0.05",
            "secondary": (
                "both categories and both pre-frozen five-subject halves net positive; "
                "any negative subject or more than 1/20 implementation failures stops promotion"
            ),
            "even_if_passed": "triggers larger fresh subject-disjoint validation, never direct submission",
        },
        "decision": "FREEZE_VLM_DIRECT_AND_NEW_ROUTER_DIRECTION",
        "resume_condition": (
            "At least 20 labeled QA/clip pairs from newly recovered clips that have never appeared "
            "in any historical VLM artifact, followed by a pre-frozen subject-clustered protocol."
        ),
        "submission": "NONE",
        "inputs": {
            "replay_sha256": sha256(replay_path),
            "historical_single_sha256": sha256(prior_paths[0]),
            "historical_object_sha256": sha256(prior_paths[1]),
            "parent_oof_sha256": sha256(parent_path),
            "sensor_oof_sha256": sha256(sensor_path),
            "partial_visual_manifest_sha256": sha256(visual_manifest_path),
        },
        "code_sha256": sha256(Path(__file__)),
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(output_path)}")


if __name__ == "__main__":
    main()
