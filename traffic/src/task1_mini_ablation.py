#!/usr/bin/env python3
"""Honest one-corridor Task 1 temporal/spatial/topology mini-ablation."""

from __future__ import annotations

import argparse
import json
import resource
import time
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd


SPEED_SCALE = 25.0
FLOW_SCALE = 600.0
SPEED_WEIGHT = 0.54
FLOW_WEIGHT = 0.46
ALPHAS = (0.0, 0.25, 0.50, 0.75)
VALUE_COLUMNS = ("speed_kmh", "flow_vph")
KEY_COLUMNS = ["timestamp", "station_id", "link_id"]


def _day(path: Path) -> str:
    return path.stem.removeprefix("synthetic_mainline_")


def _read(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(
        path,
        columns=[
            "date", "timestamp", "station_id", "link_id", "milepost", "speed_kmh", "flow_vph",
            "is_score_eligible", *( ["mask_regime"] if path.parent.parent.name == "masked" else [] ),
        ],
    )
    frame["station_id"] = frame.station_id.astype(str)
    frame["link_id"] = frame.link_id.astype(str)
    timestamp = pd.to_datetime(frame.timestamp, utc=True)
    frame["slot"] = timestamp.dt.hour * 12 + timestamp.dt.minute // 5
    return frame


def _matrix(frame: pd.DataFrame, column: str, links: list[str]) -> np.ndarray:
    pivot = frame.pivot(index="slot", columns="link_id", values=column).reindex(
        index=range(288), columns=links
    )
    return pivot.to_numpy(dtype=float)


def _temporal(observed: np.ndarray, prior: np.ndarray) -> np.ndarray:
    interpolated = pd.DataFrame(observed).interpolate(
        axis=0, method="linear", limit=12, limit_direction="both"
    ).to_numpy(dtype=float)
    return np.where(np.isfinite(interpolated), interpolated, prior)


def _spatial_residual(
    observed: np.ndarray, prior: np.ndarray, positions: np.ndarray
) -> np.ndarray:
    residual = observed - prior
    prediction = np.full_like(observed, np.nan)
    order = np.argsort(positions)
    sorted_positions = positions[order]
    for slot in range(observed.shape[0]):
        values = residual[slot, order]
        finite = np.isfinite(values) & np.isfinite(sorted_positions)
        if not finite.any():
            continue
        if finite.sum() == 1:
            filled = np.full(len(order), values[finite][0])
        else:
            filled = np.interp(sorted_positions, sorted_positions[finite], values[finite])
        prediction[slot, order] = prior[slot, order] + filled
    return np.where(np.isfinite(prediction), prediction, prior)


def _graph(network: Path) -> dict[str, set[str]]:
    topology = pd.read_csv(network / "lwr_mainline_topology.csv", dtype=str).fillna("")
    graph: dict[str, set[str]] = defaultdict(set)
    for row in topology.itertuples(index=False):
        link = str(row.link_id)
        neighbors = []
        for column in ("incoming_link_ids", "outgoing_link_ids"):
            neighbors.extend(value.strip() for value in str(getattr(row, column, "")).split(";") if value.strip())
        for neighbor in neighbors:
            graph[link].add(neighbor)
            graph[neighbor].add(link)
    return graph


def _distances(links: list[str], graph: dict[str, set[str]]) -> np.ndarray:
    index = {link: i for i, link in enumerate(links)}
    result = np.full((len(links), len(links)), np.inf)
    for source_index, source in enumerate(links):
        seen = {source}
        queue: deque[tuple[str, int]] = deque([(source, 0)])
        while queue:
            current, distance = queue.popleft()
            if current in index:
                result[source_index, index[current]] = distance
            for neighbor in graph.get(current, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, distance + 1))
    return result


def _topology_residual(observed: np.ndarray, prior: np.ndarray, distances: np.ndarray) -> np.ndarray:
    residual = observed - prior
    prediction = np.full_like(observed, np.nan)
    for slot in range(observed.shape[0]):
        available = np.flatnonzero(np.isfinite(residual[slot]))
        if len(available) == 0:
            continue
        for target in range(observed.shape[1]):
            distance = distances[target, available]
            reachable = np.isfinite(distance)
            if not reachable.any():
                continue
            candidates = available[reachable]
            candidate_distance = distance[reachable]
            nearest_order = np.argsort(candidate_distance)[:2]
            candidates = candidates[nearest_order]
            candidate_distance = candidate_distance[nearest_order]
            exact = candidate_distance == 0
            if exact.any():
                delta = float(residual[slot, candidates[exact][0]])
            else:
                weights = 1.0 / np.maximum(candidate_distance, 1.0)
                delta = float(np.average(residual[slot, candidates], weights=weights))
            prediction[slot, target] = prior[slot, target] + delta
    return np.where(np.isfinite(prediction), prediction, prior)


