"""Summarize mature remote failure modes from privacy-bounded diagnostics.

Inputs must be reports produced by ``analyze_owned_replay_stratum.py``.  Those
reports contain public farms/market data and the owned seat's private inventory
only.  This script never opens raw replays and never uses hidden seeds or the
opponent's private state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
CHECKPOINTS = (360, 504, 576, 648, 718)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
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
    return 1.0 if outcome == "win" else 0.5 if outcome == "tie" else 0.0


def metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    selected = list(rows)
    margins = [float(row["final_margin"]) for row in selected]
    outcomes = Counter(str(row["outcome"]) for row in selected)
    return {
        "games": len(selected),
        "wins": outcomes["win"],
        "ties": outcomes["tie"],
        "losses": outcomes["loss"],
        "score_points": sum(score(str(row["outcome"])) for row in selected),
        "score_rate": (
            statistics.fmean(score(str(row["outcome"])) for row in selected)
            if selected
            else None
        ),
        "mean_margin": statistics.fmean(margins) if margins else None,
        "p10_margin": percentile(margins, 0.10),
        "worst_margin": min(margins) if margins else None,
        "unique_public_opponents": len({str(row.get("opponent_name") or "") for row in selected}),
    }


def group_metrics(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return {key: metrics(values) for key, values in sorted(grouped.items())}


def checkpoint(row: dict[str, Any], step: int) -> dict[str, Any]:
    value = row.get("checkpoints", {}).get(str(step))
    if not isinstance(value, dict):
        raise ValueError(f"missing checkpoint {step} for episode {row.get('episode_id')}")
    return value


def sellable_units(inventory: Any) -> float:
    if not isinstance(inventory, dict):
        return 0.0
    return sum(
        float(quantity)
        for product, quantity in inventory.items()
        if product in SELLABLE_PRODUCTS and isinstance(quantity, (int, float))
    )


def inventory_market_value(state: dict[str, Any], field: str) -> float:
    inventory = state.get(field, {})
    prices = state.get("public_market_prices", {})
    if not isinstance(inventory, dict) or not isinstance(prices, dict):
        return 0.0
    return sum(
        float(quantity) * float(prices.get(product, 0.0))
        for product, quantity in inventory.items()
        if product in SELLABLE_PRODUCTS and isinstance(quantity, (int, float))
    )


def terminal_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for outcome in ("win", "tie", "loss", "all"):
        selected = rows if outcome == "all" else [row for row in rows if row["outcome"] == outcome]
        shed_units = [sellable_units(checkpoint(row, 718).get("own_private_shed")) for row in selected]
        carried_units = [sellable_units(checkpoint(row, 718).get("own_private_carried")) for row in selected]
        shed_values = [inventory_market_value(checkpoint(row, 718), "own_private_shed") for row in selected]
        carried_values = [inventory_market_value(checkpoint(row, 718), "own_private_carried") for row in selected]
        result[outcome] = {
            "games": len(selected),
            "games_with_sellable_shed": sum(value > 0 for value in shed_units),
            "games_with_sellable_carried": sum(value > 0 for value in carried_units),
            "sellable_shed_units": sum(shed_units),
            "sellable_carried_units": sum(carried_units),
            "shed_mark_to_market_value": sum(shed_values),
            "carried_mark_to_market_value": sum(carried_values),
        }
    return result


def failure_trajectory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    losses = [row for row in rows if row["outcome"] == "loss"]
    leading = {
        str(step): sum(float(checkpoint(row, step)["public_money_gap"]) >= 0 for row in losses)
        for step in CHECKPOINTS
    }
    near = {
        "within_100": sum(float(row["final_margin"]) >= -100 for row in losses),
        "within_500": sum(float(row["final_margin"]) >= -500 for row in losses),
        "within_2500": sum(float(row["final_margin"]) >= -2500 for row in losses),
    }
    reversal_cells = []
    for row in losses:
        gap648 = float(checkpoint(row, 648)["public_money_gap"])
        gap718 = float(checkpoint(row, 718)["public_money_gap"])
        if gap648 < 0 and gap718 < 0:
            continue
        state718 = checkpoint(row, 718)
        reversal_cells.append(
            {
                "episode_id": int(row["episode_id"]),
                "owned_seat": int(row["owned_seat"]),
                "first_shop": row.get("first_shop"),
                "second_shop": row.get("second_shop"),
                "final_margin": float(row["final_margin"]),
                "money_gap_648": gap648,
                "money_gap_718": gap718,
                "sellable_shed_units_718": sellable_units(state718.get("own_private_shed")),
                "sellable_carried_units_718": sellable_units(state718.get("own_private_carried")),
            }
        )
    reversal_cells.sort(key=lambda row: (row["final_margin"], row["episode_id"]))
    return {
        "losses": len(losses),
        "losses_with_nonnegative_public_money_gap": leading,
        "near_losses": near,
        "late_reversal_cells": reversal_cells,
    }


def frozen_hybrid_route_branch(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe, but do not tune, the frozen step-648 EGG-stock branch."""
    branches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("first_shop") == "YARN_STORE":
            continue
        inventory = checkpoint(row, 648).get("public_market_inventory", {})
        egg_stock = inventory.get("EGG") if isinstance(inventory, dict) else None
        if not isinstance(egg_stock, (int, float)):
            raise ValueError(f"missing public EGG inventory for episode {row.get('episode_id')}")
        branch = "route2" if float(egg_stock) <= 9888.0 else "route3"
        branches[branch].append(row)
    return {
        "frozen_rule": "non-Yarn worlds choose route2 when public EGG market inventory <= 9888 at step 648; otherwise route3",
        "causal_status": "descriptive only; remote episodes are unpaired and opponent-dependent, so this cannot justify threshold or route changes",
        "branches": {branch: metrics(values) for branch, values in sorted(branches.items())},
        "by_first_shop": {
            shop: {
                branch: metrics(
                    row for row in values if row.get("first_shop") == shop
                )
                for branch, values in sorted(branches.items())
                if any(row.get("first_shop") == shop for row in values)
            }
            for shop in sorted({str(row.get("first_shop")) for row in rows if row.get("first_shop") != "YARN_STORE"})
        },
    }


