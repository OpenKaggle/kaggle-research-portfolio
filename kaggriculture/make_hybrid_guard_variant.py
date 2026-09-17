"""Create an auditable first-public-shop fallback variant.

The generated wrapper changes only the set of public first-shop names that
select the frozen public policy. Component policies and assets are copied
byte-for-byte from hybrid_public_guard_v1.
"""

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
KNOWN_SHOPS = {
    "BAKERY",
    "BRUNCH_SPOT",
    "FARMERS_MARKET",
    "ICE_CREAM_SHOP",
    "PET_CAFE",
    "PIZZA_SHOP",
    "SMOOTHIE_SHOP",
    "YARN_STORE",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_sha256(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in folder.iterdir() if candidate.is_file()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def render_main(public_shops: list[str]) -> str:
    shop_literal = ", ".join(repr(shop) for shop in public_shops)
    return f'''"""First-shop fallback variant generated from hybrid_public_guard_v1.

The choice uses only the first publicly unlocked shop at step 72. It never
uses a hidden seed, identity, future shop, opponent-private state, or network.
"""

from __future__ import annotations

import public_policy
import shop_policy


_PUBLIC_FIRST_SHOPS = frozenset({{{shop_literal}}})
_ACTIVE = {{0: None, 1: None}}


def _read(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def agent(observation, configuration=None):
    step = int(_read(observation, "step", 0) or 0)
    seat = 1 if int(_read(observation, "player", 0) or 0) == 1 else 0
    if step == 0:
        _ACTIVE[seat] = None

    if step < 72:
        return shop_policy.agent(observation, configuration)

    if _ACTIVE[seat] is None:
        town = _read(observation, "town", {{}}) or {{}}
        shops = list(_read(town, "unlocked_shops", []) or [])
        _ACTIVE[seat] = "public" if shops and shops[0] in _PUBLIC_FIRST_SHOPS else "shop"

    if _ACTIVE[seat] == "public":
        return public_policy.agent(observation, configuration)
    return shop_policy.agent(observation, configuration)
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--public-on", required=True, help="comma-separated public first-shop names")
    args = parser.parse_args()

    if not re.fullmatch(r"hybrid_public_guard_[a-z0-9_]+", args.name):
        raise ValueError("name must match hybrid_public_guard_[a-z0-9_]+")
    public_shops = sorted({value.strip().upper() for value in args.public_on.split(",") if value.strip()})
    if not public_shops or not set(public_shops) <= KNOWN_SHOPS:
        raise ValueError(f"public-on must contain known shops only: {sorted(KNOWN_SHOPS)}")
    output = (AGENTS / args.name).resolve()
    if output.parent != AGENTS.resolve() or output.exists():
        raise ValueError(f"refusing to overwrite or write outside agents: {output}")
    output.mkdir()

    for path in BASE.iterdir():
        if path.is_file() and path.name not in {"main.py", "provenance.json"}:
            shutil.copy2(path, output / path.name)
    (output / "main.py").write_text(render_main(public_shops), encoding="utf-8")
    compile((output / "main.py").read_bytes(), "main.py", "exec")

    provenance = json.loads((BASE / "provenance.json").read_text(encoding="utf-8"))
    provenance.update(
        {
            "candidate": args.name,
            "derived_from": {
                "candidate": "hybrid_public_guard_v1",
                "bundle_sha256": bundle_sha256(BASE),
            },
            "decision": {
                "fallback": "public_state_955",
                "feature": "first publicly unlocked shop",
                "public_first_shops": public_shops,
                "rule": f"{','.join(public_shops)} -> public_state_955; otherwise -> shop_router_0908",
                "step": 72,
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
                "public_first_shops": public_shops,
                "main_sha256": sha256(output / "main.py"),
                "bundle_sha256": bundle_sha256(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
