#!/usr/bin/env python3
"""Create a compact error taxonomy from subject-disjoint sensor OOF predictions."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


def correct_text(row: pd.Series) -> str:
    return str(row[str(row["answer"]).strip()]).strip().lower()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    oof = pd.read_csv(root / "artifacts/oof/nonvisual_sensor_oof.csv")
    train = pd.read_csv(root / "data/raw/kaggle/training_qa.csv", encoding="utf-8-sig")
    extraction = json.loads((root / "reports/nonvisual_feature_extraction.json").read_text())
    details = train[["qa_id", "path", "question", "A", "B", "C", "D"]].copy()
    frame = oof.merge(details, on="qa_id", how="left", validate="one_to_one")
    frame["correct_text"] = frame.apply(correct_text, axis=1)
    frame["outcome"] = "both_wrong"
    frame.loc[frame["parent_correct"] & frame["expert_correct"], "outcome"] = "both_correct"
    frame.loc[frame["parent_correct"] & ~frame["expert_correct"], "outcome"] = "parent_only"
    frame.loc[~frame["parent_correct"] & frame["expert_correct"], "outcome"] = "expert_only"

    slices = {}
    for (source, category), group in frame.groupby(["source", "category"]):
        key = f"{source}/{category}"
        user_metrics = group.groupby("user").agg(parent=("parent_correct", "mean"), expert=("expert_correct", "mean"))
        user_metrics["delta"] = user_metrics["expert"] - user_metrics["parent"]
        confidence_bins = []
        ranked = group.copy()
        ranked["confidence_bin"] = pd.qcut(
            ranked["confidence"].rank(method="first"), q=min(5, len(ranked)), labels=False
        )
        for bin_id, part in ranked.groupby("confidence_bin"):
            confidence_bins.append(
                {
                    "bin": int(bin_id),
                    "rows": int(len(part)),
                    "confidence_min": float(part["confidence"].min()),
                    "confidence_max": float(part["confidence"].max()),
                    "expert_accuracy": float(part["expert_correct"].mean()),
                    "disagreement_accuracy": float(
                        part.loc[part["prediction"] != part["parent_prediction"], "expert_correct"].mean()
                    ) if (part["prediction"] != part["parent_prediction"]).any() else None,
                }
            )
        label_metrics = (
            group.groupby("correct_text")
            .agg(rows=("qa_id", "size"), parent=("parent_correct", "mean"), expert=("expert_correct", "mean"))
            .assign(delta=lambda value: value["expert"] - value["parent"])
            .sort_values(["delta", "rows"], ascending=[False, False])
        )
        slices[key] = {
            "rows": int(len(group)),
            "outcomes": {name: int(value) for name, value in group["outcome"].value_counts().items()},
            "user_delta_min": float(user_metrics["delta"].min()),
            "user_delta_median": float(user_metrics["delta"].median()),
            "user_delta_max": float(user_metrics["delta"].max()),
            "confidence_bins": confidence_bins,
            "largest_label_gains": [
                {"label": label, **{name: float(value) if name != "rows" else int(value) for name, value in row.items()}}
                for label, row in label_metrics.head(8).iterrows()
            ],
            "largest_label_losses": [
                {"label": label, **{name: float(value) if name != "rows" else int(value) for name, value in row.items()}}
                for label, row in label_metrics.tail(8).sort_values("delta").iterrows()
            ],
        }

    report = {
        "validation_contract": "18-fold leave-one-subject-out; clip intact",
        "coverage": extraction,
        "slices": slices,
        "error_taxonomy": [
            {
                "type": "sensor_recovers_structural_miss",
                "evidence": {
                    key: value["outcomes"].get("expert_only", 0)
                    for key, value in slices.items()
                },
                "action": "Retain only slices and confidence bands with positive subject-disjoint delta.",
            },
            {
                "type": "structure_beats_sensor",
                "evidence": {
                    key: value["outcomes"].get("parent_only", 0)
                    for key, value in slices.items()
                },
                "action": "Reject broad HAU single overrides and preserve the parent prediction.",
            },
            {
                "type": "modality_missing_or_empty",
                "evidence": {
                    "manifest_imu_files": extraction["manifest_declared_file_presence"]["imu"],
                    "imu_rows_with_values": extraction["finite_rows"]["imu"],
                    "empty_imu_units": extraction["manifest_declared_file_presence"]["imu"] - extraction["finite_rows"]["imu"],
                },
                "action": "Abstain from sensor-only overrides when the test unit has no usable modality.",
            },
            {
                "type": "partial_public_leaderboard_ambiguity",
                "evidence": "One changed row tied the 0.77777 parent publicly.",
                "action": "Do not infer the hidden label; keep selection anchored to OOF and private robustness.",
            },
        ],
    }
    json_path = root / "reports/nonvisual_sensor_error_analysis.json"
    md_path = root / "reports/nonvisual_sensor_error_analysis.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Nonvisual sensor error analysis",
        "",
        "Validation contract: 18-fold leave-one-subject-out, with every clip kept intact.",
        "",
        "| Slice | Parent | Expert | Expert-only wins | Parent-only wins | Worst user delta |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for key, value in slices.items():
        group = frame[(frame["source"] + "/" + frame["category"]) == key]
        lines.append(
            f"| {key} | {group['parent_correct'].mean():.4f} | {group['expert_correct'].mean():.4f} | "
            f"{value['outcomes'].get('expert_only', 0)} | {value['outcomes'].get('parent_only', 0)} | "
            f"{value['user_delta_min']:+.4f} |"
        )
    lines += [
        "",
        "## Decision implications",
        "",
        "- HARn single is a genuine sensor recovery slice: use conservative high-confidence overrides.",
        "- HAU emotion improves on average, but margins are small; require feature/seed stability before submission.",
        "- HAU single is dominated by the structural parent; broad overrides are rejected.",
        "- HARn object interaction ties overall and loses on its worst subject; only independently gated sparse changes qualify.",
        "- Fifty-eight declared IMU units contain header-only CSVs; missing-signal rows must abstain.",
        "- A public tie after one changed test row is non-diagnostic and must not be used as a hidden-label oracle.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "slices": list(slices)}, indent=2))


if __name__ == "__main__":
    main()
