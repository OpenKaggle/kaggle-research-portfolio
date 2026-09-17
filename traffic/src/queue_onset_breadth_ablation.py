#!/usr/bin/env python3
"""Sealed Queue proxy comparing V32's two onset links with one retained link."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import pandas as pd

from queue_mini_ablation import (
    CONFIRMATION_DATES,
    DEVELOPMENT_DATES,
    PANEL,
    V32_TOP2,
    _aggregate,
    _iou,
    _proxy_truth,
    _thresholds,
    _v32_forecast,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(root: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    windows = pd.read_csv(root / "task2" / "window_index.csv", dtype={"window_id": str})
    history = pd.read_parquet(root / "task2" / "window_history.parquet")
    template = pd.read_csv(
        root / "task2" / "sample_submission_queue.csv", dtype={"window_id": str, "link_id": str}
    )
    history["window_id"] = history.window_id.astype(str)
    history["link_id"] = history.link_id.astype(str)
    history["timestamp"] = pd.to_datetime(history.timestamp, utc=True)
    history["speed_kmh"] = pd.to_numeric(history.speed_kmh, errors="coerce")
    template["timestamp"] = pd.to_datetime(template.timestamp, utc=True)
    thresholds = _thresholds(root / "network")
    truth = _proxy_truth(root, template, thresholds)
    condition_by_window = windows.set_index("window_id").condition.astype(str).to_dict()
    date_by_window = windows.set_index("window_id").date.astype(str).to_dict()

    predictions = {"top2_control": [], "rank1_only": [], "rank2_only": []}
    for window_id, group in history.groupby("window_id", sort=True):
        window_id = str(window_id)
        target = template[template.window_id.eq(window_id)].copy()
        condition = condition_by_window[window_id]
        top2 = _v32_forecast(group, target, condition, thresholds, fixed_horizon=True)
        rank1 = top2.copy()
        rank2 = top2.copy()
        if "onset" in condition.lower():
            rank1.loc[rank1.link_id.eq(V32_TOP2[1]), "queue_pred"] = 0
            rank2.loc[rank2.link_id.eq(V32_TOP2[0]), "queue_pred"] = 0
        predictions["top2_control"].append(top2)
        predictions["rank1_only"].append(rank1)
        predictions["rank2_only"].append(rank2)

    detail_rows = []
    outputs = {}
    for method, pieces in predictions.items():
        prediction = pd.concat(pieces, ignore_index=True)
        outputs[method] = prediction
        for window_id, target in truth.groupby("window_id", sort=True):
            one_prediction = prediction[prediction.window_id.eq(str(window_id))]
            iou, eligible_rows, intersection, union = _iou(one_prediction, target)
            date = date_by_window[str(window_id)]
            split = "development" if date in DEVELOPMENT_DATES else "confirmation"
            detail_rows.append(
                {
                    "split": split,
                    "date": date,
                    "window_id": str(window_id),
                    "condition": condition_by_window[str(window_id)],
                    "method": method,
                    "IoU_proxy": iou,
                    "positive_predictions": int(one_prediction.queue_pred.sum()),
                    "proxy_eligible_rows": eligible_rows,
                    "proxy_intersection": intersection,
                    "proxy_union": union,
                }
            )
    detail = pd.DataFrame(detail_rows)
    aggregate = _aggregate(detail)
    overall = aggregate[aggregate.condition.eq("equal_condition_mean")]
    development = overall[overall.split.eq("development")].set_index("method")
    confirmation = overall[overall.split.eq("confirmation")].set_index("method")
    selected_method = str(development.drop(index="top2_control").S_queue_proxy.idxmax())
    dev_delta = float(
        development.loc[selected_method, "S_queue_proxy"]
        - development.loc["top2_control", "S_queue_proxy"]
    )
    confirm_delta = float(
        confirmation.loc[selected_method, "S_queue_proxy"]
        - confirmation.loc["top2_control", "S_queue_proxy"]
    )
    weighted_proxy_delta = 0.30 * confirm_delta
    passed = dev_delta > 0 and weighted_proxy_delta >= 0.005

    output_root.mkdir(parents=True, exist_ok=True)
    detail_path = output_root / "queue_onset_breadth_window_metrics.csv"
    aggregate_path = output_root / "queue_onset_breadth_aggregate_metrics.csv"
    detail.to_csv(detail_path, index=False)
    aggregate.to_csv(aggregate_path, index=False)
    for method, prediction in outputs.items():
        prediction.to_csv(
            output_root / f"{method}.csv",
            index=False,
            date_format="%Y-%m-%dT%H:%M:%SZ",
        )
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    receipt = {
        "status": "COMPLETE",
        "question": "After fixing the onset horizon, should each onset window retain only one of V32's two ranked bottleneck links?",
        "data_boundary": {
            "panel": PANEL,
            "development_dates": sorted(DEVELOPMENT_DATES),
            "confirmation_dates": sorted(CONFIRMATION_DATES),
            "same_day_windows_cross_splits": False,
        },
        "invariant": "Ongoing forecasts, onset timestamp, thresholds, and all non-onset-link rows are identical; only onset link breadth/rank changes.",
        "v32_ranked_links": V32_TOP2,
        "development_scores": {
            method: float(row.S_queue_proxy) for method, row in development.iterrows()
        },
        "confirmation_scores": {
            method: float(row.S_queue_proxy) for method, row in confirmation.iterrows()
        },
        "selected_method_from_development": selected_method,
        "development_selected_minus_top2": dev_delta,
        "confirmation_selected_minus_top2": confirm_delta,
        "confirmation_estimated_weighted_total_delta": weighted_proxy_delta,
        "metric_boundary": {
            "official_S_queue": None,
            "proxy": "IoU against released noisy eligible train observations; organizer uses withheld latent state",
        },
        "decision_rule": "Build one rank-consistent Queue-only candidate only if the selected single-link arm beats top2 on development and confirmation implies at least +0.005 weighted total.",
        "decision": "BUILD_RANK_CONSISTENT_QUEUE_CANDIDATE" if passed else "STOP_ONSET_BREADTH_FAMILY",
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": peak_mb,
        "artifacts": {
            "detail_sha256": _sha256(detail_path),
            "aggregate_sha256": _sha256(aggregate_path),
        },
    }
    receipt_path = output_root / "queue_onset_breadth_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve(), args.output_root.resolve()), indent=2))


if __name__ == "__main__":
    main()
