"""Audit two focal-agent league reports on identical opponent/seed/seat cells."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


SELLABLE_PRODUCTS = {
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def score(margin: float) -> float:
    return 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5


def first_shop(game: dict[str, Any]) -> str | None:
    for checkpoint in sorted(game.get("checkpoints", []), key=lambda row: row["observation_step"]):
        shops = checkpoint.get("shops", [])
        if shops:
            return str(shops[0])
    return None


def second_shop(game: dict[str, Any]) -> str | None:
    for checkpoint in sorted(game.get("checkpoints", []), key=lambda row: row["observation_step"]):
        shops = checkpoint.get("shops", [])
        if len(shops) >= 2:
            return str(shops[1])
    return None


def public_crop_counts_by_step(
    game: dict[str, Any], focal_seat: int
) -> dict[int, dict[str, int]]:
    """Keep only the opponent's public crop counts at recorded checkpoints."""
    result: dict[int, dict[str, int]] = {}
    for checkpoint in game.get("checkpoints", []):
        step = int(checkpoint.get("observation_step", checkpoint.get("step_index", -1)))
        farms = checkpoint.get("farms", [])
        rival = 1 - focal_seat
        if step < 0 or not isinstance(farms, list) or rival >= len(farms):
            continue
        crop_counts = farms[rival].get("crop_counts", {})
        if isinstance(crop_counts, dict):
            result[step] = {
                str(crop): int(count)
                for crop, count in crop_counts.items()
                if isinstance(count, (int, float))
            }
    return result


def own_sellable_shed_by_step(game: dict[str, Any], focal_seat: int) -> dict[int, int]:
    """Count only market-sellable products in the focal policy's own shed."""
    result: dict[int, int] = {}
    for checkpoint in game.get("checkpoints", []):
        step = int(checkpoint.get("observation_step", checkpoint.get("step_index", -1)))
        privates = checkpoint.get("private", [])
        if step < 0 or not isinstance(privates, list) or focal_seat >= len(privates):
            continue
        shed = privates[focal_seat].get("shed", {})
        if isinstance(shed, dict):
            result[step] = sum(
                int(count)
                for product, count in shed.items()
                if product in SELLABLE_PRODUCTS and isinstance(count, (int, float))
            )
    return result


def rows(report: dict[str, Any], focal: str) -> dict[tuple[str, int, int], dict[str, Any]]:
    result = {}
    for game in report["games"]:
        if game["first"] == focal:
            opponent, seat, margin = game["second"], 0, float(game["margin_first"])
        elif game["second"] == focal:
            opponent, seat, margin = game["first"], 1, -float(game["margin_first"])
        else:
            continue
        key = (str(opponent), int(game["seed"]), seat)
        if key in result:
            raise ValueError(f"duplicate cell: {key}")
        result[key] = {
            "margin": margin,
            "score": score(margin),
            "first_shop": first_shop(game),
            "second_shop": second_shop(game),
            "opponent_public_crops_by_step": public_crop_counts_by_step(game, seat),
            "own_sellable_shed_by_step": own_sellable_shed_by_step(game, seat),
            "statuses": game["statuses"],
        }
    return result


