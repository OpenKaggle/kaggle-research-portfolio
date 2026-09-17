"""Turn a league JSON into candidate-centric, replay-checkpoint diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def orient_game(game: dict[str, Any], candidate: str) -> dict[str, Any]:
    if game["first"] == candidate:
        seat = 0
        opponent = game["second"]
        margin = float(game["margin_first"])
    elif game["second"] == candidate:
        seat = 1
        opponent = game["first"]
        margin = -float(game["margin_first"])
    else:
        raise ValueError(f"candidate {candidate!r} not present in game")

    checkpoints = []
    for checkpoint in game.get("checkpoints", []):
        farms = checkpoint["farms"]
        mine, theirs = farms[seat], farms[1 - seat]
        private = checkpoint.get("private") or [{}, {}]
        my_private, their_private = private[seat], private[1 - seat]
        checkpoints.append({
            "step": checkpoint["observation_step"],
            "money_delta": float(mine["money"]) - float(theirs["money"]),
            "hands_delta": int(mine["hands"]) - int(theirs["hands"]),
            "land_delta": int(mine["land"]) - int(theirs["land"]),
            "plants_delta": int(mine["plants"]) - int(theirs["plants"]),
            "animals_delta": int(mine["animals"]) - int(theirs["animals"]),
            "weeds_delta": int(mine["weeds"]) - int(theirs["weeds"]),
            "my_shed_total": int(my_private.get("shed_total", 0) or 0),
            "their_shed_total": int(their_private.get("shed_total", 0) or 0),
            "my_carried_total": int(my_private.get("carried_total", 0) or 0),
            "their_carried_total": int(their_private.get("carried_total", 0) or 0),
            "shops": checkpoint["shops"],
        })
    return {
        "seed": int(game["seed"]),
        "seat": seat,
        "opponent": opponent,
        "margin": margin,
        "checkpoints": checkpoints,
    }


def at_or_after(game: dict[str, Any], step: int) -> dict[str, Any]:
    checkpoints = game["checkpoints"]
    return min(checkpoints, key=lambda row: (abs(int(row["step"]) - step), int(row["step"]) < step))


def failure_tags(game: dict[str, Any]) -> list[str]:
    if game["margin"] >= 0:
        return []
    early = at_or_after(game, 144)
    middle = at_or_after(game, 360)
    late = at_or_after(game, 576)
    final = game["checkpoints"][-1]
    tags = []
    if early["money_delta"] <= -5000:
        tags.append("EARLY_CAPITAL_DEFICIT")
    if middle["plants_delta"] + middle["animals_delta"] <= -3:
        tags.append("MIDGAME_PRODUCTION_DEFICIT")
    if middle["animals_delta"] <= -2:
        tags.append("LIVESTOCK_GAP")
    if late["money_delta"] >= 1000 and final["money_delta"] < 0:
        tags.append("LATE_MARKET_REVERSAL")
    elif late["money_delta"] > -3000 and final["money_delta"] <= -5000:
        tags.append("LATE_MARKET_DIVERGENCE")
    my_left = final["my_shed_total"] + final["my_carried_total"]
    their_left = final["their_shed_total"] + final["their_carried_total"]
    if my_left >= max(10, their_left + 8):
        tags.append("UNLIQUIDATED_INVENTORY")
    if not tags:
        tags.append("NARROW_OR_UNCLASSIFIED")
    return tags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--worst", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report_path = args.report.resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    games = [
        orient_game(game, args.candidate)
        for game in report["games"]
        if args.candidate in {game["first"], game["second"]}
    ]
    losses = [game for game in games if game["margin"] < 0]
    for game in losses:
        game["failure_tags"] = failure_tags(game)

    tag_counts: dict[str, int] = {}
    for game in losses:
        for tag in game["failure_tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    paired: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for game in games:
        paired.setdefault((game["seed"], game["opponent"]), []).append(game)
    seat_sensitive = []
    for (seed, opponent), pair in sorted(paired.items()):
        if len(pair) != 2:
            continue
        outcomes = [game["margin"] > 0 for game in pair]
        if outcomes[0] != outcomes[1]:
            seat_sensitive.append({
                "seed": seed,
                "opponent": opponent,
                "margins_by_seat": {
                    str(game["seat"]): game["margin"] for game in pair
                },
            })

    result = {
        "source": {"path": str(report_path), "sha256": sha256(report_path)},
        "candidate": args.candidate,
        "games": len(games),
        "losses": len(losses),
        "failure_tag_counts": dict(sorted(tag_counts.items())),
        "seat_sensitive_pairs": seat_sensitive,
        "worst_games": sorted(games, key=lambda game: game["margin"])[: args.worst],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "losses": len(losses),
        "failure_tag_counts": result["failure_tag_counts"],
        "seat_sensitive_pairs": len(seat_sensitive),
        "sha256": sha256(output),
    }, indent=2))


if __name__ == "__main__":
    main()
