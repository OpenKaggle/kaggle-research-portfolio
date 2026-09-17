#!/usr/bin/env python3
"""Turn a validated embryo-OOF receipt into an error taxonomy and next hypothesis."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path

from validate_oof_receipt import sha256, validate


def jaccard(tp: float, fp: float, fn: float) -> float | None:
    denominator = tp + fp + fn
    return tp / denominator if denominator > 0 else None


def mean(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return statistics.fmean(finite) if finite else None


def analyse(receipt: dict, protocol: dict, validation: dict) -> dict:
    if not validation["valid"]:
        return {
            "status": "rejected",
            "validation": validation,
            "submission_recommendation": "do_not_submit",
        }

    protocol_folds = {int(fold["fold"]): fold for fold in protocol["folds"]}
    enriched = []
    taxonomy: Counter[str] = Counter()
    for row in receipt["per_sample"]:
        fold_id = int(row["fold"])
        fold = protocol_folds[fold_id]
        proxy = int(fold["holdout_selection_proxy_bytes"][row["dataset"]])
        ordered = sorted(fold["holdout_selection_proxy_bytes"].values())
        rank = ordered.index(proxy)
        fraction = rank / max(len(ordered) - 1, 1)
        difficulty = "low" if fraction < 1 / 3 else "mid" if fraction < 2 / 3 else "high"

        node_ratio = float(row["total_node_ratio"])
        edge_fp = int(row["edge_fp"])
        edge_fn = int(row["edge_fn"])
        div_j = jaccard(
            int(row["division_tp"]),
            int(row["division_fp"]),
            int(row["division_fn"]),
        )
        labels = []
        if node_ratio <= -0.10:
            labels.append("node_underprediction")
        elif node_ratio >= 0.10:
            labels.append("node_overprediction")
        else:
            labels.append("node_count_near_target")
        if edge_fn > 1.5 * max(edge_fp, 1):
            labels.append("edge_recall_limited")
        elif edge_fp > 1.5 * max(edge_fn, 1):
            labels.append("edge_precision_limited")
        else:
            labels.append("edge_errors_balanced")
        if div_j is not None and div_j < 0.30:
            labels.append("division_limited")
        for label in labels:
            taxonomy[label] += 1
        enriched.append(
            {
                **row,
                "train_embryo": fold["train_embryo"],
                "holdout_embryo": fold["validation_embryo"],
                "difficulty_proxy_bytes": proxy,
                "difficulty_bin": difficulty,
                "division_jaccard": div_j,
                "error_labels": labels,
            }
        )

    strata = {}
    for difficulty in ("low", "mid", "high"):
        rows = [row for row in enriched if row["difficulty_bin"] == difficulty]
        edge_tp = sum(int(row["edge_tp"]) for row in rows)
        edge_fp = sum(int(row["edge_fp"]) for row in rows)
        edge_fn = sum(int(row["edge_fn"]) for row in rows)
        div_tp = sum(int(row["division_tp"]) for row in rows)
        div_fp = sum(int(row["division_fp"]) for row in rows)
        div_fn = sum(int(row["division_fn"]) for row in rows)
        strata[difficulty] = {
            "samples": len(rows),
            "edge_jaccard_micro": jaccard(edge_tp, edge_fp, edge_fn),
            "division_jaccard_micro": jaccard(div_tp, div_fp, div_fn),
            "node_recall_mean": mean([float(row["node_recall"]) for row in rows]),
            "node_ratio_mean": mean([float(row["total_node_ratio"]) for row in rows]),
        }

    totals = {
        key: sum(int(row[key]) for row in enriched)
        for key in ("edge_tp", "edge_fp", "edge_fn", "division_tp", "division_fp", "division_fn")
    }
    node_ratio_mean = mean([float(row["total_node_ratio"]) for row in enriched])
    edge_error_total = totals["edge_fp"] + totals["edge_fn"]
    missing_edge_share = totals["edge_fn"] / edge_error_total if edge_error_total else 0.0
    division_j = jaccard(totals["division_tp"], totals["division_fp"], totals["division_fn"])
    edge_j = jaccard(totals["edge_tp"], totals["edge_fp"], totals["edge_fn"])

    if node_ratio_mean is not None and node_ratio_mean <= -0.10:
        next_variable = "detection_threshold_downward_calibration"
        rationale = "Cross-embryo predictions undercount total nodes by at least 10% on average."
    elif node_ratio_mean is not None and node_ratio_mean >= 0.10:
        next_variable = "physical_nms_or_detection_threshold_upward_calibration"
        rationale = "Cross-embryo predictions overcount total nodes by at least 10% on average."
    elif missing_edge_share >= 0.65:
        next_variable = "temporal_link_recall"
        rationale = "At least 65% of association errors are false negatives."
    elif missing_edge_share <= 0.35:
        next_variable = "temporal_link_precision"
        rationale = "At least 65% of association errors are false positives."
    elif division_j is not None and edge_j is not None and division_j + 0.20 < edge_j:
        next_variable = "conservative_division_recovery"
        rationale = "Division Jaccard trails edge Jaccard by more than 0.20."
    else:
        next_variable = "cross_embryo_representation"
        rationale = "No single count, link, or division error dominates the frozen OOF set."

    fold_scores = validation["fold_scores"]
    direction_gap = abs(fold_scores[0] - fold_scores[1])
    return {
        "status": "complete_diagnostic",
        "validation": validation,
        "combined_holdout_score": receipt["combined_holdout_summary"]["score"],
        "fold_scores": fold_scores,
        "embryo_direction_gap": direction_gap,
        "directionally_stable_at_0_15": direction_gap <= 0.15,
        "edge_jaccard_micro": edge_j,
        "division_jaccard_micro": division_j,
        "node_ratio_mean": node_ratio_mean,
        "missing_edge_error_share": missing_edge_share,
        "taxonomy_counts": dict(sorted(taxonomy.items())),
        "difficulty_strata": strata,
        "next_experiment": {
            "single_variable": next_variable,
            "rationale": rationale,
            "requires_both_embryo_directions": True,
        },
        "submission_recommendation": "diagnostic_only_do_not_submit",
        "per_sample": enriched,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    validation = validate(receipt, protocol, sha256(args.protocol))
    report = analyse(receipt, protocol, validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    raise SystemExit(0 if report["status"] == "complete_diagnostic" else 1)


if __name__ == "__main__":
    main()
