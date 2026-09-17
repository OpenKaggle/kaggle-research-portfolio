#!/usr/bin/env python3
"""Prepare a private Kaggle fork of the public 0.946 notebook.

Only inaccessible author-owned dataset paths are replaced with their public
CC0 originals. Model settings and inference code remain unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "public_notebooks" / "reyhanksatria_0946"
SOURCE = SOURCE_DIR / "biohub-cell-tracking-0-946-lb.ipynb"
TARGET_DIR = ROOT / "kernels" / "biohub_0946_public_deps_repro"
TARGET = TARGET_DIR / "biohub-0946-public-deps-repro.ipynb"

REPLACEMENTS = {
    "/kaggle/input/datasets/reyhanksatria/biohub-tracking-support-pack": (
        "/kaggle/input/datasets/pilkwang/biohub-tracking-support-pack-50ep-v1"
    ),
    "os.environ['BIOHUB_TARGET_ARTIFACT_SLUG'] = 'biohub-tracking-support-pack'": (
        "os.environ['BIOHUB_TARGET_ARTIFACT_SLUG'] = 'biohub-tracking-support-pack-50ep-v1'"
    ),
    "/kaggle/input/datasets/reyhanksatria/biohub-deepcenterunet3d-center-prior-v1": (
        "/kaggle/input/datasets/pilkwang/biohub-deepcenter-unet3d-center-prior-v1"
    ),
    "/kaggle/input/datasets/reyhanksatria/biohub-temporalunet3d-seed-314159-v1": (
        "/kaggle/input/datasets/pilkwang/biohub-temporal-unet3d-seed314159-v1"
    ),
}

DATASETS = [
    "pilkwang/biohub-tracking-support-pack-50ep-v1",
    "pilkwang/biohub-deepcenter-unet3d-center-prior-v1",
    "pilkwang/biohub-temporal-unet3d-seed314159-v1",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    notebook = json.loads(source_bytes)
    replacement_counts = {}

    for old, new in REPLACEMENTS.items():
        count = 0
        for cell in notebook.get("cells", []):
            source = cell.get("source", "")
            if isinstance(source, list):
                joined = "".join(source)
                count += joined.count(old)
                cell["source"] = joined.replace(old, new)
            elif isinstance(source, str):
                count += source.count(old)
                cell["source"] = source.replace(old, new)
        if count < 1:
            raise RuntimeError(f"Expected dependency path not found: {old}")
        replacement_counts[old] = count

    kaggle_meta = notebook.setdefault("metadata", {}).setdefault("kaggle", {})
    kaggle_meta["accelerator"] = "gpu"
    kaggle_meta["isGpuEnabled"] = True
    kaggle_meta["isInternetEnabled"] = False
    kaggle_meta["dataSources"] = []

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    target_bytes = (json.dumps(notebook, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    TARGET.write_bytes(target_bytes)

    source_metadata = json.loads((SOURCE_DIR / "kernel-metadata.json").read_text(encoding="utf-8"))
    metadata = {
        "id": "jahyee/biohub-0-946-public-dependencies-repro",
        "title": "Biohub 0.946 Public Dependencies Repro",
        "code_file": TARGET.name,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": False,
        "keywords": ["gpu"],
        "dataset_sources": DATASETS,
        "kernel_sources": [],
        "competition_sources": ["biohub-cell-tracking-during-development"],
        "model_sources": [],
        "docker_image": source_metadata["docker_image"],
        "machine_shape": "NvidiaTeslaT4",
    }
    (TARGET_DIR / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    receipt = {
        "source_kernel": "reyhanksatria/biohub-cell-tracking-0-946-lb",
        "source_notebook_sha256": sha256_bytes(source_bytes),
        "target_notebook_sha256": sha256_bytes(target_bytes),
        "behavioral_change": "none",
        "dependency_path_substitution_only": True,
        "replacement_counts": replacement_counts,
        "datasets": [
            {"ref": ref, "license": "CC0-1.0", "access": "public"} for ref in DATASETS
        ],
        "model_thresholds_changed": False,
        "internet_enabled": False,
        "gpu": "NvidiaTeslaT4",
    }
    (TARGET_DIR / "REPRO_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
