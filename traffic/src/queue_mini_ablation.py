#!/usr/bin/env python3
"""Observation-only Queue proxy for the off-by-one and onset/ongoing mini-ablation."""

from __future__ import annotations

import argparse
import importlib.util
import json
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("queue_shockwave", HERE / "queue_shockwave.py")
queue_shockwave = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(queue_shockwave)

PANEL = "D7_I210_W"
V32_TOP2 = ["L210W-190", "L210W-246"]
DEVELOPMENT_DATES = {"2030-06-01", "2030-06-04"}
CONFIRMATION_DATES = {"2030-06-02", "2030-06-03"}


def _thresholds(network: Path) -> dict[str, float]:
    links = pd.read_csv(network / "links.csv", dtype={"link_id": str})
    return dict(
        zip(
            links.link_id.astype(str),
            0.60 * pd.to_numeric(links.free_speed_kmh, errors="coerce").fillna(105.0),
        )
    )


def _upstream(network: Path) -> dict[str, list[str]]:
    topology = pd.read_csv(network / "lwr_mainline_topology.csv", dtype=str).fillna("")
    return {
        str(row.link_id): [value.strip() for value in str(row.incoming_link_ids).split(";") if value.strip()]
        for row in topology.itertuples(index=False)
    }


def _v32_forecast(
    history: pd.DataFrame,
    template: pd.DataFrame,
    condition: str,
    thresholds: dict[str, float],
    *,
    fixed_horizon: bool,
) -> pd.DataFrame:
    output = template[["window_id", "timestamp", "link_id"]].copy()
    last_time = history.timestamp.max()
    at_last = history[history.timestamp.eq(last_time)].copy()
    at_last["queue_now"] = at_last.speed_kmh <= at_last.link_id.map(thresholds).fillna(63.0)
    at_last["queue_now"] &= at_last.is_score_eligible.astype(bool)
    queue_now = at_last.groupby("link_id").queue_now.any().to_dict()
    output["queue_pred"] = 0
    if "ongoing" in condition.lower():
        output["queue_pred"] = output.link_id.map(queue_now).fillna(False).astype(int)
    else:
        if fixed_horizon:
            future_times = sorted(output.timestamp.drop_duplicates())
            final_time = future_times[-1]
            mask = output.link_id.isin(V32_TOP2) & output.timestamp.eq(final_time)
        else:
            # Reproduce V32 exactly: last history is T-5, so this condition
            # activates both T+25 (30 minutes later) and T+30 (35 later).
            elapsed = (output.timestamp - last_time).dt.total_seconds() / 60.0
            mask = output.link_id.isin(V32_TOP2) & elapsed.ge(29.5)
        output.loc[mask, "queue_pred"] = 1
    return output


def _history_risk(history: pd.DataFrame, windows: pd.DataFrame, thresholds: dict[str, float]) -> dict[str, float]:
    development_windows = set(windows[windows.date.isin(DEVELOPMENT_DATES)].window_id.astype(str))
    sample = history[history.window_id.isin(development_windows)].copy()
    eligible = sample.is_score_eligible.astype(bool) & sample.speed_kmh.notna()
    sample = sample[eligible]
    sample["queued"] = sample.speed_kmh <= sample.link_id.map(thresholds).fillna(63.0)
    return sample.groupby("link_id").queued.mean().astype(float).to_dict()


def _proxy_truth(root: Path, template: pd.DataFrame, thresholds: dict[str, float]) -> pd.DataFrame:
    pieces = []
    for path in sorted((root / "unmasked").glob("*.parquet")):
        frame = pd.read_parquet(path, columns=["timestamp", "link_id", "speed_kmh", "is_score_eligible"])
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        frame["link_id"] = frame.link_id.astype(str)
        frame["speed_kmh"] = pd.to_numeric(frame.speed_kmh, errors="coerce")
        pieces.append(frame)
    observed = pd.concat(pieces, ignore_index=True).drop_duplicates(["timestamp", "link_id"])
    target = template[["window_id", "timestamp", "link_id"]].merge(
        observed, on=["timestamp", "link_id"], how="left", validate="many_to_one"
    )
    target["proxy_eligible"] = target.is_score_eligible.fillna(0).astype(bool) & target.speed_kmh.notna()
    target["queue_true_proxy"] = target.speed_kmh <= target.link_id.map(thresholds).fillna(63.0)
    return target


def _iou(prediction: pd.DataFrame, truth: pd.DataFrame) -> tuple[float, int, int, int]:
    keys = ["window_id", "timestamp", "link_id"]
    merged = truth.merge(prediction, on=keys, how="left", validate="one_to_one")
    eligible = merged.proxy_eligible.astype(bool)
    pred = merged.loc[eligible, "queue_pred"].fillna(0).astype(bool).to_numpy()
    actual = merged.loc[eligible, "queue_true_proxy"].astype(bool).to_numpy()
    intersection = int(np.logical_and(pred, actual).sum())
    union = int(np.logical_or(pred, actual).sum())
    return (1.0 if union == 0 else intersection / union), int(eligible.sum()), intersection, union


