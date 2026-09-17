#!/usr/bin/env python3
"""Extend the frozen visual-consensus submission with newly recovered test coverage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> pd.DataFrame:
    frame = pd.DataFrame(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if frame["qa_id"].duplicated().any() or (frame["prediction"] == "").any() or (frame["error"] != "").any():
        raise ValueError(f"Invalid VLM prediction log: {path}")
    return frame[["qa_id", "prediction"]].rename(columns={"prediction": "vlm_prediction"})


def require_positive_gate(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    gate = report["fixed_confidence_sweep_for_consensus_overlay"]["0.00"]
    if gate["net_correct_vs_parent"] <= 0 or gate["override_correct"] <= gate["override_parent_correct"]:
        raise ValueError(f"Validation gate is not positive: {path}")
    return report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parent_path = root / "candidates/public_fususu_077777.csv"
    base_path = root / "candidates/visual_sensor_consensus_v1.csv"
    sensor_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    single_vlm_path = root / "artifacts/vlm/qwen3_vl_4b_test_harn_single_v1.jsonl"
    object_vlm_path = root / "artifacts/vlm/qwen3_vl_4b_test_harn_object_v1.jsonl"
    single_validation_path = root / "reports/visual_sensor_fusion_subset_summary.json"
    object_validation_path = root / "reports/visual_sensor_object_fusion_subset_summary.json"
    output_path = root / "candidates/visual_sensor_consensus_v2.csv"
    report_path = root / "reports/visual_sensor_consensus_v2_candidate.json"

    validations = {
        "single": require_positive_gate(single_validation_path),
        "object_interaction": require_positive_gate(object_validation_path),
    }
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)
    base = pd.read_csv(base_path, dtype=str, keep_default_na=False)
    if list(parent.columns) != ["qa_id", "prediction"] or list(base.columns) != ["qa_id", "prediction"]:
        raise ValueError("Unexpected candidate schema")
    if parent["qa_id"].tolist() != base["qa_id"].tolist() or len(parent) != 682:
        raise ValueError("Parent/base IDs do not exactly match the official submission schema")
    if sha256(base_path) != "e54652a8746fca7d434a6a4bd162458448e709ff224b074ca37a0f538dec5463":
        raise ValueError("Base is not the exact submitted v1 artifact")

    sensor = pd.read_csv(sensor_path, dtype=str, keep_default_na=False)
    sensor = sensor[(sensor["source"] == "HARn") & sensor["category"].isin(validations)].copy()
    sensor = sensor.rename(columns={"prediction": "sensor_prediction"})
    sensor["sensor_present_bool"] = sensor["sensor_present"].str.lower().eq("true")
    vlm_parts = []
    for category, path in (("single", single_vlm_path), ("object_interaction", object_vlm_path)):
        frame = load_jsonl(path)
        frame["category"] = category
        vlm_parts.append(frame)
    vlm = pd.concat(vlm_parts, ignore_index=True)
    merged = (
        vlm.merge(
            sensor[["qa_id", "category", "sensor_prediction", "confidence", "sensor_present_bool"]],
            on=["qa_id", "category"],
            how="left",
            validate="one_to_one",
        )
        .merge(
            parent.rename(columns={"prediction": "parent_prediction"}),
            on="qa_id",
            how="left",
            validate="one_to_one",
        )
    )
    if merged[["sensor_prediction", "parent_prediction"]].isna().any().any():
        raise ValueError("Missing sensor or parent prediction")
    use = (
        merged["sensor_present_bool"]
        & (merged["sensor_prediction"] == merged["vlm_prediction"])
        & (merged["sensor_prediction"] != merged["parent_prediction"])
    )
    overrides = merged[use].copy()
    if overrides.empty:
        raise ValueError("Qualified consensus produced no test overrides")

    candidate = base.copy()
    candidate_index = candidate.set_index("qa_id")["prediction"].to_dict()
    conflicts = []
    for _, row in overrides.iterrows():
        current = candidate_index[row["qa_id"]]
        if current not in {row["parent_prediction"], row["sensor_prediction"]}:
            conflicts.append(row["qa_id"])
        candidate.loc[candidate["qa_id"] == row["qa_id"], "prediction"] = row["sensor_prediction"]
    if conflicts:
        raise ValueError(f"Consensus conflicts with an independent base override: {conflicts}")
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
    if not added.empty:
        raise ValueError(f"Unexpected delta versus submitted v1: {added['qa_id'].tolist()}")
    newly_covered_ids = {"test_0513", "test_0529"}
    newly_covered = merged[merged["qa_id"].isin(newly_covered_ids)].copy()
    if set(newly_covered["qa_id"]) != newly_covered_ids:
        raise ValueError("The expected newly recovered test rows are not both present")
    newly_covered["sensor_vlm_consensus"] = (
        newly_covered["sensor_present_bool"]
        & (newly_covered["sensor_prediction"] == newly_covered["vlm_prediction"])
    )
    newly_covered["qualified_override"] = newly_covered["qa_id"].isin(overrides["qa_id"])
    if newly_covered["qualified_override"].any():
        raise ValueError("A newly covered row unexpectedly qualified as an override")
    report = {
        "candidate": output_path.name,
        "candidate_sha256": sha256(output_path),
        "base_submission_ref": 56116980,
        "base_sha256": sha256(base_path),
        "gate": "pre-qualified sensor-present sensor=VLM consensus differs frozen parent; no test labels",
        "qualified_consensus_rows": int(len(overrides)),
        "total_rows_changed_vs_parent": int(len(changed)),
        "new_rows_changed_vs_submitted_v1": int(len(added)),
        "new_overrides": added.to_dict(orient="records"),
        "newly_covered_rows": newly_covered[
            [
                "qa_id",
                "category",
                "parent_prediction",
                "sensor_prediction",
                "vlm_prediction",
                "confidence",
                "sensor_present_bool",
                "sensor_vlm_consensus",
                "qualified_override",
            ]
        ].to_dict(orient="records"),
        "decision": "NO_CHANGE: test_0513 has no sensor input and test_0529 lacks sensor/VLM agreement; output bytes equal submitted v1",
        "all_consensus_overrides": overrides[
            ["qa_id", "category", "parent_prediction", "sensor_prediction", "vlm_prediction", "confidence"]
        ].to_dict(orient="records"),
        "inputs": {
            "parent_sha256": sha256(parent_path),
            "submitted_v1_sha256": sha256(base_path),
            "sensor_test_sha256": sha256(sensor_path),
            "single_vlm_sha256": sha256(single_vlm_path),
            "object_vlm_sha256": sha256(object_vlm_path),
            "single_validation_sha256": sha256(single_validation_path),
            "object_validation_sha256": sha256(object_validation_path),
            "code_sha256": sha256(Path(__file__)),
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
