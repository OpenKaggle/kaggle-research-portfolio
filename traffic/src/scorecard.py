#!/usr/bin/env python3
"""Transparent four-task scorecard for TrafficFlowBench."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


WEIGHTS = {
    "state": 0.35,
    "queue": 0.30,
    "physics": 0.15,
    "odme": 0.20,
}

OFFICIAL_BASELINE = {
    "state": 0.6903,
    "queue": 0.2518,
    "physics": 0.3467,
    "odme": 0.5904,
}


def build_scorecard(scores: dict[str, float | None]) -> list[dict[str, object]]:
    """Return task rows plus a weighted total.

    Unknown scores stay unknown instead of being silently converted to zero. The
    known weighted subtotal is useful locally because queue labels and the
    organizer boundary flows are not public.
    """
    rows: list[dict[str, object]] = []
    known = 0.0
    known_weight = 0.0
    for task, weight in WEIGHTS.items():
        score = scores.get(task)
        contribution = None if score is None else weight * score
        if contribution is not None:
            known += contribution
            known_weight += weight
        rows.append(
            {
                "task": task,
                "weight": weight,
                "score": score,
                "weighted_contribution": contribution,
                "availability": "known" if score is not None else "withheld/unmeasured",
            }
        )
    rows.append(
        {
            "task": "ALL",
            "weight": 1.0,
            "score": known if known_weight == 1.0 else None,
            "weighted_contribution": known,
            "availability": "complete" if known_weight == 1.0 else f"subtotal over weight {known_weight:.2f}",
        }
    )
    return rows


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    if not 0.0 <= result <= 1.0:
        raise argparse.ArgumentTypeError("component scores must be in [0, 1]")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=_number)
    parser.add_argument("--queue", type=_number)
    parser.add_argument("--physics", type=_number)
    parser.add_argument("--odme", type=_number)
    parser.add_argument("--official-baseline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    scores = OFFICIAL_BASELINE.copy() if args.official_baseline else {
        "state": args.state,
        "queue": args.queue,
        "physics": args.physics,
        "odme": args.odme,
    }
    rows = build_scorecard(scores)
    print("task      weight    score    contribution    availability")
    for row in rows:
        score = "?" if row["score"] is None else f"{float(row['score']):.6f}"
        contribution = row["weighted_contribution"]
        contribution_text = "?" if contribution is None else f"{float(contribution):.6f}"
        print(
            f"{str(row['task']):8s}  {float(row['weight']):.2f}    "
            f"{score:>8s}    {contribution_text:>12s}    {row['availability']}"
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
