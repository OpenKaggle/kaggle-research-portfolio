#!/usr/bin/env python3
"""Freeze the official Kaggle status record for one Biohub submission."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi


COMPETITION = "biohub-cell-tracking-during-development"
ROOT = Path(__file__).resolve().parent


def blank_to_none(value):
    return None if value in (None, "") else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission_id", type=int)
    args = parser.parse_args()

    api = KaggleApi()
    api.authenticate()
    submissions = api.competition_submissions(COMPETITION)
    match = next((item for item in submissions if int(item.ref) == args.submission_id), None)
    if match is None:
        raise RuntimeError(f"Submission {args.submission_id} not returned by official API")
    checked_at = datetime.now(timezone.utc)
    script_version_match = re.search(r"scriptVersionId=(\d+)", match.url or "")
    record = {
        "competition": COMPETITION,
        "checked_at_utc": checked_at.isoformat(),
        "submission_id": int(match.ref),
        "submitted_at_utc": match.date.replace(tzinfo=timezone.utc).isoformat(),
        "description": match.description,
        "file_name": match.file_name,
        "status": getattr(match.status, "name", str(match.status)),
        "error_description": blank_to_none(match.error_description),
        "public_score": blank_to_none(match.public_score),
        "private_score": blank_to_none(match.private_score),
        "submitted_by": match.submitted_by,
        "team_name": match.team_name,
        "kernel_url": match.url,
        "script_version_id": (
            int(script_version_match.group(1)) if script_version_match else None
        ),
        "is_frozen": bool(getattr(match, "_is_frozen", False)),
        "elapsed_seconds": (
            checked_at - match.date.replace(tzinfo=timezone.utc)
        ).total_seconds(),
        "source": "Official Kaggle competition submissions API",
    }
    destination = ROOT / "official" / f"submission_{args.submission_id}_status.json"
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
