#!/usr/bin/env python3
"""One-panel ablation of linear versus mode-preserving temporal filling."""

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
from task1_grouped_v32_control import build_frozen_profiles, v32_prediction


LINEAR_WEIGHTS = (1.0, 0.75, 0.50, 0.25, 0.0)


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
    links, profiles, profile_days = build_frozen_profiles(
        panel_root, [development_start, confirmation_start]
    )
    parameters = pd.read_csv(panel_root / "network" / "fd_parameters.csv", dtype={"link_id": str})
    parameters["link_id"] = parameters.link_id.astype(str)
    lanes = (
        parameters.set_index("link_id").lanes.reindex(links).fillna(1.0)
        .clip(lower=1.0).to_numpy(dtype=float)[None, :]
    )
    unmasked = {
        path.stem.removeprefix("synthetic_mainline_"): path
        for path in (panel_root / "train" / "mainline_states").glob("**/*.parquet")
    }
    split_ranges = {
        "development": (development_start, development_end, development_start),
        "confirmation": (confirmation_start, confirmation_end, confirmation_start),
    }
    state_sums = defaultdict(lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0.0})
    fd_sums = defaultdict(lambda: {"num": 0.0, "den": 0.0, "below": 0.0, "target_n": 0.0})
    day_rows: list[dict[str, object]] = []
    total_target = 0
    for path in sorted((panel_root / "train" / "mainline_states_masked").glob("**/*.parquet")):
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
        # Fix every candidate from released inputs before opening this day's truth.
        predictions = {
            weight: v32_prediction(masked, links, profiles[cutoff], parameters, weight)
            for weight in LINEAR_WEIGHTS
        }
        truth = _read_state(unmasked[day])
        regime = str(masked.mask_regime.iloc[0])
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
        if not total_target:
            total_target = 0
        total_target += int(target.sum())
        for weight, prediction in predictions.items():
            state = {
                "speed_sq": float(np.square((prediction["speed_kmh"] - true_speed)[usable]).sum()),
                "flow_sq": float(np.square(((prediction["flow_vph"] - true_flow) / lanes)[usable]).sum()),
                "n": float(usable.sum()),
            }
            _add(state_sums[(split, weight, regime)], state)
            reconstructed_speed = np.where(target, prediction["speed_kmh"], true_speed)
            reconstructed_flow = np.where(target, prediction["flow_vph"], true_flow)
            num, den, _ = _fd_sums(
                reconstructed_speed, reconstructed_flow, eligible, links, parameters
            )
            below = int((prediction["flow_vph"][target] < EMPTY_FLOOR_VPH).sum())
            fd = {"num": num, "den": den, "below": float(below), "target_n": float(target.sum())}
            _add(fd_sums[(split, weight, regime)], fd)
            day_rows.append(
                {
                    "split": split,
                    "day": day,
                    "panel": panel,
                    "regime": regime,
                    "linear_weight": weight,
                    **_state_score(**state),
                    "S_FD_public": _fd_score(num, den, below, int(target.sum())),
                }
            )

    aggregate_rows: list[dict[str, object]] = []
    for split in split_ranges:
        for weight in LINEAR_WEIGHTS:
            regime_rows = []
            fd_rows = []
            for regime in REGIMES:
                regime_rows.append(_state_score(**state_sums[(split, weight, regime)]))
                fd = fd_sums[(split, weight, regime)]
                fd_rows.append(
                    _fd_score(fd["num"], fd["den"], int(fd["below"]), int(fd["target_n"]))
                )
            aggregate_rows.append(
                {
                    "split": split,
                    "panel": panel,
                    "linear_weight": weight,
                    "n_target_cells": int(sum(row["n_target_cells"] for row in regime_rows)),
                    "S_state": float(np.mean([row["S_state"] for row in regime_rows])),
                    "S_FD_public": float(np.mean(fd_rows)),
                }
            )
    aggregates = pd.DataFrame(aggregate_rows)
    development = aggregates[aggregates.split == "development"].sort_values(
        ["S_state", "linear_weight"], ascending=[False, False]
    )
    selected_weight = float(development.iloc[0].linear_weight)
    control_weight = 1.0
    confirmation = aggregates[aggregates.split == "confirmation"].set_index("linear_weight")
    selected = confirmation.loc[selected_weight]
    control = confirmation.loc[control_weight]
    confirmation_delta = float(selected.S_state - control.S_state)
    fd_delta = float(selected.S_FD_public - control.S_FD_public)
    days = pd.DataFrame(day_rows)
    confirm_days = days[days.split == "confirmation"]
    selected_days = confirm_days[confirm_days.linear_weight == selected_weight].set_index("day")
    control_days = confirm_days[confirm_days.linear_weight == control_weight].set_index("day")
    day_deltas = selected_days.S_state - control_days.S_state
    worst_day_delta = float(day_deltas.min())
    gate_passed = (
        selected_weight != control_weight
        and confirmation_delta > 0.0
        and worst_day_delta >= -0.005
        and fd_delta >= -0.001
    )

    output_root.mkdir(parents=True, exist_ok=True)
    day_path = output_root / "temporal_mode_day_metrics.csv"
    aggregate_path = output_root / "temporal_mode_aggregate_metrics.csv"
    days.sort_values(["split", "day", "linear_weight"]).to_csv(day_path, index=False)
    aggregates.to_csv(aggregate_path, index=False)
    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "experiment": "task1_temporal_mode_ablation_v1",
        "question": "Does a single mode-preserving nearest-fill blend beat V32 linear interpolation on an untouched month?",
        "data_boundary": {
            "panel": panel,
            "development": f"{development_start}..{development_end}; profile dates < {development_start}",
            "confirmation": f"{confirmation_start}..{confirmation_end}; profile dates < {confirmation_start}",
            "profile_days": profile_days,
            "target_truth": "evaluator only after all weight predictions are fixed",
        },
        "only_variable": {
            "name": "linear_weight",
            "values": list(LINEAR_WEIGHTS),
            "control": control_weight,
            "definition": "weight on V32 linear time interpolation versus nearest visible time observation within the same 12-slot reach",
        },
        "development_selected_linear_weight": selected_weight,
        "confirmation": {
            "selected_S_state": float(selected.S_state),
            "control_S_state": float(control.S_state),
            "delta_S_state": confirmation_delta,
            "selected_S_FD": float(selected.S_FD_public),
            "control_S_FD": float(control.S_FD_public),
            "delta_S_FD": fd_delta,
            "worst_day_delta_S_state": worst_day_delta,
        },
        "preregistered_expansion_gate": {
            "development_selects_noncontrol": True,
            "confirmation_delta_S_state_positive": True,
            "minimum_confirmation_day_delta_S_state": -0.005,
            "minimum_confirmation_delta_S_FD": -0.001,
        },
        "organizer_only_metrics": {"S_LWR": None, "S_physics": None},
        "coverage": {"target_cells_across_both_blocks_once": total_target},
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(release / "config" / "corridors.json")},
        "outputs": {day_path.name: _sha256(day_path), aggregate_path.name: _sha256(aggregate_path)},
        "decision": "CONTINUE_TO_ALL_PANELS" if gate_passed else "STOP_TEMPORAL_MODE_FAMILY",
    }
    receipt_path = output_root / "task1_temporal_mode_receipt.json"
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
    receipt = run(
        args.release_root.resolve(), args.panel, args.development_start,
        args.development_end, args.confirmation_start, args.confirmation_end,
        args.output_root.resolve(),
    )
    print(receipt["decision"])


if __name__ == "__main__":
    main()
