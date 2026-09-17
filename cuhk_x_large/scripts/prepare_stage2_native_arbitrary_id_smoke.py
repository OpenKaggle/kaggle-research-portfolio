#!/usr/bin/env python3
"""Create equivalent original-ID and synthetic-new-ID/clip Stage2 smoke inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def official_unit(path: str) -> str:
    marker = "large_model_track_test/"
    return "Testing/" + path[path.index(marker) :].split("/")[0] + "/" + path[path.index(marker) :].split("/")[1]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    test_path = root / "data/raw/kaggle/test_qa.csv"
    feature_path = root / "cache/nonvisual_features.npz"
    output_dir = root / "artifacts/smoke/stage2_native_arbitrary_id_v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    original_qa_path = output_dir / "original_ids_qa.csv"
    renamed_qa_path = output_dir / "new_ids_clips_qa.csv"
    original_features_path = output_dir / "original_units_features.npz"
    renamed_features_path = output_dir / "new_units_features.npz"
    fixture_report_path = output_dir / "fixture.json"

    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    with np.load(feature_path) as cache:
        units = cache["units"].astype(str)
        index = {unit: position for position, unit in enumerate(units)}
        imu, radar, skeleton = cache["imu"], cache["radar"], cache["skeleton"]

        hau_candidates = []
        for path, group in test[test["source"] == "HAU"].groupby("path", sort=True):
            unit = official_unit(path)
            if unit in index and {"emotion", "sequence"}.issubset(set(group["category"])):
                hau_candidates.append(path)
        harn_candidates = []
        for path, group in test[(test["source"] == "HARn") & (test["category"] == "single")].groupby("path", sort=True):
            unit = official_unit(path)
            if unit in index and np.isfinite(skeleton[index[unit]]).any():
                harn_candidates.append(path)
        if not hau_candidates or not harn_candidates:
            raise ValueError("Could not construct modality/category smoke coverage")
        selected_paths = [hau_candidates[0], harn_candidates[0]]
        original = test[test["path"].isin(selected_paths)].copy().sort_values(["path", "qa_id"])
        original_units = [official_unit(path) for path in selected_paths]
        positions = [index[unit] for unit in original_units]
        np.savez_compressed(
            original_features_path,
            units=np.asarray(original_units),
            imu=imu[positions],
            radar=radar[positions],
            skeleton=skeleton[positions],
        )

        path_map = {path: f"stage2_unseen_batch/clip_{number:04d}" for number, path in enumerate(selected_paths, start=1)}
        renamed = original.copy()
        renamed["qa_id"] = [f"stage2_new_qa_{number:04d}" for number in range(1, len(renamed) + 1)]
        renamed["path"] = renamed["path"].map(path_map)
        renamed_units = [path_map[path] for path in selected_paths]
        np.savez_compressed(
            renamed_features_path,
            units=np.asarray(renamed_units),
            imu=imu[positions],
            radar=radar[positions],
            skeleton=skeleton[positions],
        )

    original.to_csv(original_qa_path, index=False)
    renamed.to_csv(renamed_qa_path, index=False)
    report = {
        "experiment": "stage2_native_arbitrary_id_clip_smoke_v1",
        "rows": int(len(original)),
        "clips": 2,
        "categories": original["category"].value_counts().sort_index().to_dict(),
        "source_paths": selected_paths,
        "synthetic_paths": list(path_map.values()),
        "synthetic_qa_ids": renamed["qa_id"].tolist(),
        "inputs": {
            "original_qa": [str(original_qa_path.relative_to(root)), sha256(original_qa_path)],
            "renamed_qa": [str(renamed_qa_path.relative_to(root)), sha256(renamed_qa_path)],
            "original_features": [str(original_features_path.relative_to(root)), sha256(original_features_path)],
            "renamed_features": [str(renamed_features_path.relative_to(root)), sha256(renamed_features_path)],
        },
        "labels_read_or_written": False,
    }
    fixture_report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
