#!/usr/bin/env python3
"""Recover CRC-checked labeled HAU videos from a verified official ZIP prefix."""

from __future__ import annotations

import hashlib
import json
import struct
import time
import zlib
from collections import Counter
from pathlib import Path, PurePosixPath

import pandas as pd


LOCAL_FILE_HEADER = struct.Struct("<IHHHHHIIIHH")
LOCAL_SIGNATURE = 0x04034B50
EXPECTED_FINAL_BYTES = 3_674_779_437


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    archive = root / "data/raw/media/HAU.zip"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    output_root = root / "data/raw/visual_hau_prefix"
    manifest_path = root / "cache/partial_hau_visual_manifest.json"
    report_path = root / "reports/partial_hau_visual_extraction.json"
    started = time.perf_counter()

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    hau = qa[qa["source"] == "HAU"].copy()
    allowed_units = set(hau["path"])
    archive_bytes = archive.stat().st_size
    if archive_bytes >= EXPECTED_FINAL_BYTES:
        raise ValueError("Archive is complete; use a full ZIP extractor")
    extracted = []
    incomplete = None
    complete_file_entries = 0
    with archive.open("rb") as source:
        while source.tell() + LOCAL_FILE_HEADER.size <= archive_bytes:
            header_offset = source.tell()
            values = LOCAL_FILE_HEADER.unpack(source.read(LOCAL_FILE_HEADER.size))
            signature, _, flag, method, _, _, crc, compressed_size, raw_size, name_len, extra_len = values
            if signature != LOCAL_SIGNATURE:
                break
            if flag & 0x08:
                raise ValueError("Unexpected streaming data descriptor in HAU archive")
            name = source.read(name_len).decode("utf-8")
            source.seek(extra_len, 1)
            data_offset = source.tell()
            if data_offset + compressed_size > archive_bytes:
                incomplete = {
                    "name": name,
                    "header_offset": header_offset,
                    "data_offset": data_offset,
                    "compressed_size": compressed_size,
                    "available_data_bytes": archive_bytes - data_offset,
                }
                break
            complete_file_entries += int(compressed_size > 0)
            parts = PurePosixPath(name).parts
            is_video = len(parts) == 5 and parts[0] == "HAU" and name.lower().endswith(".mp4")
            unit = "/".join(parts[:3]) if is_video else ""
            if not is_video or unit not in allowed_units:
                source.seek(compressed_size, 1)
                continue
            compressed = source.read(compressed_size)
            if method == 0:
                payload = compressed
            elif method == 8:
                payload = zlib.decompress(compressed, -zlib.MAX_WBITS)
            else:
                raise ValueError(f"Unsupported compression method {method}: {name}")
            if len(payload) != raw_size or (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
                raise ValueError(f"Size/CRC mismatch: {name}")
            relative = Path(*parts)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe ZIP path: {name}")
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            extracted.append(
                {
                    "path": name,
                    "unit": unit,
                    "subject": parts[1],
                    "modality": parts[3],
                    "bytes": len(payload),
                    "crc32": f"{crc:08x}",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(extracted, indent=2) + "\n", encoding="utf-8")
    units = {item["unit"] for item in extracted}
    covered_qa = hau[hau["path"].isin(units)]
    report = {
        "archive_prefix_bytes": archive_bytes,
        "expected_final_bytes": EXPECTED_FINAL_BYTES,
        "archive_prefix_fraction": archive_bytes / EXPECTED_FINAL_BYTES,
        "archive_prefix_sha256": sha256(archive),
        "complete_file_entries_before_boundary": complete_file_entries,
        "first_incomplete_entry": incomplete,
        "selection": "HAU units referenced by organizer training_qa.csv; complete MP4 entries only",
        "extracted_units": len(units),
        "extracted_subjects": sorted({item["subject"] for item in extracted}),
        "extracted_files": len(extracted),
        "extracted_bytes": sum(item["bytes"] for item in extracted),
        "modalities": dict(sorted(Counter(item["modality"] for item in extracted).items())),
        "covered_qa_rows_by_category": dict(sorted(covered_qa["category"].value_counts().items())),
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
