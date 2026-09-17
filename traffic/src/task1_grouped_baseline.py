#!/usr/bin/env python3
"""Build an honest all-panel Task 1 temporal baseline and public FD diagnostic.

Target-day truth is used only after predictions have been produced.  Each target
day is predicted from its released masked view and the unmasked day exactly
seven days earlier.  The script reports the official Task 1 aggregation and the
publicly reproducible FD branch of Task 3.  Organizer boundary-flux quantities
are deliberately neither estimated nor reported as leaderboard metrics.
"""

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


REGIMES = ("R1", "R2", "R3")
SPEED_SCALE = 25.0
FLOW_SCALE = 600.0
SPEED_WEIGHT = 0.54
FLOW_WEIGHT = 0.46
EMPTY_FLOOR_VPH = 50.0
EMPTY_SHARE = 0.20


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _day(path: Path) -> str:
    return path.stem.removeprefix("synthetic_mainline_")


def _slot(frame: pd.DataFrame) -> pd.Series:
    timestamp = pd.to_datetime(frame.timestamp, utc=True)
    return timestamp.dt.hour * 12 + timestamp.dt.minute // 5


def _read_state(path: Path, masked: bool = False) -> pd.DataFrame:
    columns = [
        "date", "timestamp", "station_id", "link_id", "speed_kmh", "flow_vph",
        "is_score_eligible",
    ]
    if masked:
        columns.append("mask_regime")
    frame = pd.read_parquet(path, columns=columns)
    frame["station_id"] = frame.station_id.astype(str)
    frame["link_id"] = frame.link_id.astype(str)
    frame["slot"] = _slot(frame)
    return frame


def _matrix(frame: pd.DataFrame, column: str, links: list[str]) -> np.ndarray:
    return (
        frame.pivot(index="slot", columns="link_id", values=column)
        .reindex(index=range(288), columns=links)
        .to_numpy(dtype=float)
    )


def temporal_prediction(
    masked: pd.DataFrame, prior: pd.DataFrame, parameters: pd.DataFrame
) -> tuple[list[str], dict[str, np.ndarray]]:
    """Predict a complete day without reading target-day truth."""
    links = sorted(masked.link_id.unique())
    indexed = parameters.set_index("link_id")
    predictions: dict[str, np.ndarray] = {}
    for column in ("speed_kmh", "flow_vph"):
        observed = _matrix(masked, column, links)
        prior_values = _matrix(prior, column, links)
        fallback = np.nanmedian(prior_values, axis=0)
        global_fallback = float(np.nanmedian(prior_values))
        if not np.isfinite(global_fallback):
            global_fallback = 80.0 if column == "speed_kmh" else 1000.0
        fallback = np.where(np.isfinite(fallback), fallback, global_fallback)
        prior_values = np.where(np.isfinite(prior_values), prior_values, fallback[None, :])
        interpolated = (
            pd.DataFrame(observed)
            .interpolate(axis=0, method="linear", limit=12, limit_direction="both")
            .to_numpy(dtype=float)
        )
        values = np.where(np.isfinite(interpolated), interpolated, prior_values)
        if column == "speed_kmh":
            upper = (
                indexed.free_speed_kmh.reindex(links).fillna(120.0).to_numpy(dtype=float)
                * 1.05
            )
            values = np.clip(values, 5.0, upper[None, :])
        else:
            upper = (
                indexed.capacity_vph.reindex(links).fillna(15000.0).to_numpy(dtype=float)
                * 1.15
            )
            values = np.clip(values, EMPTY_FLOOR_VPH, upper[None, :])
        predictions[column] = values
    return links, predictions


def _state_score(speed_sq: float, flow_sq: float, n: int) -> dict[str, float | int]:
    if n <= 0:
        return {
            "n_target_cells": 0,
            "rmse_speed_kmh": float("nan"),
            "rmse_flow_vph_per_lane": float("nan"),
            "S_speed": 0.0,
            "S_flow": 0.0,
            "S_state": 0.0,
        }
    rmse_speed = float(np.sqrt(speed_sq / n))
    rmse_flow = float(np.sqrt(flow_sq / n))
    speed_score = max(0.0, 1.0 - rmse_speed / SPEED_SCALE)
    flow_score = max(0.0, 1.0 - rmse_flow / FLOW_SCALE)
    return {
        "n_target_cells": int(n),
        "rmse_speed_kmh": rmse_speed,
        "rmse_flow_vph_per_lane": rmse_flow,
        "S_speed": speed_score,
        "S_flow": flow_score,
        "S_state": SPEED_WEIGHT * speed_score + FLOW_WEIGHT * flow_score,
    }