def _bounded(column: str, values: np.ndarray, links: list[str], network: Path) -> np.ndarray:
    params = pd.read_csv(network / "fd_parameters.csv", dtype={"link_id": str}).set_index("link_id")
    if column == "speed_kmh":
        upper = params.free_speed_kmh.reindex(links).fillna(120.0).to_numpy(dtype=float) * 1.05
        return np.clip(values, 5.0, upper[None, :])
    upper = params.capacity_vph.reindex(links).fillna(15000.0).to_numpy(dtype=float) * 1.15
    return np.clip(values, 50.0, upper[None, :])


def predict_day(masked: pd.DataFrame, prior_frame: pd.DataFrame, network: Path) -> dict[str, dict[str, np.ndarray]]:
    links = sorted(masked.link_id.unique())
    positions = masked.drop_duplicates("link_id").set_index("link_id").milepost.reindex(links).to_numpy(dtype=float)
    distances = _distances(links, _graph(network))
    predictions: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    for column in VALUE_COLUMNS:
        observed = _matrix(masked, column, links)
        prior = _matrix(prior_frame, column, links)
        fallback = np.nanmedian(prior, axis=0)
        fallback = np.where(np.isfinite(fallback), fallback, np.nanmedian(prior))
        prior = np.where(np.isfinite(prior), prior, fallback[None, :])
        temporal = _bounded(column, _temporal(observed, prior), links, network)
        spatial = _bounded(column, _spatial_residual(observed, prior, positions), links, network)
        topology = _bounded(column, _topology_residual(observed, prior, distances), links, network)
        predictions["temporal_only"][column] = temporal
        for alpha in ALPHAS:
            predictions[f"spatial_neighbor_a{alpha:.2f}"][column] = _bounded(
                column, alpha * temporal + (1.0 - alpha) * spatial, links, network
            )
            predictions[f"topology_aware_a{alpha:.2f}"][column] = _bounded(
                column, alpha * temporal + (1.0 - alpha) * topology, links, network
            )
    return predictions


def _score(sums: dict[str, float]) -> dict[str, float | int]:
    n = int(sums["n"])
    rmse_speed = float(np.sqrt(sums["speed_sq"] / max(n, 1)))
    rmse_flow = float(np.sqrt(sums["flow_sq"] / max(n, 1)))
    speed_score = max(0.0, 1.0 - rmse_speed / SPEED_SCALE)
    flow_score = max(0.0, 1.0 - rmse_flow / FLOW_SCALE)
    return {
        "n_target_cells": n,
        "rmse_speed_kmh": rmse_speed,
        "rmse_flow_vph_per_lane": rmse_flow,
        "S_speed": speed_score,
        "S_flow": flow_score,
        "S_state": SPEED_WEIGHT * speed_score + FLOW_WEIGHT * flow_score,
    }


