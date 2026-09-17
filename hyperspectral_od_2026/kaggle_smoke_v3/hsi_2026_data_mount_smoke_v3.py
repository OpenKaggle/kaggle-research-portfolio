"""Fail-closed, CPU-only mount receipt for HSI Detection 2026.

This script only inspects a pre-attached Kaggle competition source. It never
downloads data, trains a model, enables an accelerator, or creates a
submission.
"""

from __future__ import annotations

import csv
import hashlib
import json
import signal
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


COMPETITION = "hyperspectral-object-detection-challenge-2026"
KERNEL_REF = "jahyee/hsi-2026-data-mount-smoke-v3"
# Kaggle materializes a competition source directly under /kaggle/input/<slug>
# for script kernels created through kernel-metadata.json.  The earlier
# /kaggle/input/competitions/<slug> assumption was disproved by the v3 version
# 1 terminal receipt before any competition file was read.
INPUT_ROOT = Path("/kaggle/input") / COMPETITION
OUTPUT = Path("/kaggle/working/hsi_2026_mount_smoke_v3_terminal_receipt.json")
HARD_TIMEOUT_SECONDS = 600
KERNEL_METADATA_SHA256 = "3aac808c2f82a5d00b7ff1af6da3e95a02400d69ee0c1a995685278b56acbb05"

TRAIN_PNG_PREFIX = ("data_train", "data_train", "VIS")
TRAIN_XML_PREFIX = ("data_train", "data_train", "Annotations", "VIS")
TEST_PNG_PREFIX = ("data_test", "data_test", "VIS")
METADATA_FILES = {"class.txt", "pseudo_rgb_demo.py", "sample_submission.csv"}
EXPECTED_COUNTS = {
    "train_png": 3000,
    "train_xml": 3000,
    "test_png": 1000,
    "ranking_png": 0,
    "metadata": 3,
    "total": 7003,
}
EXPECTED_HEADER = ["id", "image_id", "class_id", "confidence", "x1", "y1", "x2", "y2"]

SAMPLE_PNG = Path("data_train/data_train/VIS/1000.png")
SAMPLE_XML = Path("data_train/data_train/Annotations/VIS/1000.xml")
SAMPLE_PNG_SHA256 = "005d9276e695a63e170c710c2713145a6196e0dd47d979619944d16750c88660"
SAMPLE_XML_SHA256 = "7a615a97047cc46dc5f86ae9a522f46fae9c3660d299cfc104e1290ad7b6b603"
SAMPLE_MOSAIC_SHAPE = [1004, 1988]
SAMPLE_CUBE_SHAPE = [251, 497, 16]
CLASS_SHA256 = "18a3758dbfb097d0f80d3b22db3c5d87d9720afe65bfa4803c117f43cb854fba"
SAMPLE_SUBMISSION_SHA256 = "ecb399387799e6cb81484fa4474f7dda1af04f9614b829763b61ef9734b2e34b"


