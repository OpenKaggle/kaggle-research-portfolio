#!/usr/bin/env python3
"""Deployable all-panel cross-validation of the current V32 State recipe.

Profiles are frozen strictly before each holdout block.  Predictions may use
the released masked values from their own day, but target truth is not read
until the prediction has been fixed.  This mirrors the information boundary of
the competition validation/private splits.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from task1_grouped_baseline import (
    EMPTY_FLOOR_VPH,
    REGIMES,
    _fd_score,
    _fd_sums,
    _matrix,
    _peak_memory_mb,
    _read_state,
    _sha256,
    _state_score,
)


def _profile_arrays(links: list[str]) -> dict[str, np.ndarray]:
    shape = (7, 288, len(links))
    return {
        "speed_sum": np.zeros(shape, dtype=np.float64),
        "speed_count": np.zeros(shape, dtype=np.int32),
        "flow_sum": np.zeros(shape, dtype=np.float64),
        "flow_count": np.zeros(shape, dtype=np.int32),
    }


def _accumulate_profile(path: Path, link_index: dict[str, int], arrays: dict[str, np.ndarray]) -> None:
    frame = pd.read_parquet(
        path,
        columns=["timestamp", "link_id", "speed_kmh", "flow_vph", "pct_observed"],
    )
    frame["link_id"] = frame.link_id.astype(str)
    timestamp = pd.to_datetime(frame.timestamp, utc=True)
    weekday = timestamp.dt.weekday.to_numpy(dtype=np.int16)
    slot = (timestamp.dt.hour * 12 + timestamp.dt.minute // 5).to_numpy(dtype=np.int16)
    link = frame.link_id.map(link_index).to_numpy(dtype=np.int32)
    speed = pd.to_numeric(frame.speed_kmh, errors="coerce").to_numpy(dtype=float)
    flow = pd.to_numeric(frame.flow_vph, errors="coerce").to_numpy(dtype=float)
    # V32 treats speed/flow as one state observation: either both channels
    # enter the historical profile or neither does.  Keeping this coupled is
    # necessary for exact reproduction at the rare partially missing cell.
    quality = (
        pd.to_numeric(frame.pct_observed, errors="coerce").ge(75).to_numpy()
        & np.isfinite(speed)
        & np.isfinite(flow)
    )
    for prefix, values in (("speed", speed), ("flow", flow)):
        valid = quality
        np.add.at(arrays[f"{prefix}_sum"], (weekday[valid], slot[valid], link[valid]), values[valid])
        np.add.at(arrays[f"{prefix}_count"], (weekday[valid], slot[valid], link[valid]), 1)


def _snapshot(arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for prefix in ("speed", "flow"):
        sums = arrays[f"{prefix}_sum"]
        counts = arrays[f"{prefix}_count"]
        mean = np.zeros_like(sums)
        np.divide(sums, np.maximum(counts, 1), out=mean, where=counts > 0)
        link_sum = sums.sum(axis=(0, 1))
        link_count = counts.sum(axis=(0, 1))
        fallback = np.divide(link_sum, np.maximum(link_count, 1))
        result[f"{prefix}_mean"] = mean.copy()
        result[f"{prefix}_count"] = counts.copy()
        result[f"{prefix}_fallback"] = fallback
    return result


def build_frozen_profiles(
    panel_root: Path, cutoffs: list[str]
) -> tuple[list[str], dict[str, dict[str, np.ndarray]], dict[str, int]]:
    paths = sorted((panel_root / "train" / "mainline_states").glob("**/*.parquet"))
    if not paths:
        raise FileNotFoundError(f"{panel_root}: no unmasked train files")
    first = pd.read_parquet(paths[0], columns=["link_id"])
    links = sorted(first.link_id.astype(str).unique())
    link_index = {link: i for i, link in enumerate(links)}
    arrays = _profile_arrays(links)
    profiles: dict[str, dict[str, np.ndarray]] = {}
    counts: dict[str, int] = {}
    cursor = 0
    for cutoff in sorted(cutoffs):
        while cursor < len(paths) and paths[cursor].stem.removeprefix("synthetic_mainline_") < cutoff:
            _accumulate_profile(paths[cursor], link_index, arrays)
            cursor += 1
        if cursor == 0:
            raise ValueError(f"{panel_root.name}: no profile days before {cutoff}")
        profiles[cutoff] = _snapshot(arrays)
        counts[cutoff] = cursor
    return links, profiles, counts


def _nearest_within(observed: np.ndarray, limit: int = 12) -> np.ndarray:
    """Nearest visible value along time, with earlier values winning exact ties."""
    rows = np.arange(observed.shape[0], dtype=int)[:, None]
    previous = np.maximum.accumulate(np.where(np.isfinite(observed), rows, -1), axis=0)
    following = np.minimum.accumulate(
        np.where(np.isfinite(observed), rows, observed.shape[0])[::-1], axis=0
    )[::-1]
    previous_distance = np.where(previous >= 0, rows - previous, observed.shape[0] + 1)
    following_distance = np.where(
        following < observed.shape[0], following - rows, observed.shape[0] + 1
    )
    choose_previous = previous_distance <= following_distance
    chosen = np.where(choose_previous, previous, following)
    distance = np.minimum(previous_distance, following_distance)
    valid = (chosen >= 0) & (chosen < observed.shape[0]) & (distance <= limit)
    result = np.full_like(observed, np.nan, dtype=float)
    columns = np.broadcast_to(np.arange(observed.shape[1]), observed.shape)
    result[valid] = observed[chosen[valid], columns[valid]]
    return result


def v32_prediction(
    masked: pd.DataFrame,
    links: list[str],
    profile: dict[str, np.ndarray],
    parameters: pd.DataFrame,
    linear_weight: float = 1.0,
) -> dict[str, np.ndarray]:
    """Reproduce the V32 State transformation with a supplied frozen profile."""
    if not 0.0 <= linear_weight <= 1.0:
        raise ValueError("linear_weight must be in [0, 1]")
    timestamp = pd.to_datetime(masked.timestamp, utc=True)
    weekdays = timestamp.dt.weekday.unique()
    if len(weekdays) != 1:
        raise ValueError("a daily masked frame must contain one weekday")
    weekday = int(weekdays[0])
    p = parameters.set_index("link_id").reindex(links)
    lanes = p.lanes.fillna(1.0).clip(lower=1.0).to_numpy(dtype=float)[None, :]
    free_speed = p.free_speed_kmh.fillna(120.0).to_numpy(dtype=float)[None, :]
    capacity = p.capacity_vph.fillna(15000.0).to_numpy(dtype=float)[None, :]

    historical: dict[str, np.ndarray] = {}
    for prefix in ("speed", "flow"):
        mean = profile[f"{prefix}_mean"][weekday]
        count = profile[f"{prefix}_count"][weekday]
        fallback = profile[f"{prefix}_fallback"]
        historical[prefix] = np.where(count > 0, mean, fallback[None, :])

    observed_speed = _matrix(masked, "speed_kmh", links)
    observed_flow_per_lane = _matrix(masked, "flow_vph", links) / lanes
    historical_flow_per_lane = historical["flow"] / lanes
    linear_speed = (
        pd.DataFrame(observed_speed)
        .interpolate(axis=0, method="linear", limit=12, limit_direction="both")
        .to_numpy(dtype=float)
    )
    linear_flow = (
        pd.DataFrame(observed_flow_per_lane)
        .interpolate(axis=0, method="linear", limit=12, limit_direction="both")
        .to_numpy(dtype=float)
    )
    nearest_speed = _nearest_within(observed_speed)
    nearest_flow = _nearest_within(observed_flow_per_lane)

    def blend(linear: np.ndarray, nearest: np.ndarray) -> np.ndarray:
        both = np.isfinite(linear) & np.isfinite(nearest)
        return np.where(
            both,
            linear_weight * linear + (1.0 - linear_weight) * nearest,
            np.where(np.isfinite(linear), linear, nearest),
        )

    temporal_speed = blend(linear_speed, nearest_speed)
    temporal_flow = blend(linear_flow, nearest_flow)
    spatial_speed = (
        pd.DataFrame(temporal_speed)
        .interpolate(axis=1, method="linear", limit=4, limit_direction="both")
        .to_numpy(dtype=float)
    )
    spatial_flow = (
        pd.DataFrame(temporal_flow)
        .interpolate(axis=1, method="linear", limit=4, limit_direction="both")
        .to_numpy(dtype=float)
    )
    pred_speed = np.where(
        np.isfinite(temporal_speed),
        0.85 * temporal_speed
        + 0.15 * np.where(np.isfinite(spatial_speed), spatial_speed, temporal_speed),
        np.where(
            np.isfinite(spatial_speed),
            0.85 * spatial_speed + 0.15 * historical["speed"],
            historical["speed"],
        ),
    )
    pred_flow_per_lane = np.where(
        np.isfinite(temporal_flow),
        0.85 * temporal_flow
        + 0.15 * np.where(np.isfinite(spatial_flow), spatial_flow, temporal_flow),
        np.where(
            np.isfinite(spatial_flow),
            0.85 * spatial_flow + 0.15 * historical_flow_per_lane,
            historical_flow_per_lane,
        ),
    )
    pred_speed = np.clip(pred_speed, 5.0, free_speed * 1.05)
    raw_flow = np.maximum(pred_flow_per_lane * lanes, EMPTY_FLOOR_VPH)
    density = raw_flow / np.maximum(pred_speed, 1.0)
    smooth_density = (
        pd.DataFrame(density)
        .rolling(3, center=True, min_periods=1)
        .mean()
        .to_numpy(dtype=float)
    )
    pred_flow = np.clip(0.85 * raw_flow + 0.15 * smooth_density * pred_speed, EMPTY_FLOOR_VPH, capacity * 1.15)
    return {"speed_kmh": pred_speed, "flow_vph": pred_flow}


def _add(bucket: dict[str, float], values: dict[str, float]) -> None:
    for key, value in values.items():
        bucket[key] += value


def run(
    release: Path,
    development_start: str,
    development_end: str,
    confirmation_start: str,
    confirmation_end: str,
    output_root: Path,
) -> dict[str, object]:
    started = time.perf_counter()
    manifest_path = release / "config" / "corridors.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panels = [str(item["corridor_id"]) for item in manifest["panels"]]
    families = {str(item["corridor_id"]): str(item["family_id"]) for item in manifest["panels"]}
    split_ranges = {
        "development": (development_start, development_end, development_start),
        "confirmation": (confirmation_start, confirmation_end, confirmation_start),
    }
    state_sums = defaultdict(lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0.0})
    fd_sums = defaultdict(lambda: {"num": 0.0, "den": 0.0, "below": 0.0, "target_n": 0.0, "rows": 0.0})
    day_rows: list[dict[str, object]] = []
    profile_days: dict[str, dict[str, int]] = {}
    total_target = 0
    total_missing = 0

    for panel in panels:
        print(f"[deployable V32 State control] {panel}: profiles", flush=True)
        panel_root = release / "corridors" / panel
        links, profiles, counts = build_frozen_profiles(
            panel_root, [development_start, confirmation_start]
        )
        profile_days[panel] = counts
        parameters = pd.read_csv(panel_root / "network" / "fd_parameters.csv", dtype={"link_id": str})
        parameters["link_id"] = parameters.link_id.astype(str)
        masked_paths = sorted((panel_root / "train" / "mainline_states_masked").glob("**/*.parquet"))
        unmasked_paths = {
            path.stem.removeprefix("synthetic_mainline_"): path
            for path in (panel_root / "train" / "mainline_states").glob("**/*.parquet")
        }
        for path in masked_paths:
            day = path.stem.removeprefix("synthetic_mainline_")
            matches = [
                (split, cutoff)
                for split, (start, end, cutoff) in split_ranges.items()
                if start <= day <= end
            ]
            if not matches:
                continue
            split, cutoff = matches[0]
            masked = _read_state(path, masked=True)
            prediction = v32_prediction(masked, links, profiles[cutoff], parameters)

            # Prediction and its frozen profile are fixed before target truth is opened.
            truth_path = unmasked_paths.get(day)
            if truth_path is None:
                raise FileNotFoundError(f"{panel} {day}: missing evaluator truth")
            truth = _read_state(truth_path)
            regime_values = masked.mask_regime.dropna().astype(str).unique()
            if len(regime_values) != 1 or regime_values[0] not in REGIMES:
                raise ValueError(f"{path}: expected one known regime")
            regime = str(regime_values[0])
            true_speed = _matrix(truth, "speed_kmh", links)
            true_flow = _matrix(truth, "flow_vph", links)
            observed_speed = _matrix(masked, "speed_kmh", links)
            observed_flow = _matrix(masked, "flow_vph", links)
            eligible = _matrix(
                truth.assign(is_score_eligible=truth.is_score_eligible.astype(bool)),
                "is_score_eligible",
                links,
            ).astype(bool)
            target = eligible & ~np.isfinite(observed_speed) & ~np.isfinite(observed_flow)
            usable = target & np.isfinite(true_speed) & np.isfinite(true_flow)
            missing = target & (
                ~np.isfinite(prediction["speed_kmh"]) | ~np.isfinite(prediction["flow_vph"])
            )
            lanes = (
                parameters.set_index("link_id").lanes.reindex(links).fillna(1.0)
                .clip(lower=1.0).to_numpy(dtype=float)[None, :]
            )
            state = {
                "speed_sq": float(np.square((prediction["speed_kmh"] - true_speed)[usable]).sum()),
                "flow_sq": float(np.square(((prediction["flow_vph"] - true_flow) / lanes)[usable]).sum()),
                "n": float(usable.sum()),
            }
            _add(state_sums[(split, panel, regime)], state)
            reconstructed_speed = np.where(target, prediction["speed_kmh"], true_speed)
            reconstructed_flow = np.where(target, prediction["flow_vph"], true_flow)
            fd_num, fd_den, fd_rows = _fd_sums(
                reconstructed_speed, reconstructed_flow, eligible, links, parameters
            )
            below = int((prediction["flow_vph"][target] < EMPTY_FLOOR_VPH).sum())
            fd = {
                "num": fd_num,
                "den": fd_den,
                "below": float(below),
                "target_n": float(target.sum()),
                "rows": float(fd_rows),
            }
            _add(fd_sums[(split, panel, regime)], fd)
            total_target += int(target.sum())
            total_missing += int(missing.sum())
            day_rows.append(
                {
                    "split": split,
                    "day": day,
                    "panel": panel,
                    "family_id": families[panel],
                    "regime": regime,
                    **_state_score(**state),
                    "S_FD_public": _fd_score(fd_num, fd_den, below, int(target.sum())),
                    "n_missing_predictions": int(missing.sum()),
                }
            )

    panel_regime_rows: list[dict[str, object]] = []
    for split in split_ranges:
        for panel in panels:
            for regime in REGIMES:
                state = state_sums[(split, panel, regime)]
                fd = fd_sums[(split, panel, regime)]
                panel_regime_rows.append(
                    {
                        "split": split,
                        "level": "panel_regime",
                        "panel": panel,
                        "family_id": families[panel],
                        "regime": regime,
                        **_state_score(**state),
                        "S_FD_public": _fd_score(
                            fd["num"], fd["den"], int(fd["below"]), int(fd["target_n"])
                        ),
                        "fd_rows": int(fd["rows"]),
                    }
                )
    panel_regime = pd.DataFrame(panel_regime_rows)
    aggregate_rows: list[dict[str, object]] = []
    for split in split_ranges:
        detail = panel_regime[panel_regime.split == split]
        for panel, group in detail.groupby("panel", sort=True):
            aggregate_rows.append(
                {
                    "split": split, "level": "panel", "panel": panel,
                    "family_id": families[panel], "regime": "macro_mean",
                    "n_target_cells": int(group.n_target_cells.sum()),
                    "S_state": float(group.S_state.mean()),
                    "S_FD_public": float(group.S_FD_public.mean()),
                }
            )
        panel_frame = pd.DataFrame(
            [row for row in aggregate_rows if row["split"] == split and row["level"] == "panel"]
        )
        for family, group in panel_frame.groupby("family_id", sort=True):
            aggregate_rows.append(
                {
                    "split": split, "level": "family", "panel": None,
                    "family_id": family, "regime": "macro_mean",
                    "n_target_cells": int(group.n_target_cells.sum()),
                    "S_state": float(group.S_state.mean()),
                    "S_FD_public": float(group.S_FD_public.mean()),
                }
            )
        family_frame = pd.DataFrame(
            [row for row in aggregate_rows if row["split"] == split and row["level"] == "family"]
        )
        aggregate_rows.append(
            {
                "split": split, "level": "overall", "panel": None,
                "family_id": "ALL", "regime": "macro_mean",
                "n_target_cells": int(family_frame.n_target_cells.sum()),
                "S_state": float(family_frame.S_state.mean()),
                "S_FD_public": float(panel_frame.S_FD_public.mean()),
            }
        )
    aggregates = pd.DataFrame(aggregate_rows)

    output_root.mkdir(parents=True, exist_ok=True)
    day_path = output_root / "task1_v32_control_day_metrics.csv"
    detail_path = output_root / "task1_v32_control_panel_regime_metrics.csv"
    aggregate_path = output_root / "task1_v32_control_aggregate_metrics.csv"
    pd.DataFrame(day_rows).sort_values(["split", "panel", "day"]).to_csv(day_path, index=False)
    panel_regime.to_csv(detail_path, index=False)
    aggregates.to_csv(aggregate_path, index=False)
    overall = aggregates[aggregates.level == "overall"].set_index("split")
    receipt: dict[str, object] = {
        "status": "COMPLETE" if total_missing == 0 else "FAILED_COVERAGE",
        "experiment": "task1_grouped_v32_frozen_profile_control_v1",
        "question": "What is the current submitted State recipe's honest all-panel score when every monthly holdout uses a pre-block frozen profile?",
        "information_boundary": {
            "development": f"{development_start}..{development_end}; profile uses dates < {development_start}",
            "confirmation": f"{confirmation_start}..{confirmation_end}; profile uses dates < {confirmation_start}",
            "profile_days_by_panel_and_cutoff": profile_days,
            "same_day_inputs": "released masked values only",
            "target_truth": "opened only after the day's prediction and profile are fixed",
        },
        "method": "V32 State recipe: weekday/time mean profile, temporal limit-12 fill, lexical-link spatial limit-4 fallback, 0.85/0.15 fallback blend, and 0.85/0.15 three-slot density smoothing.",
        "official_task1": {
            "development_S_state": float(overall.loc["development", "S_state"]),
            "confirmation_S_state": float(overall.loc["confirmation", "S_state"]),
            "aggregation": "regime -> direction panel -> corridor family -> overall, equal weights",
        },
        "public_task3_diagnostic": {
            "development_S_FD": float(overall.loc["development", "S_FD_public"]),
            "confirmation_S_FD": float(overall.loc["confirmation", "S_FD_public"]),
            "not_a_leaderboard_physics_score": True,
        },
        "organizer_only_metrics": {"S_LWR": None, "S_physics": None},
        "coverage": {"target_cells": total_target, "missing_predictions": total_missing},
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(manifest_path)},
        "outputs": {
            day_path.name: _sha256(day_path),
            detail_path.name: _sha256(detail_path),
            aggregate_path.name: _sha256(aggregate_path),
        },
        "decision": "ESTABLISH_DEPLOYABLE_CONTROL" if total_missing == 0 else "STOP_COVERAGE_FAILURE",
    }
    receipt_path = output_root / "task1_grouped_v32_control_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--development-start", default="2031_01_01")
    parser.add_argument("--development-end", default="2031_01_31")
    parser.add_argument("--confirmation-start", default="2031_02_01")
    parser.add_argument("--confirmation-end", default="2031_02_28")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.release_root.resolve(),
        args.development_start,
        args.development_end,
        args.confirmation_start,
        args.confirmation_end,
        args.output_root.resolve(),
    )


if __name__ == "__main__":
    main()
