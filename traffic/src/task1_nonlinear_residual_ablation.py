#!/usr/bin/env python3
"""Mask-matched nonlinear residual correction over the frozen V32 State control."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

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
from task1_grouped_v32_control import build_frozen_profiles, v32_prediction


CORRECTION_STRENGTHS = (0.0, 0.25, 0.50, 0.75, 1.0)
TRAINING_DAYS = 56
MAX_EXAMPLES_PER_DAY = 3000
REGIME_RATE = {"R1": 0.20, "R2": 0.30, "R3": 0.50}
FEATURE_NAMES = (
    "time_sin", "time_cos", "mask_rate", "left_distance", "right_distance",
    "gap_fraction", "speed_left_norm", "speed_right_norm", "speed_left_slope_norm",
    "speed_right_slope_norm", "flow_left_norm", "flow_right_norm",
    "flow_left_slope_norm", "flow_right_slope_norm", "density_left_norm",
    "density_right_norm", "baseline_speed_norm", "baseline_flow_norm",
    "free_speed_norm", "capacity_per_lane_norm",
)


def _date_add(day: str, days: int) -> str:
    return (pd.Timestamp(day.replace("_", "-")) + pd.Timedelta(days=days)).strftime("%Y_%m_%d")


def _endpoint_features(
    observed: np.ndarray, target: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows, columns = np.nonzero(target)
    n = len(rows)
    left_value = np.full(n, np.nan)
    right_value = np.full(n, np.nan)
    left_distance = np.full(n, np.nan)
    right_distance = np.full(n, np.nan)
    left_slope = np.full(n, np.nan)
    right_slope = np.full(n, np.nan)
    for column in np.unique(columns):
        positions = np.flatnonzero(columns == column)
        target_rows = rows[positions]
        visible = np.flatnonzero(np.isfinite(observed[:, column]))
        insertion = np.searchsorted(visible, target_rows)
        have_left = insertion > 0
        have_right = insertion < len(visible)
        if have_left.any():
            left = visible[insertion[have_left] - 1]
            at = positions[have_left]
            left_value[at] = observed[left, column]
            left_distance[at] = target_rows[have_left] - left
            have_second = insertion[have_left] > 1
            if have_second.any():
                left2 = visible[insertion[have_left][have_second] - 2]
                left1 = left[have_second]
                left_slope[at[have_second]] = (
                    observed[left1, column] - observed[left2, column]
                ) / np.maximum(left1 - left2, 1)
        if have_right.any():
            right = visible[insertion[have_right]]
            at = positions[have_right]
            right_value[at] = observed[right, column]
            right_distance[at] = right - target_rows[have_right]
            have_second = insertion[have_right] + 1 < len(visible)
            if have_second.any():
                right1 = right[have_second]
                right2 = visible[insertion[have_right][have_second] + 1]
                right_slope[at[have_second]] = (
                    observed[right2, column] - observed[right1, column]
                ) / np.maximum(right2 - right1, 1)
    return left_value, right_value, left_distance, right_distance, left_slope, right_slope


def feature_matrix(
    masked: pd.DataFrame,
    links: list[str],
    parameters: pd.DataFrame,
    baseline: dict[str, np.ndarray],
    target: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows, columns = np.nonzero(target)
    speed = _matrix(masked, "speed_kmh", links)
    flow = _matrix(masked, "flow_vph", links)
    sl, sr, ld, rd, sls, srs = _endpoint_features(speed, target)
    fl, fr, fld, frd, fls, frs = _endpoint_features(flow, target)
    p = parameters.set_index("link_id").reindex(links)
    free = p.free_speed_kmh.fillna(105.0).to_numpy(dtype=float)[columns]
    cap = p.capacity_vph.fillna(7200.0).to_numpy(dtype=float)[columns]
    lanes = p.lanes.fillna(1.0).clip(lower=1.0).to_numpy(dtype=float)[columns]
    left_distance = np.where(np.isfinite(ld), ld, fld)
    right_distance = np.where(np.isfinite(rd), rd, frd)
    distance_sum = left_distance + right_distance
    fraction = left_distance / np.where(distance_sum > 0, distance_sum, np.nan)
    critical_density = cap / np.maximum(free, 1.0)
    density_left = fl / np.maximum(sl, 1.0)
    density_right = fr / np.maximum(sr, 1.0)
    angle = 2.0 * np.pi * rows / 288.0
    regime = str(masked.mask_regime.iloc[0])
    x = np.column_stack(
        [
            np.sin(angle), np.cos(angle), np.full(len(rows), REGIME_RATE[regime]),
            left_distance, right_distance, fraction,
            sl / free, sr / free, sls / free, srs / free,
            fl / cap, fr / cap, fls / cap, frs / cap,
            density_left / critical_density, density_right / critical_density,
            baseline["speed_kmh"][rows, columns] / free,
            baseline["flow_vph"][rows, columns] / cap,
            free / 120.0, (cap / lanes) / 2000.0,
        ]
    )
    transition = (
        (np.abs(sr - sl) / np.maximum(free, 1.0) >= 0.10)
        | (np.abs(sls) / np.maximum(free, 1.0) >= 0.03)
        | (np.abs(srs) / np.maximum(free, 1.0) >= 0.03)
    )
    return x, rows, columns, transition


def _new_model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.05,
        max_iter=80,
        max_leaf_nodes=15,
        min_samples_leaf=100,
        l2_regularization=5.0,
        random_state=42,
    )


def _training_examples(
    panel: str,
    panel_root: Path,
    links: list[str],
    parameters: pd.DataFrame,
    profile: dict[str, np.ndarray],
    start: str,
    end: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    masked_paths = {
        path.stem.removeprefix("synthetic_mainline_"): path
        for path in (panel_root / "train" / "mainline_states_masked").glob("**/*.parquet")
    }
    truth_paths = {
        path.stem.removeprefix("synthetic_mainline_"): path
        for path in (panel_root / "train" / "mainline_states").glob("**/*.parquet")
    }
    p = parameters.set_index("link_id").reindex(links)
    lanes_by_column = p.lanes.fillna(1.0).clip(lower=1.0).to_numpy(dtype=float)
    x_parts, speed_parts, flow_parts = [], [], []
    for day in sorted(day for day in masked_paths if start <= day <= end):
        masked = _read_state(masked_paths[day], masked=True)
        baseline = v32_prediction(masked, links, profile, parameters)
        truth = _read_state(truth_paths[day])
        observed_speed = _matrix(masked, "speed_kmh", links)
        observed_flow = _matrix(masked, "flow_vph", links)
        eligible = _matrix(
            truth.assign(is_score_eligible=truth.is_score_eligible.astype(bool)),
            "is_score_eligible", links,
        ).astype(bool)
        true_speed = _matrix(truth, "speed_kmh", links)
        true_flow = _matrix(truth, "flow_vph", links)
        target = (
            eligible & ~np.isfinite(observed_speed) & ~np.isfinite(observed_flow)
            & np.isfinite(true_speed) & np.isfinite(true_flow)
        )
        x, rows, columns, _ = feature_matrix(masked, links, parameters, baseline, target)
        speed_residual = true_speed[rows, columns] - baseline["speed_kmh"][rows, columns]
        flow_residual = (
            true_flow[rows, columns] - baseline["flow_vph"][rows, columns]
        ) / lanes_by_column[columns]
        if len(x) > MAX_EXAMPLES_PER_DAY:
            seed = int.from_bytes(
                hashlib.blake2b(f"{panel}|{day}".encode(), digest_size=8).digest(), "big"
            )
            chosen = np.random.default_rng(seed).choice(
                len(x), size=MAX_EXAMPLES_PER_DAY, replace=False
            )
            x, speed_residual, flow_residual = (
                x[chosen], speed_residual[chosen], flow_residual[chosen]
            )
        x_parts.append(x)
        speed_parts.append(speed_residual)
        flow_parts.append(flow_residual)
    if not x_parts:
        raise ValueError(f"{panel}: no training examples in {start}..{end}")
    return np.concatenate(x_parts), np.concatenate(speed_parts), np.concatenate(flow_parts)


def _add(bucket: dict[str, float], values: dict[str, float]) -> None:
    for key, value in values.items():
        bucket[key] += value


def run(
    release: Path,
    panel: str,
    development_start: str,
    development_end: str,
    confirmation_start: str,
    confirmation_end: str,
    output_root: Path,
) -> dict[str, object]:
    started = time.perf_counter()
    panel_root = release / "corridors" / panel
    development_training_start = _date_add(development_start, -TRAINING_DAYS)
    development_training_end = _date_add(development_start, -1)
    confirmation_training_start = _date_add(confirmation_start, -TRAINING_DAYS)
    confirmation_training_end = _date_add(confirmation_start, -1)
    profile_cutoffs = [
        development_training_start, development_start,
        confirmation_training_start, confirmation_start,
    ]
    links, profiles, profile_days = build_frozen_profiles(panel_root, profile_cutoffs)
    parameters = pd.read_csv(panel_root / "network" / "fd_parameters.csv", dtype={"link_id": str})
    parameters["link_id"] = parameters.link_id.astype(str)
    lanes_by_column = (
        parameters.set_index("link_id").lanes.reindex(links).fillna(1.0)
        .clip(lower=1.0).to_numpy(dtype=float)
    )
    models = {}
    training_summary = {}
    for split, train_start, train_end in (
        ("development", development_training_start, development_training_end),
        ("confirmation", confirmation_training_start, confirmation_training_end),
    ):
        x, speed_y, flow_y = _training_examples(
            panel, panel_root, links, parameters, profiles[train_start], train_start, train_end
        )
        speed_model, flow_model = _new_model(), _new_model()
        speed_model.fit(x, speed_y)
        flow_model.fit(x, flow_y)
        models[split] = (speed_model, flow_model)
        training_summary[split] = {
            "start": train_start, "end": train_end, "examples": int(len(x)),
            "speed_residual_mean": float(np.mean(speed_y)),
            "flow_per_lane_residual_mean": float(np.mean(flow_y)),
        }

    masked_paths = {
        path.stem.removeprefix("synthetic_mainline_"): path
        for path in (panel_root / "train" / "mainline_states_masked").glob("**/*.parquet")
    }
    truth_paths = {
        path.stem.removeprefix("synthetic_mainline_"): path
        for path in (panel_root / "train" / "mainline_states").glob("**/*.parquet")
    }
    split_ranges = {
        "development": (development_start, development_end, development_start),
        "confirmation": (confirmation_start, confirmation_end, confirmation_start),
    }
    state_sums = defaultdict(lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0.0})
    transition_sums = defaultdict(lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0.0})
    fd_sums = defaultdict(lambda: {"num": 0.0, "den": 0.0, "below": 0.0, "target_n": 0.0})
    day_rows: list[dict[str, object]] = []
    total_target = 0
    missing_predictions = 0
    for day, path in sorted(masked_paths.items()):
        matches = [
            (split, cutoff)
            for split, (start, end, cutoff) in split_ranges.items()
            if start <= day <= end
        ]
        if not matches:
            continue
        split, cutoff = matches[0]
        masked = _read_state(path, masked=True)
        baseline = v32_prediction(masked, links, profiles[cutoff], parameters)
        # The correction is fixed entirely from prior-block models and released inputs.
        observed_speed = _matrix(masked, "speed_kmh", links)
        observed_flow = _matrix(masked, "flow_vph", links)
        released_eligible = _matrix(
            masked.assign(is_score_eligible=masked.is_score_eligible.astype(bool)),
            "is_score_eligible", links,
        ).astype(bool)
        released_target = (
            released_eligible & ~np.isfinite(observed_speed) & ~np.isfinite(observed_flow)
        )
        x, rows, columns, transition_vector = feature_matrix(
            masked, links, parameters, baseline, released_target
        )
        speed_correction = models[split][0].predict(x)
        flow_correction_per_lane = models[split][1].predict(x)
        predictions = {}
        p = parameters.set_index("link_id").reindex(links)
        speed_upper = p.free_speed_kmh.fillna(120.0).to_numpy(dtype=float) * 1.05
        flow_upper = p.capacity_vph.fillna(15000.0).to_numpy(dtype=float) * 1.15
        for strength in CORRECTION_STRENGTHS:
            speed = baseline["speed_kmh"].copy()
            flow = baseline["flow_vph"].copy()
            speed[rows, columns] += strength * speed_correction
            flow[rows, columns] += (
                strength * flow_correction_per_lane * lanes_by_column[columns]
            )
            speed = np.clip(speed, 5.0, speed_upper[None, :])
            flow = np.clip(flow, EMPTY_FLOOR_VPH, flow_upper[None, :])
            predictions[strength] = {"speed_kmh": speed, "flow_vph": flow}

        # Only evaluator code below opens target-day truth.
        truth = _read_state(truth_paths[day])
        true_speed = _matrix(truth, "speed_kmh", links)
        true_flow = _matrix(truth, "flow_vph", links)
        eligible = _matrix(
            truth.assign(is_score_eligible=truth.is_score_eligible.astype(bool)),
            "is_score_eligible", links,
        ).astype(bool)
        target = eligible & ~np.isfinite(observed_speed) & ~np.isfinite(observed_flow)
        if not np.array_equal(target, released_target):
            raise AssertionError("released and evaluator target masks differ")
        usable = target & np.isfinite(true_speed) & np.isfinite(true_flow)
        transition = np.zeros_like(target)
        transition[rows, columns] = transition_vector
        transition &= usable
        regime = str(masked.mask_regime.iloc[0])
        total_target += int(target.sum())
        for strength, prediction in predictions.items():
            missing_predictions += int(
                (target & (~np.isfinite(prediction["speed_kmh"]) | ~np.isfinite(prediction["flow_vph"]))).sum()
            )
            speed_error = prediction["speed_kmh"] - true_speed
            flow_error = (prediction["flow_vph"] - true_flow) / lanes_by_column[None, :]
            state = {
                "speed_sq": float(np.square(speed_error[usable]).sum()),
                "flow_sq": float(np.square(flow_error[usable]).sum()),
                "n": float(usable.sum()),
            }
            transition_state = {
                "speed_sq": float(np.square(speed_error[transition]).sum()),
                "flow_sq": float(np.square(flow_error[transition]).sum()),
                "n": float(transition.sum()),
            }
            _add(state_sums[(split, strength, regime)], state)
            _add(transition_sums[(split, strength, regime)], transition_state)
            reconstructed_speed = np.where(target, prediction["speed_kmh"], true_speed)
            reconstructed_flow = np.where(target, prediction["flow_vph"], true_flow)
            num, den, _ = _fd_sums(
                reconstructed_speed, reconstructed_flow, eligible, links, parameters
            )
            below = int((prediction["flow_vph"][target] < EMPTY_FLOOR_VPH).sum())
            _add(
                fd_sums[(split, strength, regime)],
                {"num": num, "den": den, "below": float(below), "target_n": float(target.sum())},
            )
            day_rows.append(
                {
                    "split": split, "day": day, "panel": panel, "regime": regime,
                    "correction_strength": strength, **_state_score(**state),
                    "transition_S_state": _state_score(**transition_state)["S_state"],
                    "n_transition_cells": int(transition_state["n"]),
                    "S_FD_public": _fd_score(num, den, below, int(target.sum())),
                }
            )

    aggregate_rows = []
    for split in split_ranges:
        for strength in CORRECTION_STRENGTHS:
            regime_scores, transition_scores, fd_scores = [], [], []
            total = {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0.0}
            for regime in REGIMES:
                state = state_sums[(split, strength, regime)]
                transition_state = transition_sums[(split, strength, regime)]
                regime_scores.append(_state_score(**state)["S_state"])
                transition_scores.append(_state_score(**transition_state)["S_state"])
                _add(total, state)
                fd = fd_sums[(split, strength, regime)]
                fd_scores.append(
                    _fd_score(fd["num"], fd["den"], int(fd["below"]), int(fd["target_n"]))
                )
            cell_score = _state_score(**total)
            aggregate_rows.append(
                {
                    "split": split, "panel": panel, "correction_strength": strength,
                    "n_target_cells": int(total["n"]),
                    "rmse_speed_kmh_cell_weighted": cell_score["rmse_speed_kmh"],
                    "rmse_flow_vph_per_lane_cell_weighted": cell_score["rmse_flow_vph_per_lane"],
                    "S_state": float(np.mean(regime_scores)),
                    "transition_S_state": float(np.mean(transition_scores)),
                    "S_FD_public": float(np.mean(fd_scores)),
                }
            )
    aggregates = pd.DataFrame(aggregate_rows)
    development = aggregates[aggregates.split == "development"].sort_values(
        ["S_state", "correction_strength"], ascending=[False, True]
    )
    selected_strength = float(development.iloc[0].correction_strength)
    confirmation = aggregates[aggregates.split == "confirmation"].set_index("correction_strength")
    selected = confirmation.loc[selected_strength]
    control = confirmation.loc[0.0]
    delta_state = float(selected.S_state - control.S_state)
    delta_fd = float(selected.S_FD_public - control.S_FD_public)
    delta_transition = float(selected.transition_S_state - control.transition_S_state)
    days = pd.DataFrame(day_rows)
    confirm = days[days.split == "confirmation"]
    day_delta = (
        confirm[confirm.correction_strength == selected_strength].set_index("day").S_state
        - confirm[confirm.correction_strength == 0.0].set_index("day").S_state
    )
    worst_day_delta = float(day_delta.min())
    coverage_multiplier = len(CORRECTION_STRENGTHS)
    gate_passed = (
        selected_strength != 0.0
        and delta_state >= 0.01
        and worst_day_delta >= -0.005
        and delta_fd >= -0.001
        and missing_predictions == 0
    )
    output_root.mkdir(parents=True, exist_ok=True)
    day_path = output_root / "nonlinear_residual_day_metrics.csv"
    aggregate_path = output_root / "nonlinear_residual_aggregate_metrics.csv"
    days.to_csv(day_path, index=False)
    aggregates.to_csv(aggregate_path, index=False)
    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "experiment": "task1_nonlinear_residual_ablation_v1",
        "question": "Can a link-agnostic mask-matched nonlinear residual model materially beat frozen V32 linear interpolation?",
        "data_boundary": {
            "panel": panel,
            "development": f"{development_start}..{development_end}",
            "confirmation": f"{confirmation_start}..{confirmation_end}",
            "training": training_summary,
            "profile_days_by_cutoff": profile_days,
            "same_block_truth_dependency": False,
            "training_label_availability_proof": {
                "release_path": str(panel_root / "train" / "mainline_states"),
                "fact": "All residual-training labels are in the published train observation layer. January is public train before the February confirmation analog; an actual candidate would fit through February public train and remain frozen across both validation and private.",
                "unavailable_scored_split_labels_used": False,
            },
            "target_truth_role": "training labels only on prior 56-day blocks; evaluator only on development/confirmation after predictions are fixed",
        },
        "model": {
            "type": "two HistGradientBoosting residual regressors",
            "features": list(FEATURE_NAMES),
            "link_identity_feature": False,
            "fixed_parameters": {
                "learning_rate": 0.05, "max_iter": 80, "max_leaf_nodes": 15,
                "min_samples_leaf": 100, "l2_regularization": 5.0,
            },
        },
        "only_variable": {
            "name": "correction_strength", "values": list(CORRECTION_STRENGTHS), "control": 0.0,
        },
        "development_selected_correction_strength": selected_strength,
        "development_frontier": {
            str(row.correction_strength): float(row.S_state)
            for row in aggregates[aggregates.split == "development"].itertuples(index=False)
        },
        "confirmation_frontier": {
            str(row.correction_strength): float(row.S_state)
            for row in aggregates[aggregates.split == "confirmation"].itertuples(index=False)
        },
        "confirmation": {
            "selected_S_state": float(selected.S_state), "control_S_state": float(control.S_state),
            "delta_S_state": delta_state, "delta_transition_S_state": delta_transition,
            "estimated_weighted_total_delta_from_state_only": 0.35 * delta_state,
            "selected_S_FD": float(selected.S_FD_public), "control_S_FD": float(control.S_FD_public),
            "delta_S_FD": delta_fd, "worst_day_delta_S_state": worst_day_delta,
        },
        "preregistered_expansion_gate": {
            "development_selects_noncontrol": True, "minimum_confirmation_delta_S_state": 0.01,
            "minimum_confirmation_day_delta": -0.005, "minimum_confirmation_delta_S_FD": -0.001,
            "complete_coverage": True,
        },
        "coverage": {
            "target_cells_once": total_target,
            "missing_predictions_across_all_strengths": missing_predictions,
            "expected_prediction_checks": total_target * coverage_multiplier,
        },
        "organizer_only_metrics": {"S_LWR": None, "S_physics": None},
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(release / "config" / "corridors.json")},
        "outputs": {day_path.name: _sha256(day_path), aggregate_path.name: _sha256(aggregate_path)},
        "decision": "CONTINUE_TO_ALL_PANELS" if gate_passed else "STOP_NONLINEAR_RESIDUAL_FAMILY",
    }
    receipt_path = output_root / "task1_nonlinear_residual_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--panel", default="D7_I10_E")
    parser.add_argument("--development-start", default="2031_01_01")
    parser.add_argument("--development-end", default="2031_01_31")
    parser.add_argument("--confirmation-start", default="2031_02_01")
    parser.add_argument("--confirmation-end", default="2031_02_28")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.release_root.resolve(), args.panel, args.development_start,
        args.development_end, args.confirmation_start, args.confirmation_end,
        args.output_root.resolve(),
    )


if __name__ == "__main__":
    main()