class ContractViolation(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class HardTimeout(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path, deadline: float | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            check_deadline(deadline)
            digest.update(chunk)
    return digest.hexdigest()


def check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() >= deadline:
        raise HardTimeout(f"hard timeout exceeded ({HARD_TIMEOUT_SECONDS} seconds)")


def x2cube(image: np.ndarray) -> np.ndarray:
    if image.ndim != 2:
        raise ContractViolation("sample_read", f"expected one-channel mosaic, got shape {image.shape}")
    height, width = image.shape
    if height % 4 or width % 4:
        raise ContractViolation(
            "sample_read", f"raw mosaic dimensions are not divisible by four: {width}x{height}"
        )
    return image.reshape(height // 4, 4, width // 4, 4).transpose(0, 2, 1, 3).reshape(
        height // 4, width // 4, 16
    )


def classify_relative_path(relative: Path) -> str:
    parts = relative.parts
    if len(parts) == 1 and parts[0] in METADATA_FILES:
        return "metadata"
    if len(parts) == 4 and parts[:3] == TRAIN_PNG_PREFIX and relative.suffix.lower() == ".png":
        return "train_png"
    if len(parts) == 5 and parts[:4] == TRAIN_XML_PREFIX and relative.suffix.lower() == ".xml":
        return "train_xml"
    if len(parts) == 4 and parts[:3] == TEST_PNG_PREFIX and relative.suffix.lower() == ".png":
        return "test_png"
    if relative.suffix.lower() == ".png" and "ranking" in str(relative).lower():
        return "ranking_png"
    return "unexpected"


def summarize_relative_paths(relative_paths: Iterable[Path]) -> dict[str, Any]:
    counts = {key: 0 for key in EXPECTED_COUNTS if key != "total"}
    counts["unexpected"] = 0
    train_png_stems: set[str] = set()
    train_xml_stems: set[str] = set()
    metadata_seen: set[str] = set()
    unexpected_examples: list[str] = []

    for relative in relative_paths:
        category = classify_relative_path(relative)
        counts[category] += 1
        if category == "train_png":
            train_png_stems.add(relative.stem)
        elif category == "train_xml":
            train_xml_stems.add(relative.stem)
        elif category == "metadata":
            metadata_seen.add(relative.name)
        elif len(unexpected_examples) < 20:
            unexpected_examples.append(str(relative))

    counts["total"] = sum(value for key, value in counts.items() if key != "unexpected") + counts["unexpected"]
    return {
        "counts": counts,
        "metadata_seen": sorted(metadata_seen),
        "train_stems_match": train_png_stems == train_xml_stems,
        "train_png_unique_stems": len(train_png_stems),
        "train_xml_unique_stems": len(train_xml_stems),
        "unexpected_examples": unexpected_examples,
    }


def scan_inventory(root: Path, deadline: float) -> dict[str, Any]:
    relative_paths: list[Path] = []
    bytes_by_stage = {key: 0 for key in EXPECTED_COUNTS if key != "total"}
    bytes_by_stage["unexpected"] = 0

    for index, path in enumerate(root.rglob("*")):
        if index % 128 == 0:
            check_deadline(deadline)
        if path.is_file():
            relative = path.relative_to(root)
            relative_paths.append(relative)
            bytes_by_stage[classify_relative_path(relative)] += path.stat().st_size

    bytes_by_stage["total"] = sum(bytes_by_stage.values())
    summary = summarize_relative_paths(relative_paths)
    return {**summary, "bytes_by_stage": bytes_by_stage}


def validate_inventory(summary: dict[str, Any]) -> None:
    observed = summary["counts"]
    expected_with_no_extras = {**EXPECTED_COUNTS, "unexpected": 0}
    if observed != expected_with_no_extras:
        raise ContractViolation(
            "inventory",
            f"file inventory mismatch: expected={expected_with_no_extras}, observed={observed}, "
            f"unexpected_examples={summary['unexpected_examples']}",
        )
    if summary["metadata_seen"] != sorted(METADATA_FILES):
        raise ContractViolation("inventory", f"metadata set mismatch: {summary['metadata_seen']}")
    if not summary["train_stems_match"]:
        raise ContractViolation("inventory", "training PNG/XML stems do not match")
    if summary["train_png_unique_stems"] != 3000 or summary["train_xml_unique_stems"] != 3000:
        raise ContractViolation("inventory", "training filenames are not unique by stem")


def scan_metadata(root: Path, deadline: float) -> dict[str, Any]:
    class_path = root / "class.txt"
    sample_submission_path = root / "sample_submission.csv"
    class_hash = sha256(class_path, deadline)
    sample_submission_hash = sha256(sample_submission_path, deadline)
    classes = class_path.read_text(encoding="utf-8").splitlines()
    with sample_submission_path.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle))
    return {
        "class_count": len(classes),
        "unique_class_count": len(set(classes)),
        "class_sha256": class_hash,
        "sample_submission_sha256": sample_submission_hash,
        "submission_header": header,
    }