def metrics(values: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = list(values)
    margins = [item["margin"] for item in items]
    scores = [item["score"] for item in items]
    return {
        "games": len(items),
        "wins": sum(value == 1.0 for value in scores),
        "ties": sum(value == 0.5 for value in scores),
        "losses": sum(value == 0.0 for value in scores),
        "score_points": sum(scores),
        "score_rate": statistics.fmean(scores),
        "mean_margin": statistics.fmean(margins),
        "median_margin": statistics.median(margins),
        "p10_margin": percentile(margins, 0.10),
        "worst_margin": min(margins),
        "non_done": sum(item["statuses"] != ["DONE", "DONE"] for item in items),
    }


def paired_summary(
    keys: list[tuple[str, int, int]],
    baseline: dict[tuple[str, int, int], dict[str, Any]],
    candidate: dict[tuple[str, int, int], dict[str, Any]],
) -> dict[str, Any]:
    base_metrics = metrics(baseline[key] for key in keys)
    cand_metrics = metrics(candidate[key] for key in keys)
    deltas = [candidate[key]["margin"] - baseline[key]["margin"] for key in keys]
    return {
        "baseline": base_metrics,
        "candidate": cand_metrics,
        "delta": {
            "score_points": cand_metrics["score_points"] - base_metrics["score_points"],
            "score_rate": cand_metrics["score_rate"] - base_metrics["score_rate"],
            "mean_margin": cand_metrics["mean_margin"] - base_metrics["mean_margin"],
            "p10_margin": cand_metrics["p10_margin"] - base_metrics["p10_margin"],
            "worst_margin": cand_metrics["worst_margin"] - base_metrics["worst_margin"],
            "improved_cells": sum(delta > 0 for delta in deltas),
            "unchanged_cells": sum(delta == 0 for delta in deltas),
            "degraded_cells": sum(delta < 0 for delta in deltas),
        },
    }


def bootstrap_by_seed(
    keys: list[tuple[str, int, int]],
    baseline: dict[tuple[str, int, int], dict[str, Any]],
    candidate: dict[tuple[str, int, int], dict[str, Any]],
    draws: int,
) -> dict[str, Any]:
    grouped: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for key in keys:
        grouped[key[1]].append(
            (
                candidate[key]["margin"] - baseline[key]["margin"],
                candidate[key]["score"] - baseline[key]["score"],
            )
        )
    seed_values = [
        (statistics.fmean(value[0] for value in values), statistics.fmean(value[1] for value in values))
        for _, values in sorted(grouped.items())
    ]
    rng = random.Random(20260909)
    margin_boot, score_boot = [], []
    for _ in range(draws):
        sample = [rng.choice(seed_values) for _ in seed_values]
        margin_boot.append(statistics.fmean(value[0] for value in sample))
        score_boot.append(statistics.fmean(value[1] for value in sample))
    return {
        "seed_clusters": len(seed_values),
        "draws": draws,
        "mean_margin_delta_95pct": [percentile(margin_boot, 0.025), percentile(margin_boot, 0.975)],
        "score_rate_delta_95pct": [percentile(score_boot, 0.025), percentile(score_boot, 0.975)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_report", type=Path)
    parser.add_argument("candidate_report", type=Path)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--target-shop", action="append", default=[])
    parser.add_argument("--target-second-shop", action="append", default=[])
    parser.add_argument("--exclude-first-shop", action="append", default=[])
    parser.add_argument("--target-step", type=int)
    parser.add_argument("--target-opponent-crop")
    parser.add_argument("--target-opponent-crop-min", type=int)
    parser.add_argument("--target-owned-sellable-step", type=int)
    parser.add_argument("--target-owned-sellable-min", type=int)
    parser.add_argument("--bootstrap", type=int, default=20_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline_path = args.baseline_report.resolve()
    candidate_path = args.candidate_report.resolve()
    baseline_report = json.loads(baseline_path.read_text())
    candidate_report = json.loads(candidate_path.read_text())
    baseline = rows(baseline_report, args.baseline)
    candidate = rows(candidate_report, args.candidate)
    if baseline.keys() != candidate.keys() or not baseline:
        missing = sorted(set(baseline) - set(candidate))[:5]
        extra = sorted(set(candidate) - set(baseline))[:5]
        raise ValueError(f"cell mismatch: missing={missing}, extra={extra}")
    keys = sorted(baseline)
    for key in keys:
        if baseline[key]["first_shop"] != candidate[key]["first_shop"]:
            raise ValueError(f"first-shop mismatch at {key}")
        if baseline[key]["second_shop"] != candidate[key]["second_shop"]:
            raise ValueError(f"second-shop mismatch at {key}")
    crop_target_values = (
        args.target_step,
        args.target_opponent_crop,
        args.target_opponent_crop_min,
    )
    if any(value is not None for value in crop_target_values) and not all(
        value is not None for value in crop_target_values
    ):
        raise ValueError(
            "--target-step, --target-opponent-crop, and --target-opponent-crop-min must be used together"
        )
    crop_target_mismatches: list[tuple[str, int, int]] = []
    if args.target_step is not None:
        for key in keys:
            base_crops = baseline[key]["opponent_public_crops_by_step"].get(args.target_step, {})
            cand_crops = candidate[key]["opponent_public_crops_by_step"].get(args.target_step, {})
            if base_crops != cand_crops:
                crop_target_mismatches.append(key)
        if crop_target_mismatches:
            raise ValueError(
                f"target checkpoint is post-divergence for {crop_target_mismatches[:5]}"
            )
    sellable_target_values = (
        args.target_owned_sellable_step,
        args.target_owned_sellable_min,
    )
    if any(value is not None for value in sellable_target_values) and not all(
        value is not None for value in sellable_target_values
    ):
        raise ValueError(
            "--target-owned-sellable-step and --target-owned-sellable-min must be used together"
        )
    sellable_target_mismatches: list[tuple[str, int, int]] = []
    if args.target_owned_sellable_step is not None:
        for key in keys:
            base_value = baseline[key]["own_sellable_shed_by_step"].get(
                args.target_owned_sellable_step
            )
            cand_value = candidate[key]["own_sellable_shed_by_step"].get(
                args.target_owned_sellable_step
            )
            if base_value is None or cand_value is None:
                raise ValueError(f"missing owned-sellable checkpoint at {key}")
            if base_value != cand_value:
                sellable_target_mismatches.append(key)
        if sellable_target_mismatches:
            raise ValueError(
                f"owned-sellable target checkpoint is post-divergence for {sellable_target_mismatches[:5]}"
            )

    opponents = sorted({key[0] for key in keys})
    shops = sorted({baseline[key]["first_shop"] for key in keys})
    second_shops = sorted({baseline[key]["second_shop"] for key in keys})
    overall = paired_summary(keys, baseline, candidate)
    by_opponent = {
        opponent: paired_summary([key for key in keys if key[0] == opponent], baseline, candidate)
        for opponent in opponents
    }
    by_shop = {
        shop: paired_summary([key for key in keys if baseline[key]["first_shop"] == shop], baseline, candidate)
        for shop in shops
    }
    by_second_shop = {
        shop: paired_summary([key for key in keys if baseline[key]["second_shop"] == shop], baseline, candidate)
        for shop in second_shops
    }
    target_shops = sorted(set(args.target_shop))
    target_second_shops = sorted(set(args.target_second_shop))
    excluded_first_shops = sorted(set(args.exclude_first_shop))
    target_keys = [
        key for key in keys
        if (not target_shops or baseline[key]["first_shop"] in target_shops)
        and (not target_second_shops or baseline[key]["second_shop"] in target_second_shops)
        and baseline[key]["first_shop"] not in excluded_first_shops
        and (
            args.target_step is None
            or baseline[key]["opponent_public_crops_by_step"]
            .get(args.target_step, {})
            .get(args.target_opponent_crop, 0)
            >= args.target_opponent_crop_min
        )
        and (
            args.target_owned_sellable_step is None
            or baseline[key]["own_sellable_shed_by_step"].get(
                args.target_owned_sellable_step, 0
            )
            >= args.target_owned_sellable_min
        )
    ]
    base_target_failures = sum(baseline[key]["margin"] < 0 for key in target_keys)
    cand_target_failures = sum(candidate[key]["margin"] < 0 for key in target_keys)
    target_failure_reduction = (
        (base_target_failures - cand_target_failures) / base_target_failures
        if base_target_failures
        else None
    )
    opponent_net_points = {
        opponent: details["delta"]["score_points"] for opponent, details in by_opponent.items()
    }
    target_summary = paired_summary(target_keys, baseline, candidate) if target_keys else None
    target_by_opponent = {
        opponent: paired_summary(
            [key for key in target_keys if key[0] == opponent], baseline, candidate
        )
        for opponent in opponents
        if any(key[0] == opponent for key in target_keys)
    }
    target_by_first_shop = {
        shop: paired_summary(
            [key for key in target_keys if baseline[key]["first_shop"] == shop], baseline, candidate
        )
        for shop in sorted({baseline[key]["first_shop"] for key in target_keys})
    }
    target_cells = [
        {
            "opponent": key[0],
            "seed": key[1],
            "seat": key[2],
            "first_shop": baseline[key]["first_shop"],
            "second_shop": baseline[key]["second_shop"],
            "public_checkpoint_condition_value": (
                baseline[key]["opponent_public_crops_by_step"]
                .get(args.target_step, {})
                .get(args.target_opponent_crop, 0)
                if args.target_step is not None
                else None
            ),
            "owned_sellable_condition_value": (
                baseline[key]["own_sellable_shed_by_step"].get(
                    args.target_owned_sellable_step, 0
                )
                if args.target_owned_sellable_step is not None
                else None
            ),
            "baseline_margin": baseline[key]["margin"],
            "candidate_margin": candidate[key]["margin"],
            "margin_delta": candidate[key]["margin"] - baseline[key]["margin"],
            "baseline_score": baseline[key]["score"],
            "candidate_score": candidate[key]["score"],
        }
        for key in target_keys
    ]
    gate_checks = {
        "overall_score_strictly_higher": overall["delta"]["score_rate"] > 0,
        "no_opponent_net_score_loss": min(opponent_net_points.values()) >= 0,
        "p10_delta_at_least_minus_500": overall["delta"]["p10_margin"] >= -500,
        "worst_delta_at_least_minus_2500": overall["delta"]["worst_margin"] >= -2500,
        "target_failure_reduction_at_least_30pct": (
            target_failure_reduction is not None and target_failure_reduction >= 0.30
        ),
        "target_branch_at_least_8_games": len(target_keys) >= 8,
        "all_games_done": overall["baseline"]["non_done"] == overall["candidate"]["non_done"] == 0,
    }
    result = {
        "baseline": {
            "label": args.baseline,
            "path": str(baseline_path),
            "report_sha256": sha256(baseline_path),
            "bundle_sha256": baseline_report["agents"][args.baseline]["bundle_sha256"],
        },
        "candidate": {
            "label": args.candidate,
            "path": str(candidate_path),
            "report_sha256": sha256(candidate_path),
            "bundle_sha256": candidate_report["agents"][args.candidate]["bundle_sha256"],
        },
        "paired_cells": len(keys),
        "seeds": sorted({key[1] for key in keys}),
        "opponents": opponents,
        "overall": overall,
        "bootstrap_by_seed": bootstrap_by_seed(keys, baseline, candidate, args.bootstrap),
        "by_opponent": by_opponent,
        "by_first_shop": by_shop,
        "by_second_shop": by_second_shop,
        "target": {
            "first_shops": target_shops,
            "second_shops": target_second_shops,
            "excluded_first_shops": excluded_first_shops,
            "public_checkpoint_condition": (
                {
                    "step": args.target_step,
                    "opponent_crop": args.target_opponent_crop,
                    "minimum_count": args.target_opponent_crop_min,
                    "baseline_candidate_checkpoint_mismatches": len(crop_target_mismatches),
                }
                if args.target_step is not None
                else None
            ),
            "owned_sellable_checkpoint_condition": (
                {
                    "step": args.target_owned_sellable_step,
                    "minimum_count": args.target_owned_sellable_min,
                    "baseline_candidate_checkpoint_mismatches": len(
                        sellable_target_mismatches
                    ),
                }
                if args.target_owned_sellable_step is not None
                else None
            ),
            "games": len(target_keys),
            "baseline_failures": base_target_failures,
            "candidate_failures": cand_target_failures,
            "failure_reduction": target_failure_reduction,
            "summary": target_summary,
            "by_opponent": target_by_opponent,
            "by_first_shop": target_by_first_shop,
            "cells": target_cells,
        },
        "gate": {"checks": gate_checks, "pass": all(gate_checks.values())},
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "report_sha256": sha256(output),
        "paired_cells": len(keys),
        "overall_delta": overall["delta"],
        "bootstrap_by_seed": result["bootstrap_by_seed"],
        "target": result["target"],
        "gate": result["gate"],
    }, indent=2))


if __name__ == "__main__":
    main()
