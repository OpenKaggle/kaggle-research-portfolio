#!/usr/bin/env python3
"""Audit and selectively extract P2 midpoint frames from a public Kaggle ZIP.

The Kaggle copy is treated only as a transport mirror of the organizer's
CUHK-X Thermal data.  The organizer's CUHK-X License v2.0 remains binding;
third-party Kaggle metadata cannot relicense the source material.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import re
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_FILES = 201_466
EXPECTED_BYTES = 3_524_685_759
EXPECTED_CLASSES = set(range(40))
EXPECTED_SUBJECTS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24}
ROOT = ("Thermal", "Thermal")
PATH_PATTERN = re.compile(
    r"^Thermal/Thermal/(?P<label>\d+)(?:_[^/]+)?/"
    r"user(?P<subject>\d+)/(?P<clip>[^/]+)/(?P<frame>[^/]+\.(?:jpg|jpeg|png))$",
    flags=re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member(info: zipfile.ZipInfo) -> tuple[str, re.Match[str]]:
    name = info.filename
    path = PurePosixPath(name)
    if info.is_dir():
        raise ValueError("directory members are not passed to safe_member")
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe archive member: {name!r}")
    if path.as_posix() != name or tuple(path.parts[:2]) != ROOT:
        raise ValueError(f"unexpected archive root: {name!r}")
    if info.flag_bits & 0x1:
        raise ValueError(f"encrypted archive member: {name!r}")
    unix_mode = (info.external_attr >> 16) & 0o170000
    if unix_mode == 0o120000:
        raise ValueError(f"symbolic link archive member: {name!r}")
    match = PATH_PATTERN.fullmatch(name)
    if match is None:
        raise ValueError(f"unexpected Thermal path grammar: {name!r}")
    return name, match


def midpoint_indices(length: int, segments: int = 8) -> list[int]:
    if length <= 0:
        raise ValueError("empty clip")
    return [min(length - 1, ((2 * index + 1) * length) // (2 * segments)) for index in range(segments)]


def verify_existing(path: Path, info: zipfile.ZipInfo) -> bool:
    if not path.is_file() or path.stat().st_size != info.file_size:
        return False
    crc = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            crc = binascii.crc32(chunk, crc)
    return crc & 0xFFFFFFFF == info.CRC


def extract_atomic(archive: zipfile.ZipFile, info: zipfile.ZipInfo, target: Path) -> str:
    if verify_existing(target, info):
        return "reused"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".partial")
    crc = 0
    size = 0
    with archive.open(info, "r") as source, temporary.open("wb") as output:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            crc = binascii.crc32(chunk, crc)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    if size != info.file_size or crc & 0xFFFFFFFF != info.CRC:
        raise ValueError(f"size/CRC mismatch while extracting {info.filename!r}")
    os.replace(temporary, target)
    return "extracted"


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    if not args.audit_only and args.output_root is None:
        raise SystemExit("--output-root is required unless --audit-only is set")

    archive_path = args.archive.resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)

    clips: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    names: set[str] = set()
    total_bytes = 0
    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP CRC test failed at {bad_member!r}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            name, match = safe_member(info)
            if name in names:
                raise ValueError(f"duplicate archive member: {name!r}")
            names.add(name)
            label = int(match.group("label"))
            subject = int(match.group("subject"))
            if label not in EXPECTED_CLASSES or subject not in EXPECTED_SUBJECTS:
                raise ValueError(f"label/subject outside frozen schema: {name!r}")
            if info.file_size <= 0:
                raise ValueError(f"empty image member: {name!r}")
            total_bytes += info.file_size
            clips["/".join(name.split("/")[:-1])].append(info)

        labels: set[int] = set()
        subjects: set[int] = set()
        selected: list[zipfile.ZipInfo] = []
        subject_summary: dict[str, dict[str, Any]] = {}
        for key in sorted(clips):
            frames = sorted(clips[key], key=lambda item: item.filename)
            _, match = safe_member(frames[0])
            label = int(match.group("label"))
            subject = int(match.group("subject"))
            labels.add(label)
            subjects.add(subject)
            selected.extend(frames[index] for index in sorted(set(midpoint_indices(len(frames)))))
            summary = subject_summary.setdefault(
                str(subject), {"clips": 0, "frames": 0, "bytes": 0, "classes": set()}
            )
            summary["clips"] += 1
            summary["frames"] += len(frames)
            summary["bytes"] += sum(frame.file_size for frame in frames)
            summary["classes"].add(label)

        for summary in subject_summary.values():
            summary["classes"] = sorted(summary["classes"])
        selected = sorted({info.filename: info for info in selected}.values(), key=lambda item: item.filename)
        inventory_lines = "".join(
            f"{info.filename}\t{info.file_size}\t{info.CRC:08x}\n"
            for info in sorted(
                (info for entries in clips.values() for info in entries), key=lambda item: item.filename
            )
        )
        selection_lines = "".join(
            f"{info.filename}\t{info.file_size}\t{info.CRC:08x}\n" for info in selected
        )
        if len(names) != EXPECTED_FILES or total_bytes != EXPECTED_BYTES:
            raise ValueError(
                f"mirror inventory mismatch: files={len(names)} bytes={total_bytes}; "
                f"expected files={EXPECTED_FILES} bytes={EXPECTED_BYTES}"
            )
        if labels != EXPECTED_CLASSES or subjects != EXPECTED_SUBJECTS:
            raise ValueError("mirror classes/subjects differ from the official schema")

        report: dict[str, Any] = {
            "status": "AUDITED_NOT_EXTRACTED" if args.audit_only else "PENDING_EXTRACTION",
            "archive": str(archive_path),
            "archive_bytes": archive_path.stat().st_size,
            "archive_sha256": sha256_file(archive_path),
            "license_boundary": "CUHK-X License v2.0; Kaggle CC0 metadata not relied upon",
            "inventory": {
                "files": len(names),
                "bytes": total_bytes,
                "clips": len(clips),
                "classes": sorted(labels),
                "subjects": sorted(subjects),
                "sha256_name_size_crc_lines": hashlib.sha256(inventory_lines.encode()).hexdigest(),
            },
            "midpoint_8_selection": {
                "unique_files": len(selected),
                "bytes": sum(info.file_size for info in selected),
                "sha256_name_size_crc_lines": hashlib.sha256(selection_lines.encode()).hexdigest(),
            },
            "per_subject": subject_summary,
            "test_data_read": False,
            "submission_created": False,
        }
        if not args.audit_only:
            output_root = args.output_root.resolve()
            required = sum(info.file_size for info in selected)
            if os.statvfs(output_root.parent).f_bavail * os.statvfs(output_root.parent).f_frsize < required:
                raise ValueError("insufficient free space for midpoint selection")
            outcomes = {"extracted": 0, "reused": 0}
            for info in selected:
                relative = PurePosixPath(info.filename).relative_to(*ROOT)
                outcome = extract_atomic(archive, info, output_root.joinpath(*relative.parts))
                outcomes[outcome] += 1
            report["status"] = "EXTRACTED_AND_CRC_VERIFIED"
            report["output_root"] = str(output_root)
            report["outcomes"] = outcomes

    write_json_atomic(args.report.resolve(), report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
