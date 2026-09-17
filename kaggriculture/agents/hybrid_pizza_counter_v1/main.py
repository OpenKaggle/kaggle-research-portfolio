"""Hybrid v1 plus a public late counter to visible rival Tomato production.

The counter is eligible only in Pizza-first worlds.  It uses the rival's public
farm at step 576; it never uses seed, replay/submission/opponent identity,
future shops, opponent-private state, or network access.  In non-Yarn worlds the
public component observes every turn from step 72 so its block state is coherent
if the late switch fires.  Its shadow action is discarded before the switch.
"""

from __future__ import annotations

import public_policy
import shop_policy


_ACTIVE = {0: None, 1: None}
_FIRST_SHOP = {0: None, 1: None}


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
        town = _read(observation, "town", {}) or {}
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
        step == 576
        and _FIRST_SHOP[seat] == "PIZZA_SHOP"
        and _rival_tomatoes(observation, seat) >= 12
    ):
        _ACTIVE[seat] = "public_counter"
    if _ACTIVE[seat] == "public_counter":
        return public_action
    return shop_policy.agent(observation, configuration)
