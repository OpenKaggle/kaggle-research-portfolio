#!/usr/bin/env python3
"""Build paper-ready family and rule summaries from an exact-rule audit."""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
from collections import defaultdict


def shape(grid: list[list[int]]) -> tuple[int, int]:
    return len(grid), len(grid[0])


def size_family(input_grid: list[list[int]], output_grid: list[list[int]]) -> str:
    ih, iw = shape(input_grid)
    oh, ow = shape(output_grid)
    if (ih, iw) == (oh, ow):
        return "same_shape"
    if oh <= ih and ow <= iw:
        return "contract"
    if oh >= ih and ow >= iw:
        return "expand"
    return "mixed_shape"


def palette_family(input_grid: list[list[int]], output_grid: list[list[int]]) -> str:
    source = {value for row in input_grid for value in row}
    target = {value for row in output_grid for value in row}
    if source == target:
        return "same_palette"
    if target < source:
        return "output_palette_subset"
    if source < target:
        return "output_palette_superset"
    return "palette_changed"


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_dir", type=pathlib.Path)
    parser.add_argument("data_dir", type=pathlib.Path)
    args = parser.parse_args()

    with (args.audit_dir / "per_output.csv").open(encoding="utf-8") as file:
        audit_rows = list(csv.DictReader(file))
    tasks = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in args.data_dir.glob("*.json")
    }

    enriched = []
    reason_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"selected_outputs": 0, "correct_outputs": 0}
    )
    for row in audit_rows:
        task = tasks[row["task_id"]]
        output_index = int(row["output_index"])
        input_grid = task["test"][output_index]["input"]
        output_grid = task["test"][output_index]["output"]
        selected = row["direct_selected"] == "True"
        correct = row["direct_correct"] == "True"
        item = dict(row)
        item.update(
            {
                "size_family": size_family(input_grid, output_grid),
                "palette_family": palette_family(input_grid, output_grid),
                "input_shape": "x".join(map(str, shape(input_grid))),
                "input_palette_size": len({value for line in input_grid for value in line}),
                "output_palette_size": len({value for line in output_grid for value in line}),
                "candidate_status": "selected" if selected else "no_unique_loo_candidate",
            }
        )
        enriched.append(item)
        if selected:
            for reason in filter(None, row["selected_reasons"].split("|")):
                reason_counts[reason]["selected_outputs"] += 1
                reason_counts[reason]["correct_outputs"] += int(correct)

    family_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"outputs": 0, "selected": 0, "correct": 0}
    )
    for row in enriched:
        key = (row["size_family"], row["palette_family"])
        family_counts[key]["outputs"] += 1
        family_counts[key]["selected"] += int(row["direct_selected"] == "True")
        family_counts[key]["correct"] += int(row["direct_correct"] == "True")

    family_rows = []
    for (size_name, palette_name), counts in sorted(family_counts.items()):
        family_rows.append(
            {
                "size_family": size_name,
                "palette_family": palette_name,
                **counts,
                "coverage": counts["selected"] / counts["outputs"],
                "precision": (
                    counts["correct"] / counts["selected"] if counts["selected"] else ""
                ),
            }
        )
    reason_rows = [
        {
            "reason": reason,
            **counts,
            "precision": counts["correct_outputs"] / counts["selected_outputs"],
        }
        for reason, counts in sorted(reason_counts.items())
    ]

    outputs = {
        "enriched_per_output.csv": enriched,
        "family_summary.csv": family_rows,
        "reason_summary.csv": reason_rows,
        "no_candidate_outputs.csv": [
            row for row in enriched if row["candidate_status"] == "no_unique_loo_candidate"
        ],
    }
    for filename, rows in outputs.items():
        path = args.audit_dir / filename
        if not rows:
            path.write_text("", encoding="utf-8")
            continue
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(
        json.dumps(
            {
                "audit": str(args.audit_dir),
                "outputs": len(enriched),
                "selected": sum(row["direct_selected"] == "True" for row in enriched),
                "families": len(family_rows),
                "selected_reasons": len(reason_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
