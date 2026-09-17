#!/usr/bin/env python3
"""Verify official core files and the minimal image/XML example."""

from __future__ import annotations

import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "raw" / "core"
EXPECTED_HEADER = ["id", "image_id", "class_id", "confidence", "x1", "y1", "x2", "y2"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def x2cube_fast(image: np.ndarray) -> np.ndarray:
    height, width = image.shape
    if height % 4 or width % 4:
        raise ValueError(f"mosaic dimensions must be divisible by four: {width}x{height}")
    return image.reshape(height // 4, 4, width // 4, 4).transpose(0, 2, 1, 3).reshape(height // 4, width // 4, 16)


def main() -> None:
    classes = (CORE / "class.txt").read_text(encoding="utf-8").splitlines()
    if len(classes) != 18 or len(set(classes)) != 18:
        raise ValueError("class.txt must contain 18 unique classes")

    with (CORE / "sample_submission.csv").open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
    if header != EXPECTED_HEADER:
        raise ValueError(f"sample header mismatch: {header}")

    mosaic = np.asarray(Image.open(CORE / "1000.png"))
    cube = x2cube_fast(mosaic)
    xml = ET.parse(CORE / "1000.xml").getroot()
    width = int(xml.findtext("size/width", "-1"))
    height = int(xml.findtext("size/height", "-1"))
    depth = int(xml.findtext("size/depth", "-1"))
    if cube.shape != (height, width, depth):
        raise ValueError(f"cube/XML mismatch: cube={cube.shape}, xml={(height, width, depth)}")

    payload = {
        "classes": classes,
        "sample_header": header,
        "train_mosaic_shape": list(mosaic.shape),
        "train_cube_shape": list(cube.shape),
        "train_band_min": cube.min(axis=(0, 1)).astype(int).tolist(),
        "train_band_max": cube.max(axis=(0, 1)).astype(int).tolist(),
        "sha256": {path.name: sha256(path) for path in sorted(CORE.iterdir()) if path.is_file()},
    }
    output = ROOT / "official" / "core_verification.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

