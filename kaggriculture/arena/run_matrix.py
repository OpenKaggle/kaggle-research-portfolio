"""Run paired-seat Kaggriculture matches and emit an auditable JSON report."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from kaggle_environments import make


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def agent_label(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def play(first: Path, second: Path, seed: int, episode_steps: int) -> dict:
    environment = make(
        "kaggriculture",
        configuration={"episodeSteps": episode_steps, "seed": seed},
        debug=True,
    )
    environment.run([str(first), str(second)])
    final = environment.steps[-1]
    rewards = [float(state.reward or 0.0) for state in final]
    statuses = [str(state.status) for state in final]
    return {
        "seed": seed,
        "first": agent_label(first),
        "second": agent_label(second),
        "rewards": rewards,
        "statuses": statuses,
        "margin_first": rewards[0] - rewards[1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent_a", type=Path)
    parser.add_argument("agent_b", type=Path)
    parser.add_argument("--seeds", default="1001,1002,1003,1004")
    parser.add_argument("--episode-steps", type=int, default=720)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    agent_a = args.agent_a.resolve()
    agent_b = args.agent_b.resolve()
    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    games: list[dict] = []
    for seed in seeds:
        games.append(play(agent_a, agent_b, seed, args.episode_steps))
        games.append(play(agent_b, agent_a, seed, args.episode_steps))

    a_margins: list[float] = []
    for game in games:
        margin = float(game["margin_first"])
        a_margins.append(margin if game["first"] == agent_label(agent_a) else -margin)
    wins = sum(margin > 0 for margin in a_margins)
    ties = sum(margin == 0 for margin in a_margins)
    losses = sum(margin < 0 for margin in a_margins)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": f"kaggle-environments=={version('kaggle-environments')}",
        "episode_steps": args.episode_steps,
        "agents": {
            "a": {"path": str(agent_a), "sha256": sha256(agent_a)},
            "b": {"path": str(agent_b), "sha256": sha256(agent_b)},
        },
        "summary_for_a": {
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "mean_margin": sum(a_margins) / len(a_margins),
            "worst_margin": min(a_margins),
        },
        "games": games,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