def validate_metadata(observed: dict[str, Any]) -> None:
    if observed["class_sha256"] != CLASS_SHA256:
        raise ContractViolation("metadata", f"class.txt SHA256 mismatch: {observed['class_sha256']}")
    if observed["sample_submission_sha256"] != SAMPLE_SUBMISSION_SHA256:
        raise ContractViolation(
            "metadata", f"sample_submission.csv SHA256 mismatch: {observed['sample_submission_sha256']}"
        )
    if observed["class_count"] != 18 or observed["unique_class_count"] != 18:
        raise ContractViolation(
            "metadata",
            f"expected 18 unique classes, got count={observed['class_count']}, "
            f"unique={observed['unique_class_count']}",
        )
    if observed["submission_header"] != EXPECTED_HEADER:
        raise ContractViolation("metadata", f"submission header mismatch: {observed['submission_header']}")


def scan_sample(root: Path, deadline: float) -> dict[str, Any]:
    png_path = root / SAMPLE_PNG
    xml_path = root / SAMPLE_XML
    png_hash = sha256(png_path, deadline)
    xml_hash = sha256(xml_path, deadline)
    check_deadline(deadline)
    with Image.open(png_path) as image:
        image.load()
        mosaic = np.asarray(image)
    cube = x2cube(mosaic)
    xml_root = ET.parse(xml_path).getroot()
    xml_shape = [
        int(xml_root.findtext("size/height", "-1")),
        int(xml_root.findtext("size/width", "-1")),
        int(xml_root.findtext("size/depth", "-1")),
    ]
    mosaic_shape = list(mosaic.shape)
    cube_shape = list(cube.shape)
    return {
        "png_path": str(SAMPLE_PNG),
        "xml_path": str(SAMPLE_XML),
        "png_sha256": png_hash,
        "xml_sha256": xml_hash,
        "mosaic_shape": mosaic_shape,
        "cube_shape": cube_shape,
        "xml_shape": xml_shape,
        "dtype": str(mosaic.dtype),
    }


def validate_sample(observed: dict[str, Any]) -> None:
    if observed["png_sha256"] != SAMPLE_PNG_SHA256:
        raise ContractViolation("sample_read", f"sample PNG SHA256 mismatch: {observed['png_sha256']}")
    if observed["xml_sha256"] != SAMPLE_XML_SHA256:
        raise ContractViolation("sample_read", f"sample XML SHA256 mismatch: {observed['xml_sha256']}")
    if observed["mosaic_shape"] != SAMPLE_MOSAIC_SHAPE:
        raise ContractViolation("sample_read", f"sample mosaic shape mismatch: {observed['mosaic_shape']}")
    if observed["cube_shape"] != SAMPLE_CUBE_SHAPE:
        raise ContractViolation("sample_read", f"sample cube shape mismatch: {observed['cube_shape']}")
    if observed["xml_shape"] != SAMPLE_CUBE_SHAPE:
        raise ContractViolation("sample_read", f"sample XML shape mismatch: {observed['xml_shape']}")


def base_receipt(started_utc: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "receipt_type": "hsi_2026_mount_smoke_terminal",
        "smoke_version": "v3",
        "competition": COMPETITION,
        "kernel_ref": KERNEL_REF,
        "kernel_version": None,
        "control_plane_terminal_status": None,
        "downloaded_log_sha256": None,
        "status": "RUNNING",
        "terminal": False,
        "started_utc": started_utc,
        "finished_utc": None,
        "elapsed_seconds": None,
        "hard_timeout_seconds": HARD_TIMEOUT_SECONDS,
        "code_sha256": sha256(Path(__file__)),
        "kernel_metadata_sha256_expected": KERNEL_METADATA_SHA256,
        "source_attachment": {
            "required_competition_source": COMPETITION,
            "expected_root": str(INPUT_ROOT),
            "access_method": "pre_attached_competition_source_only",
            "root_exists": False,
            "remote_metadata_competition_sources": None,
            "remote_metadata_verified_before_run": False,
            "dynamic_download_allowed": False,
            "network_download_attempted": False,
        },
        "runtime_contract": {
            "cpu_only": True,
            "gpu_enabled": False,
            "tpu_enabled": False,
            "internet_enabled": False,
            "training_started": False,
            "submission_started": False,
        },
        "inventory": {"expected": EXPECTED_COUNTS, "observed": None},
        "metadata_check": None,
        "sample_check": {
            "expected_png_path": str(SAMPLE_PNG),
            "expected_xml_path": str(SAMPLE_XML),
            "expected_png_sha256": SAMPLE_PNG_SHA256,
            "expected_xml_sha256": SAMPLE_XML_SHA256,
            "expected_mosaic_shape": SAMPLE_MOSAIC_SHAPE,
            "expected_cube_and_xml_shape": SAMPLE_CUBE_SHAPE,
            "observed": None,
        },
        "checks": [],
        "failure": None,
        "termination_reason": None,
        "receipt_path": str(OUTPUT),
        "post_run_control_plane_evidence_required": [
            "kernel_version",
            "remote_metadata_competition_sources",
            "control_plane_terminal_status",
            "downloaded_log_sha256",
        ],
    }


