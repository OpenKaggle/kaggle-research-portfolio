"""Read-only Phase-1 competition mount and schema smoke test."""

from __future__ import annotations

import csv
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image


COMPETITION = "hyperspectral-object-detection-challenge-2026"
DEFAULT_ROOT = Path("/kaggle/input") / COMPETITION
OUTPUT = Path("/kaggle/working/smoke_receipt.json")
EXPECTED_HEADER = ["id", "image_id", "class_id", "confidence", "x1", "y1", "x2", "y2"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def x2cube(image: np.ndarray) -> np.ndarray:
    height, width = image.shape
    if height % 4 or width % 4:
        raise ValueError(f"raw mosaic dimensions are not divisible by four: {width}x{height}")
    return image.reshape(height // 4, 4, width // 4, 4).transpose(0, 2, 1, 3).reshape(height // 4, width // 4, 16)


def resolve_root() -> tuple[Path, str]:
    if DEFAULT_ROOT.exists():
        return DEFAULT_ROOT, "metadata_mount"
    import kagglehub

    attached = Path(kagglehub.competition_download(COMPETITION))
    if attached.exists():
        return attached, "kagglehub_dynamic_attach"
    if DEFAULT_ROOT.exists():
        return DEFAULT_ROOT, "kagglehub_metadata_mount"
    raise FileNotFoundError(f"competition input is unavailable after official kagglehub attach: {attached}")


def main() -> None:
    started = time.time()
    root, access_method = resolve_root()
    pngs = sorted(root.rglob("*.png"))
    xmls = sorted(root.rglob("*.xml"))
    train = [path for path in pngs if "data_train" in {part.lower() for part in path.parts}]
    test = [path for path in pngs if "data_test" in {part.lower() for part in path.parts}]
    ranking = [path for path in pngs if "ranking" in str(path).lower()]
    class_paths = sorted(root.rglob("class.txt"))
    sample_paths = sorted(root.rglob("sample_submission.csv"))
    if (len(train), len(xmls), len(test), len(ranking), len(class_paths), len(sample_paths)) != (3000, 3000, 1000, 0, 1, 1):
        raise RuntimeError(
            "unexpected Phase-1 mount counts: "
            f"train={len(train)} xml={len(xmls)} test={len(test)} ranking={len(ranking)} "
            f"class={len(class_paths)} sample={len(sample_paths)}"
        )
    classes = class_paths[0].read_text(encoding="utf-8").splitlines()
    if len(classes) != 18 or len(set(classes)) != 18:
        raise RuntimeError(f"invalid class list: {classes}")
    with sample_paths[0].open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle))
    if header != EXPECTED_HEADER:
        raise RuntimeError(f"submission header mismatch: {header}")

    train_by_stem = {path.stem: path for path in train}
    xml_by_stem = {path.stem: path for path in xmls}
    if set(train_by_stem) != set(xml_by_stem):
        raise RuntimeError("training image/XML stems do not match")
    stem = sorted(train_by_stem)[0]
    mosaic = np.asarray(Image.open(train_by_stem[stem]))
    cube = x2cube(mosaic)
    xml_root = ET.parse(xml_by_stem[stem]).getroot()
    xml_shape = [
        int(xml_root.findtext("size/height", "-1")),
        int(xml_root.findtext("size/width", "-1")),
        int(xml_root.findtext("size/depth", "-1")),
    ]
    if list(cube.shape) != xml_shape:
        raise RuntimeError(f"decoded cube/XML mismatch: {cube.shape} vs {xml_shape}")

    receipt = {
        "competition": COMPETITION,
        "data_root": str(root),
        "access_method": access_method,
        "phase": 1,
        "train_png": len(train),
        "train_xml": len(xmls),
        "test_png": len(test),
        "ranking_png": len(ranking),
        "classes": classes,
        "submission_header": header,
        "sample_train_stem": stem,
        "sample_mosaic_shape": list(mosaic.shape),
        "sample_cube_shape": list(cube.shape),
        "sample_train_sha256": sha256(train_by_stem[stem]),
        "class_sha256": sha256(class_paths[0]),
        "sample_submission_sha256": sha256(sample_paths[0]),
        "runtime_seconds": time.time() - started,
        "status": "passed",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
