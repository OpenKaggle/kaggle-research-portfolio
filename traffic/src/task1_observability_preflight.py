#!/usr/bin/env python3
"""Input-only observability audit for a directional State reconstruction family.

The audit reads released validation/private masks, values that remain visible,
and released network geometry.  It never opens an unmasked target-day file and
does not generate a prediction.  Its output decides whether a directional
switching/filtering experiment is justified at all.
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
MAX_SPACING_KM = 3.0
MIN_UPSTREAM_SHARE = 0.90
MIN_DOWNSTREAM_SHARE = 0.90
MIN_BOTH_SHARE = 0.80
MIN_EITHER_SHARE = 0.99


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def directional_distances(
    observed: np.ndarray, target: np.ndarray, positions_km: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Nearest same-time visible cell before/after every target along traffic order."""
    if observed.shape != target.shape or observed.shape[1] != len(positions_km):
        raise ValueError("observed, target, and positions must describe the same grid")
    indices = np.arange(observed.shape[1], dtype=int)[None, :]
    previous = np.maximum.accumulate(np.where(observed, indices, -1), axis=1)
    following = np.minimum.accumulate(
        np.where(observed, indices, observed.shape[1])[:, ::-1], axis=1
    )[:, ::-1]
    rows, columns = np.nonzero(target)
    up_index = previous[rows, columns]
    down_index = following[rows, columns]
    upstream = np.full(len(rows), np.nan, dtype=float)
    downstream = np.full(len(rows), np.nan, dtype=float)
    have_upstream = up_index >= 0
    have_downstream = down_index < observed.shape[1]
    upstream[have_upstream] = (
        positions_km[columns[have_upstream]] - positions_km[up_index[have_upstream]]
    )
    downstream[have_downstream] = (
        positions_km[down_index[have_downstream]] - positions_km[columns[have_downstream]]
    )
    return upstream, downstream


def _empty_bucket() -> dict[str, object]:
    return {
        "target_cells": 0,
        "upstream_any": 0,
        "downstream_any": 0,
        "upstream_within": 0,
        "downstream_within": 0,
        "both_within": 0,
        "either_within": 0,
        "upstream_distances": [],
        "downstream_distances": [],
    }


def _update(bucket: dict[str, object], upstream: np.ndarray, downstream: np.ndarray) -> None:
    up_any = np.isfinite(upstream)
    down_any = np.isfinite(downstream)
    up_close = up_any & (upstream <= MAX_SPACING_KM)
    down_close = down_any & (downstream <= MAX_SPACING_KM)
    bucket["target_cells"] += len(upstream)
    bucket["upstream_any"] += int(up_any.sum())
    bucket["downstream_any"] += int(down_any.sum())
    bucket["upstream_within"] += int(up_close.sum())
    bucket["downstream_within"] += int(down_close.sum())
    bucket["both_within"] += int((up_close & down_close).sum())
    bucket["either_within"] += int((up_close | down_close).sum())
    bucket["upstream_distances"].append(upstream[up_any])
    bucket["downstream_distances"].append(downstream[down_any])


def _summarize(bucket: dict[str, object]) -> dict[str, float | int]:
    n = int(bucket["target_cells"])
    upstream = np.concatenate(bucket["upstream_distances"]) if bucket["upstream_distances"] else np.array([])
    downstream = np.concatenate(bucket["downstream_distances"]) if bucket["downstream_distances"] else np.array([])

    def share(key: str) -> float:
        return float(bucket[key]) / max(n, 1)

    def quantile(values: np.ndarray, q: float) -> float:
        return float(np.quantile(values, q)) if len(values) else float("nan")

    return {
        "target_cells": n,
        "upstream_any_share": share("upstream_any"),
        "downstream_any_share": share("downstream_any"),
        "upstream_within_3km_share": share("upstream_within"),
        "downstream_within_3km_share": share("downstream_within"),
        "both_directions_within_3km_share": share("both_within"),
        "either_direction_within_3km_share": share("either_within"),
        "upstream_distance_p50_km": quantile(upstream, 0.50),
        "upstream_distance_p95_km": quantile(upstream, 0.95),
        "upstream_distance_max_km": float(upstream.max()) if len(upstream) else float("nan"),
        "downstream_distance_p50_km": quantile(downstream, 0.50),
        "downstream_distance_p95_km": quantile(downstream, 0.95),
        "downstream_distance_max_km": float(downstream.max()) if len(downstream) else float("nan"),
    }


