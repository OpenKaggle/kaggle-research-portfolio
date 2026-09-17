"""Compare public state and our own private inventory within a replay stratum.

The input replay files contain more data than this audit is allowed to use. This
script deliberately reads only ``steps[...][owned_seat].observation``. From that
observation it keeps the public farms/market and the owned seat's private shed.
It never reads replay seed fields or the opponent seat's observation/private data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def farm_snapshot(farm: dict[str, Any]) -> dict[str, Any]:
    tiles = [
        tile
        for row in farm.get("tiles", [])
        for tile in row
        if isinstance(tile, dict)
    ]
    kinds = Counter(str(tile.get("kind") or "UNKNOWN") for tile in tiles)
    crops = Counter(
        str(tile.get("crop") or "UNKNOWN")
        for tile in tiles
        if tile.get("kind") == "PLANT"
    )
    animals = Counter(
        str(tile.get("animal") or "UNKNOWN")
        for tile in tiles
        if tile.get("animal") is not None
    )
    return {
        "money": float(farm.get("money", 0.0)),
        "unlocked_tiles": len(tiles),
        "tile_kinds": dict(sorted(kinds.items())),
        "crops": dict(sorted(crops.items())),
        "animals": dict(sorted(animals.items())),
        "hands": len(farm.get("hands", [])),
    }


def observation_snapshot(
    replay_steps: list[Any], step: int, owned_seat: int
) -> dict[str, Any]:
    states = replay_steps[step]
    if not isinstance(states, list) or owned_seat >= len(states):
        raise ValueError(f"missing owned state at step {step}, seat {owned_seat}")
    state = states[owned_seat]
    observation = state.get("observation") if isinstance(state, dict) else None
    if not isinstance(observation, dict):
        raise ValueError(f"missing owned observation at step {step}, seat {owned_seat}")
    if observation.get("player") not in {None, owned_seat}:
        raise ValueError(f"owned observation mismatch at step {step}, seat {owned_seat}")

    farms = observation.get("farms")
    if not isinstance(farms, list) or len(farms) != 2:
        raise ValueError(f"expected two public farms at step {step}")
    own_farm = farm_snapshot(farms[owned_seat])
    opponent_farm = farm_snapshot(farms[1 - owned_seat])

    market = observation.get("market")
    prices = market.get("prices", {}) if isinstance(market, dict) else {}
    prices = {
        str(key): float(value)
        for key, value in prices.items()
        if isinstance(value, (int, float))
    }
    market_inventory = market.get("inventory", {}) if isinstance(market, dict) else {}
    market_inventory = {
        str(key): float(value)
        for key, value in market_inventory.items()
        if isinstance(value, (int, float))
    }
    private = observation.get("private")
    shed = private.get("shed", {}) if isinstance(private, dict) else {}
    shed = {
        str(key): float(value)
        for key, value in shed.items()
        if isinstance(value, (int, float))
    }
    carried = Counter()
    inventories = private.get("inventories", []) if isinstance(private, dict) else []
    if isinstance(inventories, list):
        for inventory in inventories:
            if not isinstance(inventory, dict):
                continue
            carried.update(
                {
                    str(key): float(value)
                    for key, value in inventory.items()
                    if isinstance(value, (int, float))
                }
            )
    shed_market_value = sum(
        quantity * prices[product]
        for product, quantity in shed.items()
        if product in prices
    )
    return {
        "step": step,
        "own_public": own_farm,
        "opponent_public": opponent_farm,
        "public_money_gap": own_farm["money"] - opponent_farm["money"],
        "public_market_prices": dict(sorted(prices.items())),
        "public_market_inventory": dict(sorted(market_inventory.items())),
        "own_private_shed": dict(sorted(shed.items())),
        "own_private_carried": dict(sorted(carried.items())),
        "own_shed_market_value": shed_market_value,
        "own_money_plus_shed_value": own_farm["money"] + shed_market_value,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--first-shop")
    parser.add_argument(
        "--outcome",
        action="append",
        choices=("win", "tie", "loss"),
        default=[],
    )
    parser.add_argument("--step", type=int, action="append", dest="steps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary_path = args.summary.resolve()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    submissions = [row for row in summary["submissions"] if row.get("label") == args.label]
    if len(submissions) != 1:
        raise ValueError(f"expected one submission labeled {args.label!r}")

    selected_steps = sorted(set(args.steps or [576, 648, 719]))
    selected_outcomes = set(args.outcome) or {"win", "tie", "loss"}
    selected = [
        episode
        for episode in submissions[0]["episodes"]
        if episode.get("outcome") in selected_outcomes
        and (
            args.first_shop is None
            or episode.get("public_context", {}).get("first_unlocked_shop") == args.first_shop
        )
    ]
    rows: list[dict[str, Any]] = []
    for episode in selected:
        owned_seat = episode.get("owned_seat")
        if owned_seat not in {0, 1}:
            raise ValueError(f"invalid owned seat for episode {episode.get('episode_id')}")
        replay_path = Path(episode["replay"]["path"]).resolve()
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
        # Privacy boundary: do not access replay.info/configuration or the other
        # seat's observation. Only our observation contains our private state.
        replay_steps = replay.get("steps")
        if not isinstance(replay_steps, list):
            raise ValueError(f"missing steps in {replay_path}")
        if any(step < 0 or step >= len(replay_steps) for step in selected_steps):
            raise ValueError(f"requested step outside replay {episode.get('episode_id')}")
        rows.append(
            {
                "episode_id": int(episode["episode_id"]),
                "owned_seat": owned_seat,
                "opponent_name": " | ".join(episode.get("opponent_names", [])),
                "outcome": episode["outcome"],
                "final_margin": float(episode["margin"]),
                "first_shop": episode["public_context"].get("first_unlocked_shop"),
                "second_shop": episode["public_context"].get("second_unlocked_shop"),
                "checkpoints": {
                    str(step): observation_snapshot(replay_steps, step, owned_seat)
                    for step in selected_steps
                },
                "replay_sha256": episode["replay"].get("sha256") or sha256(replay_path),
            }
        )

    rows.sort(key=lambda row: (row["final_margin"], row["episode_id"]))
    outcomes = Counter(row["outcome"] for row in rows)
    output = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_summary": str(summary_path),
        "source_summary_sha256": sha256(summary_path),
        "privacy_boundary": {
            "used": [
                "public farms from owned-seat observation",
                "public market from owned-seat observation",
                "owned-seat private shed",
                "public episode result and opponent name",
            ],
            "excluded": [
                "hidden seed",
                "episode/submission identity as a policy signal",
                "opponent observation and private state",
                "future information at each checkpoint",
            ],
        },
        "filter": {
            "label": args.label,
            "first_shop": args.first_shop,
            "outcomes": sorted(selected_outcomes),
        },
        "checkpoints": selected_steps,
        "games": len(rows),
        "outcomes": {
            "wins": outcomes["win"],
            "ties": outcomes["tie"],
            "losses": outcomes["loss"],
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "games": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
