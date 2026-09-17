#!/usr/bin/env python3
"""Recover complete labeled videos from a verified prefix of a standard ZIP file.

This is intentionally strict: it parses local file headers, stops at the first
incomplete entry, verifies uncompressed length and CRC32, and rejects unsafe paths.
It is useful while the official Google Drive mirror is temporarily quota-limited.
"""

from __future__ import annotations

import argparse
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=root / "data/raw/media/HARn.zip")
    parser.add_argument("--train", type=Path, default=root / "data/raw/kaggle/training_qa.csv")
    parser.add_argument("--output-root", type=Path, default=root / "data/raw/visual_prefix")
    parser.add_argument("--manifest", type=Path, default=root / "cache/partial_visual_manifest.json")
    parser.add_argument("--summary", type=Path, default=root / "reports/partial_visual_extraction.json")
    args = parser.parse_args()

    started = time.perf_counter()
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    allowed_units = set(train.loc[train["source"] == "HARn", "path"])
    archive_bytes = args.archive.stat().st_size
    extracted = []
    incomplete = None
    complete_archive_entries = 0
    with args.archive.open("rb") as source:
        while source.tell() + LOCAL_FILE_HEADER.size <= archive_bytes:
            header_offset = source.tell()
            raw_header = source.read(LOCAL_FILE_HEADER.size)
            signature, _, flag, method, _, _, crc, compressed_size, raw_size, name_len, extra_len = (
                LOCAL_FILE_HEADER.unpack(raw_header)
            )
            if signature != LOCAL_SIGNATURE:
                break
            if flag & 0x08:
                raise ValueError("Streaming data descriptors are not supported")
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
            complete_archive_entries += int(compressed_size > 0)
            parts = PurePosixPath(name).parts
            is_video = len(parts) == 6 and parts[0] == "HARn" and name.endswith(".mp4")
            unit = "/".join(parts[:4]) if is_video else ""
            if not is_video or unit not in allowed_units:
                source.seek(compressed_size, 1)
                continue
            compressed = source.read(compressed_size)
            if method == 0:
                payload = compressed
            elif method == 8:
                payload = zlib.decompress(compressed, -zlib.MAX_WBITS)
            else:
                raise ValueError(f"Unsupported compression method {method} for {name}")
            if len(payload) != raw_size:
                raise ValueError(f"Uncompressed size mismatch for {name}")
            if (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
                raise ValueError(f"CRC mismatch for {name}")
            relative = Path(*parts)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Unsafe ZIP path {name}")
            destination = args.output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            extracted.append(
                {
                    "path": name,
                    "unit": unit,
                    "modality": parts[4],
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(extracted, indent=2) + "\n", encoding="utf-8")
    units = {item["unit"] for item in extracted}
    actions = Counter(item["unit"].split("/")[1] for item in extracted)
    users = Counter(item["unit"].split("/")[2] for item in extracted)
    modalities = Counter(item["modality"] for item in extracted)
    summary = {
        "archive_prefix_bytes": archive_bytes,
        "archive_prefix_sha256": sha256(args.archive),
        "complete_archive_file_entries_before_boundary": complete_archive_entries,
        "first_incomplete_entry": incomplete,
        "selection": "HARn units referenced by organizer training_qa.csv only",
        "extracted_files": len(extracted),
        "extracted_units": len(units),
        "extracted_bytes": sum(item["bytes"] for item in extracted),
        "actions": dict(sorted(actions.items())),
        "subjects": dict(sorted(users.items())),
        "modalities": dict(sorted(modalities.items())),
        "manifest_sha256": sha256(args.manifest),
        "runtime_seconds": time.perf_counter() - started,
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
