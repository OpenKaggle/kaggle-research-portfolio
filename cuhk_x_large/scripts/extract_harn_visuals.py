#!/usr/bin/env python3
"""Strictly verify and extract all official HARn videos referenced by training QA."""

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


EXPECTED_ARCHIVE_BYTES = 1_956_322_919
EXPECTED_ARCHIVE_SHA256 = "a972d644c1b536f836fe7e4d97ca560e04dc75e5657927b2290a63bc6add7a25"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "data/raw/media/HARn.zip"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    output_root = root / "data/raw/visual_harn"
    manifest_path = root / "cache/harn_visual_manifest.json"
    report_path = root / "reports/harn_visual_extraction.json"
    started = time.perf_counter()

    if archive.stat().st_size != EXPECTED_ARCHIVE_BYTES:
        raise ValueError("HARn archive byte-size mismatch")
    archive_digest = sha256(archive)
    if archive_digest != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("HARn archive SHA-256 mismatch")
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    allowed_units = set(qa.loc[qa["source"] == "HARn", "path"])
    manifest = []
    with ZipFile(archive) as bundle:
        bad_member = bundle.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP integrity failure at {bad_member}")
        for info in bundle.infolist():
            pure = PurePosixPath(info.filename)
            parts = pure.parts
            if pure.is_absolute() or ".." in parts:
                raise ValueError(f"Unsafe ZIP path: {info.filename}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"Symlink is not allowed: {info.filename}")
            is_video = len(parts) == 6 and parts[0] == "HARn" and info.filename.lower().endswith(".mp4")
            unit = "/".join(parts[:4]) if is_video else ""
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
                    "modality": parts[4],
                    "bytes": size,
                    "crc32": f"{info.CRC:08x}",
                    "sha256": digest.hexdigest(),
                }
            )

    extracted_units = {item["unit"] for item in manifest}
    missing_units = sorted(allowed_units - extracted_units)
    if missing_units:
        raise ValueError(f"Missing videos for {len(missing_units)} official HARn units: {missing_units[:10]}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report = {
        "archive": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": archive_digest,
        "zip_integrity": "all members passed CRC test",
        "qa_units": len(allowed_units),
        "extracted_units": len(extracted_units),
        "extracted_files": len(manifest),
        "extracted_bytes": sum(item["bytes"] for item in manifest),
        "actions": dict(sorted(Counter(item["unit"].split("/")[1] for item in manifest).items())),
        "subjects": dict(sorted(Counter(item["unit"].split("/")[2] for item in manifest).items())),
        "modalities": dict(sorted(Counter(item["modality"] for item in manifest).items())),
        "manifest_sha256": sha256(manifest_path),
        "training_qa_sha256": sha256(qa_path),
        "code_sha256": sha256(Path(__file__)),
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
