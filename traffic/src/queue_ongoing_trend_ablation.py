#!/usr/bin/env python3
"""All-panel released-observation proxy for one ongoing-Queue trend variable."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from queue_shockwave import _thresholds, _trend_features


DEVELOPMENT_DATES = {"2030-06-01"}
CONFIRMATION_DATES = {"2030-06-02", "2030-06-03"}
MAX_CROSS_STEPS = (0, 2, 3, 4, 5, 6)
TOP2 = {
    "D12_I5_N": ["L5N-059", "L5N-104"],
    "D12_I5_S": ["L5S-152", "L5S-249"],
    "D7_I10_E": ["L10E-043", "L10E-125"],
    "D7_I10_W": ["L10W-013", "L10W-212"],
    "D7_I210_E": ["L210E-132", "L210E-261"],
    "D7_I210_W": ["L210W-190", "L210W-246"],
    "D7_I405_N": ["L405N-145", "L405N-041"],
    "D7_I405_S": ["L405S-264", "L405S-127"],
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def forecast(
    history: pd.DataFrame,
    template: pd.DataFrame,
    condition: str,
    thresholds: dict[str, float],
    top2: list[str],
    max_cross_step: int,
) -> pd.DataFrame:
    output = template[["window_id", "timestamp", "link_id"]].copy()
    output["queue_pred"] = 0
    times = sorted(output.timestamp.drop_duplicates())
    steps = {timestamp: step for step, timestamp in enumerate(times, 1)}
    output["step"] = output.timestamp.map(steps).astype(int)
    if "onset" in condition.lower():
        output.loc[
            output.link_id.isin(top2) & output.timestamp.eq(times[-1]), "queue_pred"
        ] = 1
    else:
        features = _trend_features(history, thresholds)
        for link, row in features.iterrows():
            link_rows = output.link_id.eq(str(link))
            if bool(row.queue_now):
                output.loc[link_rows, "queue_pred"] = 1
            elif (
                max_cross_step > 0
                and np.isfinite(row.cross_step)
                and int(row.cross_step) <= max_cross_step
            ):
                output.loc[
                    link_rows & output.step.ge(max(2, int(row.cross_step))), "queue_pred"
                ] = 1
    output["queue_pred"] = output.queue_pred.astype(int)
    return output.drop(columns="step")


def _proxy_truth(
    panel_root: Path, template: pd.DataFrame, thresholds: dict[str, float]
) -> pd.DataFrame:
    wanted_dates = DEVELOPMENT_DATES | CONFIRMATION_DATES
    paths = [
        path
        for path in (panel_root / "train" / "mainline_states").glob("**/*.parquet")
        if path.stem.removeprefix("synthetic_mainline_").replace("_", "-") in wanted_dates
    ]
    pieces = []
    for path in sorted(paths):
        frame = pd.read_parquet(
            path, columns=["timestamp", "link_id", "speed_kmh", "is_score_eligible"]
        )
        frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
        frame["link_id"] = frame.link_id.astype(str)
        pieces.append(frame)
    observed = pd.concat(pieces, ignore_index=True).drop_duplicates(["timestamp", "link_id"])
    truth = template[["window_id", "timestamp", "link_id"]].merge(
        observed, on=["timestamp", "link_id"], how="left", validate="many_to_one"
    )
    truth["proxy_eligible"] = (
        truth.is_score_eligible.fillna(0).astype(bool) & truth.speed_kmh.notna()
    )
    truth["queue_true_proxy"] = (
        pd.to_numeric(truth.speed_kmh, errors="coerce")
        <= truth.link_id.map(thresholds).fillna(63.0)
    )
    return truth


def _iou(prediction: pd.DataFrame, truth: pd.DataFrame) -> tuple[float, int, int, int]:
    merged = truth.merge(
        prediction,
        on=["window_id", "timestamp", "link_id"],
        how="left",
        validate="one_to_one",
    )
    eligible = merged.proxy_eligible.astype(bool)
    pred = merged.loc[eligible, "queue_pred"].fillna(0).astype(bool).to_numpy()
    actual = merged.loc[eligible, "queue_true_proxy"].astype(bool).to_numpy()
    intersection = int((pred & actual).sum())
    union = int((pred | actual).sum())
    return (1.0 if union == 0 else intersection / union), int(eligible.sum()), intersection, union


def _aggregate(detail: pd.DataFrame, families: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    panel_condition = (
        detail.groupby(["split", "max_cross_step", "panel", "condition"], sort=True)
        .agg(S_queue_proxy=("IoU_proxy", "mean"), windows=("window_id", "nunique"))
        .reset_index()
    )
    for item in panel_condition.itertuples(index=False):
        rows.append(
            {
                "split": item.split, "max_cross_step": item.max_cross_step,
                "level": "panel_condition", "panel": item.panel,
                "family_id": families[item.panel], "condition": item.condition,
                "windows": item.windows, "S_queue_proxy": item.S_queue_proxy,
            }
        )
    pc = pd.DataFrame(rows)
    panel_rows = []
    for (split, step, panel), group in pc.groupby(
        ["split", "max_cross_step", "panel"], sort=True
    ):
        panel_rows.append(
            {
                "split": split, "max_cross_step": step, "level": "panel",
                "panel": panel, "family_id": families[panel], "condition": "equal_mean",
                "windows": int(group.windows.sum()), "S_queue_proxy": float(group.S_queue_proxy.mean()),
            }
        )
    panels = pd.DataFrame(panel_rows)
    family_rows = []
    for (split, step, family), group in panels.groupby(
        ["split", "max_cross_step", "family_id"], sort=True
    ):
        family_rows.append(
            {
                "split": split, "max_cross_step": step, "level": "family",
                "panel": None, "family_id": family, "condition": "equal_mean",
                "windows": int(group.windows.sum()), "S_queue_proxy": float(group.S_queue_proxy.mean()),
            }
        )
    family = pd.DataFrame(family_rows)
    overall_rows = []
    for (split, step), group in family.groupby(["split", "max_cross_step"], sort=True):
        overall_rows.append(
            {
                "split": split, "max_cross_step": step, "level": "overall",
                "panel": None, "family_id": "ALL", "condition": "equal_mean",
                "windows": int(group.windows.sum()), "S_queue_proxy": float(group.S_queue_proxy.mean()),
            }
        )
    return pd.concat([pc, panels, family, pd.DataFrame(overall_rows)], ignore_index=True)


def run(release: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    manifest_path = release / "config" / "corridors.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    families = {str(p["corridor_id"]): str(p["family_id"]) for p in manifest["panels"]}
    panels = [panel for panel in TOP2 if panel in families]
    detail_rows: list[dict[str, object]] = []
    prediction_changes = defaultdict(int)
    for panel in panels:
        print(f"[ongoing trend proxy] {panel}", flush=True)
        task_root = release / "task2" / panel / "train"
        windows = pd.read_csv(task_root / "window_index.csv", dtype={"window_id": str})
        windows = windows[windows.date.astype(str).isin(DEVELOPMENT_DATES | CONFIRMATION_DATES)]
        history = pd.read_parquet(task_root / "window_history.parquet")
        history["window_id"] = history.window_id.astype(str)
        history["link_id"] = history.link_id.astype(str)
        history["timestamp"] = pd.to_datetime(history.timestamp, utc=True)
        history["speed_kmh"] = pd.to_numeric(history.speed_kmh, errors="coerce")
        history["is_score_eligible"] = history.is_score_eligible.astype(bool)
        template = pd.read_csv(
            task_root / "sample_submission_queue.csv", dtype={"window_id": str, "link_id": str}
        )
        template["timestamp"] = pd.to_datetime(template.timestamp, utc=True)
        template = template[template.window_id.isin(windows.window_id)]
        thresholds = _thresholds(release, panel)
        truth = _proxy_truth(release / "corridors" / panel, template, thresholds)
        condition = windows.set_index("window_id").condition.astype(str).to_dict()
        dates = windows.set_index("window_id").date.astype(str).to_dict()
        for window_id, group in history[history.window_id.isin(windows.window_id)].groupby(
            "window_id", sort=True
        ):
            target = template[template.window_id == window_id]
            predictions = {
                step: forecast(group, target, condition[window_id], thresholds, TOP2[panel], step)
                for step in MAX_CROSS_STEPS
            }
            control = predictions[0].queue_pred.to_numpy()
            for step, prediction in predictions.items():
                prediction_changes[step] += int((prediction.queue_pred.to_numpy() != control).sum())
                one_truth = truth[truth.window_id == window_id]
                iou, eligible, intersection, union = _iou(prediction, one_truth)
                date = dates[window_id]
                split = "development" if date in DEVELOPMENT_DATES else "confirmation"
                detail_rows.append(
                    {
                        "split": split, "date": date, "panel": panel,
                        "family_id": families[panel], "window_id": window_id,
                        "condition": condition[window_id], "max_cross_step": step,
                        "IoU_proxy": iou, "proxy_eligible_rows": eligible,
                        "proxy_intersection": intersection, "proxy_union": union,
                        "positive_predictions": int(prediction.queue_pred.sum()),
                    }
                )
    detail = pd.DataFrame(detail_rows)
    aggregate = _aggregate(detail, families)
    overall = aggregate[aggregate.level == "overall"]
    development = overall[overall.split == "development"].sort_values(
        ["S_queue_proxy", "max_cross_step"], ascending=[False, True]
    )
    selected_step = int(development.iloc[0].max_cross_step)
    confirmation = overall[overall.split == "confirmation"].set_index("max_cross_step")
    selected = confirmation.loc[selected_step]
    control = confirmation.loc[0]
    queue_delta = float(selected.S_queue_proxy - control.S_queue_proxy)
    weighted_delta = 0.30 * queue_delta
    pc = aggregate[
        (aggregate.level == "panel_condition")
        & (aggregate.split == "confirmation")
        & (aggregate.condition == "queue_ongoing")
    ]
    selected_pc = pc[pc.max_cross_step == selected_step].set_index("panel").S_queue_proxy
    control_pc = pc[pc.max_cross_step == 0].set_index("panel").S_queue_proxy
    panel_deltas = selected_pc - control_pc
    positive_panels = int((panel_deltas > 0).sum())
    gate_passed = (
        selected_step != 0
        and weighted_delta >= 0.005
        and positive_panels >= 6
        and float(panel_deltas.min()) >= -0.05
    )
    output_root.mkdir(parents=True, exist_ok=True)
    detail_path = output_root / "ongoing_trend_window_metrics.csv"
    aggregate_path = output_root / "ongoing_trend_aggregate_metrics.csv"
    detail.to_csv(detail_path, index=False)
    aggregate.to_csv(aggregate_path, index=False)
    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "experiment": "queue_ongoing_trend_ablation_v1",
        "question": "Keeping proven onset rows fixed, does one trend-crossing horizon improve ongoing Queue persistence across all released train panels?",
        "data_boundary": {
            "panels": panels,
            "development_dates": sorted(DEVELOPMENT_DATES),
            "confirmation_dates": sorted(CONFIRMATION_DATES),
            "proxy_only": "IoU against released noisy eligible mainline observations; hidden queue labels are never accessed or reconstructed",
        },
        "only_variable": {
            "name": "max_cross_step",
            "values": list(MAX_CROSS_STEPS),
            "control": 0,
            "effect": "currently nonqueued but decelerating links may activate by this forecast step; onset and queued-now persistence are invariant",
        },
        "development_selected_max_cross_step": selected_step,
        "development_frontier": {
            str(int(row.max_cross_step)): float(row.S_queue_proxy)
            for row in overall[overall.split == "development"].itertuples(index=False)
        },
        "confirmation_frontier": {
            str(int(row.max_cross_step)): float(row.S_queue_proxy)
            for row in overall[overall.split == "confirmation"].itertuples(index=False)
        },
        "changed_train_proxy_rows_frontier": {
            str(step): int(count) for step, count in sorted(prediction_changes.items())
        },
        "confirmation": {
            "selected_S_queue_proxy": float(selected.S_queue_proxy),
            "control_S_queue_proxy": float(control.S_queue_proxy),
            "delta_S_queue_proxy": queue_delta,
            "estimated_weighted_total_delta": weighted_delta,
            "ongoing_panel_deltas": {panel: float(delta) for panel, delta in panel_deltas.items()},
            "positive_ongoing_panels": positive_panels,
            "minimum_ongoing_panel_delta": float(panel_deltas.min()),
            "changed_train_proxy_rows_vs_control": int(prediction_changes[selected_step]),
        },
        "preregistered_expansion_gate": {
            "development_selects_noncontrol": True,
            "minimum_confirmation_estimated_weighted_total_delta": 0.005,
            "minimum_positive_ongoing_panels": 6,
            "minimum_panel_delta": -0.05,
        },
        "official_S_queue": None,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(manifest_path)},
        "outputs": {detail_path.name: _sha256(detail_path), aggregate_path.name: _sha256(aggregate_path)},
        "decision": "BUILD_GROUPED_QUEUE_CANDIDATE" if gate_passed else "STOP_ONGOING_TREND_FAMILY",
    }
    receipt_path = output_root / "queue_ongoing_trend_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.release_root.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
