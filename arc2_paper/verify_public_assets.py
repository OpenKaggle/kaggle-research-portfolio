#!/usr/bin/env python3
"""Fail closed unless the minimal public neural anchor assets are complete."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib


MODEL_FILES = {
    "added_tokens.json": 68,
    "config.json": 1532,
    "generation_config.json": 113,
    "model-00001-of-00002.safetensors": 4_996_836_472,
    "model-00002-of-00002.safetensors": 2_270_397_024,
    "model.safetensors.index.json": 32_913,
    "special_tokens_map.json": 367,
    "tokenizer.json": 1731,
    "tokenizer_config.json": 988,
    "vocab.json": 94,
}
TRM_FILES = {"step_220708": 2_159_719_349}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(root: pathlib.Path, expected: dict[str, int], hash_complete: bool) -> dict:
    rows = []
    for name, size in expected.items():
        matches = sorted(root.rglob(name))
        path = matches[0] if len(matches) == 1 else root / name
        actual = path.stat().st_size if path.is_file() else None
        complete = actual == size
        rows.append(
            {
                "name": name,
                "path": str(path),
                "expected_bytes": size,
                "actual_bytes": actual,
                "complete": complete,
                "sha256": sha256(path) if complete and hash_complete else None,
            }
        )
    return {
        "root": str(root),
        "complete": all(row["complete"] for row in rows),
        "files": rows,
    }


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--hash", action="store_true", help="hash only files whose sizes are complete")
    parser.add_argument(
        "--model-dir",
        type=pathlib.Path,
        default=root / "public_assets/qwen3_4b_grids15_sft139",
    )
    parser.add_argument(
        "--trm-dir",
        type=pathlib.Path,
        default=root / "public_assets/trm_checkpoint",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="optionally save the verification receipt as JSON",
    )
    args = parser.parse_args()
    report = {
        "qwen": check(args.model_dir, MODEL_FILES, args.hash),
        "trm": check(args.trm_dir, TRM_FILES, args.hash),
    }
    report["complete"] = report["qwen"]["complete"] and report["trm"]["complete"]
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
