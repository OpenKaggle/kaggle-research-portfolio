#!/usr/bin/env python3
"""Download only official test Zarr metadata for schema and bounds validation."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi


COMPETITION = "biohub-cell-tracking-during-development"
ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "official" / "file_manifest.csv"
DESTINATION = ROOT / "data" / "test_metadata"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["name"].startswith("test/") and row["name"].endswith("zarr.json")
        ]
    api = KaggleApi()
    api.authenticate()
    files = []
    for row in rows:
        remote = row["name"]
        relative = Path(remote).relative_to("test")
        local = DESTINATION / relative
        local.parent.mkdir(parents=True, exist_ok=True)
        api.competition_download_file(
            COMPETITION, remote, path=str(local.parent), force=True, quiet=True
        )
        expected_bytes = int(row["total_bytes"])
        if local.stat().st_size != expected_bytes:
            raise RuntimeError(f"Size mismatch for {remote}")
        files.append(
            {
                "remote": remote,
                "relative": str(relative),
                "bytes": expected_bytes,
                "sha256": sha256(local),
            }
        )
    receipt = {
        "competition": COMPETITION,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Official Kaggle competition API",
        "purpose": "schema and coordinate-bounds validation only",
        "files": files,
    }
    receipt_path = DESTINATION / "DOWNLOAD_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
