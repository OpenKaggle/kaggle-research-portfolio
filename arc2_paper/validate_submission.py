#!/usr/bin/env python3
"""Validate ARC-AGI-2 submission schema against a challenge file."""

from __future__ import annotations

import argparse
import json
import pathlib


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("challenge", type=pathlib.Path)
    parser.add_argument("submission", type=pathlib.Path)
    args = parser.parse_args()

    challenge = json.loads(args.challenge.read_text(encoding="utf-8"))
    submission = json.loads(args.submission.read_text(encoding="utf-8"))
    if set(challenge) != set(submission):
        missing = sorted(set(challenge) - set(submission))
        extra = sorted(set(submission) - set(challenge))
        raise SystemExit(f"task mismatch; missing={missing[:5]}, extra={extra[:5]}")

    output_count = 0
    for task_id, task in challenge.items():
        expected = len(task["test"])
        rows = submission[task_id]
        if not isinstance(rows, list) or len(rows) != expected:
            raise SystemExit(f"{task_id}: expected {expected} outputs, got {len(rows)}")
        for output_index, attempts in enumerate(rows):
            if set(attempts) != {"attempt_1", "attempt_2"}:
                raise SystemExit(f"{task_id}_{output_index}: invalid attempt keys")
            for name, grid in attempts.items():
                if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
                    raise SystemExit(f"{task_id}_{output_index}_{name}: invalid height")
                if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
                    raise SystemExit(f"{task_id}_{output_index}_{name}: invalid width")
                width = len(grid[0])
                if any(not isinstance(row, list) or len(row) != width for row in grid):
                    raise SystemExit(f"{task_id}_{output_index}_{name}: non-rectangular")
                if any(
                    type(value) is not int or not 0 <= value <= 9
                    for row in grid
                    for value in row
                ):
                    raise SystemExit(f"{task_id}_{output_index}_{name}: invalid color")
            output_count += 1
    print(f"valid: {len(challenge)} tasks, {output_count} outputs, two attempts each")


if __name__ == "__main__":
    main()
