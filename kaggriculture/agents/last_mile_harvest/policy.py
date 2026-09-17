# SPDX-License-Identifier: Apache-2.0
"""Settings-driven terminal collection extension to Thomas Tschinkel's public router."""
import importlib.util
import sys
from pathlib import Path

_FACTORY_COUNT = 0
DEFAULT_SETTINGS = {"enabled": True, "max_simulations": 64, "passes": 1, "proposals_per_actor": 4}


def _sibling(name, filename):
    path = Path(_sibling.__code__.co_filename).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _bounded(value, default, lower, upper):
    try:
        return min(upper, max(lower, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def build_agent(settings):
    """Independent per-seat state. Disabled is exact Thomas; bounds remain 710/718."""
    global _FACTORY_COUNT
    settings = dict(settings or {})
    effective = {"enabled": settings.get("enabled", True) is True,
                 "max_simulations": _bounded(settings.get("max_simulations", 64), 64, 1, 256),
                 "passes": _bounded(settings.get("passes", 1), 1, 1, 2),
                 "proposals_per_actor": _bounded(settings.get("proposals_per_actor", 4), 4, 1, 16)}
    _FACTORY_COUNT += 1
    _sibling("unit_model", "unit_model.py")
    planner = _sibling("_e180_planner_" + str(_FACTORY_COUNT), "terminal_planner.py")
    parent = _sibling("_e180_parent_" + str(_FACTORY_COUNT), "thomas_parent.py")
    plans, last_steps = {}, {}
    telemetry = {"planner_invocations": 0, "activated_games": 0, "activated_steps": 0,
                 "changedworkers": 0, "aborts": 0, "maxplanning_ms": 0.0,
                 "predicted_delta": {}, "settings": effective, "cases": []}

    def agent(observation, configuration=None):
        seat = int(observation["player"])
        step = int(observation.get("step", observation["day"] * 24 + observation["hour"]))
        action = parent.agent(observation, configuration)
        if step == 0 or step < last_steps.get(seat, -1):
            plans.pop(seat, None)
        last_steps[seat] = step
        if not effective["enabled"] or not 710 <= step <= 718:
            return action
        if step == 710:
            session = tuple(parent._SESSIONS[seat])
            baseline = [parent.planned_action(t, seat=seat, session=session) for t in range(710, 719)]
            plan = planner.plan_terminal(observation, configuration, baseline,
                max_simulations=effective["max_simulations"], passes=effective["passes"],
                proposals_per_actor=effective["proposals_per_actor"])
            plans[seat] = plan
            telemetry["planner_invocations"] += 1
            telemetry["activated_games"] += int(plan["accepted"])
            telemetry["changedworkers"] += len(plan.get("changed_workers", []))
            telemetry["maxplanning_ms"] = max(telemetry["maxplanning_ms"], plan["planning_ms"])
            certificate = plan.get("certificate", {})
            for item, amount in certificate.get("sold_unit_delta", {}).items():
                telemetry["predicted_delta"][item] = telemetry["predicted_delta"].get(item, 0) + amount
            case = {"seat": seat, "route": session[1], "accepted": plan["accepted"],
                    "reason": plan["reason"], "planning_ms": plan["planning_ms"],
                    "simulations": plan["simulations"], "changed_workers": plan.get("changed_workers", []),
                    "changes": plan.get("changes", []),
                    "predicted_sold_unit_delta": certificate.get("sold_unit_delta", {}),
                    "predicted_stock_value_gain": certificate.get("stock_value_gain_at_initial_prices", 0),
                    "predicted_overflow": certificate.get("candidate_overflow"),
                    "markets_710_717_unchanged": certificate.get("markets_710_717_unchanged"),
                    "activated_steps": 0}
            telemetry["cases"].append(case)
            plan["telemetry_case"] = case
        plan = plans.get(seat)
        abandoned = bool(plan and plan.get("abandoned"))
        result = planner.terminal_action(observation, configuration, action, plan)
        if result != action:
            telemetry["activated_steps"] += 1
            plan["telemetry_case"]["activated_steps"] += 1
        if plan and plan.get("abandoned") and not abandoned:
            telemetry["aborts"] += 1
            plan["telemetry_case"]["abandon_step"] = step
        if plan and plan.get("recovery_steps"):
            plan["telemetry_case"]["recovery_steps"] = plan["recovery_steps"]
            plan["telemetry_case"]["recovery_failures"] = plan.get("recovery_failures", [])
            plan["telemetry_case"]["safety_failure"] = True
        return result

    agent.telemetry = telemetry
    agent.settings = effective
    return agent
