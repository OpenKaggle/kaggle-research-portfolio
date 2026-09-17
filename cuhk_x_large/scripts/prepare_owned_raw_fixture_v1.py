#!/usr/bin/env python3
"""Create a tiny official-derived raw fixture and an ID/path-renamed twin."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from extract_owned_raw_features_v1 import discover_units, resolve_unit


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def write_case(root: Path, qa: pd.DataFrame, unit_map: dict[str, str], source_root: Path) -> None:
    raw_root = root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    source_manifest = pd.read_csv(source_root / "manifest_nonvisual.csv", dtype=str, keep_default_na=False)
    modalities = dict(zip(source_manifest["unit"], source_manifest["modalities"]))
    for source_unit, target_unit in sorted(unit_map.items()):
        shutil.copytree(source_root / source_unit, raw_root / target_unit)
        manifest_rows.append({"unit": target_unit, "modalities": modalities[source_unit]})
    pd.DataFrame(manifest_rows).to_csv(raw_root / "manifest_nonvisual.csv", index=False)
    qa.to_csv(root / "qa.csv", index=False)
    pd.DataFrame({"qa_id": qa["qa_id"], "prediction": ""}).to_csv(root / "sample.csv", index=False)


def main() -> None:
    campaign = Path(__file__).resolve().parents[1]
    source_root = campaign / "data/raw/nonvisual/LMT_(IMU,Radar,Skeleton)"
    output = campaign / "artifacts/fixtures/stage2_native_owned_raw_v1"
    if output.exists():
        raise ValueError(f"Fixture already exists; refusing to overwrite: {output}")
    qa = pd.read_csv(campaign / "data/raw/kaggle/test_qa.csv", dtype=str, keep_default_na=False)
    units = discover_units(source_root)
    qa = qa.drop(columns=[column for column in ("prediction", "answer") if column in qa.columns])
    qa["_unit"] = [resolve_unit(path, set(units)) for path in qa["path"]]

    selected_paths: list[str] = []
    for source, category in (("HAU", "emotion"), ("HARn", "single")):
        candidates = qa[(qa["source"] == source) & (qa["category"] == category) & qa["_unit"].notna()]
        if candidates.empty:
            raise ValueError(f"No fixture candidate for {source}/{category}")
        selected_paths.append(sorted(candidates["path"].unique())[0])
    original = qa[qa["path"].isin(selected_paths)].drop(columns="_unit").sort_values(["path", "qa_id"]).reset_index(drop=True)
    original_units = {resolve_unit(path, set(units)) for path in selected_paths}
    if None in original_units or len(original_units) != 2:
        raise ValueError("Fixture selection did not resolve to two unique raw units")
    original_map = {str(unit): str(unit) for unit in original_units}

    synthetic_units = ["incoming_batch_alpha/novel_clip_blue", "incoming_batch_alpha/novel_clip_gold"]
    unit_pairs = dict(zip(sorted(original_units), synthetic_units))
    path_to_unit = {path: resolve_unit(path, set(units)) for path in selected_paths}
    renamed = original.copy()
    renamed["qa_id"] = [f"owned_unseen_qa_{index:04d}" for index in range(1, len(renamed) + 1)]
    renamed["path"] = [
        unit_pairs[str(path_to_unit[path])] + "/Depth/Depth.mp4" for path in original["path"]
    ]

    write_case(output / "original", original, original_map, source_root)
    write_case(output / "renamed", renamed, unit_pairs, source_root)
    report = {
        "experiment": "stage2_native_owned_raw_fixture_v1",
        "rows": len(original),
        "clips": len(selected_paths),
        "categories": original["category"].value_counts().sort_index().to_dict(),
        "source_units": sorted(original_units),
        "synthetic_units": synthetic_units,
        "labels_read_or_written": False,
        "files": {},
    }
    for path in sorted(output.rglob("*")):
        if path.is_file():
            report["files"][str(path.relative_to(output))] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    (output / "fixture.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
