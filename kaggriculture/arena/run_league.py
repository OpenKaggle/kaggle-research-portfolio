"""Run an auditable, paired-seat Kaggriculture opponent league.

Every unordered agent pair plays the same seed twice with seats swapped.  The
report keeps both game-level results and robust per-agent/per-opponent views so
we do not mistake a good mean margin for broad head-to-head strength.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from kaggle_environments import make


CHECKPOINT_INTERVAL = 72


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_manifest(main_path: Path) -> dict[str, Any]:
    """Hash every regular file beside main.py because submissions may be bundles."""
    folder = main_path.parent
    files = []
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in folder.iterdir() if candidate.is_file()):
        relative = path.name
        file_digest = sha256(path)
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": file_digest})
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_digest))
    return {
        "main_path": str(main_path),
        "main_sha256": sha256(main_path),
        "bundle_sha256": digest.hexdigest(),
        "files": files,
    }


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if hasattr(value, "toJSON"):
        return value.toJSON()
    try:
        return dict(value)
    except (TypeError, ValueError):
        return value


def _farm_summary(farm: Any) -> dict[str, Any]:
    farm = _plain(farm)
    counts: dict[str, int] = {
        "plants": 0,
        "animals": 0,
        "weeds": 0,
        "structures_empty": 0,
    }
    crop_counts: dict[str, int] = {}
    animal_counts: dict[str, int] = {}
    for row in farm.get("tiles", []) or []:
        for raw_tile in row or []:
            tile = _plain(raw_tile)
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "PLANT":
                counts["plants"] += 1
                crop = str(tile.get("crop", "UNKNOWN"))
                crop_counts[crop] = crop_counts.get(crop, 0) + 1
            elif kind == "WEED":
                counts["weeds"] += 1
            elif kind in {"COOP", "PASTURE"}:
                animal = tile.get("animal")
                if animal:
                    counts["animals"] += 1
                    animal = str(animal)
                    animal_counts[animal] = animal_counts.get(animal, 0) + 1
                else:
                    counts["structures_empty"] += 1
    return {
        "money": float(farm.get("money", 0) or 0),
        "hands": len(farm.get("hands", []) or []),
        "land": len(farm.get("unlocked_quadrants", []) or []),
        **counts,
        "crop_counts": dict(sorted(crop_counts.items())),
        "animal_counts": dict(sorted(animal_counts.items())),
    }


def _private_summary(private: Any) -> dict[str, Any]:
    private = _plain(private)
    shed = dict(private.get("shed", {}) or {})
    seeds = dict(private.get("seeds", {}) or {})
    inventories = [dict(value or {}) for value in private.get("inventories", []) or []]
    return {
        "shed": shed,
        "shed_total": sum(int(value or 0) for value in shed.values()),
        "seeds": seeds,
        "carried_total": sum(
            int(value or 0) for inventory in inventories for value in inventory.values()
        ),
    }


def _checkpoint(environment: Any, index: int) -> dict[str, Any]:
    states = environment.steps[index]
    observation = _plain(states[0].observation)
    market = _plain(observation.get("market", {}))
    town = _plain(observation.get("town", {}))
    return {
        "step_index": index,
        "observation_step": int(observation.get("step", index) or index),
        "shops": list(town.get("unlocked_shops", []) or []),
        "market_inventory": dict(market.get("inventory", {}) or {}),
        "market_prices": dict(market.get("prices", {}) or {}),
        "farms": [_farm_summary(farm) for farm in observation.get("farms", []) or []],
        "private": [_private_summary(_plain(state.observation).get("private", {})) for state in states],
    }


def play(task: tuple[str, str, str, str, int, int, tuple[int, ...]]) -> dict[str, Any]:
    first_label, first_path, second_label, second_path, seed, episode_steps, extra_checkpoints = task
    environment = make(
        "kaggriculture",
        configuration={"episodeSteps": episode_steps, "seed": seed},
        debug=True,
    )
    environment.run([first_path, second_path])
    final = environment.steps[-1]
    rewards = [float(state.reward or 0.0) for state in final]
    statuses = [str(state.status) for state in final]
    checkpoint_indices = list(range(0, len(environment.steps), CHECKPOINT_INTERVAL))
    checkpoint_indices.extend(
        index for index in extra_checkpoints if 0 <= index < len(environment.steps)
    )
    if len(environment.steps) - 1 not in checkpoint_indices:
        checkpoint_indices.append(len(environment.steps) - 1)
    checkpoint_indices = sorted(set(checkpoint_indices))
    return {
        "seed": seed,
        "first": first_label,
        "second": second_label,
        "rewards": rewards,
        "statuses": statuses,
        "margin_first": rewards[0] - rewards[1],
        "checkpoints": [_checkpoint(environment, index) for index in checkpoint_indices],
    }


def _score(margin: float) -> float:
    if margin > 0:
        return 1.0
    if margin < 0:
        return 0.0
    return 0.5


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1.0 - fraction) + ordered[high] * fraction


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    margins = [float(row["margin"]) for row in rows]
    scores = [_score(margin) for margin in margins]
    seats: dict[str, dict[str, Any]] = {}
    for seat in (0, 1):
        selected = [row for row in rows if int(row["seat"]) == seat]
        selected_margins = [float(row["margin"]) for row in selected]
        seats[str(seat)] = {
            "games": len(selected),
            "win_rate": sum(_score(margin) for margin in selected_margins) / len(selected),
            "mean_margin": statistics.fmean(selected_margins),
        }
    return {
        "games": len(rows),
        "wins": sum(margin > 0 for margin in margins),
        "ties": sum(margin == 0 for margin in margins),
        "losses": sum(margin < 0 for margin in margins),
        "win_rate": sum(scores) / len(scores),
        "mean_margin": statistics.fmean(margins),
        "median_margin": statistics.median(margins),
        "p10_margin": _quantile(margins, 0.10),
        "worst_margin": min(margins),
        "seat": seats,
        "non_done_games": sum(any(status != "DONE" for status in row["statuses"]) for row in rows),
    }


def build_summary(labels: list[str], games: list[dict[str, Any]]) -> dict[str, Any]:
    rows_by_agent: dict[str, list[dict[str, Any]]] = {label: [] for label in labels}
    rows_by_pair: dict[str, dict[str, list[dict[str, Any]]]] = {
        label: {} for label in labels
    }
    for game in games:
        for seat, label in enumerate((game["first"], game["second"])):
            opponent = game["second"] if seat == 0 else game["first"]
            margin = float(game["margin_first"]) * (1.0 if seat == 0 else -1.0)
            row = {
                "seed": game["seed"],
                "seat": seat,
                "opponent": opponent,
                "margin": margin,
                "statuses": game["statuses"],
            }
            rows_by_agent[label].append(row)
            rows_by_pair[label].setdefault(opponent, []).append(row)

    agents: dict[str, Any] = {}
    for label in labels:
        overall = summarize_rows(rows_by_agent[label])
        opponents = {
            opponent: summarize_rows(rows)
            for opponent, rows in sorted(rows_by_pair[label].items())
        }
        worst_win = min(opponents, key=lambda name: (opponents[name]["win_rate"], opponents[name]["mean_margin"]))
        worst_margin = min(opponents, key=lambda name: (opponents[name]["mean_margin"], opponents[name]["win_rate"]))
        agents[label] = {
            **overall,
            "opponents": opponents,
            "worst_opponent_by_win_rate": {
                "agent": worst_win,
                **opponents[worst_win],
            },
            "worst_opponent_by_mean_margin": {
                "agent": worst_margin,
                **opponents[worst_margin],
            },
        }
    ranking = sorted(
        labels,
        key=lambda label: (
            agents[label]["win_rate"],
            agents[label]["worst_opponent_by_win_rate"]["win_rate"],
            agents[label]["mean_margin"],
        ),
        reverse=True,
    )
    return {"ranking": ranking, "agents": agents}


def parse_agent(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("agent must be LABEL=PATH")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    path = Path(raw_path).expanduser().resolve()
    if not label or not path.is_file() or path.name != "main.py":
        raise argparse.ArgumentTypeError(f"invalid agent specification: {value}")
    return label, path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="append", type=parse_agent, required=True)
    parser.add_argument("--seeds", required=True, help="comma-separated public evaluation seeds")
    parser.add_argument("--episode-steps", type=int, default=720)
    parser.add_argument(
        "--checkpoint",
        type=int,
        action="append",
        default=[],
        help="additional pre-action state index to retain in the report",
    )
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    parser.add_argument("--focal", help="only run pairs containing this agent label")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    agents = dict(args.agent)
    if len(agents) != len(args.agent) or len(agents) < 2:
        raise ValueError("provide at least two agents with distinct labels")
    if args.focal is not None and args.focal not in agents:
        raise ValueError("--focal must name one of the supplied agents")
    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be a non-empty list of unique integers")
    extra_checkpoints = tuple(sorted(set(args.checkpoint)))
    if any(index < 0 or index >= args.episode_steps for index in extra_checkpoints):
        raise ValueError("checkpoint must be inside the configured episode")

    tasks = []
    labels = list(agents)
    for left_index, left in enumerate(labels):
        for right in labels[left_index + 1 :]:
            if args.focal is not None and args.focal not in {left, right}:
                continue
            for seed in seeds:
                tasks.append(
                    (
                        left,
                        str(agents[left]),
                        right,
                        str(agents[right]),
                        seed,
                        args.episode_steps,
                        extra_checkpoints,
                    )
                )
                tasks.append(
                    (
                        right,
                        str(agents[right]),
                        left,
                        str(agents[left]),
                        seed,
                        args.episode_steps,
                        extra_checkpoints,
                    )
                )

    games = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(play, task) for task in tasks]
        for future in as_completed(futures):
            games.append(future.result())
    games.sort(key=lambda game: (game["seed"], game["first"], game["second"]))

    environment_folder = Path(__import__("kaggle_environments").__file__).resolve().parent / "envs" / "kaggriculture"
    environment_files = [environment_folder / "kaggriculture.py", environment_folder / "kaggriculture.json"]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "package": f"kaggle-environments=={version('kaggle-environments')}",
            "python": platform.python_version(),
            "files": {path.name: sha256(path) for path in environment_files},
        },
        "episode_steps": args.episode_steps,
        "extra_checkpoints": list(extra_checkpoints),
        "seeds": seeds,
        "paired_seats": True,
        "focal": args.focal,
        "agents": {label: bundle_manifest(path) for label, path in agents.items()},
        "summary": build_summary(labels, games),
        "games": games,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "games": len(games),
        "ranking": report["summary"]["ranking"],
        "sha256": sha256(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
