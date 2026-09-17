#!/usr/bin/env python3
"""Evaluate label-free sensor/VLM agreement gates on honest HARn OOF rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


THRESHOLDS = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(prediction: pd.Series, answer: pd.Series, subject: pd.Series) -> dict[str, float | int]:
    correct = prediction == answer
    by_subject = correct.groupby(subject).mean()
    return {
        "rows": int(len(correct)),
        "accuracy": float(correct.mean()),
        "correct": int(correct.sum()),
        "worst_subject_accuracy": float(by_subject.min()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=("single", "object_interaction"), default="single")
    parser.add_argument("--vlm-log", default="qwen3_vl_4b_zero_shot_full122_v1.jsonl")
    parser.add_argument("--output", default="visual_sensor_fusion_subset_summary.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    vlm_path = root / "artifacts/vlm" / args.vlm_log
    sensor_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    parent_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    output_path = root / "reports" / args.output

    vlm = pd.DataFrame(json.loads(line) for line in vlm_path.read_text(encoding="utf-8").splitlines() if line.strip())
    if vlm["qa_id"].duplicated().any() or (vlm["error"] != "").any() or (vlm["prediction"] == "").any():
        raise ValueError("VLM log must contain unique, valid predictions without errors")
    sensor = pd.read_csv(sensor_path, dtype=str, keep_default_na=False)
    sensor = sensor[(sensor["source"] == "HARn") & (sensor["category"] == args.category)].copy()
    sensor["confidence"] = sensor["confidence"].astype(float)
    sensor = sensor.rename(columns={"prediction": "sensor_prediction", "user": "sensor_user"})
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)[["qa_id", "prediction"]]
    parent = parent.rename(columns={"prediction": "parent_prediction"})
    frame = vlm.merge(
        sensor[["qa_id", "answer", "sensor_prediction", "confidence", "sensor_user"]],
        on="qa_id",
        how="left",
        validate="one_to_one",
        suffixes=("_vlm", "_sensor"),
    ).merge(parent, on="qa_id", how="left", validate="one_to_one")
    if frame[["sensor_prediction", "parent_prediction"]].eq("").any().any() or frame[["sensor_prediction", "parent_prediction"]].isna().any().any():
        raise ValueError("Missing OOF prediction after merge")
    if not (frame["answer_vlm"] == frame["answer_sensor"]).all():
        raise ValueError("Answer mismatch across artifacts")
    if not (frame["subject"].str.removeprefix("user") == frame["sensor_user"]).all():
        raise ValueError("Subject mismatch across artifacts")

    answer = frame["answer_vlm"]
    subject = frame["subject"]
    baselines = {
        "public_graph_oof": metrics(frame["parent_prediction"], answer, subject),
        "sensor_loso": metrics(frame["sensor_prediction"], answer, subject),
        "zero_shot_vlm": metrics(frame["prediction"], answer, subject),
    }
    consensus = frame["sensor_prediction"] == frame["prediction"]
    consensus_diff_parent = consensus & (frame["sensor_prediction"] != frame["parent_prediction"])
    consensus_correct = frame.loc[consensus, "sensor_prediction"] == answer[consensus]

    gates = {}
    parent_correct = int((frame["parent_prediction"] == answer).sum())
    for threshold in THRESHOLDS:
        use = consensus_diff_parent & (frame["confidence"] >= threshold)
        fused = frame["parent_prediction"].where(~use, frame["sensor_prediction"])
        result = metrics(fused, answer, subject)
        result.update(
            {
                "overrides": int(use.sum()),
                "override_correct": int((frame.loc[use, "sensor_prediction"] == answer[use]).sum()),
                "override_parent_correct": int((frame.loc[use, "parent_prediction"] == answer[use]).sum()),
                "net_correct_vs_parent": int(result["correct"] - parent_correct),
            }
        )
        gates[f"{threshold:.2f}"] = result

    report = {
        "experiment": f"visual_sensor_agreement_on_recovered_harn_{args.category}_subset_v1",
        "validation": "Sensor and public-graph predictions are 18-fold leave-one-subject-out; VLM is zero-shot; clips intact",
        "scope_caution": "Recovered archive-prefix subset only; use to qualify mechanisms, not to claim full-dataset performance",
        "rows": int(len(frame)),
        "subjects": int(subject.nunique()),
        "actions": int(frame["action"].nunique()),
        "baselines": baselines,
        "sensor_vlm_consensus": {
            "rows": int(consensus.sum()),
            "coverage": float(consensus.mean()),
            "accuracy_when_agree": float(consensus_correct.mean()),
            "correct": int(consensus_correct.sum()),
            "differs_from_parent_rows": int(consensus_diff_parent.sum()),
        },
        "fixed_confidence_sweep_for_consensus_overlay": gates,
        "error_overlap": {
            "both_sensor_and_vlm_wrong": int(((frame["sensor_prediction"] != answer) & (frame["prediction"] != answer)).sum()),
            "sensor_wrong_vlm_right": int(((frame["sensor_prediction"] != answer) & (frame["prediction"] == answer)).sum()),
            "sensor_right_vlm_wrong": int(((frame["sensor_prediction"] == answer) & (frame["prediction"] != answer)).sum()),
        },
        "inputs": {
            "vlm_predictions_sha256": sha256(vlm_path),
            "sensor_oof_sha256": sha256(sensor_path),
            "parent_oof_sha256": sha256(parent_path),
            "analysis_code_sha256": sha256(Path(__file__)),
        },
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(output_path)}")


if __name__ == "__main__":
    main()
