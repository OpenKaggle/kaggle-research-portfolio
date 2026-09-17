#!/usr/bin/env python3
"""Fetch the complete official Kaggle file inventory without downloading the data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi


COMPETITION = "hyperspectral-object-detection-challenge-2026"
ROOT = Path(__file__).resolve().parents[1]


def stage(name: str) -> str:
    lower = name.lower()
    if "ranking" in lower:
        return "ranking"
    if "data_train" in lower:
        return "train"
    if "data_test" in lower:
        return "test"
    return "metadata"


def main() -> None:
    api = KaggleApi()
    api.authenticate()
    rows: list[dict[str, object]] = []
    token: str | None = None
    page = 0
    while True:
        response = api.competition_list_files(COMPETITION, page_token=token, page_size=200)
        page += 1
        rows.extend(
            {
                "name": item.name,
                "bytes": int(item.total_bytes),
                "creation_utc": str(item.creation_date),
                "stage": stage(item.name),
            }
            for item in response.files
        )
        print(f"manifest page {page}: {len(rows)} files", flush=True)
        token = response.next_page_token or None
        if token is None:
            break

    rows.sort(key=lambda row: str(row["name"]))
    manifest = ROOT / "official" / "official_file_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "bytes", "creation_utc", "stage"])
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    sizes: dict[str, int] = {}
    for row in rows:
        key = str(row["stage"])
        counts[key] = counts.get(key, 0) + 1
        sizes[key] = sizes.get(key, 0) + int(row["bytes"])
    summary = {
        "competition": COMPETITION,
        "file_count": len(rows),
        "total_bytes": sum(int(row["bytes"]) for row in rows),
        "counts_by_stage": counts,
        "bytes_by_stage": sizes,
        "ranking_files_present": counts.get("ranking", 0) > 0,
    }
    (ROOT / "official" / "official_file_manifest_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
