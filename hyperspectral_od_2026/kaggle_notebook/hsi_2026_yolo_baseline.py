"""Private Kaggle GPU baseline for HOD26.

One COCO-pretrained YOLO11m model, one checkpoint, pseudo-RGB bands [5, 8,
13] from the alternative shown in the official demo, and no model ensemble or
pseudo-labeling.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image


COMPETITION = "hyperspectral-object-detection-challenge-2026"
INPUT_ROOT = Path("/kaggle/input") / COMPETITION
WORK = Path("/kaggle/working")
DATASET = WORK / "pseudo_rgb_b5_8_13"
SEED = 20260909
BANDS = (5, 8, 13)
MODEL_NAME = "yolo11m.pt"
EPOCHS = 50
IMGSZ = 640
PRED_CONF = 0.001
PRED_IOU = 0.70
MAX_DET = 300
EXPECTED_COLUMNS = ["id", "image_id", "class_id", "confidence", "x1", "y1", "x2", "y2"]


def ensure_ultralytics():
    try:
        import ultralytics
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ultralytics>=8.3,<9"])
        import ultralytics
    return ultralytics


def find_files() -> tuple[list[Path], list[Path], list[Path], Path]:
    if not INPUT_ROOT.exists():
        raise FileNotFoundError(f"competition input is not mounted: {INPUT_ROOT}")
    pngs = sorted(INPUT_ROOT.rglob("*.png"))
    xmls = sorted(INPUT_ROOT.rglob("*.xml"))
    class_files = sorted(INPUT_ROOT.rglob("class.txt"))
    train = [path for path in pngs if "data_train" in {part.lower() for part in path.parts}]
    test = [path for path in pngs if "data_test" in {part.lower() for part in path.parts}]
    ranking = [path for path in pngs if "ranking" in str(path).lower()]
    if len(train) != 3000 or len(xmls) != 3000 or len(test) != 1000:
        raise RuntimeError(
            f"unexpected Phase-1 file counts: train_png={len(train)}, xml={len(xmls)}, "
            f"test_png={len(test)}, ranking_png={len(ranking)}"
        )
    if ranking:
        raise RuntimeError("Phase-2 ranking files are present; this Phase-1 notebook must not create a final CSV")
    if len(class_files) != 1:
        raise RuntimeError(f"expected one class.txt, found {class_files}")
    return train, xmls, test, class_files[0]


def x2cube(image: np.ndarray) -> np.ndarray:
    height, width = image.shape
    if height % 4 or width % 4:
        raise ValueError(f"raw mosaic dimensions are not divisible by four: {width}x{height}")
    return image.reshape(height // 4, 4, width // 4, 4).transpose(0, 2, 1, 3).reshape(height // 4, width // 4, 16)


def pseudo_rgb(source: Path, destination: Path) -> tuple[int, int]:
    mosaic = np.asarray(Image.open(source))
    cube = x2cube(mosaic)
    rgb = cube[:, :, BANDS].astype(np.float32)
    for channel in range(3):
        plane = rgb[:, :, channel]
        minimum = float(plane.min())
        maximum = float(plane.max())
        if maximum > minimum:
            rgb[:, :, channel] = (plane - minimum) / (maximum - minimum) * 255.0
        else:
            rgb[:, :, channel] = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb.astype(np.uint8), mode="RGB").save(destination, compress_level=2)
    return cube.shape[1], cube.shape[0]


def parse_voc(xml_path: Path, class_to_id: dict[str, int]) -> tuple[int, int, list[str]]:
    root = ET.parse(xml_path).getroot()
    width = int(root.findtext("size/width", "0"))
    height = int(root.findtext("size/height", "0"))
    depth = int(root.findtext("size/depth", "0"))
    if width <= 0 or height <= 0 or depth != 16:
        raise ValueError(f"invalid size in {xml_path}: {width}x{height}x{depth}")
    labels: list[str] = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip()
        if name not in class_to_id:
            raise ValueError(f"unknown class {name!r} in {xml_path}")
        box = obj.find("bndbox")
        if box is None:
            raise ValueError(f"missing bndbox in {xml_path}")
        xmin = max(0.0, min(float(box.findtext("xmin", "nan")), float(width)))
        ymin = max(0.0, min(float(box.findtext("ymin", "nan")), float(height)))
        xmax = max(0.0, min(float(box.findtext("xmax", "nan")), float(width)))
        ymax = max(0.0, min(float(box.findtext("ymax", "nan")), float(height)))
        if xmax <= xmin or ymax <= ymin:
            raise ValueError(f"invalid box in {xml_path}: {(xmin, ymin, xmax, ymax)}")
        x_center = (xmin + xmax) / (2 * width)
        y_center = (ymin + ymax) / (2 * height)
        box_width = (xmax - xmin) / width
        box_height = (ymax - ymin) / height
        labels.append(
            f"{class_to_id[name]} {x_center:.8f} {y_center:.8f} {box_width:.8f} {box_height:.8f}"
        )
    return width, height, labels


def prepare_dataset(
    train_images: list[Path], xmls: list[Path], test_images: list[Path], classes: list[str]
) -> dict[str, object]:
    random.seed(SEED)
    np.random.seed(SEED)
    xml_by_stem = {path.stem: path for path in xmls}
    train_by_stem = {path.stem: path for path in train_images}
    if set(xml_by_stem) != set(train_by_stem):
        raise RuntimeError("train PNG/XML stems do not match exactly")
    stems = sorted(train_by_stem)
    rng = random.Random(SEED)
    rng.shuffle(stems)
    val_count = round(0.20 * len(stems))
    val_stems = set(stems[:val_count])
    class_to_id = {name: index for index, name in enumerate(classes)}
    class_counts: Counter[int] = Counter()

    for index, stem in enumerate(sorted(train_by_stem), start=1):
        split = "val" if stem in val_stems else "train"
        image_out = DATASET / "images" / split / f"{stem}.png"
        label_out = DATASET / "labels" / split / f"{stem}.txt"
        xml_width, xml_height, labels = parse_voc(xml_by_stem[stem], class_to_id)
        image_width, image_height = pseudo_rgb(train_by_stem[stem], image_out)
        if (image_width, image_height) != (xml_width, xml_height):
            raise RuntimeError(
                f"image/XML dimensions disagree for {stem}: {(image_width, image_height)} vs {(xml_width, xml_height)}"
            )
        label_out.parent.mkdir(parents=True, exist_ok=True)
        label_out.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
        for label in labels:
            class_counts[int(label.split()[0])] += 1
        if index % 250 == 0:
            print(f"prepared train/val {index}/{len(train_by_stem)}", flush=True)

    test_out = DATASET / "images" / "test"
    for index, path in enumerate(test_images, start=1):
        pseudo_rgb(path, test_out / f"{path.stem}.png")
        if index % 250 == 0:
            print(f"prepared test {index}/{len(test_images)}", flush=True)

    yaml_path = DATASET / "dataset.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                f"path: {DATASET}",
                "train: images/train",
                "val: images/val",
                f"nc: {len(classes)}",
                "names:",
                *[f"  {index}: {json.dumps(name)}" for index, name in enumerate(classes)],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "train_images": len(stems) - val_count,
        "val_images": val_count,
        "test_images": len(test_images),
        "class_instance_counts": {classes[key]: value for key, value in sorted(class_counts.items())},
        "yaml": str(yaml_path),
    }


def validate_submission(path: Path, test_dir: Path) -> dict[str, int]:
    image_sizes = {}
    for image_path in test_dir.glob("*.png"):
        with Image.open(image_path) as image:
            image_sizes[image_path.stem] = image.size
    seen_ids: set[int] = set()
    predicted_images: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise RuntimeError(f"submission header mismatch: {reader.fieldnames}")
        for row_number, row in enumerate(reader):
            row_id = int(row["id"])
            image_id = row["image_id"]
            class_id = int(row["class_id"])
            confidence = float(row["confidence"])
            x1, y1, x2, y2 = (float(row[key]) for key in ("x1", "y1", "x2", "y2"))
            if row_id != row_number or row_id in seen_ids:
                raise RuntimeError(f"id contract failed at row {row_number}")
            seen_ids.add(row_id)
            if image_id not in image_sizes:
                raise RuntimeError(f"unknown test image_id {image_id}")
            width, height = image_sizes[image_id]
            if not 0 <= class_id < 18 or not 0 <= confidence <= 1:
                raise RuntimeError(f"class/confidence contract failed at row {row_number}")
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                raise RuntimeError(f"box contract failed at row {row_number}: {(x1, y1, x2, y2)} vs {width}x{height}")
            predicted_images[image_id] += 1
    if not seen_ids:
        raise RuntimeError("submission contains no detections")
    return {
        "rows": len(seen_ids),
        "predicted_images": len(predicted_images),
        "zero_detection_images": len(image_sizes) - len(predicted_images),
        "max_detections_per_image": max(predicted_images.values()),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    started = time.time()
    os.environ["PYTHONHASHSEED"] = str(SEED)
    ultralytics = ensure_ultralytics()
    from ultralytics import YOLO

    train_images, xmls, test_images, class_path = find_files()
    classes = class_path.read_text(encoding="utf-8").splitlines()
    if len(classes) != 18 or len(set(classes)) != 18:
        raise RuntimeError(f"expected 18 unique classes, got {classes}")
    data_summary = prepare_dataset(train_images, xmls, test_images, classes)

    model = YOLO(MODEL_NAME)
    model_info = model.info(detailed=False, verbose=False)
    train_results = model.train(
        data=data_summary["yaml"],
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=-1,
        workers=4,
        device=0,
        seed=SEED,
        deterministic=True,
        pretrained=True,
        patience=12,
        amp=True,
        cache=False,
        project=str(WORK / "training"),
        name="single_yolo11m_b5_8_13",
        exist_ok=True,
        verbose=True,
        plots=True,
    )
    best = WORK / "training" / "single_yolo11m_b5_8_13" / "weights" / "best.pt"
    if not best.exists():
        raise FileNotFoundError(f"best checkpoint missing: {best}")

    inference_model = YOLO(best)
    test_dir = DATASET / "images" / "test"
    sources = [str(path) for path in sorted(test_dir.glob("*.png"), key=lambda path: int(path.stem))]
    rows: list[dict[str, object]] = []
    results = inference_model.predict(
        source=sources,
        imgsz=IMGSZ,
        conf=PRED_CONF,
        iou=PRED_IOU,
        max_det=MAX_DET,
        batch=32,
        device=0,
        stream=True,
        verbose=False,
    )
    for result in results:
        image_id = Path(result.path).stem
        if result.boxes is None:
            continue
        xyxy = result.boxes.xyxy.detach().cpu().numpy()
        confidences = result.boxes.conf.detach().cpu().numpy()
        class_ids = result.boxes.cls.detach().cpu().numpy().astype(int)
        order = np.argsort(-confidences)
        for index in order:
            x1, y1, x2, y2 = xyxy[index].tolist()
            rows.append(
                {
                    "image_id": image_id,
                    "class_id": int(class_ids[index]),
                    "confidence": float(confidences[index]),
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2),
                }
            )

    rows.sort(key=lambda row: (int(str(row["image_id"])), -float(row["confidence"])))
    submission = WORK / "submission.csv"
    with submission.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        for row_id, row in enumerate(rows):
            writer.writerow({"id": row_id, **row})
    gate = validate_submission(submission, test_dir)

    best_copy = WORK / "best_yolo11m_b5_8_13.pt"
    best_copy.write_bytes(best.read_bytes())
    metrics = getattr(train_results, "results_dict", {}) or {}
    summary = {
        "competition": COMPETITION,
        "phase": 1,
        "data": data_summary,
        "seed": SEED,
        "model": MODEL_NAME,
        "model_info_layers_parameters_gradients_gflops": list(model_info) if model_info else None,
        "single_checkpoint": True,
        "pretraining": {
            "dataset": "COCO",
            "source": "Ultralytics yolo11m.pt",
            "license": "AGPL-3.0",
        },
        "ultralytics_version": ultralytics.__version__,
        "bands": list(BANDS),
        "normalization": "per-image per-band min-max to uint8",
        "epochs_requested": EPOCHS,
        "imgsz": IMGSZ,
        "split": "fixed random image split 80/20",
        "metrics": {key: float(value) for key, value in metrics.items() if np.isscalar(value)},
        "prediction": {"conf": PRED_CONF, "iou": PRED_IOU, "max_det": MAX_DET, "tta": False},
        "submission_gate": gate,
        "submission_sha256": sha256(submission),
        "checkpoint_sha256": sha256(best_copy),
        "runtime_minutes": (time.time() - started) / 60.0,
    }
    (WORK / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
