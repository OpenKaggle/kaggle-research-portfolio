#!/usr/bin/env python3
"""Download one complete public training sample through the official Kaggle API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi


COMPETITION = "biohub-cell-tracking-during-development"
ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "official" / "file_manifest.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample", nargs="?", default="6bba_43fea39d")
    parser.add_argument(
        "--geff-only",
        action="store_true",
        help="Download only the sparse GEFF annotation graph, not the image Zarr.",
    )
    args = parser.parse_args()

    prefixes = (f"train/{args.sample}.geff/",)
    if not args.geff_only:
        prefixes = (f"train/{args.sample}.zarr/", *prefixes)
    rows = []
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["name"].startswith(prefixes):
                rows.append(row)
    if not rows:
        raise RuntimeError(f"Sample not found in official manifest: {args.sample}")

    destination = ROOT / "data" / "sample" / args.sample
    api = KaggleApi()
    api.authenticate()
    receipts = []
    for index, row in enumerate(rows, start=1):
        remote = row["name"]
        relative = Path(remote).relative_to("train")
        local = destination / relative
        expected_bytes = int(row["total_bytes"])
        local.parent.mkdir(parents=True, exist_ok=True)
        if not local.is_file() or local.stat().st_size != expected_bytes:
            api.competition_download_file(
                COMPETITION, remote, path=str(local.parent), force=True, quiet=True
            )
        actual_bytes = local.stat().st_size
        if actual_bytes != expected_bytes:
            raise RuntimeError(
                f"Size mismatch for {remote}: expected {expected_bytes}, got {actual_bytes}"
            )
        receipts.append(
            {
                "remote": remote,
                "relative": str(local.relative_to(destination)),
                "bytes": actual_bytes,
                "sha256": sha256(local),
            }
        )
        print(f"[{index}/{len(rows)}] {remote} {actual_bytes}", flush=True)

    receipt = {
        "competition": COMPETITION,
        "sample": args.sample,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Official Kaggle competition API",
        "scope": "geff_only" if args.geff_only else "zarr_and_geff",
        "file_count": len(receipts),
        "total_bytes": sum(item["bytes"] for item in receipts),
        "files": receipts,
    }
    receipt_path = destination / "DOWNLOAD_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"receipt={receipt_path}", flush=True)


if __name__ == "__main__":
    main()
