#!/usr/bin/env python3
"""Audit a public Kaggle Thermal mirror without downloading payload bytes.

The script enumerates dataset members through Kaggle's read-only API, enforces
the expected CUHK-X Thermal path grammar, and can freeze the exact eight-frame
midpoint manifest required by the preregistered P2 experiment.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from kaggle.api.kaggle_api_extended import KaggleApi


DATASET = "nimeshparmar/cuhk-thermal-dataset"
ROOT = ("Thermal", "Thermal")
PATH_PATTERN = re.compile(
    r"^Thermal/Thermal/(?P<label>\d+)(?:_[^/]+)?/"
    r"user(?P<subject>\d+)/(?P<clip>[^/]+)/(?P<frame>[^/]+\.(?:jpg|jpeg|png))$",
    flags=re.IGNORECASE,
)
TRAIN_SUBJECTS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24}


def safe_name(name: str) -> str:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe dataset member: {name!r}")
    normalized = path.as_posix()
    if normalized != name or tuple(path.parts[:2]) != ROOT:
        raise ValueError(f"unexpected dataset member root: {name!r}")
    return normalized


def midpoint_indices(length: int, segments: int = 8) -> list[int]:
    if length <= 0:
        raise ValueError("empty clip")
    return [min(length - 1, ((2 * index + 1) * length) // (2 * segments)) for index in range(segments)]


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=DATASET)
    parser.add_argument("--page-size", type=int, default=10_000)
    parser.add_argument("--output-manifest", type=Path)
    args = parser.parse_args()
    if not 1 <= args.page_size <= 500_000:
        raise SystemExit("--page-size must be within 1..500000")

    api = KaggleApi()
    api.authenticate()
    token: str | None = None
    names: set[str] = set()
    clips: dict[str, list[tuple[str, int]]] = defaultdict(list)
    total_bytes = 0
    page_count = 0
    while True:
        response = api.dataset_list_files(args.dataset, page_token=token, page_size=args.page_size)
        page_count += 1
        for member in response.files or []:
            name = safe_name(str(member.name))
            match = PATH_PATTERN.fullmatch(name)
            if match is None:
                raise ValueError(f"unexpected Thermal member grammar: {name!r}")
            label = int(match.group("label"))
            subject = int(match.group("subject"))
            if label not in range(40) or subject not in TRAIN_SUBJECTS:
                raise ValueError(f"label/subject outside frozen training schema: {name!r}")
            if name in names:
                raise ValueError(f"duplicate dataset member: {name!r}")
            names.add(name)
            size = int(member.total_bytes)
            if size <= 0:
                raise ValueError(f"empty dataset member: {name!r}")
            total_bytes += size
            clip_key = "/".join(name.split("/")[:-1])
            clips[clip_key].append((name, size))
        token = response.next_page_token or None
        if not token:
            break

    selected: list[dict[str, Any]] = []
    subject_summary: dict[str, dict[str, Any]] = {}
    for clip_key in sorted(clips):
        frames = sorted(clips[clip_key])
        match = PATH_PATTERN.fullmatch(frames[0][0])
        assert match is not None
        subject = int(match.group("subject"))
        label = int(match.group("label"))
        for index in midpoint_indices(len(frames)):
            name, size = frames[index]
            selected.append(
                {"name": name, "size": size, "clip": clip_key, "subject": subject, "label": label}
            )
        summary = subject_summary.setdefault(
            str(subject), {"clips": 0, "frames": 0, "bytes": 0, "classes": set()}
        )
        summary["clips"] += 1
        summary["frames"] += len(frames)
        summary["bytes"] += sum(size for _, size in frames)
        summary["classes"].add(label)

    for summary in subject_summary.values():
        summary["classes"] = sorted(summary["classes"])

    inventory_lines = "".join(f"{name}\t{size}\n" for name, size in sorted(
        (name, size) for frames in clips.values() for name, size in frames
    ))
    selection_lines = "".join(f"{item['name']}\t{item['size']}\n" for item in selected)
    report: dict[str, Any] = {
        "dataset": args.dataset,
        "operation": "metadata_only_no_payload_download",
        "pages": page_count,
        "inventory": {
            "files": len(names),
            "bytes": total_bytes,
            "clips": len(clips),
            "subjects": sorted(int(value) for value in subject_summary),
            "classes": sorted({item["label"] for item in selected}),
            "sha256_name_size_lines": hashlib.sha256(inventory_lines.encode()).hexdigest(),
        },
        "midpoint_8_selection": {
            "files": len(selected),
            "bytes": sum(item["size"] for item in selected),
            "sha256_name_size_lines": hashlib.sha256(selection_lines.encode()).hexdigest(),
            "members": selected,
        },
        "per_subject": subject_summary,
        "test_data_read": False,
        "submission_created": False,
    }
    if args.output_manifest:
        atomic_json(args.output_manifest.resolve(), report)
    print(json.dumps({**report, "midpoint_8_selection": {
        key: value for key, value in report["midpoint_8_selection"].items() if key != "members"
    }}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