def run(root: Path, dev_end: str, confirm_end: str, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    unmasked_paths = sorted((root / "unmasked").glob("*.parquet"))
    masked_paths = sorted((root / "masked").glob("*/*.parquet"))
    unmasked = {_day(path): _read(path) for path in unmasked_paths}
    masked = {_day(path): _read(path) for path in masked_paths}
    target_days = sorted(day for day in masked if day <= confirm_end)
    dev_days = [day for day in target_days if day <= dev_end]
    confirmation_days = [day for day in target_days if dev_end < day <= confirm_end]
    if not dev_days or not confirmation_days:
        raise ValueError("both development and confirmation date blocks must be non-empty")

    lanes = pd.read_csv(root / "network" / "fd_parameters.csv", dtype={"link_id": str}).set_index("link_id").lanes
    per_day_predictions = {}
    truth_by_day = {}
    for day in target_days:
        prior_day = (pd.Timestamp(day.replace("_", "-")) - pd.Timedelta(days=7)).strftime("%Y_%m_%d")
        if day not in unmasked or prior_day not in unmasked:
            raise FileNotFoundError(f"{day}: needs unmasked truth and prior day {prior_day}")
        per_day_predictions[day] = predict_day(masked[day], unmasked[prior_day], root / "network")
        truth_by_day[day] = unmasked[day]

    accumulators: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0}
    )
    day_rows = []
    for split_name, days in (("development", dev_days), ("confirmation", confirmation_days)):
        for day in days:
            masked_day = masked[day]
            truth_day = truth_by_day[day]
            links = sorted(masked_day.link_id.unique())
            truth_speed = _matrix(truth_day, "speed_kmh", links)
            truth_flow = _matrix(truth_day, "flow_vph", links)
            target = _matrix(
                masked_day.assign(
                    target=masked_day.is_score_eligible.astype(bool)
                    & masked_day.speed_kmh.isna()
                    & masked_day.flow_vph.isna()
                ),
                "target",
                links,
            ).astype(bool)
            lane_vector = lanes.reindex(links).fillna(1.0).to_numpy(dtype=float)[None, :]
            regime = str(masked_day.mask_regime.iloc[0])
            for method, channels in per_day_predictions[day].items():
                usable = target & np.isfinite(truth_speed) & np.isfinite(truth_flow)
                speed_error = channels["speed_kmh"] - truth_speed
                flow_error = (channels["flow_vph"] - truth_flow) / lane_vector
                values = {
                    "speed_sq": float(np.sum(np.square(speed_error[usable]))),
                    "flow_sq": float(np.sum(np.square(flow_error[usable]))),
                    "n": int(usable.sum()),
                }
                for group_regime in (regime, "ALL_WEIGHTED"):
                    bucket = accumulators[(split_name, method, group_regime)]
                    for key in bucket:
                        bucket[key] += values[key]
                day_rows.append({"split": split_name, "day": day, "regime": regime, "method": method, **_score(values)})

    aggregate_rows = []
    for (split_name, method, regime), sums in sorted(accumulators.items()):
        aggregate_rows.append({"split": split_name, "method": method, "regime": regime, **_score(sums)})
    aggregates = pd.DataFrame(aggregate_rows)
    macro_rows = []
    for (split_name, method), group in aggregates[aggregates.regime.isin(["R1", "R2", "R3"])].groupby(
        ["split", "method"]
    ):
        macro_rows.append(
            {
                "split": split_name,
                "method": method,
                "regime": "MACRO_REGIME",
                "n_target_cells": int(group.n_target_cells.sum()),
                "rmse_speed_kmh": np.nan,
                "rmse_flow_vph_per_lane": np.nan,
                "S_speed": np.nan,
                "S_flow": np.nan,
                "S_state": float(group.S_state.mean()),
            }
        )
    aggregates = pd.concat([aggregates, pd.DataFrame(macro_rows)], ignore_index=True)
    macro = aggregates[aggregates.regime.eq("MACRO_REGIME")]

    def best(prefix: str) -> dict[str, object]:
        development = macro[(macro.split == "development") & macro.method.str.startswith(prefix)]
        winner = development.sort_values("S_state", ascending=False).iloc[0]
        confirmation = macro[(macro.split == "confirmation") & macro.method.eq(winner.method)].iloc[0]
        return {
            "method": str(winner.method),
            "development_S_state": float(winner.S_state),
            "confirmation_S_state": float(confirmation.S_state),
        }

    temporal = best("temporal_only")
    best_spatial = best("spatial_neighbor")
    best_topology = best("topology_aware")
    runtime = time.perf_counter() - started
    peak_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_mb = peak_raw / (1024 * 1024)
    confirmation_delta = best_topology["confirmation_S_state"] - temporal["confirmation_S_state"]
    receipt = {
        "status": "COMPLETE",
        "question": "Does topology-aware residual interpolation beat equal-cost temporal and milepost-neighbor reconstruction on an untouched one-corridor train block?",
        "data_boundary": {
            "panel": "D12_I405_N",
            "development_days": dev_days,
            "confirmation_days": confirmation_days,
            "prior_rule": "exactly seven days earlier; prediction code never reads target-day truth",
            "selection": "one shared temporal blend alpha selected on development only",
        },
        "methods": {"temporal_only": temporal, "best_spatial_neighbor": best_spatial, "best_topology_aware": best_topology},
        "confirmation_topology_minus_temporal": confirmation_delta,
        "official_metric": "Task 1 formula on released train truth and organizer-published masks; one panel only",
        "organizer_only_metrics": {"S_queue": None, "S_physics_with_boundary_flux": None},
        "runtime_seconds": runtime,
        "peak_memory_mb": peak_mb,
        "decision_rule": "Do not scale topology if confirmation is not positive or if it regresses S_state by more than 0.005; full candidates must later pass grouped all-panel scoring.",
        "decision": "CONTINUE_TO_GROUPED_PANEL_TEST" if confirmation_delta > 0 else "STOP_TOPOLOGY_FAMILY",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(day_rows).to_csv(output_root / "task1_mini_day_metrics.csv", index=False)
    aggregates.to_csv(output_root / "task1_mini_aggregate_metrics.csv", index=False)
    (output_root / "task1_mini_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--development-end", default="2030_06_14")
    parser.add_argument("--confirmation-end", default="2030_06_21")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.root.resolve(), args.development_end, args.confirmation_end, args.output_root.resolve())
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
