"""Create a shadow-synchronized late Pizza/Tomato counter ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
AGENTS = HERE / "agents"
BASE = AGENTS / "hybrid_public_guard_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_sha256(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in folder.iterdir() if candidate.is_file()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def render_main(trigger_step: int, rival_tomato_min: int) -> str:
    return f'''"""Hybrid v1 plus a public late counter to visible rival Tomato production.

The counter is eligible only in Pizza-first worlds.  It uses the rival's public
farm at step {trigger_step}; it never uses seed, replay/submission/opponent identity,
future shops, opponent-private state, or network access.  In non-Yarn worlds the
public component observes every turn from step 72 so its block state is coherent
if the late switch fires.  Its shadow action is discarded before the switch.
"""

from __future__ import annotations

import public_policy
import shop_policy


_ACTIVE = {{0: None, 1: None}}
_FIRST_SHOP = {{0: None, 1: None}}


def _read(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def _rival_tomatoes(observation, seat):
    farms = list(_read(observation, "farms", []) or [])
    if len(farms) != 2:
        return 0
    rival = farms[1 - seat]
    total = 0
    for row in list(_read(rival, "tiles", []) or []):
        for tile in list(row or []):
            if _read(tile, "kind") == "PLANT" and _read(tile, "crop") == "TOMATO":
                total += 1
    return total


def agent(observation, configuration=None):
    step = int(_read(observation, "step", 0) or 0)
    seat = 1 if int(_read(observation, "player", 0) or 0) == 1 else 0
    if step == 0:
        _ACTIVE[seat] = None
        _FIRST_SHOP[seat] = None

    if step < 72:
        return shop_policy.agent(observation, configuration)

    if _ACTIVE[seat] is None:
        town = _read(observation, "town", {{}}) or {{}}
        shops = list(_read(town, "unlocked_shops", []) or [])
        _FIRST_SHOP[seat] = shops[0] if shops else None
        _ACTIVE[seat] = "public_yarn" if _FIRST_SHOP[seat] == "YARN_STORE" else "shop"

    if _ACTIVE[seat] == "public_yarn":
        return public_policy.agent(observation, configuration)

    # Keep the alternate continuation's internal block route synchronized with
    # the actually reached public/owned state.  The returned action is ignored
    # until the one pre-registered switch point.
    public_action = public_policy.agent(observation, configuration)
    if (
        step == {trigger_step}
        and _FIRST_SHOP[seat] == "PIZZA_SHOP"
        and _rival_tomatoes(observation, seat) >= {rival_tomato_min}
    ):
        _ACTIVE[seat] = "public_counter"
    if _ACTIVE[seat] == "public_counter":
        return public_action
    return shop_policy.agent(observation, configuration)
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--trigger-step", type=int, default=576)
    parser.add_argument("--rival-tomato-min", type=int, default=12)
    args = parser.parse_args()
    if not re.fullmatch(r"hybrid_pizza_counter_[a-z0-9_]+", args.name):
        raise ValueError("name must match hybrid_pizza_counter_[a-z0-9_]+")
    if args.trigger_step != 576 or args.rival_tomato_min != 12:
        raise ValueError("KG-005 is pre-registered at step 576 and Tomato >= 12")

    output = (AGENTS / args.name).resolve()
    if output.parent != AGENTS.resolve() or output.exists():
        raise ValueError(f"refusing to overwrite or write outside agents: {output}")
    output.mkdir()
    for path in BASE.iterdir():
        if path.is_file() and path.name not in {"main.py", "provenance.json"}:
            shutil.copy2(path, output / path.name)
    (output / "main.py").write_text(
        render_main(args.trigger_step, args.rival_tomato_min), encoding="utf-8"
    )
    compile((output / "main.py").read_bytes(), "main.py", "exec")

    provenance = json.loads((BASE / "provenance.json").read_text(encoding="utf-8"))
    provenance.update(
        {
            "candidate": args.name,
            "derived_from": {
                "candidate": "hybrid_public_guard_v1",
                "bundle_sha256": bundle_sha256(BASE),
            },
            "experiment": {
                "id": "KG-005",
                "question": "Can a late public continuation counter visible rival Tomato production in Pizza-first worlds?",
                "single_change": (
                    "At step 576 only, when the first public shop is PIZZA_SHOP and "
                    "the rival public farm has at least 12 TOMATO plants, commit to "
                    "the shadow-synchronized public continuation."
                ),
                "first_possible_action_difference": args.trigger_step,
                "runtime_features": [
                    "first already-public shop",
                    "current public rival crop layout",
                ],
                "excluded_runtime_features": [
                    "seed",
                    "episode/submission/opponent identity",
                    "future shops",
                    "opponent private state",
                ],
            },
        }
    )
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "main_sha256": sha256(output / "main.py"),
                "bundle_sha256": bundle_sha256(output),
                "trigger_step": args.trigger_step,
                "rival_tomato_min": args.rival_tomato_min,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
