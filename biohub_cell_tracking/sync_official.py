#!/usr/bin/env python3
"""Snapshot official Kaggle competition metadata for auditability."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi


COMPETITION = "biohub-cell-tracking-during-development"
ROOT = Path(__file__).resolve().parent
OFFICIAL = ROOT / "official"
PAGES = OFFICIAL / "pages"


def json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    OFFICIAL.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()
    synced_at = datetime.now(timezone.utc).isoformat()

    competitions = api.competitions_list(search=COMPETITION, page_size=20)
    matches = [
        item.to_dict(ignore_defaults=False)
        for item in (competitions.competitions if competitions else [])
        if COMPETITION in item.ref
    ]

    pages = api.competition_list_pages(COMPETITION)
    page_receipts = []
    for page in pages:
        page_path = PAGES / f"{page.name.lower().replace(' ', '-')}.md"
        page_path.write_text(page.content, encoding="utf-8")
        page_receipts.append(
            {
                "name": page.name,
                "path": str(page_path.relative_to(ROOT)),
                "sha256": sha256(page_path),
            }
        )

    files = []
    page_token = None
    while True:
        response = api.competition_list_files(COMPETITION, page_token=page_token, page_size=200)
        files.extend(response.files or [])
        page_token = response.next_page_token
        if not page_token:
            break

    manifest_path = OFFICIAL / "file_manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "total_bytes", "creation_date"])
        writer.writeheader()
        for item in files:
            writer.writerow(
                {
                    "name": item.name,
                    "total_bytes": item.total_bytes,
                    "creation_date": item.creation_date.isoformat() if item.creation_date else "",
                }
            )

    split_counts: Counter[str] = Counter()
    split_bytes: Counter[str] = Counter()
    for item in files:
        split = item.name.split("/", 1)[0] if "/" in item.name else "root"
        split_counts[split] += 1
        split_bytes[split] += item.total_bytes

    receipt = {
        "competition": COMPETITION,
        "competition_url": f"https://www.kaggle.com/competitions/{COMPETITION}",
        "synced_at_utc": synced_at,
        "cli_state": matches,
        "rules_acceptance": {
            "accepted": bool(matches and matches[0].get("userHasEntered")),
            "ui_receipt": "Kaggle displayed: Rules accepted. Good luck!",
            "optional_marketing_or_data_sharing": "No optional controls were presented in the join dialog.",
        },
        "pages": page_receipts,
        "files": {
            "count": len(files),
            "total_bytes": sum(item.total_bytes for item in files),
            "by_split_count": dict(sorted(split_counts.items())),
            "by_split_bytes": dict(sorted(split_bytes.items())),
            "manifest_path": str(manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256(manifest_path),
        },
    }
    receipt_path = OFFICIAL / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False, default=json_default))


if __name__ == "__main__":
    main()
