#!/usr/bin/env python3
"""Read-only 10-panel audit of fixed versus link-relative congestion strata."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from task1_mini_ablation import _matrix, _temporal


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _date(path: Path) -> str:
    return path.stem.removeprefix("synthetic_mainline_").replace("_", "-")


def _read(path: Path, masked: bool) -> pd.DataFrame:
    columns = [
        "date",
        "timestamp",
        "station_id",
        "link_id",
        "milepost",
        "speed_kmh",
        "flow_vph",
        "pct_observed",
        "is_score_eligible",
    ]
    if masked:
        columns.append("mask_regime")
    frame = pd.read_parquet(path, columns=columns)
    frame["station_id"] = frame.station_id.astype(str)
    frame["link_id"] = frame.link_id.astype(str)
    timestamp = pd.to_datetime(frame.timestamp, utc=True)
    frame["slot"] = timestamp.dt.hour * 12 + timestamp.dt.minute // 5
    return frame


def _predict(masked: pd.DataFrame, prior: pd.DataFrame, fd: pd.DataFrame) -> tuple[list[str], dict[str, np.ndarray]]:
    links = sorted(masked.link_id.unique())
    prediction = {}
    for column in ("speed_kmh", "flow_vph"):
        observed = _matrix(masked, column, links)
        prior_values = _matrix(prior, column, links)
        fallback = np.nanmedian(prior_values, axis=0)
        fallback = np.where(np.isfinite(fallback), fallback, np.nanmedian(prior_values))
        prior_values = np.where(np.isfinite(prior_values), prior_values, fallback[None, :])
        values = _temporal(observed, prior_values)
        if column == "speed_kmh":
            upper = fd.free_speed_kmh.reindex(links).fillna(120.0).to_numpy(dtype=float) * 1.05
            values = np.clip(values, 5.0, upper[None, :])
        else:
            upper = fd.capacity_vph.reindex(links).fillna(15000.0).to_numpy(dtype=float) * 1.15
            values = np.clip(values, 50.0, upper[None, :])
        prediction[column] = values
    return links, prediction


def _stratum_row(
    panel: str,
    split: str,
    classifier: str,
    bucket: str,
    mask: np.ndarray,
    speed_error: np.ndarray,
    flow_error: np.ndarray,
) -> dict[str, object]:
    total_speed_loss = max(float(np.square(speed_error).sum()), 1e-12)
    n = int(mask.sum())
    return {
        "panel": panel,
        "split": split,
        "classifier": classifier,
        "bucket": bucket,
        "n": n,
        "support_fraction": float(mask.mean()),
        "speed_rmse_kmh": float(np.sqrt(np.mean(np.square(speed_error[mask])))) if n else np.nan,
        "flow_rmse_vph_per_lane": float(np.sqrt(np.mean(np.square(flow_error[mask])))) if n else np.nan,
        "speed_squared_loss_capture": float(np.square(speed_error[mask]).sum()) / total_speed_loss,
    }


def run(
    release: Path,
    output_root: Path,
    development_start: str,
    development_end: str,
    confirmation_start: str,
    confirmation_end: str,
) -> dict[str, object]:
    started = time.perf_counter()
    manifest = json.loads((release / "config" / "corridors.json").read_text(encoding="utf-8"))
    panel_records = manifest["panels"]
    rows = []
    comparison_rows = []
    daily_rows = []
    cutoff_ranges = {}
    for panel_record in panel_records:
        panel = panel_record["corridor_id"]
        panel_dir = release / "corridors" / panel
        unmasked = {
            _date(path): path
            for path in (panel_dir / "train" / "mainline_states").glob("**/*.parquet")
        }
        masked = {
            _date(path): path
            for path in (panel_dir / "train" / "mainline_states_masked").glob("**/*.parquet")
        }
        fd = pd.read_csv(panel_dir / "network" / "fd_parameters.csv", dtype={"link_id": str}).set_index("link_id")
        panel_cutoffs = 0.60 * pd.to_numeric(fd.free_speed_kmh, errors="coerce")
        cutoff_ranges[panel] = {
            "n_links": int(panel_cutoffs.notna().sum()),
            "n_unique": int(panel_cutoffs.nunique()),
            "minimum": float(panel_cutoffs.min()),
            "maximum": float(panel_cutoffs.max()),
            "range": float(panel_cutoffs.max() - panel_cutoffs.min()),
        }
        split_arrays: dict[str, dict[str, list[np.ndarray]]] = defaultdict(
            lambda: defaultdict(list)
        )
        chosen_days = [
            day
            for day in sorted(masked)
            if development_start <= day <= development_end
            or confirmation_start <= day <= confirmation_end
        ]
        print(f"[Task1 cutoff audit] panel={panel} days={len(chosen_days)}", flush=True)
        for day in chosen_days:
            split = "development" if day <= development_end else "confirmation"
            prior_day = (pd.Timestamp(day) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
            if day not in unmasked or prior_day not in unmasked:
                raise FileNotFoundError(f"{panel}/{day}: missing truth or seven-day prior")
            truth = _read(unmasked[day], masked=False)
            masked_day = _read(masked[day], masked=True)
            prior = _read(unmasked[prior_day], masked=False)
            links, prediction = _predict(masked_day, prior, fd)
            true_speed = _matrix(truth, "speed_kmh", links)
            true_flow = _matrix(truth, "flow_vph", links)
            target = _matrix(
                masked_day.assign(
                    target=masked_day.is_score_eligible.astype(bool)
                    & masked_day.speed_kmh.isna()
                    & masked_day.flow_vph.isna()
                ),
                "target",
                links,
            ).astype(bool)
            truth_eligible = _matrix(truth, "is_score_eligible", links).astype(bool)
            link_period_coverage = truth_eligible.mean(axis=0)
            keep_link = link_period_coverage > 0.50
            usable_before_filter = target & np.isfinite(true_speed) & np.isfinite(true_flow)
            usable = usable_before_filter & keep_link[None, :]
            slot_index, link_index = np.where(usable)
            lane_values = fd.lanes.reindex(links).fillna(1.0).to_numpy(dtype=float)
            cutoff_values = panel_cutoffs.reindex(links).to_numpy(dtype=float)
            previous_speed = np.vstack([np.full((1, len(links)), np.nan), true_speed[:-1]])
            speed = true_speed[usable]
            cutoff = cutoff_values[link_index]
            previous = previous_speed[usable]
            speed_error = prediction["speed_kmh"][usable] - speed
            flow_error = (
                prediction["flow_vph"][usable] - true_flow[usable]
            ) / lane_values[link_index]
            split_arrays[split]["speed"].append(speed)
            split_arrays[split]["cutoff"].append(cutoff)
            split_arrays[split]["previous"].append(previous)
            split_arrays[split]["speed_error"].append(speed_error)
            split_arrays[split]["flow_error"].append(flow_error)
            daily_rows.append(
                {
                    "panel": panel,
                    "split": split,
                    "day": day,
                    "regime": str(masked_day.mask_regime.iloc[0]),
                    "target_cells_before_coverage_filter": int(usable_before_filter.sum()),
                    "target_cells_after_coverage_filter": int(usable.sum()),
                    "coverage_fraction": float(usable.sum()) / max(int(usable_before_filter.sum()), 1),
                }
            )
        for split in ("development", "confirmation"):
            arrays = {
                key: np.concatenate(parts)
                for key, parts in split_arrays[split].items()
            }
            speed = arrays["speed"]
            cutoff = arrays["cutoff"]
            previous = arrays["previous"]
            speed_error = arrays["speed_error"]
            flow_error = arrays["flow_error"]
            fixed_masks = {
                "congested_le60": speed <= 60.0,
                "transition_60_90": (speed > 60.0) & (speed <= 90.0),
                "free_gt90": speed > 90.0,
            }
            crossing_down = np.isfinite(previous) & (previous > cutoff) & (speed <= cutoff)
            crossing_up = np.isfinite(previous) & (previous <= cutoff) & (speed > cutoff)
            cutoff_masks = {
                "crossing_into_congestion": crossing_down,
                "crossing_out_of_congestion": crossing_up,
                "congested_non_crossing": (speed <= cutoff) & ~crossing_down,
                "free_non_crossing": (speed > cutoff) & ~crossing_up,
            }
            for classifier, masks in (("fixed60_90", fixed_masks), ("link_cutoff", cutoff_masks)):
                for bucket, mask in masks.items():
                    rows.append(
                        _stratum_row(
                            panel, split, classifier, bucket, mask, speed_error, flow_error
                        )
                    )
            fixed_congested = speed <= 60.0
            cutoff_congested = speed <= cutoff
            total_loss = max(float(np.square(speed_error).sum()), 1e-12)
            abs_error = np.abs(speed_error)
            tail_threshold = float(np.quantile(abs_error, 0.99))
            tail = abs_error >= tail_threshold
            fixed_support = float(fixed_congested.mean())
            cutoff_support = float(cutoff_congested.mean())
            fixed_capture = float(np.square(speed_error[fixed_congested]).sum()) / total_loss
            cutoff_capture = float(np.square(speed_error[cutoff_congested]).sum()) / total_loss
            comparison_rows.append(
                {
                    "panel": panel,
                    "split": split,
                    "n": len(speed),
                    "fixed_support": fixed_support,
                    "cutoff_support": cutoff_support,
                    "fixed_speed_loss_capture": fixed_capture,
                    "cutoff_speed_loss_capture": cutoff_capture,
                    "fixed_concentration_lift": fixed_capture / max(fixed_support, 1e-12),
                    "cutoff_concentration_lift": cutoff_capture / max(cutoff_support, 1e-12),
                    "fixed_top1pct_tail_share": float(fixed_congested[tail].mean()),
                    "cutoff_top1pct_tail_share": float(cutoff_congested[tail].mean()),
                    "crossing_target_cells": int((crossing_down | crossing_up).sum()),
                }
            )

    strata = pd.DataFrame(rows)
    comparisons = pd.DataFrame(comparison_rows)
    daily = pd.DataFrame(daily_rows)
    output_root.mkdir(parents=True, exist_ok=True)
    strata_path = output_root / "task1_cutoff_strata.csv"
    comparisons_path = output_root / "task1_cutoff_comparison.csv"
    daily_path = output_root / "task1_cutoff_daily_coverage.csv"
    strata.to_csv(strata_path, index=False)
    comparisons.to_csv(comparisons_path, index=False)
    daily.to_csv(daily_path, index=False)

    all_cutoffs_usable = all(
        value["n_links"] > 0 and value["n_unique"] > 1 and value["range"] > 1.0
        for value in cutoff_ranges.values()
    )
    minimum_coverage = float(daily.coverage_fraction.min())
    lift_delta = comparisons.cutoff_concentration_lift - comparisons.fixed_concentration_lift
    tail_delta = comparisons.cutoff_top1pct_tail_share - comparisons.fixed_top1pct_tail_share
    passed = (
        all_cutoffs_usable
        and minimum_coverage >= 0.95
        and bool((lift_delta > 0).all())
        and bool((tail_delta >= 0).all())
    )
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    receipt = {
        "status": "COMPLETE_READ_ONLY",
        "question": "Does a link-specific scoring-contract cutoff produce a more stable and concentrated congestion-transition residual stratum than fixed 60/90 km/h buckets?",
        "data_boundary": {
            "source": "released train truth only; validation/private truth is withheld and was not inferred",
            "development_dates": [development_start, development_end],
            "confirmation_dates": [confirmation_start, confirmation_end],
            "prior_rule": "exactly seven days earlier",
            "panels": [record["corridor_id"] for record in panel_records],
        },
        "cutoff_rule": "v_cut = 0.60 * released free_speed_kmh, exactly as published in the competition scoring specification; no cutoff is fit from target truth",
        "missingness_rule": "drop only link-day periods whose released eligible share is <= 0.50",
        "cutoff_ranges": cutoff_ranges,
        "minimum_target_coverage_after_filter": minimum_coverage,
        "minimum_cutoff_minus_fixed_concentration_lift": float(lift_delta.min()),
        "minimum_cutoff_minus_fixed_top1pct_tail_share": float(tail_delta.min()),
        "metric_boundary": {"official_S_state": "diagnostic residuals on released train masks", "organizer_S_physics": None},
        "decision_rule": "Allow one event-gated persistence-vs-temporal A/B only if cutoffs are non-degenerate, >=95% target coverage remains, and cutoff-relative concentration lift and top-1%-tail share never reverse across either split or any panel.",
        "decision": "ALLOW_EVENT_GATED_AB" if passed else "STOP_CUTOFF_GATED_FAMILY",
        "external_method_context": [
            "https://github.com/asu-trans-ai-lab/CBI",
            "https://github.com/asu-trans-ai-lab/data2SupplyModel",
        ],
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": peak_mb,
        "artifact_sha256": {
            "strata": _sha256(strata_path),
            "comparisons": _sha256(comparisons_path),
            "daily_coverage": _sha256(daily_path),
        },
    }
    receipt_path = output_root / "task1_cutoff_residual_audit_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--development-start", default="2031-02-01")
    parser.add_argument("--development-end", default="2031-02-14")
    parser.add_argument("--confirmation-start", default="2031-02-15")
    parser.add_argument("--confirmation-end", default="2031-02-28")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.release_root.resolve(),
                args.output_root.resolve(),
                args.development_start,
                args.development_end,
                args.confirmation_start,
                args.confirmation_end,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
