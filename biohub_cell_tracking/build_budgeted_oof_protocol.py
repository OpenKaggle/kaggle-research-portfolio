#!/usr/bin/env python3
"""Freeze a deterministic, embryo-isolated OOF protocol under the 12-hour limit."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "official" / "file_manifest.csv"
OUTPUT = ROOT / "artifacts" / "budgeted_embryo_oof.json"
VISIBLE_TEST_COPIES = {
    "44b6_0113de3b",
    "44b6_0b24845f",
    "6bba_05b6850b",
    "6bba_05db0fb1",
}
VALIDATION_SAMPLES_PER_FOLD = 8
MONITOR_SAMPLES_PER_FOLD = 8
EPOCHS = 12
REFERENCE_TRAIN_SECONDS_PER_EPOCH = 1216.9537849733606
REFERENCE_TRAIN_DATASETS = 199
REFERENCE_INFERENCE_SECONDS_PER_MOVIE = 600.088581085205 / 4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def evenly_spaced(items: list[tuple[str, int]], count: int) -> list[tuple[str, int]]:
    """Select fixed order-statistic quantiles, including both endpoints."""
    if len(items) < count:
        raise ValueError(f"Need {count} candidates, found {len(items)}")
    indices = [round(i * (len(items) - 1) / (count - 1)) for i in range(count)]
    if len(set(indices)) != count:
        raise RuntimeError("Quantile selection produced duplicate indices")
    return [items[index] for index in indices]


def main() -> None:
    samples: dict[str, int] = {}
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row["name"]
            suffix = ".geff/nodes/ids/c/0"
            if name.startswith("train/") and name.endswith(suffix):
                sample = name.removeprefix("train/").removesuffix(suffix)
                samples[sample] = int(row["total_bytes"])

    by_embryo: dict[str, list[tuple[str, int]]] = {}
    for sample, proxy_bytes in samples.items():
        embryo = sample.split("_", 1)[0]
        by_embryo.setdefault(embryo, []).append((sample, proxy_bytes))
    for embryo in by_embryo:
        by_embryo[embryo].sort(key=lambda item: (item[1], item[0]))

    folds = []
    for fold, validation_embryo in enumerate(("44b6", "6bba")):
        train_embryo = "6bba" if validation_embryo == "44b6" else "44b6"
        holdout_candidates = [
            item for item in by_embryo[validation_embryo]
            if item[0] not in VISIBLE_TEST_COPIES
        ]
        selected_holdout = evenly_spaced(
            holdout_candidates, VALIDATION_SAMPLES_PER_FOLD
        )
        monitor_candidates = [
            item for item in by_embryo[train_embryo]
            if item[0] not in VISIBLE_TEST_COPIES
        ]
        selected_monitor = evenly_spaced(
            monitor_candidates, MONITOR_SAMPLES_PER_FOLD
        )
        monitor_names = {name for name, _ in selected_monitor}
        model_train = sorted(
            name for name, _ in by_embryo[train_embryo]
            if name not in monitor_names
        )
        folds.append(
            {
                "fold": fold,
                "seed": 20260909 + fold,
                "train_embryo": train_embryo,
                "validation_embryo": validation_embryo,
                "train": model_train,
                "monitor": [name for name, _ in selected_monitor],
                "holdout": [name for name, _ in selected_holdout],
                "monitor_selection_proxy_bytes": {
                    name: proxy for name, proxy in selected_monitor
                },
                "holdout_selection_proxy_bytes": {
                    name: proxy for name, proxy in selected_holdout
                },
            }
        )

    train_equivalent = sum(len(fold["train"]) for fold in folds) / REFERENCE_TRAIN_DATASETS
    estimated_training_seconds = REFERENCE_TRAIN_SECONDS_PER_EPOCH * EPOCHS * train_equivalent
    estimated_inference_seconds = (
        REFERENCE_INFERENCE_SECONDS_PER_MOVIE
        * sum(len(fold["holdout"]) for fold in folds)
    )
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "competition": "biohub-cell-tracking-during-development",
        "protocol": "budgeted_leave_one_embryo_out",
        "purpose": "honest generalization and error diagnosis; not a direct proxy for BH-0001",
        "data_manifest_sha256": sha256(MANIFEST),
        "selection": {
            "method": "eight fixed order-statistic quantiles of compressed GEFF node-id chunk bytes",
            "fixed_before_modeling": True,
            "visible_test_copies_excluded": sorted(VISIBLE_TEST_COPIES),
            "validation_samples_per_fold": VALIDATION_SAMPLES_PER_FOLD,
            "monitor_samples_per_fold": MONITOR_SAMPLES_PER_FOLD,
            "model_selection": "same-embryo monitor only; final cross-embryo holdout is untouched until inference",
        },
        "training": {
            "epochs": EPOCHS,
            "batch_size": 8,
            "learning_rate": 0.0001,
            "downsample_zyx": [1, 4, 4],
            "augmentations": "disabled for deterministic diagnostic",
            "warm_start": None,
        },
        "runtime_budget": {
            "official_limit_hours": 12,
            "reference_train_seconds_per_epoch_199_datasets": REFERENCE_TRAIN_SECONDS_PER_EPOCH,
            "reference_inference_seconds_per_movie": REFERENCE_INFERENCE_SECONDS_PER_MOVIE,
            "estimated_training_seconds": estimated_training_seconds,
            "estimated_inference_seconds": estimated_inference_seconds,
            "estimated_total_hours_before_overhead": (
                estimated_training_seconds + estimated_inference_seconds
            ) / 3600,
        },
        "folds": folds,
        "limitations": [
            "Only eight validation movies per embryo are fully inferred and scored.",
            "The 12-epoch diagnostic is intentionally undertrained relative to the 400-epoch public checkpoint.",
            "Checkpoint selection uses only the same-embryo monitor subset; the cross-embryo holdout does not participate in training or selection.",
            "Promotion requires directionally consistent results in both embryo directions; this protocol cannot justify leaderboard-only tuning.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
