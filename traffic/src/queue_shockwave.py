#!/usr/bin/env python3
"""Build a data-driven Task 2 queue forecast from released window histories.

This is deliberately conservative. It starts from persistence, adds robust
per-link speed extrapolation, and permits one upstream propagation step only
when the upstream link is already close to its queue threshold and slowing.
For onset windows, where the contract guarantees a future queue, it selects the
most plausible link from the current trajectory and historical recurrent risk.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd


def _parts(root: Path, splits: list[str], name: str) -> list[Path]:
    result: list[Path] = []
    for panel_dir in sorted(p for p in (root / "task2").glob("*") if p.is_dir()):
        for split in splits:
            path = panel_dir / split / name
            if path.exists():
                result.append(path)
    return result


def _read_windows(root: Path, splits: list[str]) -> pd.DataFrame:
    files = _parts(root, splits, "window_index.csv")
    if not files:
        raise FileNotFoundError(f"no Task 2 window_index.csv below {root / 'task2'}")
    frame = pd.concat([pd.read_csv(path) for path in files], ignore_index=True)
    frame["window_id"] = frame.window_id.astype(str)
    return frame


def _read_history(root: Path, splits: list[str]) -> pd.DataFrame:
    files = _parts(root, splits, "window_history.parquet")
    if not files:
        raise FileNotFoundError(f"no Task 2 window_history.parquet below {root / 'task2'}")
    columns = ["window_id", "timestamp", "link_id", "speed_kmh", "is_score_eligible"]
    frame = pd.concat([pd.read_parquet(path, columns=columns) for path in files], ignore_index=True)
    frame["window_id"] = frame.window_id.astype(str)
    frame["link_id"] = frame.link_id.astype(str)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    frame["speed_kmh"] = pd.to_numeric(frame.speed_kmh, errors="coerce")
    frame["is_score_eligible"] = frame.is_score_eligible.astype(bool)
    return frame


def _read_template(root: Path, splits: list[str]) -> pd.DataFrame:
    files = _parts(root, splits, "sample_submission_queue.csv")
    if not files:
        raise FileNotFoundError(f"no Task 2 sample_submission_queue.csv below {root / 'task2'}")
    frame = pd.concat([pd.read_csv(path) for path in files], ignore_index=True)
    frame = frame[["window_id", "timestamp", "link_id"]].copy()
    frame["window_id"] = frame.window_id.astype(str)
    frame["link_id"] = frame.link_id.astype(str)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    return frame.drop_duplicates(["window_id", "timestamp", "link_id"])


def _thresholds(root: Path, panel: str) -> dict[str, float]:
    network = root / "corridors" / panel / "network"
    links = pd.read_csv(network / "links.csv", dtype={"link_id": str})
    free_speed = pd.to_numeric(links.free_speed_kmh, errors="coerce").fillna(105.0)
    result = dict(zip(links.link_id.astype(str), (0.60 * free_speed).astype(float)))
    fd_path = network / "fd_parameters.csv"
    if fd_path.exists():
        fd = pd.read_csv(fd_path, dtype={"link_id": str})
        if "v_cut" in fd:
            valid = fd.dropna(subset=["link_id", "v_cut"])
            result.update(zip(valid.link_id.astype(str), pd.to_numeric(valid.v_cut).astype(float)))
    return result


def _raw_upstream(root: Path, panel: str) -> dict[str, list[str]]:
    path = root / "corridors" / panel / "network" / "lwr_mainline_topology.csv"
    if not path.exists():
        return {}
    topology = pd.read_csv(path, dtype=str).fillna("")
    result: dict[str, list[str]] = {}
    for row in topology.itertuples(index=False):
        result[str(row.link_id)] = [
            value.strip()
            for value in str(getattr(row, "incoming_link_ids", "")).split(";")
            if value.strip()
        ]
    return result


def nearest_observed_upstream(
    link: str, observed_links: set[str], upstream: dict[str, list[str]], max_depth: int = 8
) -> set[str]:
    """Traverse latent topology nodes until the nearest observed links appear."""
    found: set[str] = set()
    seen = {link}
    queue: deque[tuple[str, int]] = deque([(link, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for candidate in upstream.get(current, []):
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate in observed_links:
                found.add(candidate)
            else:
                queue.append((candidate, depth + 1))
    return found


def _trend_features(history: pd.DataFrame, thresholds: dict[str, float]) -> pd.DataFrame:
    rows = []
    for link, group in history.groupby("link_id", sort=False):
        group = group[group.is_score_eligible & group.speed_kmh.notna()].sort_values("timestamp")
        if group.empty:
            continue
        speeds = group.speed_kmh.to_numpy(dtype=float)
        tail = speeds[-4:]
        slope = float(np.median(np.diff(tail))) if len(tail) >= 2 else 0.0
        last = float(tail[-1])
        cut = float(thresholds.get(str(link), 63.0))
        margin = (last - cut) / max(cut, 1.0)
        cross_step = math.inf
        if last <= cut:
            cross_step = 0
        elif slope < -0.25:
            cross_step = max(1, math.ceil((last - cut) / -slope))
        rows.append(
            {
                "link_id": str(link),
                "last_speed": last,
                "slope_per_step": slope,
                "margin": margin,
                "cross_step": cross_step,
                "queue_now": last <= cut,
            }
        )
    return pd.DataFrame(rows).set_index("link_id") if rows else pd.DataFrame()


def _recurrent_risk(root: Path, panel: str, thresholds: dict[str, float]) -> dict[str, float]:
    """Learn link-level queue frequency from released, unmasked train records."""
    paths = sorted((root / "corridors" / panel / "train" / "mainline_states").glob("**/*.parquet"))
    queued: defaultdict[str, int] = defaultdict(int)
    eligible: defaultdict[str, int] = defaultdict(int)
    for path in paths:
        frame = pd.read_parquet(path, columns=["link_id", "speed_kmh", "is_score_eligible"])
        frame["link_id"] = frame.link_id.astype(str)
        speed = pd.to_numeric(frame.speed_kmh, errors="coerce")
        good = frame.is_score_eligible.astype(bool) & speed.notna()
        if not good.any():
            continue
        sample = frame.loc[good, ["link_id"]].copy()
        sample["queued"] = speed[good].to_numpy() <= sample.link_id.map(thresholds).fillna(63.0).to_numpy()
        counts = sample.groupby("link_id").queued.agg(["sum", "count"])
        for link, row in counts.iterrows():
            queued[str(link)] += int(row["sum"])
            eligible[str(link)] += int(row["count"])
    return {link: queued[link] / max(count, 1) for link, count in eligible.items()}


def forecast_window(
    history: pd.DataFrame,
    template: pd.DataFrame,
    condition: str,
    thresholds: dict[str, float],
    upstream: dict[str, list[str]],
    recurrent_risk: dict[str, float],
    onset_top_k: int = 1,
) -> pd.DataFrame:
    """Forecast one window using no future or organizer-only information."""
    features = _trend_features(history, thresholds)
    output = template[["window_id", "timestamp", "link_id"]].copy()
    output["queue_pred"] = 0
    if features.empty:
        return output

    # The public history is [T-60, T), so its last timestamp is T-5 rather than
    # the forecast origin T. Deriving the step from ``timestamp-last_history``
    # creates an off-by-one error. Rank the six template timestamps directly:
    # T+5 -> 1, ..., T+30 -> 6.
    future_times = sorted(output.timestamp.drop_duplicates())
    step_by_time = {timestamp: step for step, timestamp in enumerate(future_times, 1)}
    output["step"] = output.timestamp.map(step_by_time).astype(int)
    observed = set(features.index.astype(str))
    condition = condition.lower()

    if "onset" in condition:
        rank = features.copy()
        rank["risk"] = [recurrent_risk.get(link, 0.0) for link in rank.index]
        rank["near_score"] = np.exp(-np.maximum(rank.margin.to_numpy(dtype=float), 0.0) / 0.20)
        rank["decel_score"] = np.clip(-rank.slope_per_step.to_numpy(dtype=float) / 5.0, 0.0, 1.0)
        rank["candidate_score"] = 0.50 * rank.near_score + 0.30 * rank.decel_score + 0.20 * rank.risk
        candidates = rank.sort_values("candidate_score", ascending=False).head(onset_top_k)
        for link, row in candidates.iterrows():
            trigger = int(row.cross_step) if np.isfinite(row.cross_step) else 6
            trigger = min(6, max(3, trigger))
            mask = output.link_id.eq(str(link)) & output.step.ge(trigger)
            output.loc[mask, "queue_pred"] = 1
    else:
        # Persistence remains the low-variance anchor for ongoing windows.
        for link, row in features.iterrows():
            if bool(row.queue_now):
                output.loc[output.link_id.eq(str(link)), "queue_pred"] = 1
            elif np.isfinite(row.cross_step) and int(row.cross_step) <= 6:
                mask = output.link_id.eq(str(link)) & output.step.ge(max(2, int(row.cross_step)))
                output.loc[mask, "queue_pred"] = 1

        # One guarded shockwave step: only close, slowing upstream sensors and
        # only in the second half of the six-step horizon.
        queued_now = features.index[features.queue_now.astype(bool)].astype(str).tolist()
        for downstream in queued_now:
            for link in nearest_observed_upstream(downstream, observed, upstream):
                row = features.loc[link]
                if float(row.margin) <= 0.20 and float(row.slope_per_step) <= -0.25:
                    mask = output.link_id.eq(link) & output.step.ge(4)
                    output.loc[mask, "queue_pred"] = 1

    output["queue_pred"] = output.queue_pred.astype(int)
    return output.drop(columns=["step"])


def build_submission(root: Path, splits: list[str], output: Path, onset_top_k: int = 1) -> pd.DataFrame:
    windows = _read_windows(root, splits)
    history = _read_history(root, splits)
    template = _read_template(root, splits)
    panel_by_window = windows.set_index("window_id").panel.astype(str).to_dict()
    condition_by_window = windows.set_index("window_id").condition.astype(str).to_dict()
    panel_assets: dict[str, tuple[dict[str, float], dict[str, list[str]], dict[str, float]]] = {}
    pieces = []
    for window_id, group in history.groupby("window_id", sort=True):
        panel = panel_by_window.get(str(window_id))
        if panel is None:
            continue
        if panel not in panel_assets:
            cutoffs = _thresholds(root, panel)
            panel_assets[panel] = (cutoffs, _raw_upstream(root, panel), _recurrent_risk(root, panel, cutoffs))
        cutoffs, upstream, risk = panel_assets[panel]
        target = template[template.window_id.eq(str(window_id))].copy()
        pieces.append(
            forecast_window(
                group,
                target,
                condition_by_window.get(str(window_id), "queue_ongoing"),
                cutoffs,
                upstream,
                risk,
                onset_top_k=onset_top_k,
            )
        )
    if not pieces:
        raise RuntimeError("no Task 2 predictions were generated")
    result = pd.concat(pieces, ignore_index=True).drop_duplicates(["window_id", "timestamp", "link_id"])
    result = result.sort_values(["window_id", "timestamp", "link_id"])
    if not set(result.queue_pred.unique()).issubset({0, 1}):
        raise AssertionError("queue_pred is not binary")
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--split", action="append", choices=["train", "validation", "private"])
    parser.add_argument("--onset-top-k", type=int, default=1, choices=[1, 2])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    splits = args.split or ["validation", "private"]
    result = build_submission(args.release_root.resolve(), splits, args.output.resolve(), args.onset_top_k)
    print(f"Wrote {len(result):,} queue rows to {args.output.resolve()}")


if __name__ == "__main__":
    main()
