"""Compare two candidate reports on identical seed/opponent/seat cells."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_rows(report: dict[str, Any], candidate: str, opponent: str) -> dict[tuple[int, int], float]:
    rows = {}
    for game in report["games"]:
        if {game["first"], game["second"]} != {candidate, opponent}:
            continue
        if game["first"] == candidate:
            seat = 0
            margin = float(game["margin_first"])
        else:
            seat = 1
            margin = -float(game["margin_first"])
        key = (int(game["seed"]), seat)
        if key in rows:
            raise ValueError(f"duplicate cell: {key}")
        rows[key] = margin
    return rows


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_report", type=Path)
    parser.add_argument("candidate_report", type=Path)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--opponent", required=True)
    parser.add_argument("--bootstrap", type=int, default=20_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline_path = args.baseline_report.resolve()
    candidate_path = args.candidate_report.resolve()
    baseline = candidate_rows(json.loads(baseline_path.read_text()), args.baseline, args.opponent)
    candidate = candidate_rows(json.loads(candidate_path.read_text()), args.candidate, args.opponent)
    if baseline.keys() != candidate.keys() or not baseline:
        raise ValueError("reports must contain identical non-empty seed/seat cells")

    per_seed = []
    for seed in sorted({key[0] for key in baseline}):
        baseline_values = [baseline[(seed, seat)] for seat in (0, 1)]
        candidate_values = [candidate[(seed, seat)] for seat in (0, 1)]
        baseline_margin = statistics.fmean(baseline_values)
        candidate_margin = statistics.fmean(candidate_values)
        per_seed.append({
            "seed": seed,
            "baseline_margin": baseline_margin,
            "candidate_margin": candidate_margin,
            "margin_delta": candidate_margin - baseline_margin,
            "baseline_score": statistics.fmean(1.0 if value > 0 else 0.0 if value < 0 else 0.5 for value in baseline_values),
            "candidate_score": statistics.fmean(1.0 if value > 0 else 0.0 if value < 0 else 0.5 for value in candidate_values),
        })

    deltas = [row["margin_delta"] for row in per_seed]
    rng = random.Random(20260908)
    boot = []
    for _ in range(args.bootstrap):
        boot.append(statistics.fmean(rng.choice(deltas) for _ in deltas))
    result = {
        "baseline": {"label": args.baseline, "path": str(baseline_path), "sha256": sha256(baseline_path)},
        "candidate": {"label": args.candidate, "path": str(candidate_path), "sha256": sha256(candidate_path)},
        "opponent": args.opponent,
        "paired_seeds": len(per_seed),
        "summary": {
            "mean_margin_delta": statistics.fmean(deltas),
            "median_margin_delta": statistics.median(deltas),
            "worst_margin_delta": min(deltas),
            "best_margin_delta": max(deltas),
            "improved_seeds": sum(delta > 0 for delta in deltas),
            "unchanged_seeds": sum(delta == 0 for delta in deltas),
            "degraded_seeds": sum(delta < 0 for delta in deltas),
            "candidate_score_delta": statistics.fmean(
                row["candidate_score"] - row["baseline_score"] for row in per_seed
            ),
            "bootstrap_mean_delta_95pct": [percentile(boot, 0.025), percentile(boot, 0.975)],
            "bootstrap_draws": args.bootstrap,
        },
        "per_seed": per_seed,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **result["summary"], "sha256": sha256(output)}, indent=2))


if __name__ == "__main__":
    main()