def _aggregate(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (split, method, condition), group in detail.groupby(["split", "method", "condition"], sort=True):
        rows.append(
            {
                "split": split,
                "method": method,
                "condition": condition,
                "windows": len(group),
                "S_queue_proxy": float(group.IoU_proxy.mean()),
                "positive_predictions": int(group.positive_predictions.sum()),
                "proxy_eligible_rows": int(group.proxy_eligible_rows.sum()),
            }
        )
    by_condition = pd.DataFrame(rows)
    overall_rows = []
    for (split, method), group in by_condition.groupby(["split", "method"], sort=True):
        overall_rows.append(
            {
                "split": split,
                "method": method,
                "condition": "equal_condition_mean",
                "windows": int(group.windows.sum()),
                "S_queue_proxy": float(group.S_queue_proxy.mean()),
                "positive_predictions": int(group.positive_predictions.sum()),
                "proxy_eligible_rows": int(group.proxy_eligible_rows.sum()),
            }
        )
    return pd.concat([by_condition, pd.DataFrame(overall_rows)], ignore_index=True)


def run(root: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    windows = pd.read_csv(root / "task2" / "window_index.csv", dtype={"window_id": str})
    history = pd.read_parquet(root / "task2" / "window_history.parquet")
    template = pd.read_csv(root / "task2" / "sample_submission_queue.csv", dtype={"window_id": str, "link_id": str})
    history["window_id"] = history.window_id.astype(str)
    history["link_id"] = history.link_id.astype(str)
    history["timestamp"] = pd.to_datetime(history.timestamp, utc=True)
    history["speed_kmh"] = pd.to_numeric(history.speed_kmh, errors="coerce")
    template["timestamp"] = pd.to_datetime(template.timestamp, utc=True)
    thresholds = _thresholds(root / "network")
    upstream = _upstream(root / "network")
    risk = _history_risk(history, windows, thresholds)
    truth = _proxy_truth(root, template, thresholds)
    condition_by_window = windows.set_index("window_id").condition.astype(str).to_dict()
    date_by_window = windows.set_index("window_id").date.astype(str).to_dict()

    predictions: dict[str, list[pd.DataFrame]] = {
        "v32_bug_anchor": [],
        "off_by_one_only": [],
        "onset_trend_ongoing_persistence": [],
        "full_shockwave_v1": [],
    }
    for window_id, group in history.groupby("window_id", sort=True):
        target = template[template.window_id.eq(str(window_id))].copy()
        condition = condition_by_window[str(window_id)]
        anchor = _v32_forecast(group, target, condition, thresholds, fixed_horizon=False)
        fixed = _v32_forecast(group, target, condition, thresholds, fixed_horizon=True)
        shockwave = queue_shockwave.forecast_window(
            group, target, condition, thresholds, upstream, risk, onset_top_k=1
        )
        onset_only = shockwave if "onset" in condition.lower() else anchor
        predictions["v32_bug_anchor"].append(anchor)
        predictions["off_by_one_only"].append(fixed)
        predictions["onset_trend_ongoing_persistence"].append(onset_only)
        predictions["full_shockwave_v1"].append(shockwave)

    detail_rows = []
    prediction_outputs = {}
    for method, pieces in predictions.items():
        prediction = pd.concat(pieces, ignore_index=True)
        prediction_outputs[method] = prediction
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
    confirmation = aggregate[
        (aggregate.split == "confirmation") & (aggregate.condition == "equal_condition_mean")
    ].set_index("method")
    anchor_score = float(confirmation.loc["v32_bug_anchor", "S_queue_proxy"])
    candidate_scores = confirmation.S_queue_proxy.drop(index="v32_bug_anchor")
    winner = str(candidate_scores.idxmax())
    winner_score = float(candidate_scores.max())
    proxy_queue_delta = winner_score - anchor_score
    proxy_weighted_delta = 0.30 * proxy_queue_delta
    runtime = time.perf_counter() - started
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    receipt = {
        "status": "COMPLETE",
        "question": "Does fixing the T-5 horizon bug and separating onset/ongoing improve an untouched public-train observation proxy enough to justify one Queue-only leaderboard test?",
        "data_boundary": {
            "panel": PANEL,
            "development_dates": sorted(DEVELOPMENT_DATES),
            "confirmation_dates": sorted(CONFIRMATION_DATES),
            "same_day_windows_cross_splits": False,
            "risk_prior": "estimated only from development window histories",
        },
        "metric_boundary": {
            "official_S_queue": None,
            "proxy": "IoU against released noisy eligible train observations; organizer uses withheld latent state",
        },
        "confirmation_scores": {method: float(row.S_queue_proxy) for method, row in confirmation.iterrows()},
        "winner": winner,
        "winner_minus_v32_proxy_queue": proxy_queue_delta,
        "winner_estimated_weighted_total_delta": proxy_weighted_delta,
        "runtime_seconds": runtime,
        "peak_memory_mb": peak_mb,
        "decision_rule": "Only build a Queue-only leaderboard candidate if confirmation proxy implies at least +0.015 weighted total; after submission continue only for actual public gain >= +0.015. Otherwise stop this Queue family.",
        "decision": "BUILD_QUEUE_ONLY_CANDIDATE" if proxy_weighted_delta >= 0.015 else "STOP_QUEUE_FAMILY",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output_root / "queue_mini_window_metrics.csv", index=False)
    aggregate.to_csv(output_root / "queue_mini_aggregate_metrics.csv", index=False)
    for method, prediction in prediction_outputs.items():
        prediction.to_csv(output_root / f"{method}.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    (output_root / "queue_mini_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve(), args.output_root.resolve()), indent=2))


if __name__ == "__main__":
    main()
