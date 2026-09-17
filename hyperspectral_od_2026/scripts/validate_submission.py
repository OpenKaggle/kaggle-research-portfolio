#!/usr/bin/env python3
"""Fail closed on the official HOD26 submission contract."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path


EXPECTED_COLUMNS = ["id", "image_id", "class_id", "confidence", "x1", "y1", "x2", "y2"]


def read_image_sizes(image_dir: Path | None) -> dict[str, tuple[int, int]]:
    if image_dir is None:
        return {}
    from PIL import Image

    sizes: dict[str, tuple[int, int]] = {}
    for path in sorted(image_dir.glob("*.png")):
        with Image.open(path) as image:
            raw_width, raw_height = image.size
        if raw_width % 4 or raw_height % 4:
            raise ValueError(f"raw mosaic is not divisible by 4: {path} {raw_width}x{raw_height}")
        sizes[path.stem] = (raw_width // 4, raw_height // 4)
    return sizes


def validate(path: Path, image_dir: Path | None = None, require_all_images: bool = False) -> dict[str, object]:
    sizes = read_image_sizes(image_dir)
    seen_ids: set[int] = set()
    seen_images: Counter[str] = Counter()
    row_count = 0

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(f"header mismatch: expected {EXPECTED_COLUMNS}, got {reader.fieldnames}")

        for line_no, row in enumerate(reader, start=2):
            row_count += 1
            try:
                row_id = int(row["id"])
                image_id = row["image_id"].strip()
                class_id = int(row["class_id"])
                confidence = float(row["confidence"])
                x1, y1, x2, y2 = (float(row[key]) for key in ("x1", "y1", "x2", "y2"))
            except Exception as exc:
                raise ValueError(f"line {line_no}: parse failure: {exc}") from exc

            if row_id in seen_ids:
                raise ValueError(f"line {line_no}: duplicate id {row_id}")
            seen_ids.add(row_id)
            if not image_id:
                raise ValueError(f"line {line_no}: empty image_id")
            if not 0 <= class_id <= 17:
                raise ValueError(f"line {line_no}: class_id {class_id} outside 0..17")
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError(f"line {line_no}: invalid confidence {confidence}")
            coords = (x1, y1, x2, y2)
            if not all(math.isfinite(value) for value in coords):
                raise ValueError(f"line {line_no}: non-finite coordinate")
            if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
                raise ValueError(f"line {line_no}: invalid box {coords}")

            if sizes:
                if image_id not in sizes:
                    raise ValueError(f"line {line_no}: image_id {image_id!r} not found in {image_dir}")
                width, height = sizes[image_id]
                if x2 > width or y2 > height:
                    raise ValueError(
                        f"line {line_no}: box {coords} exceeds demosaiced size {width}x{height}"
                    )
            seen_images[image_id] += 1

    if seen_ids != set(range(row_count)):
        raise ValueError("id must be the contiguous sequence 0..N-1")
    if require_all_images and sizes and set(seen_images) != set(sizes):
        missing = sorted(set(sizes) - set(seen_images))
        raise ValueError(f"{len(missing)} images have no prediction rows; first: {missing[:10]}")

    return {
        "path": str(path),
        "rows": row_count,
        "predicted_images": len(seen_images),
        "reference_images": len(sizes) if sizes else None,
        "max_detections_per_image": max(seen_images.values(), default=0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--image-dir", type=Path)
    parser.add_argument("--require-all-images", action="store_true")
    args = parser.parse_args()
    print(validate(args.submission, args.image_dir, args.require_all_images))


if __name__ == "__main__":
    main()

