"""First-shop fallback variant generated from hybrid_public_guard_v1.

The choice uses only the first publicly unlocked shop at step 72. It never
uses a hidden seed, identity, future shop, opponent-private state, or network.
"""

from __future__ import annotations

import public_policy
import shop_policy


_PUBLIC_FIRST_SHOPS = frozenset({'SMOOTHIE_SHOP', 'YARN_STORE'})
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

    if step < 72:
        return shop_policy.agent(observation, configuration)

    if _ACTIVE[seat] is None:
        town = _read(observation, "town", {}) or {}
        shops = list(_read(town, "unlocked_shops", []) or [])
        _ACTIVE[seat] = "public" if shops and shops[0] in _PUBLIC_FIRST_SHOPS else "shop"

    if _ACTIVE[seat] == "public":
        return public_policy.agent(observation, configuration)
    return shop_policy.agent(observation, configuration)