def _geometry(panel_root: Path) -> tuple[list[str], np.ndarray, dict[str, float]]:
    topology_path = panel_root / "network" / "lwr_mainline_topology.csv"
    topology = pd.read_csv(topology_path, dtype={"link_id": str})
    topology["link_id"] = topology.link_id.astype(str)
    topology["order_index"] = pd.to_numeric(topology.order_index, errors="raise")
    topology["length_km"] = pd.to_numeric(topology.length_km, errors="raise")
    topology = topology.sort_values(["order_index", "link_id"]).drop_duplicates("link_id")
    links = topology.link_id.tolist()
    lengths = topology.length_km.to_numpy(dtype=float)
    positions = np.concatenate(([0.0], np.cumsum(lengths[:-1])))
    gaps = np.diff(positions)
    geometry = {
        "n_links": len(links),
        "adjacent_spacing_p95_km": float(np.quantile(gaps, 0.95)) if len(gaps) else 0.0,
        "adjacent_spacing_max_km": float(gaps.max()) if len(gaps) else 0.0,
    }
    return links, positions, geometry


def run(release: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    manifest_path = release / "config" / "corridors.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panels = [str(item["corridor_id"]) for item in manifest["panels"]]
    buckets: dict[tuple[str, str, str], dict[str, object]] = defaultdict(_empty_bucket)
    geometries: dict[str, dict[str, float]] = {}
    input_files: list[Path] = [manifest_path]

    for panel in panels:
        print(f"[input-only observability] {panel}", flush=True)
        panel_root = release / "corridors" / panel
        links, positions, geometry = _geometry(panel_root)
        geometries[panel] = geometry
        link_set = set(links)
        for split in ("validation", "private"):
            paths = sorted((panel_root / split / "mainline_states_masked").glob("**/*.parquet"))
            if not paths:
                raise FileNotFoundError(f"{panel}: no {split} masked state files")
            for path in paths:
                frame = pd.read_parquet(
                    path,
                    columns=[
                        "timestamp", "link_id", "speed_kmh", "flow_vph",
                        "is_score_eligible", "mask_regime",
                    ],
                )
                frame["link_id"] = frame.link_id.astype(str)
                unknown = set(frame.link_id) - link_set
                if unknown:
                    raise ValueError(f"{panel}: masked frame contains links absent from topology")
                timestamp = pd.to_datetime(frame.timestamp, utc=True)
                frame["slot"] = timestamp.dt.hour * 12 + timestamp.dt.minute // 5
                regime_values = frame.mask_regime.dropna().astype(str).unique()
                if len(regime_values) != 1 or regime_values[0] not in REGIMES:
                    raise ValueError(f"{path}: expected one known regime")
                regime = str(regime_values[0])
                observed = (
                    frame.assign(observed=frame.speed_kmh.notna() & frame.flow_vph.notna())
                    .pivot(index="slot", columns="link_id", values="observed")
                    .reindex(index=range(288), columns=links, fill_value=False)
                    .fillna(False)
                    .to_numpy(dtype=bool)
                )
                target = (
                    frame.assign(
                        target=frame.is_score_eligible.astype(bool)
                        & frame.speed_kmh.isna()
                        & frame.flow_vph.isna()
                    )
                    .pivot(index="slot", columns="link_id", values="target")
                    .reindex(index=range(288), columns=links, fill_value=False)
                    .fillna(False)
                    .to_numpy(dtype=bool)
                )
                upstream, downstream = directional_distances(observed, target, positions)
                _update(buckets[(split, panel, regime)], upstream, downstream)

    regime_rows: list[dict[str, object]] = []
    panel_rows: list[dict[str, object]] = []
    for split in ("validation", "private"):
        for panel in panels:
            panel_bucket = _empty_bucket()
            for regime in REGIMES:
                bucket = buckets[(split, panel, regime)]
                summary = _summarize(bucket)
                regime_rows.append(
                    {"split": split, "panel": panel, "regime": regime, **summary}
                )
                # Merge raw counters and distance chunks into the panel bucket.
                for key in (
                    "target_cells", "upstream_any", "downstream_any", "upstream_within",
                    "downstream_within", "both_within", "either_within",
                ):
                    panel_bucket[key] += bucket[key]
                panel_bucket["upstream_distances"].extend(bucket["upstream_distances"])
                panel_bucket["downstream_distances"].extend(bucket["downstream_distances"])
            panel_summary = _summarize(panel_bucket)
            geometry = geometries[panel]
            passes = (
                geometry["adjacent_spacing_max_km"] <= MAX_SPACING_KM
                and panel_summary["upstream_within_3km_share"] >= MIN_UPSTREAM_SHARE
                and panel_summary["downstream_within_3km_share"] >= MIN_DOWNSTREAM_SHARE
                and panel_summary["both_directions_within_3km_share"] >= MIN_BOTH_SHARE
                and panel_summary["either_direction_within_3km_share"] >= MIN_EITHER_SHARE
            )
            panel_rows.append(
                {
                    "split": split,
                    "panel": panel,
                    **geometry,
                    **panel_summary,
                    "passes_gate": bool(passes),
                }
            )

    output_root.mkdir(parents=True, exist_ok=True)
    regime_path = output_root / "observability_by_panel_regime.csv"
    panel_path = output_root / "observability_by_panel_split.csv"
    pd.DataFrame(regime_rows).to_csv(regime_path, index=False)
    panel_frame = pd.DataFrame(panel_rows)
    panel_frame.to_csv(panel_path, index=False)
    failures = panel_frame.loc[~panel_frame.passes_gate, [
        "split", "panel", "adjacent_spacing_max_km", "upstream_within_3km_share",
        "downstream_within_3km_share", "both_directions_within_3km_share",
        "either_direction_within_3km_share",
    ]].to_dict("records")
    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "experiment": "task1_directional_observability_preflight_v1",
        "question": "Do released scored-split inputs make both directional propagation modes observable enough to justify a switching-filter experiment?",
        "data_boundary": {
            "splits": ["validation", "private"],
            "panels": panels,
            "inputs_only": "released masked speed/flow, eligibility flags, and topology order/length",
            "unmasked_target_truth_read": False,
            "predictions_generated": False,
        },
        "method_basis": [
            {
                "source": "https://arxiv.org/abs/1608.00917",
                "constraint": "switching traffic dynamics use conservation and require bounded behavior through observable and unobservable modes",
            },
            {
                "source": "https://arxiv.org/abs/cond-mat/0210050",
                "constraint": "free-flow information propagates downstream, congested perturbations upstream, and reported robustness assumes neighboring detector spacing no more than 3 km",
            },
        ],
        "preregistered_gate": {
            "maximum_adjacent_released_link_spacing_km": MAX_SPACING_KM,
            "minimum_upstream_within_3km_share_each_panel_split": MIN_UPSTREAM_SHARE,
            "minimum_downstream_within_3km_share_each_panel_split": MIN_DOWNSTREAM_SHARE,
            "minimum_both_directions_within_3km_share_each_panel_split": MIN_BOTH_SHARE,
            "minimum_either_direction_within_3km_share_each_panel_split": MIN_EITHER_SHARE,
            "all_panel_splits_must_pass": True,
        },
        "summary": {
            "panel_splits": int(len(panel_frame)),
            "panel_splits_passed": int(panel_frame.passes_gate.sum()),
            "minimum_upstream_within_3km_share": float(panel_frame.upstream_within_3km_share.min()),
            "minimum_downstream_within_3km_share": float(panel_frame.downstream_within_3km_share.min()),
            "minimum_both_directions_within_3km_share": float(panel_frame.both_directions_within_3km_share.min()),
            "minimum_either_direction_within_3km_share": float(panel_frame.either_direction_within_3km_share.min()),
            "maximum_adjacent_spacing_km": float(panel_frame.adjacent_spacing_max_km.max()),
            "failures": failures,
        },
        "organizer_only_metrics": {"S_state": None, "S_LWR": None, "S_physics": None},
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {"corridors_manifest_sha256": _sha256(manifest_path)},
        "outputs": {
            regime_path.name: _sha256(regime_path),
            panel_path.name: _sha256(panel_path),
        },
        "decision": "CONTINUE_TO_ONE_PANEL_FILTER" if not failures else "STOP_DIRECTIONAL_SWITCHING_FAMILY",
    }
    receipt_path = output_root / "task1_directional_observability_receipt.json"
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
