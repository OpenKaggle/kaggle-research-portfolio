#!/usr/bin/env python3
"""Build the owned Stage2 feature cache directly from organizer raw sensors.

The cache schema is intentionally identical to ``nonvisual_features.npz``.  Unit
discovery and QA matching are name-agnostic, and every selected raw unit is
validated before any output is committed.  Organizer header-only IMU/radar CSVs
remain valid representations of an empty detection stream.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import socket
import time
import zipfile
from pathlib import Path, PurePosixPath

import numpy as np
import pandas as pd

from extract_nonvisual_features import extract_imu, extract_radar, extract_skeleton


MODALITIES = ("IMU", "Radar", "Skeleton")
VIDEO_MODALITIES = {"depth", "color", "rgb", "ir", "infrared"}
EXPECTED_WIDTHS = {"imu": 655, "radar": 84, "skeleton": 650}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def install_network_block() -> dict[str, object]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    original_socket = socket.socket

    class BlockedSocket(original_socket):
        def connect(self, address: object) -> None:
            raise RuntimeError(f"Network disabled for owned raw extraction: {address}")

        def connect_ex(self, address: object) -> int:
            raise RuntimeError(f"Network disabled for owned raw extraction: {address}")

    def blocked_connection(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network disabled for owned raw extraction")

    socket.socket = BlockedSocket
    socket.create_connection = blocked_connection
    try:
        socket.create_connection(("example.invalid", 443), timeout=0.01)
        probe_blocked = False
    except RuntimeError:
        probe_blocked = True
    if not probe_blocked:
        raise RuntimeError("Network isolation probe unexpectedly succeeded")
    return {
        "hf_hub_offline": os.environ["HF_HUB_OFFLINE"],
        "transformers_offline": os.environ["TRANSFORMERS_OFFLINE"],
        "socket_probe_blocked": probe_blocked,
    }


def normalized(value: str) -> str:
    return str(PurePosixPath(str(value).replace("\\", "/").strip("/")))


def clip_base(value: str) -> str:
    parts = list(PurePosixPath(normalized(value)).parts)
    if parts and PurePosixPath(parts[-1]).suffix:
        parts.pop()
    if parts and parts[-1].lower() in VIDEO_MODALITIES:
        parts.pop()
    if not parts:
        raise ValueError(f"Cannot derive clip key from path: {value!r}")
    return "/".join(parts)


def discover_units(sensor_root: Path) -> dict[str, Path]:
    if not sensor_root.is_dir():
        raise ValueError(f"Sensor root is not a directory: {sensor_root}")
    if sensor_root.is_symlink():
        raise ValueError("Sensor root may not be a symlink")
    candidates: dict[str, Path] = {}
    for modality in MODALITIES:
        for folder in sorted(sensor_root.rglob(modality)):
            if not folder.is_dir() or folder.is_symlink():
                continue
            unit_dir = folder.parent
            unit = normalized(str(unit_dir.relative_to(sensor_root)))
            previous = candidates.get(unit)
            if previous is not None and previous != unit_dir:
                raise ValueError(f"Duplicate discovered unit: {unit}")
            candidates[unit] = unit_dir
    return dict(sorted(candidates.items()))


def resolve_unit(path: str, available: set[str]) -> str | None:
    base = clip_base(path)
    matches: list[tuple[int, str]] = []
    for unit in available:
        forms = {unit}
        parts = unit.split("/")
        if parts and parts[0].lower() in {"testing", "training"} and len(parts) > 1:
            forms.add("/".join(parts[1:]))
        if any(base == form or base.endswith("/" + form) or form.endswith("/" + base) for form in forms):
            matches.append((max(len(form) for form in forms if base == form or base.endswith("/" + form) or form.endswith("/" + base)), unit))
    if not matches:
        return None
    longest = max(length for length, _ in matches)
    winners = sorted(unit for length, unit in matches if length == longest)
    if len(winners) != 1:
        raise ValueError(f"Ambiguous raw-unit match for {path!r}: {winners}")
    return winners[0]


def load_manifest(path: Path | None) -> dict[str, set[str]] | None:
    if path is None:
        return None
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if not {"unit", "modalities"}.issubset(frame.columns) or frame["unit"].duplicated().any():
        raise ValueError("Raw manifest schema or duplicate-unit invariant failed")
    output: dict[str, set[str]] = {}
    for _, row in frame.iterrows():
        declared = {item.strip() for item in row["modalities"].split(";") if item.strip()}
        if not declared or not declared.issubset(MODALITIES):
            raise ValueError(f"Invalid modality declaration for {row['unit']!r}: {sorted(declared)}")
        output[normalized(row["unit"])] = declared
    return output


def _strict_csv(path: Path, minimum_columns: int, modality: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Corrupt {modality} CSV: {path}") from exc
    if frame.shape[1] < minimum_columns:
        raise ValueError(f"Corrupt {modality} schema ({frame.shape[1]} columns): {path}")
    if 0 < len(frame) < 2:
        raise ValueError(f"Short {modality} stream ({len(frame)} row): {path}")
    return frame


def _valid_pose(payload: object) -> bool:
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        if not isinstance(item, dict) or "keypoints" not in item:
            continue
        try:
            keypoints = np.asarray(item["keypoints"], dtype=np.float64)
            scores = np.asarray(item.get("keypoint_scores", np.ones(17)), dtype=np.float64).reshape(-1)
        except (TypeError, ValueError):
            continue
        if keypoints.shape == (17, 3) and scores.shape == (17,):
            return True
    return False


def validate_unit(unit: str, unit_dir: Path, declared: set[str]) -> list[dict[str, object]]:
    inventory: list[dict[str, object]] = []
    for path in sorted(unit_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink rejected in selected raw unit {unit}: {path}")
    top = sorted(unit_dir.iterdir(), key=lambda item: item.name)
    if any(not item.is_dir() or item.name not in MODALITIES for item in top):
        extras = [item.name for item in top if not item.is_dir() or item.name not in MODALITIES]
        raise ValueError(f"Extra raw entry in {unit}: {extras}")
    actual = {item.name for item in top}
    if actual != declared:
        raise ValueError(f"Declared/actual modalities differ for {unit}: declared={sorted(declared)} actual={sorted(actual)}")

    if "IMU" in declared:
        folder = unit_dir / "IMU"
        files = sorted(folder.iterdir(), key=lambda item: item.name)
        if not files or any(not path.is_file() or path.suffix.lower() != ".csv" for path in files):
            raise ValueError(f"Missing or extra IMU file in {unit}")
        for path in files:
            _strict_csv(path, 18, "IMU")

    if "Radar" in declared:
        folder = unit_dir / "Radar"
        files = sorted(folder.iterdir(), key=lambda item: item.name)
        if [path.name for path in files] != ["Radar.csv"] or not files[0].is_file():
            raise ValueError(f"Missing or extra radar file in {unit}")
        _strict_csv(files[0], 9, "radar")

    if "Skeleton" in declared:
        folder = unit_dir / "Skeleton"
        if [path.name for path in sorted(folder.iterdir(), key=lambda item: item.name)] != ["predictions"]:
            raise ValueError(f"Missing or extra skeleton entry in {unit}")
        prediction_dir = folder / "predictions"
        paths = sorted(prediction_dir.iterdir(), key=lambda item: item.name)
        if len(paths) < 2 or any(not path.is_file() or path.suffix.lower() != ".json" for path in paths):
            raise ValueError(f"Short, missing, or extra skeleton stream in {unit}: {len(paths)} files")
        valid = 0
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Corrupt skeleton JSON: {path}") from exc
            if not _valid_pose(payload):
                raise ValueError(f"Invalid skeleton payload: {path}")
            valid += 1
        if valid < 2:
            raise ValueError(f"Short skeleton pose stream in {unit}: {valid} valid frames")

    for path in sorted(unit_dir.rglob("*")):
        if path.is_file():
            inventory.append(
                {
                    "unit": unit,
                    "path": normalized(str(path.relative_to(unit_dir))),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return inventory


def deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ("units", "imu", "radar", "skeleton"):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, payload.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(buffer.getvalue())
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sensor-root", type=Path, required=True)
    parser.add_argument("--input-qa", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=None, help="Defaults to sensor-root/manifest_nonvisual.csv when present")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-all-clips", action="store_true")
    parser.add_argument("--require-manifest", action="store_true")
    parser.add_argument(
        "--allow-manifest-unlisted-clips-as-all-missing",
        action="store_true",
        help="Allow QA clips absent from both the raw tree and manifest as explicit all-sensor-missing clips",
    )
    args = parser.parse_args()
    started = time.perf_counter()
    network = install_network_block()
    sensor_root = args.sensor_root.resolve()
    manifest_path = args.manifest
    if manifest_path is None and (sensor_root / "manifest_nonvisual.csv").is_file():
        manifest_path = sensor_root / "manifest_nonvisual.csv"
    if args.require_manifest and manifest_path is None:
        raise ValueError("Required raw manifest is missing")
    if manifest_path is not None:
        manifest_path = manifest_path.resolve()

    qa = pd.read_csv(args.input_qa, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if not {"qa_id", "path"}.issubset(qa.columns) or qa["qa_id"].duplicated().any() or not len(qa):
        raise ValueError("Input QA schema/ID invariant failed")
    discovered = discover_units(sensor_root)
    manifest = load_manifest(manifest_path)
    by_clip: dict[str, str | None] = {}
    declared_by_clip: dict[str, str | None] = {}
    for path in sorted(set(qa["path"])):
        by_clip[path] = resolve_unit(path, set(discovered))
        declared_by_clip[path] = resolve_unit(path, set(manifest)) if manifest is not None else None
    missing_declared = [
        {"path": path, "declared_unit": declared_by_clip[path]}
        for path, unit in by_clip.items()
        if unit is None and declared_by_clip[path] is not None
    ]
    if missing_declared:
        raise ValueError(f"Manifest-declared raw unit is missing for {len(missing_declared)} QA clips")
    missing_clips = sorted(path for path, unit in by_clip.items() if unit is None)
    if args.require_all_clips and missing_clips:
        raise ValueError(f"No raw sensor unit for {len(missing_clips)} QA clips")
    if missing_clips and not args.allow_manifest_unlisted_clips_as_all_missing:
        raise ValueError(
            f"No raw sensor unit or manifest declaration for {len(missing_clips)} QA clips; "
            "explicit all-missing authorization required"
        )
    selected = sorted({unit for unit in by_clip.values() if unit is not None})
    if not selected:
        raise ValueError("No QA clip matched a discovered raw sensor unit")

    records: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    inventory: list[dict[str, object]] = []
    for unit in selected:
        actual = {item.name for item in discovered[unit].iterdir() if item.is_dir() and item.name in MODALITIES}
        if manifest is not None:
            if unit not in manifest:
                raise ValueError(f"Discovered selected unit absent from raw manifest: {unit}")
            declared = manifest[unit]
        else:
            declared = actual
        inventory.extend(validate_unit(unit, discovered[unit], declared))
        records[unit] = (
            extract_imu(discovered[unit]),
            extract_radar(discovered[unit]),
            extract_skeleton(discovered[unit]),
        )

    arrays = {
        "units": np.asarray(selected),
        "imu": np.stack([records[unit][0] for unit in selected]).astype(np.float32),
        "radar": np.stack([records[unit][1] for unit in selected]).astype(np.float32),
        "skeleton": np.stack([records[unit][2] for unit in selected]).astype(np.float32),
    }
    for name, width in EXPECTED_WIDTHS.items():
        if arrays[name].shape != (len(selected), width):
            raise ValueError(f"Feature schema drift for {name}: {arrays[name].shape}")
    inventory_bytes = (json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n").encode()
    deterministic_npz(args.output, arrays)
    report = {
        "experiment": "stage2_native_owned_raw_features_v1",
        "network_isolation": network,
        "input_qa_sha256": sha256(args.input_qa),
        "manifest_sha256": sha256(manifest_path) if manifest_path is not None else None,
        "raw_inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "raw_files": len(inventory),
        "discovered_units": len(discovered),
        "selected_units": len(selected),
        "unique_qa_clips": int(qa["path"].nunique()),
        "unmatched_qa_clips": len(missing_clips),
        "unmatched_clip_paths": missing_clips,
        "manifest_unlisted_clips_treated_as_all_sensor_missing": len(missing_clips),
        "manifest_required": args.require_manifest,
        "manifest_unlisted_all_missing_authorized": args.allow_manifest_unlisted_clips_as_all_missing,
        "feature_shapes": {name: list(arrays[name].shape) for name in EXPECTED_WIDTHS},
        "finite_rows": {name: int(np.isfinite(arrays[name]).any(axis=1).sum()) for name in EXPECTED_WIDTHS},
        "output_sha256": sha256(args.output),
        "code_sha256": sha256(Path(__file__)),
        "runtime_seconds": time.perf_counter() - started,
        "labels_read": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