def run_contract(root: Path, receipt: dict[str, Any], deadline: float) -> None:
    check_deadline(deadline)
    if root != INPUT_ROOT:
        raise ContractViolation("source_attachment", f"refusing non-contract root: {root}")
    if not root.is_dir():
        raise ContractViolation("source_attachment", f"pre-attached competition root is unavailable: {root}")
    receipt["source_attachment"]["root_exists"] = True
    receipt["checks"].append({"name": "pre_attached_root", "status": "PASS"})

    inventory = scan_inventory(root, deadline)
    receipt["inventory"]["observed"] = inventory
    validate_inventory(inventory)
    receipt["checks"].append({"name": "exact_phase1_inventory", "status": "PASS"})

    metadata_check = scan_metadata(root, deadline)
    receipt["metadata_check"] = metadata_check
    validate_metadata(metadata_check)
    receipt["checks"].append({"name": "metadata_schema_and_hashes", "status": "PASS"})

    sample_check = scan_sample(root, deadline)
    receipt["sample_check"]["observed"] = sample_check
    validate_sample(sample_check)
    receipt["checks"].append({"name": "paired_sample_read_shape_and_hash", "status": "PASS"})


def finalize_receipt(receipt: dict[str, Any], started_monotonic: float) -> None:
    receipt["terminal"] = True
    receipt["finished_utc"] = utc_now()
    receipt["elapsed_seconds"] = round(time.monotonic() - started_monotonic, 6)


def emit_receipt(receipt: dict[str, Any], output: Path) -> bool:
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(output)
    except Exception as exc:  # stdout remains the terminal fallback receipt.
        receipt["receipt_write_error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(receipt, indent=2, sort_keys=True), flush=True)
        return False
    print(payload, end="", flush=True)
    return True


def _alarm_handler(signum: int, frame: object) -> None:
    del signum, frame
    raise HardTimeout(f"hard timeout exceeded ({HARD_TIMEOUT_SECONDS} seconds)")


def execute(root: Path = INPUT_ROOT, output: Path = OUTPUT) -> int:
    started_monotonic = time.monotonic()
    receipt = base_receipt(utc_now())
    receipt["receipt_path"] = str(output)
    deadline = started_monotonic + HARD_TIMEOUT_SECONDS
    previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(HARD_TIMEOUT_SECONDS)
    exit_code = 1
    try:
        run_contract(root, receipt, deadline)
        receipt["status"] = "PASS"
        receipt["termination_reason"] = "all_contract_checks_passed"
        exit_code = 0
    except HardTimeout as exc:
        receipt["status"] = "TIMEOUT"
        receipt["failure"] = {"stage": "hard_timeout", "type": type(exc).__name__, "message": str(exc)}
        receipt["termination_reason"] = "hard_timeout_fail_closed"
        exit_code = 124
    except Exception as exc:
        stage = exc.stage if isinstance(exc, ContractViolation) else "unexpected_exception"
        receipt["status"] = "FAIL"
        receipt["failure"] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
        receipt["termination_reason"] = "contract_failure_fail_closed"
        exit_code = 1
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
        finalize_receipt(receipt, started_monotonic)
        if not emit_receipt(receipt, output):
            exit_code = 2
    return exit_code


if __name__ == "__main__":
    sys.exit(execute())
