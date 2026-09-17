#!/usr/bin/env python3
"""Concatenate CSV parts while validating and preserving exactly one header."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def concatenate(inputs: list[Path], output: Path) -> int:
    if not inputs:
        raise ValueError("at least one input is required")
    header = None
    rows = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as sink:
        for path in inputs:
            with path.open("r", encoding="utf-8", newline="") as source:
                current = source.readline()
                if not current:
                    raise ValueError(f"empty CSV part: {path}")
                if header is None:
                    header = current
                    sink.write(current)
                elif current != header:
                    raise ValueError(f"header mismatch in {path}")
                for line in source:
                    sink.write(line)
                    rows += 1
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    rows = concatenate([path.resolve() for path in args.inputs], args.output.resolve())
    print(f"rows={rows} output={args.output.resolve()}")


if __name__ == "__main__":
    main()
