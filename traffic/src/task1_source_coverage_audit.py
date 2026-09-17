#!/usr/bin/env python3
"""Measure which V32 fallback source can affect released scored-split targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import time
from pathlib import Path

import numpy as np
import pandas as pd


PROFILE_RELEVANCE_SHARE = 0.001


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def source_counts(frame: pd.DataFrame) -> dict[str, int]:
    frame = frame.copy()
    frame["link_id"] = frame.link_id.astype(str)
    timestamp = pd.to_datetime(frame.timestamp, utc=True)
    frame["slot"] = timestamp.dt.hour * 12 + timestamp.dt.minute // 5
    links = sorted(frame.link_id.unique())

    def matrix(column: str) -> np.ndarray:
        return (
            frame.pivot(index="slot", columns="link_id", values=column)
            .reindex(index=range(288), columns=links)
            .to_numpy(dtype=float)
        )

    target = (
        frame.assign(
            target=frame.is_score_eligible.astype(bool)
            & frame.speed_kmh.isna()
            & frame.flow_vph.isna()
        )
        .pivot(index="slot", columns="link_id", values="target")
        .reindex(index=range(288), columns=links)
        .fillna(False)
        .to_numpy(dtype=bool)
    )
    temporal_finite = []
    spatial_finite = []
    for column in ("speed_kmh", "flow_vph"):
        observed = matrix(column)
        temporal = (
            pd.DataFrame(observed)
            .interpolate(axis=0, method="linear", limit=12, limit_direction="both")
            .to_numpy(dtype=float)
        )
        spatial = (
            pd.DataFrame(temporal)
            .interpolate(axis=1, method="linear", limit=4, limit_direction="both")
            .to_numpy(dtype=float)
        )
        temporal_finite.append(np.isfinite(temporal))
        spatial_finite.append(np.isfinite(spatial))
    temporal_complete = temporal_finite[0] & temporal_finite[1]
    spatial_complete = spatial_finite[0] & spatial_finite[1]
    return {
        "target_cells": int(target.sum()),
        "temporal_complete": int((target & temporal_complete).sum()),
        "spatial_fallback": int((target & ~temporal_complete & spatial_complete).sum()),
        "profile_any_channel": int((target & ~spatial_complete).sum()),
    }


def run(release: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    manifest_path = release / "config" / "corridors.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panels = [str(item["corridor_id"]) for item in manifest["panels"]]
    rows: list[dict[str, object]] = []
    totals = {"target_cells": 0, "temporal_complete": 0, "spatial_fallback": 0, "profile_any_channel": 0}
    for panel in panels:
        print(f"[V32 source coverage] {panel}", flush=True)
        panel_root = release / "corridors" / panel
        for split in ("validation", "private"):
            counts = {key: 0 for key in totals}
            paths = sorted((panel_root / split / "mainline_states_masked").glob("**/*.parquet"))
            if not paths:
                raise FileNotFoundError(f"{panel}: no {split} masked files")
            for path in paths:
                frame = pd.read_parquet(
                    path,
                    columns=[
                        "timestamp", "link_id", "speed_kmh", "flow_vph", "is_score_eligible"
                    ],
                )
                day = source_counts(frame)
                for key in counts:
                    counts[key] += day[key]
                    totals[key] += day[key]
            n = max(counts["target_cells"], 1)
            rows.append(
                {
                    "panel": panel,
                    "split": split,
                    **counts,
                    "temporal_complete_share": counts["temporal_complete"] / n,
                    "spatial_fallback_share": counts["spatial_fallback"] / n,
                    "profile_any_channel_share": counts["profile_any_channel"] / n,
                }
            )
    frame = pd.DataFrame(rows)
    output_root.mkdir(parents=True, exist_ok=True)
    detail_path = output_root / "source_coverage_by_panel_split.csv"
    frame.to_csv(detail_path, index=False)
    total_n = max(totals["target_cells"], 1)
    profile_share = totals["profile_any_channel"] / total_n
    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "experiment": "task1_v32_source_coverage_audit_v1",
        "question": "Can changing the frozen historical profile affect enough scored-split targets to justify a new modeling family?",
        "data_boundary": {
            "splits": ["validation", "private"],
            "panels": panels,
            "inputs_only": True,
            "unmasked_truth_read": False,
            "predictions_generated": False,
        },
        "source_order": "temporal limit-12 -> lexical-link spatial limit-4 -> historical profile",
        "preregistered_gate": {
            "minimum_overall_profile_dependent_share": PROFILE_RELEVANCE_SHARE,
            "reason": "Below 0.1%, even a perfect profile replacement cannot materially move the 35%-weighted State component.",
        },
        "summary": {
            **totals,
            "temporal_complete_share": totals["temporal_complete"] / total_n,
            "spatial_fallback_share": totals["spatial_fallback"] / total_n,
            "profile_any_channel_share": profile_share,
            "maximum_panel_split_profile_share": float(frame.profile_any_channel_share.max()),
            "minimum_panel_split_temporal_share": float(frame.temporal_complete_share.min()),
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(manifest_path)},
        "outputs": {detail_path.name: _sha256(detail_path)},
        "decision": "CONTINUE_ROBUST_PROFILE_FAMILY" if profile_share >= PROFILE_RELEVANCE_SHARE else "STOP_ROBUST_PROFILE_FAMILY",
    }
    receipt_path = output_root / "task1_source_coverage_receipt.json"
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
