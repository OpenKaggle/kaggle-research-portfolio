#!/usr/bin/env python3
"""Strictly verify and extract official test videos with per-file hashes."""

from __future__ import annotations

import hashlib
import json
import stat
import time
import zlib
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pandas as pd


EXPECTED_ARCHIVE_BYTES = 1_994_984_736


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "data/raw/media/large_model_track_test.zip"
    qa_path = root / "data/raw/kaggle/test_qa.csv"
    output_root = root / "data/raw/visual_test"
    manifest_path = root / "cache/test_visual_manifest.json"
    report_path = root / "reports/test_visual_extraction.json"
    started = time.perf_counter()

    if archive.stat().st_size != EXPECTED_ARCHIVE_BYTES:
        raise ValueError(
            f"Test archive is incomplete: {archive.stat().st_size}/{EXPECTED_ARCHIVE_BYTES} bytes"
        )
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    allowed_units = {
        "/".join(PurePosixPath(path).parts[:2])
        for path in qa["path"]
        if len(PurePosixPath(path).parts) >= 2
    }
    manifest = []
    with ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP integrity failure at {bad_member}")
        for info in bundle.infolist():
            parts = PurePosixPath(info.filename).parts
            if PurePosixPath(info.filename).is_absolute() or ".." in parts:
                raise ValueError(f"Unsafe ZIP path: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Symlink is not allowed: {info.filename}")
            is_video = len(parts) == 4 and info.filename.lower().endswith(".mp4")
            unit = "/".join(parts[:2]) if is_video else ""
            if not is_video or unit not in allowed_units:
                continue
            destination = output_root.joinpath(*parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            partial = destination.with_suffix(destination.suffix + ".part")
            digest = hashlib.sha256()
            crc = 0
            size = 0
            with bundle.open(info) as source, partial.open("wb") as target:
                while chunk := source.read(1 << 20):
                    target.write(chunk)
                    digest.update(chunk)
                    crc = zlib.crc32(chunk, crc)
                    size += len(chunk)
            if size != info.file_size or (crc & 0xFFFFFFFF) != info.CRC:
                raise ValueError(f"Extracted size/CRC mismatch: {info.filename}")
            partial.replace(destination)
            manifest.append(
                {
                    "path": info.filename,
                    "unit": unit,
                    "modality": parts[2],
                    "bytes": size,
                    "crc32": f"{info.CRC:08x}",
                    "sha256": digest.hexdigest(),
                }
            )

    extracted_units = {item["unit"] for item in manifest}
    missing_units = sorted(allowed_units - extracted_units)
    if missing_units:
        raise ValueError(f"No video extracted for {len(missing_units)} test units: {missing_units[:10]}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report = {
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256(archive),
        "zip_integrity": "all members passed CRC test",
        "qa_units": len(allowed_units),
        "extracted_units": len(extracted_units),
        "extracted_files": len(manifest),
        "extracted_bytes": sum(item["bytes"] for item in manifest),
        "modalities": dict(sorted(Counter(item["modality"] for item in manifest).items())),
        "manifest_sha256": sha256(manifest_path),
        "test_qa_sha256": sha256(qa_path),
        "code_sha256": sha256(Path(__file__)),
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
