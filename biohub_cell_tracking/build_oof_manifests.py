#!/usr/bin/env python3
"""Build embryo-isolated validation manifests from the official file listing."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "official" / "file_manifest.csv"
OUTPUT = ROOT / "artifacts" / "embryo_leave_one_out.json"


def main() -> None:
    samples = set()
    with INPUT.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row["name"]
            if name.startswith("train/") and name.endswith(".zarr/zarr.json"):
                samples.add(Path(name).parts[1].removesuffix(".zarr"))

    by_embryo: dict[str, list[str]] = defaultdict(list)
    for sample in sorted(samples):
        by_embryo[sample.split("_", 1)[0]].append(sample)
    embryos = sorted(by_embryo)
    if len(embryos) < 2:
        raise RuntimeError("At least two embryos are required for grouped validation")

    folds = []
    for fold, validation_embryo in enumerate(embryos):
        train = [sample for embryo in embryos if embryo != validation_embryo for sample in by_embryo[embryo]]
        validation = list(by_embryo[validation_embryo])
        folds.append(
            {
                "fold": fold,
                "train_embryos": [embryo for embryo in embryos if embryo != validation_embryo],
                "validation_embryos": [validation_embryo],
                "train": train,
                "validation": validation,
            }
        )

    manifest = {
        "source_manifest": str(INPUT.relative_to(ROOT)),
        "source_manifest_sha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
        "group_key": "sample prefix before first underscore",
        "policy": "leave-one-embryo-out; both folds required for promotion",
        "sample_count": len(samples),
        "embryo_counts": {embryo: len(by_embryo[embryo]) for embryo in embryos},
        "folds": folds,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "folds"}, indent=2))
    for fold in folds:
        print(
            f"fold={fold['fold']} train={len(fold['train'])} "
            f"validation={len(fold['validation'])} validation_embryo={fold['validation_embryos'][0]}"
        )


if __name__ == "__main__":
    main()