def load_diagnostic(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    required = {"rows", "source_summary_sha256", "privacy_boundary", "filter"}
    if not required.issubset(report):
        raise ValueError(f"not a privacy-bounded diagnostic: {path}")
    if not isinstance(report["rows"], list):
        raise ValueError(f"invalid rows in {path}")
    return report


def summarize_one(
    current_path: Path,
    previous_path: Path,
    expected_label: str,
) -> dict[str, Any]:
    current = load_diagnostic(current_path)
    previous = load_diagnostic(previous_path)
    if current["filter"].get("label") != expected_label:
        raise ValueError(f"current label mismatch for {expected_label}")
    if previous["filter"].get("label") != expected_label:
        raise ValueError(f"previous label mismatch for {expected_label}")
    rows = current["rows"]
    previous_ids = {int(row["episode_id"]) for row in previous["rows"]}
    current_ids = {int(row["episode_id"]) for row in rows}
    if not previous_ids.issubset(current_ids):
        raise ValueError(f"previous diagnostic is not a subset for {expected_label}")
    new_rows = [row for row in rows if int(row["episode_id"]) not in previous_ids]
    result = {
        "label": expected_label,
        "current_diagnostic": {
            "path": str(current_path),
            "sha256": sha256(current_path),
            "source_summary_sha256": current["source_summary_sha256"],
        },
        "previous_diagnostic": {
            "path": str(previous_path),
            "sha256": sha256(previous_path),
            "source_summary_sha256": previous["source_summary_sha256"],
        },
        "overall": metrics(rows),
        "new_since_previous": {
            "games": len(new_rows),
            "episode_ids": sorted(int(row["episode_id"]) for row in new_rows),
            "metrics": metrics(new_rows),
            "by_first_shop": group_metrics(new_rows, "first_shop"),
            "by_second_shop": group_metrics(new_rows, "second_shop"),
        },
        "by_seat": {
            str(seat): metrics(row for row in rows if int(row["owned_seat"]) == seat)
            for seat in (0, 1)
        },
        "by_first_shop": group_metrics(rows, "first_shop"),
        "by_second_shop": group_metrics(rows, "second_shop"),
        "failure_trajectory": failure_trajectory(rows),
        "terminal_owned_inventory": terminal_inventory(rows),
    }
    if expected_label == "hybrid_public_guard_v1":
        result["frozen_step648_route_audit"] = frozen_hybrid_route_branch(rows)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-public", type=Path, required=True)
    parser.add_argument("--previous-public", type=Path, required=True)
    parser.add_argument("--current-hybrid", type=Path, required=True)
    parser.add_argument("--previous-hybrid", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    public = summarize_one(
        args.current_public.resolve(),
        args.previous_public.resolve(),
        "public_state_955",
    )
    hybrid = summarize_one(
        args.current_hybrid.resolve(),
        args.previous_hybrid.resolve(),
        "hybrid_public_guard_v1",
    )
    current_hashes = {
        public["current_diagnostic"]["source_summary_sha256"],
        hybrid["current_diagnostic"]["source_summary_sha256"],
    }
    if len(current_hashes) != 1:
        raise ValueError("current diagnostics do not share one remote summary")

    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_summary_sha256": next(iter(current_hashes)),
        "privacy_boundary": {
            "used": [
                "public episode outcome and public shops",
                "public farms and public market from the owned-seat observation",
                "owned-seat private shed and carried inventory",
            ],
            "excluded": [
                "hidden seed",
                "opponent observation or private state",
                "future shops at any checkpoint",
                "episode, submission, or opponent identity as a runtime policy signal",
            ],
            "episode_ids": "retained only as offline replay audit keys",
        },
        "comparison_warning": "public and hybrid remote episodes are not paired; cross-agent differences are descriptive, not causal A/B evidence",
        "submissions": {
            "public_state_955": public,
            "hybrid_public_guard_v1": hybrid,
        },
        "decision": {
            "candidate_created": False,
            "confirmation_run": False,
            "submission_change": False,
            "reason": "KG006 remains frozen as a failed gate; mature remote strata are reviewed only to document failure modes, not to derive KG007 or tune thresholds",
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
                "public_new": public["new_since_previous"]["metrics"],
                "hybrid_new": hybrid["new_since_previous"]["metrics"],
                "decision": output["decision"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
