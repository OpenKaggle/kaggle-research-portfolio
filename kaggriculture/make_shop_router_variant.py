"""Create an auditable Shop Router experiment without modifying its frozen anchor."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ASSETS = ("main.py", "observation.py", "actions.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--early-choice", type=int, choices=(0, 1))
    parser.add_argument("--late-choice", type=int, choices=(2, 3))
    args = parser.parse_args()

    source = args.source.resolve()
    destination = args.destination.resolve()
    if args.early_choice is None and args.late_choice is None:
        raise ValueError("set --early-choice, --late-choice, or both")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"destination must be absent or empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        shutil.copyfile(source / name, destination / name)

    model = json.loads((source / "model.json").read_text(encoding="utf-8"))
    stages = {int(stage["step"]): stage for stage in model["stages"]}
    if args.early_choice is not None:
        if 144 not in stages:
            raise ValueError("source model has no step-144 route")
        stages[144]["tree"] = {"choice": args.early_choice}
    if args.late_choice is not None:
        if 648 not in stages:
            raise ValueError("source model has no step-648 route")
        stages[648]["tree"] = {"choice": args.late_choice}
    model["variant"] = {
        "kind": "forced_router_choice_counterfactual",
        "source": str(source),
        "early_choice": args.early_choice,
        "late_choice": args.late_choice,
    }
    (destination / "model.json").write_text(
        json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(destination)


if __name__ == "__main__":
    main()
