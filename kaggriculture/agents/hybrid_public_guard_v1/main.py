"""Public-shop guard: Shop Router trunk with a Yarn-first stability fallback.

The choice is made only from the first shop after it becomes public.  It does
not use the episode seed, replay identity, submission identity, or future shop
order.  Both component policies are frozen public anchors with independent
runtime state and are credited in provenance.json.
"""

from __future__ import annotations

import public_policy
import shop_policy


_ACTIVE = {0: None, 1: None}


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

    # The two policies share the Shop Router trunk until the first shop is
    # public.  Delaying the decision makes it legal and replay-explainable.
    if step < 72:
        return shop_policy.agent(observation, configuration)

    if _ACTIVE[seat] is None:
        town = _read(observation, "town", {}) or {}
        shops = list(_read(town, "unlocked_shops", []) or [])
        _ACTIVE[seat] = "public" if shops and shops[0] == "YARN_STORE" else "shop"

    if _ACTIVE[seat] == "public":
        return public_policy.agent(observation, configuration)
    return shop_policy.agent(observation, configuration)

