"""Compare two component policies on the exact same live observations.

The primary policy drives the environment.  The secondary policy receives every
observation but its action is never emitted.  This isolates action-prefix and
state-synchronization compatibility without changing the played trajectory.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import statistics
import sys
import types
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from kaggle_environments import make


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_agent_module(path: Path, name: str) -> Any:
    """Load a single-file agent or an isolated hybrid bundle.

    Hybrid main.py files use absolute sibling imports. Loading two such files
    through ordinary import state would alias their mutable policy sessions.
    Give each side uniquely named sibling modules and rewrite only those import
    bindings in-memory; source files and runtime behavior are unchanged.
    """
    public_path = path.parent / "public_policy.py"
    shop_path = path.parent / "shop_policy.py"
    if not (public_path.is_file() and shop_path.is_file()):
        return load_module(path, name)

    public_name = f"{name}_public_policy"
    shop_name = f"{name}_shop_policy"
    load_module(public_path, public_name)
    load_module(shop_path, shop_name)
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        "import public_policy",
        f"import {public_name} as public_policy",
    ).replace(
        "import shop_policy",
        f"import {shop_name} as shop_policy",
    )
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ""
    sys.modules[name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    return module


def read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def canonical(value: Any) -> str:
    if hasattr(value, "toJSON"):
        value = value.toJSON()
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Auditor:
    def __init__(self, primary_path: Path, secondary_path: Path, token: str):
        self.primary = load_agent_module(primary_path, f"prefix_primary_{token}")
        self.secondary = load_agent_module(secondary_path, f"prefix_secondary_{token}")
        self.events: list[dict[str, Any]] = []

    def __call__(self, observation: Any, configuration: Any = None) -> Any:
        primary_action = self.primary.agent(observation, configuration)
        secondary_action = self.secondary.agent(observation, configuration)
        step = int(read(observation, "step", 0) or 0)
        town = read(observation, "town", {}) or {}
        shops = list(read(town, "unlocked_shops", []) or [])
        same = canonical(primary_action) == canonical(secondary_action)
        event = {
            "step": step,
            "shops": shops,
            "same": same,
        }
        if not same and not any(not previous["same"] for previous in self.events):
            event["primary_action"] = json.loads(canonical(primary_action))
            event["secondary_action"] = json.loads(canonical(secondary_action))
        self.events.append(event)
        return copy.deepcopy(primary_action)


def play(task: tuple[str, str, str, str, int, int, int]) -> dict[str, Any]:
    primary_raw, secondary_raw, opponent_label, opponent_raw, seed, seat, episode_steps = task
    primary_path, secondary_path, opponent_path = map(Path, (primary_raw, secondary_raw, opponent_raw))
    auditor = Auditor(primary_path, secondary_path, f"{seed}_{seat}_{opponent_label}")
    agents = [auditor, str(opponent_path)] if seat == 0 else [str(opponent_path), auditor]
    environment = make(
        "kaggriculture",
        configuration={"episodeSteps": episode_steps, "seed": seed},
        debug=True,
    )
    environment.run(agents)
    final = environment.steps[-1]
    mismatches = [event["step"] for event in auditor.events if not event["same"]]
    final_shops = auditor.events[-1]["shops"] if auditor.events else []
    first_diff_event = next((event for event in auditor.events if not event["same"]), None)
    return {
        "seed": seed,
        "seat": seat,
        "opponent": opponent_label,
        "statuses": [str(state.status) for state in final],
        "observed_steps": len(auditor.events),
        "shops": final_shops,
        "first_shop": final_shops[0] if final_shops else None,
        "second_shop": final_shops[1] if len(final_shops) > 1 else None,
        "first_diff_step": min(mismatches) if mismatches else None,
        "first_diff_actions": (
            {
                "primary": first_diff_event["primary_action"],
                "secondary": first_diff_event["secondary_action"],
            }
            if first_diff_event is not None
            else None
        ),
        "mismatch_steps": mismatches,
    }


def compatible_through(game: dict[str, Any], step: int) -> bool:
    return all(value > step for value in game["mismatch_steps"])


def grouped(games: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = sorted({game[key] for game in games}, key=lambda value: str(value))
    return {
        str(value): {
            "games": len(selected := [game for game in games if game[key] == value]),
            "unique_seeds": len({game["seed"] for game in selected}),
            "compatible_through_71": sum(compatible_through(game, 71) for game in selected),
            "compatible_through_87": sum(compatible_through(game, 87) for game in selected),
            "compatible_through_143": sum(compatible_through(game, 143) for game in selected),
            "compatible_through_152": sum(compatible_through(game, 152) for game in selected),
            "first_diff_min": min(
                (game["first_diff_step"] for game in selected if game["first_diff_step"] is not None),
                default=None,
            ),
        }
        for value in values
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("primary", type=Path)
    parser.add_argument("secondary", type=Path)
    parser.add_argument("--opponent", action="append", required=True, help="LABEL=PATH")
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--episode-steps", type=int, default=170)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    primary, secondary = args.primary.resolve(), args.secondary.resolve()
    opponents = []
    for raw in args.opponent:
        label, separator, path = raw.partition("=")
        if not separator:
            raise ValueError("--opponent must be LABEL=PATH")
        opponents.append((label, str(Path(path).resolve())))
    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    tasks = [
        (str(primary), str(secondary), label, path, seed, seat, args.episode_steps)
        for seed in seeds
        for label, path in opponents
        for seat in (0, 1)
    ]
    games = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(play, task) for task in tasks]
        for future in as_completed(futures):
            games.append(future.result())
    games.sort(key=lambda row: (row["seed"], row["opponent"], row["seat"]))
    first_diffs = [game["first_diff_step"] for game in games if game["first_diff_step"] is not None]
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": f"kaggle-environments=={version('kaggle-environments')}",
        "episode_steps": args.episode_steps,
        "primary": {"path": str(primary), "sha256": sha256(primary)},
        "secondary": {"path": str(secondary), "sha256": sha256(secondary)},
        "seeds": seeds,
        "opponents": dict(opponents),
        "summary": {
            "games": len(games),
            "all_done": all(game["statuses"] == ["DONE", "DONE"] for game in games),
            "compatible_through_71": sum(compatible_through(game, 71) for game in games),
            "compatible_through_87": sum(compatible_through(game, 87) for game in games),
            "compatible_through_143": sum(compatible_through(game, 143) for game in games),
            "compatible_through_152": sum(compatible_through(game, 152) for game in games),
            "first_diff_min": min(first_diffs, default=None),
            "first_diff_median": statistics.median(first_diffs) if first_diffs else None,
        },
        "by_first_shop": grouped(games, "first_shop"),
        "by_second_shop": grouped(games, "second_shop"),
        "games": games,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": report["summary"], "sha256": sha256(output)}, indent=2))


if __name__ == "__main__":
    main()
