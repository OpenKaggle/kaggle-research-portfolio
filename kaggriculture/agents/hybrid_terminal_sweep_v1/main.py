"""Hybrid v1 with a bounded final-step market liquidation guard.

Only the action at public step 718 can differ.  The guard keeps the base unit
actions and market-order positions, saturates existing SELL quantities, then
uses still-free market slots for sellable products currently in our own shed or
carried inventories.  It never reads seed, identity, future information, the
opponent's private state, or network data.
"""

from __future__ import annotations

import public_policy
import shop_policy


_PRODUCTS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)
_ACTIVE = {0: None, 1: None}


def _read(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def _copy_action(action):
    action = action if isinstance(action, dict) else {}
    farmer = list(action.get("farmer") or ["PASS"])
    hands = [list(order or ["PASS"]) for order in (action.get("hands") or [])]
    market = [list(order) if isinstance(order, list) else [] for order in (action.get("market") or [])]
    return {"farmer": farmer, "hands": hands, "market": market}


def _terminal_sweep(action, observation, seat):
    result = _copy_action(action)
    market = result["market"][:10]
    scheduled = set()
    for order in market:
        if len(order) >= 3 and order[0] == "SELL" and order[1] in _PRODUCTS:
            order[2] = 1_000_000
            scheduled.add(order[1])

    private = _read(observation, "private", {}) or {}
    available = {product: 0 for product in _PRODUCTS}
    shed = _read(private, "shed", {}) or {}
    for product in _PRODUCTS:
        available[product] += int(_read(shed, product, 0) or 0)
    for inventory in list(_read(private, "inventories", []) or []):
        for product in _PRODUCTS:
            available[product] += int(_read(inventory, product, 0) or 0)

    for product in _PRODUCTS:
        if len(market) >= 10:
            break
        if available[product] > 0 and product not in scheduled:
            market.append(["SELL", product, 1_000_000])
            scheduled.add(product)
    result["market"] = market
    return result


def agent(observation, configuration=None):
    step = int(_read(observation, "step", 0) or 0)
    seat = 1 if int(_read(observation, "player", 0) or 0) == 1 else 0
    if step == 0:
        _ACTIVE[seat] = None

    if step < 72:
        action = shop_policy.agent(observation, configuration)
    else:
        if _ACTIVE[seat] is None:
            town = _read(observation, "town", {}) or {}
            shops = list(_read(town, "unlocked_shops", []) or [])
            _ACTIVE[seat] = "public" if shops and shops[0] == "YARN_STORE" else "shop"
        if _ACTIVE[seat] == "public":
            action = public_policy.agent(observation, configuration)
        else:
            action = shop_policy.agent(observation, configuration)

    if step == 718:
        return _terminal_sweep(action, observation, seat)
    return action
