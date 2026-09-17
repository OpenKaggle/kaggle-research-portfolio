#!/usr/bin/env python3
"""Build a gated HARn single-action multimodal consensus candidate.

The gate requires real sensor data, agreement between the frozen RF specialist
and the selected subject-disjoint ExtraTrees early-fusion specialist, and a
disagreement with the frozen public parent. When a valid zero-shot VLM result is
available, it may veto but never create a sensor-only override.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


BASE_SHA256 = "e54652a8746fca7d434a6a4bd162458448e709ff224b074ca37a0f538dec5463"
LABELS = "ABCD"
SINGLE_CATEGORIES = {"single", "combination", "emotion", "object_interaction"}


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def valid_prediction(value: str, category: str) -> bool:
    if not value or any(char not in LABELS for char in value) or len(set(value)) != len(value):
        return False
    if category in SINGLE_CATEGORIES:
        return len(value) == 1
    if category == "multi":
        return value == "".join(sorted(value))
    if category == "sequence":
        return len(value) == 4 and set(value) == set(LABELS)
    return False


def load_vlm(path: Path) -> pd.DataFrame:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    frame = pd.DataFrame(rows)
    if frame["qa_id"].duplicated().any() or frame["prediction"].eq("").any() or frame["error"].ne("").any():
        raise ValueError(f"Invalid VLM evidence: {path}")
    return frame[["qa_id", "prediction"]].rename(columns={"prediction": "vlm_prediction"})


def gate_metrics(frame: pd.DataFrame, use: pd.Series) -> dict[str, object]:
    chosen = frame[use].copy()
    chosen["expert_correct"] = chosen["prediction"] == chosen["answer"]
    chosen["parent_correct"] = chosen["parent_prediction"] == chosen["answer"]
    chosen["delta"] = chosen["expert_correct"].astype(int) - chosen["parent_correct"].astype(int)
    by_user = chosen.groupby("user")["delta"].sum()
    return {
        "rows": int(len(chosen)),
        "expert_correct": int(chosen["expert_correct"].sum()),
        "expert_accuracy": float(chosen["expert_correct"].mean()),
        "parent_correct": int(chosen["parent_correct"].sum()),
        "parent_accuracy": float(chosen["parent_correct"].mean()),
        "net_correct_vs_parent": int(chosen["delta"].sum()),
        "subjects": int(chosen["user"].nunique()),
        "worst_subject_net": int(by_user.min()),
        "by_user_net": {str(int(user)): int(value) for user, value in by_user.items()},
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    features_path = root / "cache/nonvisual_features.npz"
    parent_path = root / "candidates/public_fususu_077777.csv"
    base_path = root / "candidates/visual_sensor_consensus_v1.csv"
    et_oof_path = root / "artifacts/oof/harn_multimodal_extratrees_oof.csv"
    et_test_path = root / "artifacts/predictions/harn_multimodal_extratrees_test.csv"
    rf_oof_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    rf_test_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    vlm_oof_path = root / "artifacts/vlm/qwen3_vl_4b_zero_shot_full122_v1.jsonl"
    vlm_test_path = root / "artifacts/vlm/qwen3_vl_4b_test_harn_single_v1.jsonl"
    model_report_path = root / "reports/harn_multimodal_extratrees_summary.json"
    output_path = root / "candidates/harn_multimodal_consensus_v1.csv"
    report_path = root / "reports/harn_multimodal_consensus_v1_candidate.json"

    if sha256(base_path) != BASE_SHA256:
        raise ValueError("Base is not the exact submitted visual-consensus v1 artifact")
    model_report = json.loads(model_report_path.read_text(encoding="utf-8"))
    if model_report["selected_variant"] != "early_fusion":
        raise ValueError("Unexpected selected ExtraTrees variant")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    base = pd.read_csv(base_path, dtype=str, keep_default_na=False)
    if list(base.columns) != ["qa_id", "prediction"] or base["qa_id"].tolist() != test["qa_id"].tolist():
        raise ValueError("Base does not match official test schema/order")

    et_oof = pd.read_csv(et_oof_path, dtype=str, keep_default_na=False)
    et_oof = et_oof[et_oof["category"] == "single"].copy()
    et_oof["sensor_present"] = et_oof["sensor_present"].str.lower().eq("true")
    rf_oof = pd.read_csv(rf_oof_path, dtype=str, keep_default_na=False)
    rf_oof = rf_oof[(rf_oof["source"] == "HARn") & (rf_oof["category"] == "single")]
    rf_oof = rf_oof[["qa_id", "prediction"]].rename(columns={"prediction": "rf_prediction"})
    vlm_oof = load_vlm(vlm_oof_path)

    with np.load(features_path) as features:
        units = features["units"].astype(str)
        skeleton = features["skeleton"]
        index = {unit: position for position, unit in enumerate(units)}
        rf_present = {}
        for _, row in train[(train["source"] == "HARn") & (train["category"] == "single")].iterrows():
            unit = "Training/" + row["path"]
            rf_present[row["qa_id"]] = bool(unit in index and np.isfinite(skeleton[index[unit]]).any())

    validation = et_oof.merge(rf_oof, on="qa_id", validate="one_to_one").merge(
        vlm_oof, on="qa_id", how="left", validate="one_to_one"
    )
    validation["rf_present"] = validation["qa_id"].map(rf_present).fillna(False).astype(bool)
    base_gate = (
        validation["sensor_present"]
        & validation["rf_present"]
        & (validation["prediction"] == validation["rf_prediction"])
        & (validation["prediction"] != validation["parent_prediction"])
    )
    vlm_veto = base_gate & validation["vlm_prediction"].notna() & (
        validation["prediction"] != validation["vlm_prediction"]
    )
    accepted = base_gate & ~vlm_veto
    base_metrics = gate_metrics(validation, base_gate)
    accepted_metrics = gate_metrics(validation, accepted)
    vetoed_metrics = gate_metrics(validation, vlm_veto)
    if not (
        accepted_metrics["rows"] >= 100
        and accepted_metrics["expert_accuracy"] >= 0.88
        and accepted_metrics["net_correct_vs_parent"] > 0
        and accepted_metrics["subjects"] == 18
        and accepted_metrics["worst_subject_net"] > 0
    ):
        raise ValueError(f"Validation gate failed: {accepted_metrics}")

    et_test = pd.read_csv(et_test_path, dtype=str, keep_default_na=False)
    et_test = et_test[et_test["category"] == "single"].copy()
    et_test = et_test.drop(columns=["parent_prediction"])
    et_test["sensor_present"] = et_test["sensor_present"].str.lower().eq("true")
    rf_test = pd.read_csv(rf_test_path, dtype=str, keep_default_na=False)
    rf_test = rf_test[(rf_test["source"] == "HARn") & (rf_test["category"] == "single")].copy()
    rf_test["rf_present"] = rf_test["sensor_present"].str.lower().eq("true")
    rf_test = rf_test[["qa_id", "prediction", "confidence", "rf_present"]].rename(
        columns={"prediction": "rf_prediction", "confidence": "rf_confidence"}
    )
    vlm_test = load_vlm(vlm_test_path)
    test_gate = (
        et_test.merge(rf_test, on="qa_id", validate="one_to_one")
        .merge(vlm_test, on="qa_id", how="left", validate="one_to_one")
        .merge(parent, on="qa_id", validate="one_to_one")
    )
    base_use = (
        test_gate["sensor_present"]
        & test_gate["rf_present"]
        & (test_gate["prediction"] == test_gate["rf_prediction"])
        & (test_gate["prediction"] != test_gate["parent_prediction"])
    )
    test_gate["vlm_veto"] = base_use & test_gate["vlm_prediction"].notna() & (
        test_gate["prediction"] != test_gate["vlm_prediction"]
    )
    test_gate["accepted"] = base_use & ~test_gate["vlm_veto"]
    overrides = test_gate[test_gate["accepted"]].copy()

    candidate = base.copy()
    base_map = base.set_index("qa_id")["prediction"].to_dict()
    conflicts = overrides[
        ~overrides.apply(
            lambda row: base_map[row["qa_id"]] in {row["parent_prediction"], row["prediction"]}, axis=1
        )
    ]
    if len(conflicts):
        raise ValueError(f"Consensus conflicts with base overrides: {conflicts['qa_id'].tolist()}")
    for _, row in overrides.iterrows():
        candidate.loc[candidate["qa_id"] == row["qa_id"], "prediction"] = row["prediction"]
    if not all(
        valid_prediction(prediction, category)
        for prediction, category in zip(candidate["prediction"], test["category"])
    ):
        raise ValueError("Candidate grammar invalid")
    if candidate["qa_id"].duplicated().any() or len(candidate) != 682:
        raise ValueError("Candidate row/ID invariant failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(output_path, index=False)

    comparison = base.rename(columns={"prediction": "base_prediction"}).merge(
        candidate.rename(columns={"prediction": "candidate_prediction"}), on="qa_id", validate="one_to_one"
    ).merge(parent, on="qa_id", validate="one_to_one")
    new_rows = comparison[comparison["candidate_prediction"] != comparison["base_prediction"]]
    all_changes = comparison[comparison["candidate_prediction"] != comparison["parent_prediction"]]
    if len(new_rows) == 0:
        raise ValueError("Qualified gate produced no new rows")

    evidence_columns = [
        "qa_id", "parent_prediction", "prediction", "confidence", "rf_prediction",
        "rf_confidence", "vlm_prediction", "vlm_veto", "accepted",
    ]
    report = {
        "candidate": output_path.name,
        "candidate_sha256": sha256(output_path),
        "base_submission_ref": 56116980,
        "base_sha256": sha256(base_path),
        "gate": "HARn single only; real early-fusion and skeleton inputs; ExtraTrees=RF; differs frozen parent; valid VLM disagreement vetoes",
        "validation": {
            "base_sensor_consensus": base_metrics,
            "vlm_vetoed": vetoed_metrics,
            "accepted": accepted_metrics,
        },
        "test": {
            "base_gate_rows": int(base_use.sum()),
            "vlm_veto_rows": int(test_gate["vlm_veto"].sum()),
            "accepted_rows": int(test_gate["accepted"].sum()),
            "accepted_evidence": test_gate.loc[test_gate["accepted"], evidence_columns].fillna("").to_dict(orient="records"),
            "vetoed_evidence": test_gate.loc[test_gate["vlm_veto"], evidence_columns].fillna("").to_dict(orient="records"),
        },
        "total_rows_changed_vs_parent": int(len(all_changes)),
        "new_rows_changed_vs_submitted_v1": int(len(new_rows)),
        "new_rows": new_rows.to_dict(orient="records"),
        "inputs": {
            "training_qa_sha256": sha256(train_path),
            "test_qa_sha256": sha256(test_path),
            "feature_cache_sha256": sha256(features_path),
            "parent_sha256": sha256(parent_path),
            "base_sha256": sha256(base_path),
            "extratrees_oof_sha256": sha256(et_oof_path),
            "extratrees_test_sha256": sha256(et_test_path),
            "rf_oof_sha256": sha256(rf_oof_path),
            "rf_test_sha256": sha256(rf_test_path),
            "vlm_oof_sha256": sha256(vlm_oof_path),
            "vlm_test_sha256": sha256(vlm_test_path),
            "model_report_sha256": sha256(model_report_path),
            "code_sha256": sha256(Path(__file__)),
        },
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
