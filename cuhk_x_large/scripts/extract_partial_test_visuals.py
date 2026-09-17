#!/usr/bin/env python3
"""Recover complete official test videos from a verified ZIP prefix."""

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
EXPECTED_FINAL_BYTES = 1_994_984_736


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
    output_root = root / "data/raw/visual_test_prefix"
    manifest_path = root / "cache/partial_test_visual_manifest.json"
    report_path = root / "reports/partial_test_visual_extraction.json"
    started = time.perf_counter()

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    allowed_units = {"/".join(PurePosixPath(path).parts[:2]) for path in qa["path"]}
    unit_source = {
        "/".join(PurePosixPath(row.path).parts[:2]): row.source
        for row in qa[["path", "source"]].drop_duplicates().itertuples(index=False)
    }
    archive_bytes = archive.stat().st_size
    if archive_bytes >= EXPECTED_FINAL_BYTES:
        raise ValueError("Archive is complete; use extract_test_visuals.py instead")

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
            name = source.read(name_len).decode("utf-8")
            source.seek(extra_len, 1)
            data_offset = source.tell()
            parts = PurePosixPath(name).parts
            is_video = (
                len(parts) == 4
                and parts[0] == "large_model_track_test"
                and name.lower().endswith(".mp4")
            )
            unit = "/".join(parts[:2]) if is_video else ""
            wanted = is_video and unit in allowed_units

            if flag & 0x08:
                if method != 8:
                    raise ValueError(f"Unsupported streaming compression method {method}: {name}")
                decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                payload_parts = []
                calculated_crc = 0
                calculated_size = 0
                compressed_size = 0
                while not decompressor.eof and source.tell() < archive_bytes:
                    block = source.read(min(1 << 20, archive_bytes - source.tell()))
                    output = decompressor.decompress(block)
                    consumed = len(block) - len(decompressor.unused_data)
                    compressed_size += consumed
                    calculated_size += len(output)
                    calculated_crc = zlib.crc32(output, calculated_crc)
                    if wanted:
                        payload_parts.append(output)
                    if decompressor.unused_data:
                        source.seek(-len(decompressor.unused_data), 1)
                if not decompressor.eof or source.tell() + 16 > archive_bytes:
                    incomplete = {
                        "name": name,
                        "header_offset": header_offset,
                        "data_offset": data_offset,
                        "compressed_size": None,
                        "available_data_bytes": archive_bytes - data_offset,
                    }
                    break
                descriptor = source.read(16)
                descriptor_signature, crc, declared_compressed, raw_size = struct.unpack("<IIII", descriptor)
                if descriptor_signature != 0x08074B50:
                    raise ValueError(f"Missing data-descriptor signature: {name}")
                if (
                    compressed_size != declared_compressed
                    or calculated_size != raw_size
                    or (calculated_crc & 0xFFFFFFFF) != crc
                ):
                    raise ValueError(f"Streaming size/CRC mismatch: {name}")
                payload = b"".join(payload_parts) if wanted else b""
            else:
                if data_offset + compressed_size > archive_bytes:
                    incomplete = {
                        "name": name,
                        "header_offset": header_offset,
                        "data_offset": data_offset,
                        "compressed_size": compressed_size,
                        "available_data_bytes": archive_bytes - data_offset,
                    }
                    break
                compressed = source.read(compressed_size)
                if method == 0:
                    payload = compressed if wanted else b""
                elif method == 8:
                    output = zlib.decompress(compressed, -zlib.MAX_WBITS)
                    payload = output if wanted else b""
                    if len(output) != raw_size or (zlib.crc32(output) & 0xFFFFFFFF) != crc:
                        raise ValueError(f"Size/CRC mismatch: {name}")
                else:
                    raise ValueError(f"Unsupported compression method {method}: {name}")
            complete_file_entries += int(compressed_size > 0)
            if not wanted:
                continue
            if len(payload) != raw_size or (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
                raise ValueError(f"Selected payload size/CRC mismatch: {name}")
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
                    "source": unit_source[unit],
                    "modality": parts[2],
                    "bytes": len(payload),
                    "crc32": f"{crc:08x}",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(extracted, indent=2) + "\n", encoding="utf-8")
    units = {item["unit"] for item in extracted}
    report = {
        "archive_prefix_bytes": archive_bytes,
        "expected_final_bytes": EXPECTED_FINAL_BYTES,
        "archive_prefix_fraction": archive_bytes / EXPECTED_FINAL_BYTES,
        "archive_prefix_sha256": sha256(archive),
        "complete_file_entries_before_boundary": complete_file_entries,
        "first_incomplete_entry": incomplete,
        "selection": "official test units referenced by organizer test_qa.csv; complete MP4 entries only",
        "qa_units": len(allowed_units),
        "extracted_units": len(units),
        "extracted_units_by_source": dict(sorted(Counter(unit_source[unit] for unit in units).items())),
        "extracted_files": len(extracted),
        "extracted_bytes": sum(item["bytes"] for item in extracted),
        "modalities": dict(sorted(Counter(item["modality"] for item in extracted).items())),
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
