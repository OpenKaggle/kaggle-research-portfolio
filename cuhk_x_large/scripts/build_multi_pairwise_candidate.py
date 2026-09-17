#!/usr/bin/env python3
"""Overlay the pre-qualified HAU multi-answer model on the current best candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


GATE = 0.05


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parent_path = root / "candidates/public_fususu_077777.csv"
    base_path = root / "candidates/visual_sensor_consensus_v1.csv"
    prediction_path = root / "artifacts/predictions/multi_pairwise_xgb_test.csv"
    validation_path = root / "reports/multi_pairwise_xgb_summary.json"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    output_path = root / "candidates/multi_pairwise_conf005_union_v1.csv"
    report_path = root / "reports/multi_pairwise_conf005_union_v1_candidate.json"

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    gate_key = f"{GATE:.2f}"
    gate = validation["fixed_confidence_overlays"][gate_key]
    if gate["net_correct_vs_parent"] <= 0:
        raise ValueError("Selected validation gate is not positive versus the frozen parent")
    if gate["accuracy"] <= validation["parent_accuracy"]:
        raise ValueError("Selected validation gate does not improve overall exact-match accuracy")
    parent_worst = min(
        pd.read_csv(root / "artifacts/oof/multi_pairwise_xgb_oof.csv")
        .assign(parent_correct=lambda frame: frame["parent_correct"].astype(bool))
        .groupby("user")["parent_correct"]
        .mean()
    )
    if gate["worst_subject_accuracy"] < parent_worst:
        raise ValueError("Selected validation gate degrades the worst held-out subject")

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)
    base = pd.read_csv(base_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    predictions = pd.read_csv(prediction_path, dtype=str, keep_default_na=False)
    if list(parent.columns) != ["qa_id", "prediction"] or list(base.columns) != ["qa_id", "prediction"]:
        raise ValueError("Unexpected candidate schema")
    if parent["qa_id"].tolist() != base["qa_id"].tolist() or parent["qa_id"].tolist() != test["qa_id"].tolist():
        raise ValueError("Candidate IDs/order do not exactly match test_qa.csv")
    multi_ids = set(test.loc[test["category"] == "multi", "qa_id"])
    if set(predictions["qa_id"]) != multi_ids or predictions["qa_id"].duplicated().any():
        raise ValueError("Test predictions do not cover the multi category exactly once")
    predictions["confidence_float"] = pd.to_numeric(predictions["confidence"], errors="raise")
    predictions["sensor_present_bool"] = predictions["sensor_present"].str.lower().eq("true")
    use = (
        predictions["sensor_present_bool"]
        & (predictions["confidence_float"] >= GATE)
        & (predictions["prediction"] != predictions["parent_prediction"])
    )
    overrides = predictions.loc[use].copy()
    if overrides.empty:
        raise ValueError("Qualified multi-answer gate produced no test overrides")

    candidate = base.copy()
    candidate_index = candidate.set_index("qa_id")["prediction"].to_dict()
    conflicts = []
    for _, row in overrides.iterrows():
        current = candidate_index[row["qa_id"]]
        if current != row["parent_prediction"]:
            conflicts.append(row["qa_id"])
        candidate.loc[candidate["qa_id"] == row["qa_id"], "prediction"] = row["prediction"]
    if conflicts:
        raise ValueError(f"Multi-answer overlay conflicts with an independent base override: {conflicts}")
    if not candidate["prediction"].str.fullmatch(r"[ABCD]{1,4}").all():
        raise ValueError("Invalid candidate labels")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(output_path, index=False)

    comparison = (
        parent.rename(columns={"prediction": "parent_prediction"})
        .merge(base.rename(columns={"prediction": "base_prediction"}), on="qa_id", validate="one_to_one")
        .merge(candidate.rename(columns={"prediction": "new_prediction"}), on="qa_id", validate="one_to_one")
    )
    changed = comparison[comparison["new_prediction"] != comparison["parent_prediction"]]
    added = comparison[comparison["new_prediction"] != comparison["base_prediction"]]
    report = {
        "candidate": output_path.name,
        "candidate_sha256": sha256(output_path),
        "gate": {
            "category": "HAU multi",
            "confidence_threshold": GATE,
            "selection_rule": "fixed grid; maximize OOF overlay exact-match accuracy, then worst-subject accuracy, then fewer overrides",
            "validation_rows": validation["rows"],
            "validation_parent_accuracy": validation["parent_accuracy"],
            "validation_overlay_accuracy": gate["accuracy"],
            "validation_net_correct_vs_parent": gate["net_correct_vs_parent"],
            "validation_parent_worst_subject_accuracy": float(parent_worst),
            "validation_overlay_worst_subject_accuracy": gate["worst_subject_accuracy"],
        },
        "multi_test_rows": int(len(predictions)),
        "multi_test_overrides": int(len(overrides)),
        "total_rows_changed_vs_frozen_parent": int(len(changed)),
        "new_rows_changed_vs_visual_base": int(len(added)),
        "overrides": overrides[
            ["qa_id", "parent_prediction", "prediction", "confidence"]
        ].to_dict(orient="records"),
        "inputs": {
            "parent_sha256": sha256(parent_path),
            "visual_base_sha256": sha256(base_path),
            "test_predictions_sha256": sha256(prediction_path),
            "validation_sha256": sha256(validation_path),
            "test_qa_sha256": sha256(test_path),
            "code_sha256": sha256(Path(__file__)),
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
