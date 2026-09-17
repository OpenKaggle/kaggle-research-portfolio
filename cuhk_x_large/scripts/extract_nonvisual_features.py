#!/usr/bin/env python3
"""Extract fixed-length IMU, radar, and skeleton features from the official supplement.

The raw competition data remain under the ignored ``data/raw`` tree.  This script
writes only derived feature caches under ``cache`` and a non-sensitive aggregate
summary under ``reports``.  It never reads the test target column.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_ARCHIVE_SHA256 = "72f34e9f0005d2ee0fefe9a7687bd54fa6dbdf171b6112132523085fa7475afb"
DEVICES = ("WTC", "WTRA", "WTLA", "WTRL", "WTLL")
IMU_CHANNELS = tuple(range(2, 18))


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def finite(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return np.where(np.isfinite(values), values, np.nan)


def column_stats(values: np.ndarray) -> np.ndarray:
    """Seven robust distribution/kinematic statistics per column."""
    x = finite(values)
    if x.ndim == 1:
        x = x[:, None]
    width = x.shape[1]
    if len(x) == 0:
        return np.full(width * 7, np.nan, dtype=np.float32)
    with np.errstate(all="ignore"):
        mean = np.nanmean(x, axis=0)
        std = np.nanstd(x, axis=0)
        q10 = np.nanquantile(x, 0.10, axis=0)
        q90 = np.nanquantile(x, 0.90, axis=0)
        rms = np.sqrt(np.nanmean(x * x, axis=0))
        if len(x) > 1:
            delta = np.diff(x, axis=0)
            delta_abs = np.nanmean(np.abs(delta), axis=0)
            delta_std = np.nanstd(delta, axis=0)
        else:
            delta_abs = np.full(width, np.nan)
            delta_std = np.full(width, np.nan)
    return np.concatenate((mean, std, q10, q90, rms, delta_abs, delta_std)).astype(np.float32)


def spectral_stats(values: np.ndarray) -> np.ndarray:
    """Dominant normalized frequency, dominance, entropy per signal."""
    x = finite(values)
    if x.ndim == 1:
        x = x[:, None]
    out: list[float] = []
    for column in x.T:
        column = column[np.isfinite(column)]
        if len(column) < 8:
            out.extend((math.nan, math.nan, math.nan))
            continue
        column = column - column.mean()
        power = np.abs(np.fft.rfft(column)) ** 2
        power = power[1:]
        total = float(power.sum())
        if not np.isfinite(total) or total <= 1e-12:
            out.extend((0.0, 0.0, 0.0))
            continue
        probability = power / total
        peak = int(np.argmax(power))
        dominant_frequency = (peak + 1) / max(1, len(column) // 2)
        dominance = float(probability[peak])
        entropy = float(-(probability * np.log(probability + 1e-12)).sum() / np.log(len(probability)))
        out.extend((dominant_frequency, dominance, entropy))
    return np.asarray(out, dtype=np.float32)


def empty_imu() -> np.ndarray:
    # 16 channels × 7 stats + acceleration/gyro 6 channels × 3 spectral stats,
    # one block per wearable, plus per-device row counts.
    return np.full(len(DEVICES) * (16 * 7 + 6 * 3 + 1), np.nan, dtype=np.float32)


def extract_imu(unit_dir: Path) -> np.ndarray:
    files = sorted((unit_dir / "IMU").glob("*.csv"))
    if not files:
        return empty_imu()
    frames = []
    for path in files:
        try:
            frames.append(pd.read_csv(path, encoding="utf-8-sig", low_memory=False))
        except (OSError, UnicodeDecodeError, pd.errors.ParserError):
            continue
    if not frames:
        return empty_imu()
    data = pd.concat(frames, ignore_index=True, sort=False)
    if data.shape[1] < 18:
        return empty_imu()
    time_values = data.iloc[:, 0].astype(str).to_numpy()
    device_values = data.iloc[:, 1].astype(str).str.extract(r"^([A-Za-z]+)", expand=False).str.upper().to_numpy()
    numeric = data.iloc[:, list(IMU_CHANNELS)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    blocks = []
    for device in DEVICES:
        mask = device_values == device
        if not mask.any():
            blocks.append(np.full(16 * 7 + 6 * 3 + 1, np.nan, dtype=np.float32))
            continue
        order = np.argsort(time_values[mask], kind="stable")
        values = numeric[mask][order]
        blocks.append(
            np.concatenate(
                (
                    column_stats(values),
                    spectral_stats(values[:, :6]),
                    np.asarray([len(values)], dtype=np.float32),
                )
            )
        )
    return np.concatenate(blocks).astype(np.float32)


def empty_radar() -> np.ndarray:
    # Six detection columns × seven stats, then frame-level count stats and five bins.
    return np.full(42 + 7 + 5 * 7, np.nan, dtype=np.float32)


def extract_radar(unit_dir: Path) -> np.ndarray:
    path = unit_dir / "Radar" / "Radar.csv"
    if not path.exists():
        return empty_radar()
    try:
        data = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError):
        return empty_radar()
    if len(data) == 0 or data.shape[1] < 9:
        # Header-only radar files are present modalities with zero detections.
        output = empty_radar()
        output[42] = 0.0
        return output
    numeric = data.iloc[:, 3:9].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=np.float64)
    frame = pd.to_numeric(data.iloc[:, 1], errors="coerce").to_numpy()
    base = column_stats(numeric)
    valid_frame = np.isfinite(frame)
    if not valid_frame.any():
        return np.concatenate((base, np.full(7 + 35, np.nan, dtype=np.float32)))
    unique = np.unique(frame[valid_frame])
    rows = []
    for value in unique:
        subset = numeric[frame == value]
        rows.append(np.concatenate(([len(subset)], np.nanmean(subset, axis=0))))
    per_frame = np.asarray(rows, dtype=np.float64)
    count_stats = column_stats(per_frame[:, 0])
    bins = []
    for indices in np.array_split(np.arange(len(per_frame)), 5):
        bins.append(np.nanmean(per_frame[indices], axis=0) if len(indices) else np.full(7, np.nan))
    return np.concatenate((base, count_stats, np.concatenate(bins))).astype(np.float32)


_FRAME_NUMBER = re.compile(r"_(\d+)\.json$")


def empty_skeleton() -> np.ndarray:
    # centered/scaled xyz × four stats; velocity × three stats; five temporal bins;
    # confidence mean/std; clip-level frame/presence summaries.
    return np.full(17 * 3 * 4 + 17 * 3 * 3 + 5 * 17 * 3 + 17 * 2 + 4, np.nan, dtype=np.float32)


def frame_number(path: Path) -> int:
    match = _FRAME_NUMBER.search(path.name)
    return int(match.group(1)) if match else -1


def extract_skeleton(unit_dir: Path) -> np.ndarray:
    paths = sorted((unit_dir / "Skeleton" / "predictions").glob("*.json"), key=frame_number)
    if not paths:
        return empty_skeleton()
    poses = []
    scores = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, list) and payload:
            candidates = [item for item in payload if isinstance(item, dict) and "keypoints" in item]
            if not candidates:
                continue
            item = max(candidates, key=lambda candidate: float(np.nanmean(candidate.get("keypoint_scores", [0]))))
        elif isinstance(payload, dict) and "keypoints" in payload:
            item = payload
        else:
            continue
        keypoints = np.asarray(item.get("keypoints"), dtype=np.float64)
        confidence = np.asarray(item.get("keypoint_scores", np.ones(17)), dtype=np.float64).reshape(-1)
        if keypoints.shape != (17, 3) or confidence.shape[0] != 17:
            continue
        poses.append(keypoints)
        scores.append(confidence)
    if not poses:
        return empty_skeleton()
    xyz = np.asarray(poses, dtype=np.float64)
    confidence = np.asarray(scores, dtype=np.float64)
    # COCO hips are 11/12. Center each frame and normalize by robust body spread.
    root = (xyz[:, 11] + xyz[:, 12]) / 2.0
    centered = xyz - root[:, None, :]
    spread = np.sqrt(np.nanmean(centered * centered, axis=(1, 2)))
    stable_spread = np.nanmedian(spread[spread > 1e-6]) if np.any(spread > 1e-6) else 1.0
    spread = np.where(spread > 1e-6, spread, stable_spread)
    normalized = centered / spread[:, None, None]
    flat = normalized.reshape(len(normalized), -1)
    with np.errstate(all="ignore"):
        position = np.concatenate(
            (
                np.nanmean(flat, axis=0),
                np.nanstd(flat, axis=0),
                np.nanquantile(flat, 0.10, axis=0),
                np.nanquantile(flat, 0.90, axis=0),
            )
        )
        if len(flat) > 1:
            velocity = np.diff(flat, axis=0)
            velocity_stats = np.concatenate(
                (np.nanmean(np.abs(velocity), axis=0), np.nanstd(velocity, axis=0), np.nanmax(np.abs(velocity), axis=0))
            )
        else:
            velocity_stats = np.full(flat.shape[1] * 3, np.nan)
        bins = []
        for indices in np.array_split(np.arange(len(flat)), 5):
            bins.append(np.nanmean(flat[indices], axis=0) if len(indices) else np.full(flat.shape[1], np.nan))
        confidence_stats = np.concatenate((np.nanmean(confidence, axis=0), np.nanstd(confidence, axis=0)))
    clip_stats = np.asarray(
        [len(paths), len(poses), len(poses) / max(1, len(paths)), stable_spread], dtype=np.float32
    )
    return np.concatenate((position, velocity_stats, np.concatenate(bins), confidence_stats, clip_stats)).astype(np.float32)


def extract_one(root: Path, unit: str) -> tuple[str, np.ndarray, np.ndarray, np.ndarray]:
    unit_dir = root / unit
    return unit, extract_imu(unit_dir), extract_radar(unit_dir), extract_skeleton(unit_dir)


def main() -> None:
    campaign_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sensor-root",
        type=Path,
        default=campaign_root / "data/raw/nonvisual/LMT_(IMU,Radar,Skeleton)",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=campaign_root / "data/raw/media/LMT_(IMU,Radar,Skeleton).zip",
    )
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--output", type=Path, default=campaign_root / "cache/nonvisual_features.npz")
    parser.add_argument("--summary", type=Path, default=campaign_root / "reports/nonvisual_feature_extraction.json")
    args = parser.parse_args()

    started = time.perf_counter()
    archive_hash = sha256(args.archive)
    if archive_hash != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(f"Official archive hash mismatch: {archive_hash}")
    manifest_path = args.sensor_root / "manifest_nonvisual.csv"
    manifest = pd.read_csv(manifest_path, encoding="utf-8-sig")
    if manifest["unit"].duplicated().any():
        raise ValueError("Duplicate units in official nonvisual manifest")
    units = manifest["unit"].astype(str).tolist()

    records: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(extract_one, args.sensor_root, unit): unit for unit in units}
        for index, future in enumerate(as_completed(futures), start=1):
            unit, imu, radar, skeleton = future.result()
            records[unit] = (imu, radar, skeleton)
            if index % 200 == 0 or index == len(units):
                print(f"extracted {index}/{len(units)}", flush=True)

    ordered = sorted(records)
    imu = np.stack([records[unit][0] for unit in ordered])
    radar = np.stack([records[unit][1] for unit in ordered])
    skeleton = np.stack([records[unit][2] for unit in ordered])
    # The official README defines coverage as directory/file presence. Some files
    # are intentionally header-only, so record numerical usability separately.
    presence_patterns = {
        "IMU": ("IMU", "*.csv"),
        "Radar": ("Radar", "Radar.csv"),
        "Skeleton": ("Skeleton", "predictions/*.json"),
    }
    actual_presence = {}
    for modality, (folder, pattern) in presence_patterns.items():
        actual_presence[modality] = sum(bool(list((args.sensor_root / unit / folder).glob(pattern))) for unit in ordered)
        declared = int(manifest["modalities"].str.contains(modality, na=False).sum())
        if actual_presence[modality] != declared:
            raise ValueError(
                f"{modality} file-presence coverage differs: actual={actual_presence[modality]} declared={declared}"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, units=np.asarray(ordered), imu=imu, radar=radar, skeleton=skeleton)
    summary = {
        "archive_sha256": archive_hash,
        "archive_bytes": args.archive.stat().st_size,
        "manifest_sha256": sha256(manifest_path),
        "units": len(ordered),
        "train_units": sum(unit.startswith("Training/") for unit in ordered),
        "test_units": sum(unit.startswith("Testing/") for unit in ordered),
        "feature_shapes": {
            "imu": list(imu.shape),
            "radar": list(radar.shape),
            "skeleton": list(skeleton.shape),
        },
        "finite_rows": {
            "imu": int(np.isfinite(imu).any(axis=1).sum()),
            "radar": int(np.isfinite(radar).any(axis=1).sum()),
            "skeleton": int(np.isfinite(skeleton).any(axis=1).sum()),
        },
        "manifest_declared_file_presence": {
            modality.lower(): int(manifest["modalities"].str.contains(modality, na=False).sum())
            for modality in presence_patterns
        },
        "verified_actual_file_presence": {
            modality.lower(): count for modality, count in actual_presence.items()
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
