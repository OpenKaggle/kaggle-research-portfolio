#!/usr/bin/env python3
"""Fail-closed validator for heterogeneous ARC candidate JSONL receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


REQUIRED = {
    "schema_version",
    "task_id",
    "output_index",
    "candidate_id",
    "grid",
    "grid_sha256",
    "solver",
    "generation",
    "provenance",
    "label_boundary",
}
ALLOWED = REQUIRED | {"demo_predictions", "structural_metadata", "evidence"}
BANNED_EVIDENCE_TOKENS = {
    "target",
    "test_label",
    "test_solution",
    "heldout_output",
    "test_correct",
    "public_eval_correct",
}


def validate_object_keys(
    value: object,
    context: str,
    required: set[str],
    allowed: set[str],
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{context}: must be an object")
    missing = required - set(value)
    extra = set(value) - allowed
    if missing or extra:
        raise ValueError(f"{context}: missing={sorted(missing)} extra={sorted(extra)}")
    return value


def validate_optional_string(value: object, context: str) -> None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{context}: must be a string or null")


def grid_hash(grid: list[list[int]]) -> str:
    encoded = json.dumps(grid, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_grid(grid: object, context: str) -> None:
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        raise ValueError(f"{context}: grid height must be 1..30")
    if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
        raise ValueError(f"{context}: grid width must be 1..30")
    width = len(grid[0])
    for row in grid:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"{context}: grid must be rectangular")
        for value in row:
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 9:
                raise ValueError(f"{context}: grid values must be integer colors 0..9")


def walk_keys(value: object, prefix: str = "") -> list[str]:
    keys = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            keys.append(path.lower())
            keys.extend(walk_keys(child, path))
    elif isinstance(value, list):
        for child in value:
            keys.extend(walk_keys(child, prefix))
    return keys


def validate_receipt(receipt: object, line_number: int) -> None:
    context = f"line {line_number}"
    if not isinstance(receipt, dict):
        raise ValueError(f"{context}: receipt must be an object")
    missing = REQUIRED - set(receipt)
    extra = set(receipt) - ALLOWED
    if missing or extra:
        raise ValueError(f"{context}: missing={sorted(missing)} extra={sorted(extra)}")
    if receipt["schema_version"] != 1:
        raise ValueError(f"{context}: unsupported schema_version")
    task_id = receipt["task_id"]
    if not isinstance(task_id, str) or len(task_id) != 8 or any(c not in "0123456789abcdef" for c in task_id):
        raise ValueError(f"{context}: task_id must be eight lowercase hex characters")
    if isinstance(receipt["output_index"], bool) or not isinstance(receipt["output_index"], int) or receipt["output_index"] < 0:
        raise ValueError(f"{context}: output_index must be a nonnegative integer")
    if not isinstance(receipt["candidate_id"], str) or not receipt["candidate_id"]:
        raise ValueError(f"{context}: candidate_id is required")

    validate_grid(receipt["grid"], context)
    expected_hash = grid_hash(receipt["grid"])
    if receipt["grid_sha256"] != expected_hash:
        raise ValueError(f"{context}: grid_sha256 mismatch; expected {expected_hash}")

    solver = validate_object_keys(
        receipt["solver"],
        f"{context}.solver",
        {"family", "version"},
        {"family", "version", "checkpoint", "program"},
    )
    if not isinstance(solver["family"], str) or not solver["family"] or not isinstance(solver["version"], str) or not solver["version"]:
        raise ValueError(f"{context}: solver family/version are required")
    for key in ("checkpoint", "program"):
        if key in solver:
            validate_optional_string(solver[key], f"{context}.solver.{key}")

    generation = validate_object_keys(
        receipt["generation"],
        f"{context}.generation",
        {"seed", "compute_seconds", "candidate_rank"},
        {"seed", "compute_seconds", "candidate_rank", "budget_name", "stopping_reason"},
    )
    seed = generation["seed"]
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, (int, str))):
        raise ValueError(f"{context}: generation.seed must be an integer, string, or null")
    if not isinstance(generation.get("compute_seconds"), (int, float)) or isinstance(generation.get("compute_seconds"), bool) or generation["compute_seconds"] < 0:
        raise ValueError(f"{context}: generation.compute_seconds must be nonnegative")
    if isinstance(generation.get("candidate_rank"), bool) or not isinstance(generation.get("candidate_rank"), int) or generation["candidate_rank"] < 1:
        raise ValueError(f"{context}: generation.candidate_rank must be >=1")
    for key in ("budget_name", "stopping_reason"):
        if key in generation:
            validate_optional_string(generation[key], f"{context}.generation.{key}")

    provenance = receipt["provenance"]
    if not isinstance(provenance, list) or not provenance:
        raise ValueError(f"{context}: at least one provenance row is required")
    for index, row in enumerate(provenance):
        row = validate_object_keys(
            row,
            f"{context}.provenance[{index}]",
            {"name", "version", "license", "sha256"},
            {"name", "version", "license", "sha256", "url"},
        )
        for key in ("name", "version", "license", "sha256"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"{context}: provenance[{index}].{key} is required")
        sha = row["sha256"]
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"{context}: provenance[{index}].sha256 is invalid")
        if "url" in row:
            validate_optional_string(row["url"], f"{context}.provenance[{index}].url")

    boundary = validate_object_keys(
        receipt["label_boundary"],
        f"{context}.label_boundary",
        {"generation_saw_target", "selection_saw_target", "evaluator_receipt_separate"},
        {"generation_saw_target", "selection_saw_target", "evaluator_receipt_separate"},
    )
    if boundary.get("generation_saw_target") is not False or boundary.get("selection_saw_target") is not False:
        raise ValueError(f"{context}: generation and selection must not see the target")
    if boundary.get("evaluator_receipt_separate") is not True:
        raise ValueError(f"{context}: evaluator receipt must be separate")

    if "demo_predictions" in receipt and (
        not isinstance(receipt["demo_predictions"], list)
        or any(not isinstance(row, dict) for row in receipt["demo_predictions"])
    ):
        raise ValueError(f"{context}: demo_predictions must be an array of objects")
    for key in ("structural_metadata", "evidence"):
        if key in receipt and not isinstance(receipt[key], dict):
            raise ValueError(f"{context}: {key} must be an object")

    for path in walk_keys(receipt.get("evidence", {})):
        leaf = path.rsplit(".", 1)[-1]
        normalized = leaf.replace("-", "_")
        if any(token in normalized for token in BANNED_EVIDENCE_TOKENS):
            raise ValueError(f"{context}: label-like evidence key is forbidden: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts", type=Path, help="JSONL file, one candidate receipt per line")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    rows = []
    for line_number, line in enumerate(args.receipts.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        receipt = json.loads(line)
        validate_receipt(receipt, line_number)
        rows.append(receipt)
    if not rows:
        raise SystemExit("no candidate receipts found")

    candidate_ids = [row["candidate_id"] for row in rows]
    duplicates = [key for key, count in Counter(candidate_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate candidate_id values: {duplicates[:10]}")
    summary = {
        "schema_version": 1,
        "receipts": len(rows),
        "tasks": len({row["task_id"] for row in rows}),
        "task_outputs": len({(row["task_id"], row["output_index"]) for row in rows}),
        "solver_families": dict(sorted(Counter(row["solver"]["family"] for row in rows).items())),
        "unique_grids": len({(row["task_id"], row["output_index"], row["grid_sha256"]) for row in rows}),
        "receipt_file_sha256": hashlib.sha256(args.receipts.read_bytes()).hexdigest(),
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
