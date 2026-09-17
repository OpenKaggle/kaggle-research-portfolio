#!/usr/bin/env python3
"""Build a conservative sensor override candidate from fixed, auditable gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


PARENT_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"
THRESHOLD = 0.30


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parent_path = root / "candidates/public_fususu_077777.csv"
    expert_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    oof_summary_path = root / "reports/nonvisual_sensor_oof_summary.json"
    output_path = root / "candidates/nonvisual_rf_v1_harn_single_highconf.csv"
    audit_path = root / "reports/nonvisual_rf_v1_harn_single_highconf_candidate.json"

    if sha256(parent_path) != PARENT_SHA256:
        raise ValueError("Frozen 0.77777 parent hash changed")
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)
    expert = pd.read_csv(expert_path, keep_default_na=False)
    selected = expert[
        (expert["source"] == "HARn")
        & (expert["category"] == "single")
        & expert["sensor_present"].astype(bool)
        & (expert["confidence"] >= THRESHOLD)
        & (expert["prediction"] != expert["parent_prediction"])
    ].copy()
    if len(selected) == 0:
        raise ValueError("Fixed high-confidence gate produced no overrides")
    if not (selected["parent_prediction"] != selected["prediction"]).all():
        raise ValueError("Selected rows do not change the parent")

    candidate = parent.copy()
    replacement = dict(zip(selected["qa_id"], selected["prediction"]))
    candidate["prediction"] = candidate.apply(
        lambda row: replacement.get(row["qa_id"], row["prediction"]), axis=1
    )
    changed = candidate.merge(parent, on="qa_id", suffixes=("_new", "_parent"))
    changed = changed[changed["prediction_new"] != changed["prediction_parent"]]
    if set(changed["qa_id"]) != set(selected["qa_id"]):
        raise ValueError("Candidate changes differ from gated expert rows")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(output_path, index=False)
    summary = json.loads(oof_summary_path.read_text(encoding="utf-8"))
    oof_gate = summary["metrics"]["HARn/single"]["fixed_threshold_overlays"][f"{THRESHOLD:.2f}"]
    audit = {
        "candidate": output_path.name,
        "parent_sha256": sha256(parent_path),
        "expert_predictions_sha256": sha256(expert_path),
        "oof_summary_sha256": sha256(oof_summary_path),
        "gate": {
            "source": "HARn",
            "category": "single",
            "sensor_present": True,
            "confidence_at_least": THRESHOLD,
            "must_disagree_with_parent": True,
        },
        "subject_disjoint_oof_gate_result": oof_gate,
        "changed_rows": [
            {
                "qa_id": row.qa_id,
                "parent_prediction": row.parent_prediction,
                "sensor_prediction": row.prediction,
                "confidence": float(row.confidence),
                "sensor_unit": row.sensor_unit,
            }
            for row in selected.itertuples(index=False)
        ],
        "changed_row_count": int(len(selected)),
        "candidate_sha256": sha256(output_path),
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
