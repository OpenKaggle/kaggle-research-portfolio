#!/usr/bin/env python3
"""Fetch and validate the six official Kaggle files after rules are accepted.

This script never joins a competition or accepts rules. It fails before any
download unless the authenticated API already reports userHasEntered=True.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import pathlib
import subprocess
from datetime import datetime, timezone


COMPETITION = "arc-prize-2026-arc-agi-2"
FILES = (
    "arc-agi_evaluation_challenges.json",
    "arc-agi_evaluation_solutions.json",
    "arc-agi_test_challenges.json",
    "arc-agi_training_challenges.json",
    "arc-agi_training_solutions.json",
    "sample_submission.json",
)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: pathlib.Path, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout if capture else ""


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    workspace = root.parent
    kaggle = workspace / ".venv/bin/kaggle"
    output_dir = root / "official/competition_files"

    listing = run(
        [str(kaggle), "competitions", "list", "-s", COMPETITION, "--csv"],
        workspace,
        capture=True,
    )
    listing_lines = listing.splitlines()
    try:
        header_index = next(
            index for index, line in enumerate(listing_lines) if line.startswith("ref,")
        )
    except StopIteration as exc:
        raise RuntimeError(f"Kaggle competition listing had no CSV header: {listing!r}") from exc
    rows = list(csv.DictReader(io.StringIO("\n".join(listing_lines[header_index:]))))
    matches = [row for row in rows if row["ref"].rstrip("/").endswith(COMPETITION)]
    if len(matches) != 1 or matches[0].get("userHasEntered") != "True":
        raise SystemExit(
            "Kaggle still reports userHasEntered=False; accept the competition rules "
            "in the browser first. No files were downloaded."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        run(
            [
                str(kaggle),
                "competitions",
                "download",
                "-c",
                COMPETITION,
                "-f",
                filename,
                "-p",
                str(output_dir),
            ],
            workspace,
        )

    loaded = {
        name: json.loads((output_dir / name).read_text(encoding="utf-8"))
        for name in FILES
    }
    for split in ("training", "evaluation"):
        challenges = loaded[f"arc-agi_{split}_challenges.json"]
        solutions = loaded[f"arc-agi_{split}_solutions.json"]
        if set(challenges) != set(solutions):
            raise RuntimeError(f"{split} challenge/solution task IDs do not match")
        for task_id, task in challenges.items():
            if len(task["test"]) != len(solutions[task_id]):
                raise RuntimeError(f"{split}/{task_id}: solution output count mismatch")

    test = loaded["arc-agi_test_challenges.json"]
    sample = loaded["sample_submission.json"]
    if set(test) != set(sample):
        raise RuntimeError("test challenge/sample task IDs do not match")
    for task_id, task in test.items():
        if len(task["test"]) != len(sample[task_id]):
            raise RuntimeError(f"test/{task_id}: sample output count mismatch")

    manifest = {
        "competition": COMPETITION,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "user_has_entered": True,
        "splits": {
            "training": {
                "tasks": len(loaded["arc-agi_training_challenges.json"]),
                "outputs": sum(
                    len(task["test"])
                    for task in loaded["arc-agi_training_challenges.json"].values()
                ),
            },
            "evaluation": {
                "tasks": len(loaded["arc-agi_evaluation_challenges.json"]),
                "outputs": sum(
                    len(task["test"])
                    for task in loaded["arc-agi_evaluation_challenges.json"].values()
                ),
            },
            "test": {
                "tasks": len(test),
                "outputs": sum(len(task["test"]) for task in test.values()),
            },
        },
        "files": {
            name: {
                "bytes": (output_dir / name).stat().st_size,
                "sha256": sha256(output_dir / name),
            }
            for name in FILES
        },
    }
    manifest_path = output_dir / "competition_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
