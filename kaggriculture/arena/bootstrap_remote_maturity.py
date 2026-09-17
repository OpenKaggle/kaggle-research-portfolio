"""Bootstrap mature public-score diagnostics without using hidden replay data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def score(outcome: str) -> float:
    if outcome == "win":
        return 1.0
    if outcome == "tie":
        return 0.5
    if outcome == "loss":
        return 0.0
    raise ValueError(f"unexpected outcome {outcome!r}")


def load_rows(path: Path, expected_label: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("filter", {}).get("label") != expected_label:
        raise ValueError(f"label mismatch in {path}")
    if report.get("filter", {}).get("outcomes") != ["loss", "tie", "win"]:
        raise ValueError(f"diagnostic does not contain every outcome in {path}")
    rows = report.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"missing diagnostic rows in {path}")
    if any(row.get("owned_seat") not in {0, 1} for row in rows):
        raise ValueError(f"invalid seat in {path}")
    return report, rows


def sample_metrics(rows: list[dict[str, Any]]) -> tuple[float, float, float]:
    scores = [score(str(row["outcome"])) for row in rows]
    margins = [float(row["final_margin"]) for row in rows]
    return (
        statistics.fmean(scores),
        statistics.fmean(margins),
        percentile(margins, 0.10),
    )


def observed(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score_rate, mean_margin, p10_margin = sample_metrics(rows)
    by_seat = {
        seat: [row for row in rows if int(row["owned_seat"]) == seat]
        for seat in (0, 1)
    }
    return {
        "games": len(rows),
        "wins": sum(row["outcome"] == "win" for row in rows),
        "ties": sum(row["outcome"] == "tie" for row in rows),
        "losses": sum(row["outcome"] == "loss" for row in rows),
        "score_rate": score_rate,
        "mean_margin": mean_margin,
        "p10_margin": p10_margin,
        "worst_margin": min(float(row["final_margin"]) for row in rows),
        "seat_games": {str(seat): len(values) for seat, values in by_seat.items()},
        "seat_balanced_score_rate": statistics.fmean(
            statistics.fmean(score(str(row["outcome"])) for row in values)
            for values in by_seat.values()
        ),
    }


def stratified_bootstrap(
    rows: list[dict[str, Any]], draws: int, rng: random.Random
) -> dict[str, list[float]]:
    by_seat = {
        seat: [row for row in rows if int(row["owned_seat"]) == seat]
        for seat in (0, 1)
    }
    if any(not values for values in by_seat.values()):
        raise ValueError("stratified bootstrap requires both seats")
    result = {
        "score_rate": [],
        "seat_balanced_score_rate": [],
        "mean_margin": [],
        "p10_margin": [],
    }
    for _ in range(draws):
        sampled_by_seat = {
            seat: rng.choices(values, k=len(values))
            for seat, values in by_seat.items()
        }
        combined = sampled_by_seat[0] + sampled_by_seat[1]
        score_rate, mean_margin, p10_margin = sample_metrics(combined)
        result["score_rate"].append(score_rate)
        result["mean_margin"].append(mean_margin)
        result["p10_margin"].append(p10_margin)
        result["seat_balanced_score_rate"].append(
            statistics.fmean(
                statistics.fmean(score(str(row["outcome"])) for row in sampled_by_seat[seat])
                for seat in (0, 1)
            )
        )
    return result


def interval(values: list[float]) -> list[float]:
    return [percentile(values, 0.025), percentile(values, 0.975)]


def summarize_bootstrap(values: dict[str, list[float]]) -> dict[str, Any]:
    return {
        metric: {
            "mean": statistics.fmean(samples),
            "interval_95pct": interval(samples),
        }
        for metric, samples in values.items()
    }


def difference_bootstrap(
    public: dict[str, list[float]], hybrid: dict[str, list[float]]
) -> dict[str, Any]:
    if public.keys() != hybrid.keys() or any(
        len(public[key]) != len(hybrid[key]) for key in public
    ):
        raise ValueError("bootstrap distributions are not aligned")
    result = {}
    for metric in public:
        differences = [
            hybrid_value - public_value
            for public_value, hybrid_value in zip(public[metric], hybrid[metric], strict=True)
        ]
        result[metric] = {
            "hybrid_minus_public_mean": statistics.fmean(differences),
            "interval_95pct": interval(differences),
            "probability_hybrid_greater": sum(value > 0 for value in differences) / len(differences),
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--public-diagnostic", type=Path, required=True)
    parser.add_argument("--hybrid-diagnostic", type=Path, required=True)
    parser.add_argument("--draws", type=int, default=20_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.draws < 1_000:
        raise ValueError("use at least 1,000 bootstrap draws")

    summary_path = args.summary.resolve()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    public_path = args.public_diagnostic.resolve()
    hybrid_path = args.hybrid_diagnostic.resolve()
    public_report, public_rows = load_rows(public_path, "public_state_955")
    hybrid_report, hybrid_rows = load_rows(hybrid_path, "hybrid_public_guard_v1")
    summary_hash = sha256(summary_path)
    if {
        public_report.get("source_summary_sha256"),
        hybrid_report.get("source_summary_sha256"),
    } != {summary_hash}:
        raise ValueError("diagnostics were not generated from the supplied summary")

    remote = {row["label"]: row for row in summary["submissions"]}
    if set(remote) != {"public_state_955", "hybrid_public_guard_v1"}:
        raise ValueError("unexpected remote submission labels")
    for label, rows in (
        ("public_state_955", public_rows),
        ("hybrid_public_guard_v1", hybrid_rows),
    ):
        if len(rows) != int(remote[label]["summary"]["evaluation"]["games"]):
            raise ValueError(f"game count mismatch for {label}")

    rng = random.Random(20260909)
    public_boot = stratified_bootstrap(public_rows, args.draws, rng)
    hybrid_boot = stratified_bootstrap(hybrid_rows, args.draws, rng)
    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "summary_path": str(summary_path),
            "summary_sha256": summary_hash,
            "public_diagnostic_path": str(public_path),
            "public_diagnostic_sha256": sha256(public_path),
            "hybrid_diagnostic_path": str(hybrid_path),
            "hybrid_diagnostic_sha256": sha256(hybrid_path),
        },
        "method": {
            "draws": args.draws,
            "random_seed": 20260909,
            "resampling": "independent episode bootstrap stratified by owned seat; original seat counts retained",
            "interval": "2.5th to 97.5th bootstrap percentiles",
        },
        "privacy_boundary": {
            "used": ["public outcome", "owned seat", "final public margin"],
            "excluded": [
                "hidden seed",
                "opponent private state or logs",
                "episode/submission/opponent identity as a policy signal",
            ],
        },
        "submissions": {
            "public_state_955": {
                "submission_id": int(remote["public_state_955"]["id"]),
                "rating": float(remote["public_state_955"]["remote"]["public_score"]),
                "observed": observed(public_rows),
                "bootstrap": summarize_bootstrap(public_boot),
            },
            "hybrid_public_guard_v1": {
                "submission_id": int(remote["hybrid_public_guard_v1"]["id"]),
                "rating": float(remote["hybrid_public_guard_v1"]["remote"]["public_score"]),
                "observed": observed(hybrid_rows),
                "bootstrap": summarize_bootstrap(hybrid_boot),
            },
        },
        "unpaired_hybrid_minus_public": {
            "warning": "remote episodes are not paired by opponent/world; intervals describe sampling uncertainty but are not causal A/B evidence",
            "rating_point_difference": (
                float(remote["hybrid_public_guard_v1"]["remote"]["public_score"])
                - float(remote["public_state_955"]["remote"]["public_score"])
            ),
            "bootstrap": difference_bootstrap(public_boot, hybrid_boot),
        },
        "decision": {
            "active_slots_changed": False,
            "candidate_created": False,
            "submission_change": False,
            "interpretation": "rating gap is mature and stable, while episode-level unpaired uncertainty still overlaps on some metrics; retain both active best-of-two hedges and do not infer a policy change",
        },
    }
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(destination),
                "sha256": sha256(destination),
                "public": output["submissions"]["public_state_955"],
                "hybrid": output["submissions"]["hybrid_public_guard_v1"],
                "difference": output["unpaired_hybrid_minus_public"],
                "decision": output["decision"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
