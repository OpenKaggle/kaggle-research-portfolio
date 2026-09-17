#!/usr/bin/env python3
"""Read-only residual audit for the sealed one-corridor temporal control."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd

from task1_mini_ablation import _day, _matrix, _read, predict_day


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_lengths(mask: np.ndarray) -> np.ndarray:
    result = np.zeros_like(mask, dtype=np.int16)
    for link in range(mask.shape[1]):
        start = None
        for slot in range(mask.shape[0] + 1):
            active = slot < mask.shape[0] and bool(mask[slot, link])
            if active and start is None:
                start = slot
            elif not active and start is not None:
                result[start:slot, link] = slot - start
                start = None
    return result


def _summarize(group: pd.DataFrame) -> pd.Series:
    speed_abs = group.speed_residual.abs()
    flow_abs = group.flow_per_lane_residual.abs()
    return pd.Series(
        {
            "n": len(group),
            "speed_bias_kmh": group.speed_residual.mean(),
            "speed_mae_kmh": speed_abs.mean(),
            "speed_rmse_kmh": np.sqrt(np.mean(np.square(group.speed_residual))),
            "speed_abs_p95_kmh": speed_abs.quantile(0.95),
            "flow_bias_vphpl": group.flow_per_lane_residual.mean(),
            "flow_mae_vphpl": flow_abs.mean(),
            "flow_rmse_vphpl": np.sqrt(np.mean(np.square(group.flow_per_lane_residual))),
            "flow_abs_p95_vphpl": flow_abs.quantile(0.95),
        }
    )


def run(root: Path, dev_end: str, confirm_end: str, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    unmasked = {_day(path): _read(path) for path in sorted((root / "unmasked").glob("*.parquet"))}
    masked = {_day(path): _read(path) for path in sorted((root / "masked").glob("*/*.parquet"))}
    target_days = sorted(day for day in masked if day <= confirm_end)
    lanes = (
        pd.read_csv(root / "network" / "fd_parameters.csv", dtype={"link_id": str})
        .set_index("link_id")
        .lanes
    )
    residual_parts = []
    for day in target_days:
        prior_day = (pd.Timestamp(day.replace("_", "-")) - pd.Timedelta(days=7)).strftime("%Y_%m_%d")
        if day not in unmasked or prior_day not in unmasked:
            raise FileNotFoundError(f"{day}: needs target truth and prior day {prior_day}")
        masked_day = masked[day]
        links = sorted(masked_day.link_id.unique())
        predictions = predict_day(masked_day, unmasked[prior_day], root / "network")["temporal_only"]
        true_speed = _matrix(unmasked[day], "speed_kmh", links)
        true_flow = _matrix(unmasked[day], "flow_vph", links)
        target = _matrix(
            masked_day.assign(
                target=masked_day.is_score_eligible.astype(bool)
                & masked_day.speed_kmh.isna()
                & masked_day.flow_vph.isna()
            ),
            "target",
            links,
        ).astype(bool)
        usable = target & np.isfinite(true_speed) & np.isfinite(true_flow)
        slot_index, link_index = np.where(usable)
        link_lanes = lanes.reindex(links).fillna(1.0).to_numpy(dtype=float)
        run_length = _run_lengths(target)[usable]
        part = pd.DataFrame(
            {
                "split": "development" if day <= dev_end else "confirmation",
                "day": day,
                "regime": str(masked_day.mask_regime.iloc[0]),
                "slot": slot_index,
                "link_id": np.asarray(links)[link_index],
                "run_length": run_length,
                "true_speed_kmh": true_speed[usable],
                "speed_residual": predictions["speed_kmh"][usable] - true_speed[usable],
                "flow_per_lane_residual": (
                    predictions["flow_vph"][usable] - true_flow[usable]
                ) / link_lanes[link_index],
            }
        )
        residual_parts.append(part)
    residuals = pd.concat(residual_parts, ignore_index=True)
    residuals["speed_band"] = pd.cut(
        residuals.true_speed_kmh,
        bins=[-np.inf, 60.0, 90.0, np.inf],
        labels=["congested_le60", "transition_60_90", "free_gt90"],
    ).astype(str)
    residuals["run_bin"] = pd.cut(
        residuals.run_length,
        bins=[0, 1, 3, 6, 12, np.inf],
        labels=["1", "2_3", "4_6", "7_12", "13_plus"],
    ).astype(str)

    summary_parts = []
    for dimension in ("regime", "speed_band", "run_bin"):
        grouped = residuals.groupby(["split", dimension], observed=True).apply(
            _summarize, include_groups=False
        ).reset_index()
        grouped.insert(1, "dimension", dimension)
        grouped = grouped.rename(columns={dimension: "stratum"})
        summary_parts.append(grouped)
    summary = pd.concat(summary_parts, ignore_index=True)
    bias_stability = summary.pivot_table(
        index=["dimension", "stratum"],
        columns="split",
        values=["speed_bias_kmh", "flow_bias_vphpl"],
    )
    bias_stability.columns = ["_".join(column) for column in bias_stability.columns]
    bias_stability = bias_stability.reset_index()
    for channel in ("speed_bias_kmh", "flow_bias_vphpl"):
        bias_stability[f"{channel}_confirmation_minus_development"] = (
            bias_stability[f"{channel}_confirmation"]
            - bias_stability[f"{channel}_development"]
        )

    output_root.mkdir(parents=True, exist_ok=True)
    residual_path = output_root / "task1_temporal_residuals.parquet"
    summary_path = output_root / "task1_residual_summary.csv"
    stability_path = output_root / "task1_bias_stability.csv"
    residuals.to_parquet(residual_path, index=False)
    summary.to_csv(summary_path, index=False)
    bias_stability.to_csv(stability_path, index=False)

    confirmation = summary[summary.split.eq("confirmation")]
    largest_speed = confirmation.loc[confirmation.speed_rmse_kmh.idxmax()]
    largest_flow = confirmation.loc[confirmation.flow_rmse_vphpl.idxmax()]
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    receipt = {
        "status": "COMPLETE_READ_ONLY",
        "panel": "D12_I405_N",
        "method": "sealed temporal-only control",
        "target_truth_usage": "evaluator/diagnostic only; no candidate was generated",
        "development_end": dev_end,
        "confirmation_end": confirm_end,
        "n_target_cells": len(residuals),
        "largest_confirmation_speed_rmse_stratum": {
            "dimension": str(largest_speed.dimension),
            "stratum": str(largest_speed.stratum),
            "rmse_speed_kmh": float(largest_speed.speed_rmse_kmh),
        },
        "largest_confirmation_flow_rmse_stratum": {
            "dimension": str(largest_flow.dimension),
            "stratum": str(largest_flow.stratum),
            "rmse_flow_vph_per_lane": float(largest_flow.flow_rmse_vphpl),
        },
        "organizer_only_S_physics": None,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": peak_mb,
        "artifacts": {
            "residuals_sha256": _sha256(residual_path),
            "summary_sha256": _sha256(summary_path),
            "bias_stability_sha256": _sha256(stability_path),
        },
    }
    receipt_path = output_root / "task1_residual_audit_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--development-end", default="2030_06_14")
    parser.add_argument("--confirmation-end", default="2030_06_21")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                args.root.resolve(),
                args.development_end,
                args.confirmation_end,
                args.output_root.resolve(),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