def _fd_sums(
    speed: np.ndarray,
    flow: np.ndarray,
    eligible: np.ndarray,
    links: list[str],
    parameters: pd.DataFrame,
) -> tuple[float, float, int]:
    """Return the exact public numerator/denominator terms for S_FD."""
    p = parameters.set_index("link_id").reindex(links)
    lanes = p.lanes.fillna(1.0).clip(lower=1.0).to_numpy(dtype=float)[None, :]
    free_speed = p.free_speed_kmh.to_numpy(dtype=float)[None, :]
    capacity = p.capacity_vph.to_numpy(dtype=float)[None, :]
    critical = capacity / np.maximum(free_speed, 1.0)
    jam = p.k_jam.fillna(pd.Series(100.0 * lanes.ravel(), index=p.index)).to_numpy(dtype=float)[None, :]
    jam = np.maximum(jam, critical * 1.05)

    q_lane = flow / lanes
    density = flow / np.maximum(speed, 1.0)
    k_lane = density / lanes
    cap_lane = capacity / lanes
    kcrit_lane = critical / lanes
    kjam_lane = jam / lanes
    q_fd = np.where(
        k_lane <= kcrit_lane,
        free_speed * k_lane,
        (cap_lane / np.maximum(kjam_lane - kcrit_lane, 1e-9))
        * np.maximum(kjam_lane - k_lane, 0.0),
    )
    valid = eligible & np.isfinite(q_lane) & np.isfinite(k_lane) & np.isfinite(q_fd)
    numerator = float(np.abs(q_lane[valid] - q_fd[valid]).sum())
    denominator = float(np.abs(q_lane[valid]).sum())
    return numerator, denominator, int(valid.sum())


def _fd_score(numerator: float, denominator: float, target_below: int, target_n: int) -> float:
    score = max(0.0, 1.0 - numerator / (denominator + 1e-9))
    if target_n and target_below / target_n > EMPTY_SHARE:
        return 0.0
    return float(score)


