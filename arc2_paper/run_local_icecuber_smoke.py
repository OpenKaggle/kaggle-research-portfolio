#!/usr/bin/env python3
"""Run a solution-blind one-task Icecuber compatibility smoke locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_submission(challenge_path: Path, submission_path: Path) -> bool:
    challenges = json.loads(challenge_path.read_text(encoding="utf-8"))
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    if set(submission) != set(challenges):
        return False
    for task_id, task in challenges.items():
        rows = submission[task_id]
        if not isinstance(rows, list) or len(rows) != len(task["test"]):
            return False
        for attempts in rows:
            if not isinstance(attempts, dict) or set(attempts) != {"attempt_1", "attempt_2"}:
                return False
            for grid in attempts.values():
                if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
                    return False
                if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
                    return False
                width = len(grid[0])
                if any(not isinstance(row, list) or len(row) != width for row in grid):
                    return False
                if any(
                    type(value) is not int or not 0 <= value <= 9
                    for row in grid
                    for value in row
                ):
                    return False
    return True


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", default="bc1d5164")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "artifacts" / "icecuber_local_smoke_bc1d5164",
    )
    args = parser.parse_args()

    challenges_path = root / "official" / "competition_files" / "arc-agi_training_challenges.json"
    source_entry = root / "public_assets" / "trm_source" / "run_entry.py"
    challenges = json.loads(challenges_path.read_text(encoding="utf-8"))
    if args.task_id not in challenges:
        raise KeyError(args.task_id)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = args.output_dir / "input"
    working_dir = args.output_dir / "working"
    input_dir.mkdir(exist_ok=True)
    working_dir.mkdir(exist_ok=True)
    smoke_challenge = input_dir / "arc-agi_test_challenges.json"
    smoke_challenge.write_text(
        json.dumps({args.task_id: challenges[args.task_id]}, separators=(",", ":")),
        encoding="utf-8",
    )

    environment = os.environ.copy()
    environment["ARC_INPUT_ROOT"] = str(input_dir.resolve())
    environment["ARC_WORKING_ROOT"] = str(working_dir.resolve())
    started = time.time()
    result = subprocess.run(
        [sys.executable, str(source_entry)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=360,
        check=False,
    )
    elapsed = time.time() - started
    log_path = args.output_dir / "smoke.log"
    log_path.write_text(result.stdout, encoding="utf-8")
    submission_path = working_dir / "submission.json"

    guards = {
        "returncode_zero": result.returncode == 0,
        "compiled": (working_dir / "proof_search_runtime" / "third_party" / "icecuber" / "run").is_file(),
        "submission_exists": submission_path.is_file(),
    }
    if submission_path.is_file():
        try:
            guards["submission_schema_valid"] = valid_submission(
                smoke_challenge, submission_path
            )
        except Exception:
            guards["submission_schema_valid"] = False
    else:
        guards["submission_schema_valid"] = False

    receipt = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "local runtime compatibility smoke; not accuracy evidence",
        "solver_family": "Icecuber depth 2 plus unchanged symbolic fallback",
        "data_boundary": "one official public-training challenge; solutions never loaded",
        "task_id": args.task_id,
        "task_count": 1,
        "returncode": result.returncode,
        "elapsed_seconds": elapsed,
        "guards": guards,
        "all_guards_passed": all(guards.values()),
        "input_sha256": sha256(smoke_challenge),
        "source_entry_sha256": sha256(source_entry),
        "submission_sha256": sha256(submission_path) if submission_path.is_file() else None,
        "log_sha256": sha256(log_path),
        "external_actions": False,
        "solutions_loaded": False,
    }
    receipt_path = args.output_dir / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if not receipt["all_guards_passed"]:
        print("\n".join(result.stdout.splitlines()[-80:]), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
