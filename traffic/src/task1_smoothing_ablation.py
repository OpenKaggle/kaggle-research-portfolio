#!/usr/bin/env python3
"""Honest one-corridor ablation of V32-style density smoothing for Task 1.

The only changed quantity is the blend weight between the reconstructed raw
flow and a three-slot centered smoothing of density times the same predicted
speed.  Target-day truth is used only after prediction for scoring.
"""

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

from task1_mini_ablation import (
    VALUE_COLUMNS,
    _bounded,
    _day,
    _matrix,
    _read,
    _score,
    predict_day,
)


SMOOTHING_ALPHAS = (0.0, 0.05, 0.10, 0.15, 0.25)


def density_smoothing_variants(
    base: dict[str, np.ndarray], links: list[str], network: Path
) -> dict[str, dict[str, np.ndarray]]:
    """Return flow-only smoothing variants; speed is identical in every arm."""
    speed = base["speed_kmh"]
    raw_flow = base["flow_vph"]
    density = raw_flow / np.maximum(speed, 1.0)
    smooth_density = (
        pd.DataFrame(density)
        .rolling(3, center=True, min_periods=1)
        .mean()
        .to_numpy(dtype=float)
    )
    smooth_flow = smooth_density * speed
    result = {}
    for alpha in SMOOTHING_ALPHAS:
        flow = _bounded(
            "flow_vph",
            (1.0 - alpha) * raw_flow + alpha * smooth_flow,
            links,
            network,
        )
        result[f"density_smoothing_a{alpha:.2f}"] = {
            "speed_kmh": speed.copy(),
            "flow_vph": flow,
        }
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(root: Path, dev_end: str, confirm_end: str, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    unmasked = {_day(path): _read(path) for path in sorted((root / "unmasked").glob("*.parquet"))}
    masked = {_day(path): _read(path) for path in sorted((root / "masked").glob("*/*.parquet"))}
    target_days = sorted(day for day in masked if day <= confirm_end)
    dev_days = [day for day in target_days if day <= dev_end]
    confirmation_days = [day for day in target_days if dev_end < day <= confirm_end]
    if not dev_days or not confirmation_days:
        raise ValueError("both development and confirmation date blocks must be non-empty")

    lanes = (
        pd.read_csv(root / "network" / "fd_parameters.csv", dtype={"link_id": str})
        .set_index("link_id")
        .lanes
    )
    network = root / "network"
    predictions_by_day = {}
    for day in target_days:
        prior_day = (pd.Timestamp(day.replace("_", "-")) - pd.Timedelta(days=7)).strftime("%Y_%m_%d")
        if day not in unmasked or prior_day not in unmasked:
            raise FileNotFoundError(f"{day}: needs unmasked truth and prior day {prior_day}")
        links = sorted(masked[day].link_id.unique())
        base = predict_day(masked[day], unmasked[prior_day], network)["temporal_only"]
        predictions_by_day[day] = density_smoothing_variants(base, links, network)

    accumulators: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {"speed_sq": 0.0, "flow_sq": 0.0, "n": 0}
    )
    day_rows = []
    for split_name, days in (("development", dev_days), ("confirmation", confirmation_days)):
        for day in days:
            masked_day = masked[day]
            truth_day = unmasked[day]
            links = sorted(masked_day.link_id.unique())
            truth = {column: _matrix(truth_day, column, links) for column in VALUE_COLUMNS}
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
            usable = target & np.isfinite(truth["speed_kmh"]) & np.isfinite(truth["flow_vph"])
            for method, channels in predictions_by_day[day].items():
                speed_error = channels["speed_kmh"] - truth["speed_kmh"]
                flow_error = (channels["flow_vph"] - truth["flow_vph"]) / lane_vector
                values = {
                    "speed_sq": float(np.sum(np.square(speed_error[usable]))),
                    "flow_sq": float(np.sum(np.square(flow_error[usable]))),
                    "n": int(usable.sum()),
                }
                for group_regime in (regime, "ALL_WEIGHTED"):
                    bucket = accumulators[(split_name, method, group_regime)]
                    for key in bucket:
                        bucket[key] += values[key]
                day_rows.append(
                    {"split": split_name, "day": day, "regime": regime, "method": method, **_score(values)}
                )

    aggregate_rows = []
    for (split_name, method, regime), sums in sorted(accumulators.items()):
        aggregate_rows.append({"split": split_name, "method": method, "regime": regime, **_score(sums)})
    aggregates = pd.DataFrame(aggregate_rows)
    macro_rows = []
    for (split_name, method), group in aggregates[
        aggregates.regime.isin(["R1", "R2", "R3"])
    ].groupby(["split", "method"]):
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
    development = macro[macro.split.eq("development")].sort_values("S_state", ascending=False)
    winner = development.iloc[0]
    selected_method = str(winner.method)
    baseline_method = "density_smoothing_a0.00"
    confirmation = macro[macro.split.eq("confirmation")].set_index("method")
    confirmation_delta = float(
        confirmation.loc[selected_method, "S_state"] - confirmation.loc[baseline_method, "S_state"]
    )
    per_regime_deltas = {}
    confirm_regime = aggregates[
        aggregates.split.eq("confirmation") & aggregates.regime.isin(["R1", "R2", "R3"])
    ]
    for regime in ("R1", "R2", "R3"):
        values = confirm_regime[confirm_regime.regime.eq(regime)].set_index("method").S_state
        per_regime_deltas[regime] = float(values[selected_method] - values[baseline_method])
    min_regime_delta = min(per_regime_deltas.values())
    passed = selected_method != baseline_method and confirmation_delta > 0 and min_regime_delta >= -0.005

    output_root.mkdir(parents=True, exist_ok=True)
    day_path = output_root / "task1_smoothing_day_metrics.csv"
    aggregate_path = output_root / "task1_smoothing_aggregate_metrics.csv"
    pd.DataFrame(day_rows).to_csv(day_path, index=False)
    aggregates.to_csv(aggregate_path, index=False)
    peak_raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    receipt = {
        "status": "COMPLETE",
        "question": "Does changing only V32-style three-slot density-smoothing weight improve Task 1 state reconstruction?",
        "data_boundary": {
            "panel": "D12_I405_N",
            "development_days": dev_days,
            "confirmation_days": confirmation_days,
            "prior_rule": "exactly seven days earlier; target-day truth is evaluator-only",
            "selection": "one flow density-smoothing alpha selected on development only",
        },
        "invariant": "Speed predictions and the underlying temporal flow reconstruction are identical across arms; only the flow smoothing alpha changes.",
        "candidate_alphas": list(SMOOTHING_ALPHAS),
        "selected_method": selected_method,
        "development_S_state": float(winner.S_state),
        "confirmation_selected_S_state": float(confirmation.loc[selected_method, "S_state"]),
        "confirmation_no_smoothing_S_state": float(confirmation.loc[baseline_method, "S_state"]),
        "confirmation_selected_minus_no_smoothing": confirmation_delta,
        "confirmation_per_regime_deltas": per_regime_deltas,
        "official_metric": "Task 1 formula on released train truth and organizer-published masks; one panel only",
        "organizer_only_metrics": {"S_physics_with_boundary_flux": None},
        "decision_rule": "Scale only if development selects nonzero smoothing, confirmation delta is positive, and no confirmation regime regresses by more than 0.005.",
        "decision": "CONTINUE_TO_GROUPED_PANEL_TEST" if passed else "STOP_DENSITY_SMOOTHING_FAMILY",
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": peak_raw / (1024 * 1024),
        "artifacts": {
            "day_metrics": str(day_path),
            "day_metrics_sha256": _sha256(day_path),
            "aggregate_metrics": str(aggregate_path),
            "aggregate_metrics_sha256": _sha256(aggregate_path),
        },
    }
    receipt_path = output_root / "task1_smoothing_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--development-end", default="2030_06_14")
    parser.add_argument("--confirmation-end", default="2030_06_21")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(
        args.root.resolve(),
        args.development_end,
        args.confirmation_end,
        args.output_root.resolve(),
    )
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