def _date_in_range(day: str, start: str, end: str) -> bool:
    return start <= day <= end


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def _add_sums(bucket: dict[str, float], values: dict[str, float]) -> None:
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

    zero_state = lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0.0}
    zero_fd = lambda: {"fd_num": 0.0, "fd_den": 0.0, "fd_rows": 0.0, "below": 0.0, "target_n": 0.0}
    state_sums: dict[tuple[str, str, str], dict[str, float]] = defaultdict(zero_state)
    fd_sums: dict[tuple[str, str, str], dict[str, float]] = defaultdict(zero_fd)
    day_rows: list[dict[str, object]] = []
    split_days: dict[str, list[str]] = {"development": [], "confirmation": []}
    total_target = 0
    total_missing = 0

    for panel in panels:
        print(f"[grouped temporal baseline] {panel}", flush=True)
        panel_root = release / "corridors" / panel
        unmasked_paths = sorted((panel_root / "train" / "mainline_states").glob("**/*.parquet"))
        masked_paths = sorted((panel_root / "train" / "mainline_states_masked").glob("**/*.parquet"))
        unmasked = {_day(path): path for path in unmasked_paths}
        masked = {_day(path): path for path in masked_paths}
        parameters = pd.read_csv(panel_root / "network" / "fd_parameters.csv", dtype={"link_id": str})
        parameters["link_id"] = parameters.link_id.astype(str)
        if parameters.link_id.duplicated().any():
            raise ValueError(f"{panel}: duplicate link_id in fd_parameters.csv")

        selected: list[tuple[str, str]] = []
        for day in sorted(masked):
            if _date_in_range(day, development_start, development_end):
                selected.append(("development", day))
            elif _date_in_range(day, confirmation_start, confirmation_end):
                selected.append(("confirmation", day))
        if not selected:
            raise ValueError(f"{panel}: no masked days in requested ranges")

        for split, day in selected:
            if day not in split_days[split]:
                split_days[split].append(day)
            prior_day = (pd.Timestamp(day.replace("_", "-")) - pd.Timedelta(days=7)).strftime("%Y_%m_%d")
            if day not in unmasked or prior_day not in unmasked:
                raise FileNotFoundError(f"{panel} {day}: needs truth day and prior {prior_day}")

            masked_frame = _read_state(masked[day], masked=True)
            prior_frame = _read_state(unmasked[prior_day])
            links, prediction = temporal_prediction(masked_frame, prior_frame, parameters)

            # Prediction is now fixed.  Only from this point onward is target-day
            # truth read, and only by the evaluator branch below.
            truth = _read_state(unmasked[day])
            regime_values = masked_frame.mask_regime.dropna().astype(str).unique()
            if len(regime_values) != 1 or regime_values[0] not in REGIMES:
                raise ValueError(f"{panel} {day}: expected exactly one known mask regime")
            regime = str(regime_values[0])
            truth_speed = _matrix(truth, "speed_kmh", links)
            truth_flow = _matrix(truth, "flow_vph", links)
            observed_speed = _matrix(masked_frame, "speed_kmh", links)
            observed_flow = _matrix(masked_frame, "flow_vph", links)
            eligible = _matrix(
                truth.assign(is_score_eligible=truth.is_score_eligible.astype(bool)),
                "is_score_eligible",
                links,
            ).astype(bool)
            target = eligible & ~np.isfinite(observed_speed) & ~np.isfinite(observed_flow)
            usable = target & np.isfinite(truth_speed) & np.isfinite(truth_flow)
            missing_prediction = target & (
                ~np.isfinite(prediction["speed_kmh"]) | ~np.isfinite(prediction["flow_vph"])
            )
            lanes = (
                parameters.set_index("link_id").lanes.reindex(links).fillna(1.0)
                .clip(lower=1.0).to_numpy(dtype=float)[None, :]
            )
            speed_error = prediction["speed_kmh"] - truth_speed
            flow_error = (prediction["flow_vph"] - truth_flow) / lanes
            state_values = {
                "speed_sq": float(np.square(speed_error[usable]).sum()),
                "flow_sq": float(np.square(flow_error[usable]).sum()),
                "n": float(usable.sum()),
            }
            _add_sums(state_sums[(split, panel, regime)], state_values)

            # Reconstruct the complete eligible field exactly as Task 3 does:
            # submitted values at targets, released observations elsewhere.
            reconstructed_speed = np.where(target, prediction["speed_kmh"], truth_speed)
            reconstructed_flow = np.where(target, prediction["flow_vph"], truth_flow)
            fd_num, fd_den, fd_rows = _fd_sums(
                reconstructed_speed, reconstructed_flow, eligible, links, parameters
            )
            below = int((prediction["flow_vph"][target] < EMPTY_FLOOR_VPH).sum())
            fd_values = {
                "fd_num": fd_num,
                "fd_den": fd_den,
                "fd_rows": float(fd_rows),
                "below": float(below),
                "target_n": float(target.sum()),
            }
            _add_sums(fd_sums[(split, panel, regime)], fd_values)
            total_target += int(target.sum())
            total_missing += int(missing_prediction.sum())
            day_rows.append(
                {
                    "split": split,
                    "day": day,
                    "panel": panel,
                    "family_id": families[panel],
                    "regime": regime,
                    **_state_score(**state_values),
                    "S_FD_public": _fd_score(fd_num, fd_den, below, int(target.sum())),
                    "fd_rows": fd_rows,
                    "n_missing_predictions": int(missing_prediction.sum()),
                }
            )

    panel_regime_rows: list[dict[str, object]] = []
    for split in ("development", "confirmation"):
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
                            fd["fd_num"], fd["fd_den"], int(fd["below"]), int(fd["target_n"])
                        ),
                        "fd_rows": int(fd["fd_rows"]),
                        "empty_target_share": fd["below"] / max(fd["target_n"], 1.0),
                    }
                )

    panel_regime = pd.DataFrame(panel_regime_rows)
    aggregate_rows: list[dict[str, object]] = []
    for split in ("development", "confirmation"):
        split_frame = panel_regime[panel_regime.split == split]
        for panel, group in split_frame.groupby("panel", sort=True):
            aggregate_rows.append(
                {
                    "split": split,
                    "level": "panel",
                    "panel": panel,
                    "family_id": families[panel],
                    "regime": "macro_mean",
                    "n_target_cells": int(group.n_target_cells.sum()),
                    "S_state": float(group.S_state.mean()),
                    "S_FD_public": float(group.S_FD_public.mean()),
                }
            )
        panels_frame = pd.DataFrame([r for r in aggregate_rows if r["split"] == split and r["level"] == "panel"])
        for family, group in panels_frame.groupby("family_id", sort=True):
            aggregate_rows.append(
                {
                    "split": split,
                    "level": "family",
                    "panel": None,
                    "family_id": family,
                    "regime": "macro_mean",
                    "n_target_cells": int(group.n_target_cells.sum()),
                    "S_state": float(group.S_state.mean()),
                    "S_FD_public": float(group.S_FD_public.mean()),
                }
            )
        families_frame = pd.DataFrame([r for r in aggregate_rows if r["split"] == split and r["level"] == "family"])
        aggregate_rows.append(
            {
                "split": split,
                "level": "overall",
                "panel": None,
                "family_id": "ALL",
                "regime": "macro_mean",
                "n_target_cells": int(families_frame.n_target_cells.sum()),
                "S_state": float(families_frame.S_state.mean()),
                "S_FD_public": float(panels_frame.S_FD_public.mean()),
            }
        )
    aggregates = pd.DataFrame(aggregate_rows)

    output_root.mkdir(parents=True, exist_ok=True)
    day_path = output_root / "task1_grouped_day_metrics.csv"
    panel_regime_path = output_root / "task1_grouped_panel_regime_metrics.csv"
    aggregate_path = output_root / "task1_grouped_aggregate_metrics.csv"
    pd.DataFrame(day_rows).sort_values(["split", "panel", "day"]).to_csv(day_path, index=False)
    panel_regime.to_csv(panel_regime_path, index=False)
    aggregates.to_csv(aggregate_path, index=False)

    overall = aggregates[aggregates.level == "overall"].set_index("split")
    runtime = time.perf_counter() - started
    receipt: dict[str, object] = {
        "status": "COMPLETE" if total_missing == 0 else "FAILED_COVERAGE",
        "experiment": "task1_grouped_temporal_baseline_v1",
        "question": "What is the honest all-panel Task 1 temporal control and its public FD consistency before testing a new State family?",
        "data_boundary": {
            "release_root": str(release),
            "panels": panels,
            "development_days": sorted(split_days["development"]),
            "confirmation_days": sorted(split_days["confirmation"]),
            "prior_rule": "exactly seven days earlier",
            "leakage_guard": "target-day truth is first read only after masked-day predictions are fixed",
        },
        "method": {
            "name": "temporal_only",
            "interpolation": "within target day along time, linear, limit 12 five-minute slots, both directions",
            "fallback": "same panel/link/time slot exactly seven days earlier",
            "bounds": "speed [5,1.05*free_speed], flow [50,1.15*capacity]",
        },
        "official_task1": {
            "development_S_state": float(overall.loc["development", "S_state"]),
            "confirmation_S_state": float(overall.loc["confirmation", "S_state"]),
            "aggregation": "regime -> direction panel -> corridor family -> overall, equal weights",
        },
        "public_task3_diagnostic": {
            "development_S_FD": float(overall.loc["development", "S_FD_public"]),
            "confirmation_S_FD": float(overall.loc["confirmation", "S_FD_public"]),
            "aggregation": "regime -> panel -> overall, equal weights",
            "definition": "official per-lane triangular fundamental-diagram branch on reconstructed eligible state",
            "not_a_leaderboard_physics_score": True,
        },
        "organizer_only_metrics": {
            "S_LWR": None,
            "S_physics": None,
            "reason": "organizer-held boundary flux is not in the public release; topology fallback is not leaderboard-valid",
        },
        "coverage": {
            "target_cells": total_target,
            "missing_predictions": total_missing,
        },
        "runtime_seconds": runtime,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(manifest_path)},
        "outputs": {
            day_path.name: _sha256(day_path),
            panel_regime_path.name: _sha256(panel_regime_path),
            aggregate_path.name: _sha256(aggregate_path),
        },
        "decision": "ESTABLISH_CONTROL_ONLY" if total_missing == 0 else "STOP_COVERAGE_FAILURE",
    }
    receipt_path = output_root / "task1_grouped_baseline_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--development-start", default="2031_02_01")
    parser.add_argument("--development-end", default="2031_02_14")
    parser.add_argument("--confirmation-start", default="2031_02_15")
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
