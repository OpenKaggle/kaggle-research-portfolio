"""Create a prefix-compatible Yarn-second route ablation from the frozen hybrid."""

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


def first_difference(left: list[object], right: list[object]) -> int | None:
    return next((index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    args = parser.parse_args()
    if not re.fullmatch(r"hybrid_yarn2_route0_[a-z0-9_]+", args.name):
        raise ValueError("name must match hybrid_yarn2_route0_[a-z0-9_]+")
    output = (AGENTS / args.name).resolve()
    if output.parent != AGENTS.resolve() or output.exists():
        raise ValueError(f"refusing to overwrite or write outside agents: {output}")

    base_model = json.loads((BASE / "model.json").read_text(encoding="utf-8"))
    stage = next((row for row in base_model["stages"] if int(row["step"]) == 144), None)
    expected = {
        "feature": 23,
        "threshold": 0.5,
        "left": {"choice": 0},
        "right": {"choice": 1},
    }
    if stage is None or stage["tree"] != expected:
        raise ValueError("frozen base no longer has the expected Yarn-count route")
    tapes = json.loads((BASE / "actions.json").read_text(encoding="utf-8"))
    boundary = first_difference(tapes[0], tapes[1])
    if boundary is None or boundary < 144:
        raise ValueError(f"route 0/1 prefix is not safe for a step-144 choice: first diff={boundary}")

    output.mkdir()
    for path in BASE.iterdir():
        if path.is_file() and path.name not in {"model.json", "provenance.json"}:
            shutil.copy2(path, output / path.name)
    stage["tree"] = {"choice": 0}
    base_model["variant"] = {
        "kind": "yarn_second_route0_ablation",
        "source": str(BASE),
        "source_bundle_sha256": bundle_sha256(BASE),
        "decision_step": 144,
        "route_0_1_first_action_difference": boundary,
        "scope": "Only non-Yarn-first worlds can reach shop_policy; forcing route 0 therefore changes Yarn-second worlds only.",
    }
    (output / "model.json").write_text(
        json.dumps(base_model, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    provenance = json.loads((BASE / "provenance.json").read_text(encoding="utf-8"))
    provenance.update({
        "candidate": args.name,
        "derived_from": {
            "candidate": "hybrid_public_guard_v1",
            "bundle_sha256": bundle_sha256(BASE),
        },
        "experiment": {
            "id": "KG-004",
            "question": "Does retaining route 0 on public Yarn-second worlds reduce the current route-1 tail?",
            "single_change": "At step 144, shop_policy retains route 0 instead of selecting route 1 when Yarn is among the first two public shops.",
            "first_possible_action_difference": boundary,
            "runtime_features": ["already-public first and second shops"],
        },
    })
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    compile((output / "main.py").read_bytes(), "main.py", "exec")
    print(json.dumps({
        "output": str(output),
        "main_sha256": sha256(output / "main.py"),
        "model_sha256": sha256(output / "model.json"),
        "first_possible_action_difference": boundary,
        "bundle_sha256": bundle_sha256(output),
    }, indent=2))


if __name__ == "__main__":
    main()
