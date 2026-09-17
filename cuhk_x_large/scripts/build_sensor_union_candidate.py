#!/usr/bin/env python3
"""Union independently gated HARn and HAU emotion candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


PARENT_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"
HARn_SHA256 = "1154a175c51b989957206ba02d9091528ffe5a50eda9cc87da8221614d8cb300"
EMOTION_SHA256 = "a98e211c5aea9d00df68d60e2b4a9d8c86281d170f26d1c8b67c054a98031980"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed(parent: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    joined = candidate.merge(parent, on="qa_id", suffixes=("_new", "_parent"), validate="one_to_one")
    return joined[joined["prediction_new"] != joined["prediction_parent"]]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parent_path = root / "candidates/public_fususu_077777.csv"
    harn_path = root / "candidates/nonvisual_rf_v1_harn_single_highconf.csv"
    emotion_path = root / "candidates/emotion_rf_xgb_consensus_v1.csv"
    expected = {parent_path: PARENT_SHA256, harn_path: HARn_SHA256, emotion_path: EMOTION_SHA256}
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise ValueError(f"Input hash changed: {path.name}")
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False)
    harn = pd.read_csv(harn_path, dtype=str, keep_default_na=False)
    emotion = pd.read_csv(emotion_path, dtype=str, keep_default_na=False)
    harn_diff = changed(parent, harn)
    emotion_diff = changed(parent, emotion)
    if set(harn_diff["qa_id"]) & set(emotion_diff["qa_id"]):
        raise ValueError("Independent candidate diffs overlap")
    replacement = dict(zip(harn_diff["qa_id"], harn_diff["prediction_new"]))
    replacement.update(dict(zip(emotion_diff["qa_id"], emotion_diff["prediction_new"])))
    union = parent.copy()
    union["prediction"] = union.apply(lambda row: replacement.get(row["qa_id"], row["prediction"]), axis=1)
    union_diff = changed(parent, union)
    if set(union_diff["qa_id"]) != set(replacement):
        raise ValueError("Union diff mismatch")
    output = root / "candidates/nonvisual_sensor_union_v1.csv"
    report = root / "reports/nonvisual_sensor_union_v1_candidate.json"
    union.to_csv(output, index=False)
    audit = {
        "candidate": output.name,
        "candidate_sha256": sha256(output),
        "parent_sha256": sha256(parent_path),
        "component_sha256": {"harn": sha256(harn_path), "emotion": sha256(emotion_path)},
        "component_submission_evidence": {
            "harn": {"submission_ref": 56108202, "public_score": 0.77777, "changed_rows": int(len(harn_diff))},
            "emotion": {"submission_ref": 56108577, "public_score": 0.78070, "changed_rows": int(len(emotion_diff))},
        },
        "changed_row_count": int(len(union_diff)),
        "changed_rows": union_diff[["qa_id", "prediction_parent", "prediction_new"]].to_dict(orient="records"),
        "selection_rationale": "Disjoint union of two independently pre-gated mechanisms; no row-level leaderboard inference.",
    }
    report.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
