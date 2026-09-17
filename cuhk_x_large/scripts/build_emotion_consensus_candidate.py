#!/usr/bin/env python3
"""Build a sparse RF/XGBoost emotion-consensus candidate with fixed gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


PARENT_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"
RF_SHA256 = "ff48f19986e95390430120630a73c253486b5f50fe88fe07145ac43a09da914d"
XGB_SHA256 = "1f4b2028857d8fccdc5f5eca0d0170e5424c7c0a4f2053223cbf2fd839bf5a4d"
GRAPH_SHA256 = "165f204ba3a4358db93c116c288260dd09484e8ea6212021f246425157807677"
XGB_THRESHOLD = 0.05


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = {
        "parent": root / "candidates/public_fususu_077777.csv",
        "rf": root / "artifacts/predictions/nonvisual_sensor_test.csv",
        "xgb": root / "artifacts/predictions/emotion_pairwise_xgb_test.csv",
        "graph": root / "artifacts/predictions/public_graph_test.csv",
    }
    expected = {"parent": PARENT_SHA256, "rf": RF_SHA256, "xgb": XGB_SHA256, "graph": GRAPH_SHA256}
    for name, path in paths.items():
        if sha256(path) != expected[name]:
            raise ValueError(f"{name} input hash changed")

    parent = pd.read_csv(paths["parent"], dtype=str, keep_default_na=False)
    rf = pd.read_csv(paths["rf"], keep_default_na=False)
    rf = rf[(rf["source"] == "HAU") & (rf["category"] == "emotion")][
        ["qa_id", "prediction", "confidence", "sensor_present", "parent_prediction"]
    ].rename(columns={"prediction": "rf_prediction", "confidence": "rf_confidence"})
    xgb = pd.read_csv(paths["xgb"], keep_default_na=False)[["qa_id", "prediction", "confidence"]].rename(
        columns={"prediction": "xgb_prediction", "confidence": "xgb_confidence"}
    )
    graph = pd.read_csv(paths["graph"], dtype=str, keep_default_na=False).rename(
        columns={"prediction": "graph_prediction"}
    )
    evidence = rf.merge(xgb, on="qa_id", validate="one_to_one").merge(graph, on="qa_id", validate="one_to_one")
    selected = evidence[
        evidence["sensor_present"].astype(bool)
        & (evidence["rf_prediction"] == evidence["xgb_prediction"])
        & (evidence["rf_prediction"] != evidence["parent_prediction"])
        & (evidence["rf_prediction"] != evidence["graph_prediction"])
        & (evidence["xgb_confidence"] >= XGB_THRESHOLD)
    ].copy()
    if len(selected) == 0:
        raise ValueError("Consensus gate produced no changes")

    replacement = dict(zip(selected["qa_id"], selected["rf_prediction"]))
    candidate = parent.copy()
    candidate["prediction"] = candidate.apply(
        lambda row: replacement.get(row["qa_id"], row["prediction"]), axis=1
    )
    changed = candidate.merge(parent, on="qa_id", suffixes=("_new", "_parent"))
    changed = changed[changed["prediction_new"] != changed["prediction_parent"]]
    if set(changed["qa_id"]) != set(selected["qa_id"]):
        raise ValueError("Candidate diff differs from selected evidence")

    output = root / "candidates/emotion_rf_xgb_consensus_v1.csv"
    report = root / "reports/emotion_rf_xgb_consensus_v1_candidate.json"
    candidate.to_csv(output, index=False)
    audit = {
        "candidate": output.name,
        "candidate_sha256": sha256(output),
        "input_sha256": {name: sha256(path) for name, path in paths.items()},
        "gate": {
            "source_category": "HAU/emotion",
            "sensor_present": True,
            "rf_equals_xgb": True,
            "prediction_differs_from_frozen_parent": True,
            "prediction_differs_from_public_compact_graph": True,
            "xgb_confidence_at_least": XGB_THRESHOLD,
        },
        "corresponding_subject_disjoint_oof_gate": {
            "rf_threshold": 0.0,
            "xgb_threshold": XGB_THRESHOLD,
            "overrides": 114,
            "accuracy": 0.39555006180469715,
            "net_correct_vs_public_graph_parent": 61,
            "worst_subject_accuracy": 0.3333333333333333,
        },
        "changed_row_count": int(len(selected)),
        "changed_rows": selected[
            ["qa_id", "parent_prediction", "graph_prediction", "rf_prediction", "rf_confidence", "xgb_confidence"]
        ].sort_values("qa_id").to_dict(orient="records"),
    }
    report.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
