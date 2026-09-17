#!/usr/bin/env python3
"""Verify the four D-30 task baselines and their cross-corridor evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import resource
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path


QUEUE_WINDOW = re.compile(r"^Q2_(?P<panel>.+)_(?P<split>validation|private)_\d+$")
SPLITS = {"development", "confirmation"}
QUEUE_SPLITS = {"validation", "private"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-12)


def parse_queue_window(window_id: str) -> tuple[str, str]:
    match = QUEUE_WINDOW.fullmatch(window_id)
    if not match:
        raise ValueError(f"unexpected Queue window_id: {window_id}")
    return match.group("panel"), match.group("split")


def normalize_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"naive Queue timestamp: {value}")
    return parsed.astimezone(timezone.utc).isoformat()


def queue_change_counts(
    source_path: Path,
    candidate_path: Path,
) -> tuple[int, Counter[tuple[str, str]], list[str]]:
    """Stream two natural-key Queue files and count only 1-to-0 changes."""
    errors: list[str] = []
    counts: Counter[tuple[str, str]] = Counter()
    rows = 0
    key_mismatches = 0
    first_key_mismatch: int | None = None
    transition_mismatches = 0
    first_transition_mismatch: int | None = None
    window_errors = 0
    first_window_error: str | None = None
    with source_path.open(newline="", encoding="utf-8") as source_handle, candidate_path.open(
        newline="", encoding="utf-8"
    ) as candidate_handle:
        source = csv.DictReader(source_handle)
        candidate = csv.DictReader(candidate_handle)
        expected = ["window_id", "timestamp", "link_id", "queue_pred"]
        if source.fieldnames != expected or candidate.fieldnames != expected:
            errors.append("Queue natural-key header mismatch")
        for row_number, (before, after) in enumerate(zip_longest(source, candidate), start=2):
            if before is None or after is None:
                errors.append("Queue source and candidate lengths differ")
                break
            rows += 1
            try:
                key = (
                    before["window_id"],
                    normalize_timestamp(before["timestamp"]),
                    before["link_id"],
                )
                candidate_key = (
                    after["window_id"],
                    normalize_timestamp(after["timestamp"]),
                    after["link_id"],
                )
            except ValueError:
                key_mismatches += 1
                first_key_mismatch = first_key_mismatch or row_number
                continue
            if key != candidate_key:
                key_mismatches += 1
                first_key_mismatch = first_key_mismatch or row_number
                continue
            before_value = float(before["queue_pred"])
            after_value = float(after["queue_pred"])
            if before_value == after_value:
                continue
            if (before_value, after_value) != (1.0, 0.0):
                transition_mismatches += 1
                first_transition_mismatch = first_transition_mismatch or row_number
                continue
            try:
                panel, split = parse_queue_window(before["window_id"])
            except ValueError as error:
                window_errors += 1
                first_window_error = first_window_error or str(error)
                continue
            counts[(panel, split)] += 1
    if key_mismatches:
        errors.append(
            f"Queue natural-key mismatches={key_mismatches}; first CSV row={first_key_mismatch}"
        )
    if transition_mismatches:
        errors.append(
            f"Queue non-1-to-0 transitions={transition_mismatches}; "
            f"first CSV row={first_transition_mismatch}"
        )
    if window_errors:
        errors.append(f"Queue window parse failures={window_errors}; first={first_window_error}")
    return rows, counts, errors


def odme_panel_gains(
    rows: list[dict[str, str]],
    target_lambda: float,
    comparison_lambda: float,
) -> tuple[list[dict[str, object]], list[str]]:
    """Pair panel/split S_link rows and return target-minus-comparison gains."""
    values: dict[tuple[str, str], dict[float, float]] = defaultdict(dict)
    errors: list[str] = []
    for row in rows:
        if row["level"] != "panel":
            continue
        key = (row["panel"], row["split"])
        lam = float(row["lambda"])
        if lam in values[key]:
            errors.append(f"duplicate ODME metric for {key} lambda={lam}")
        values[key][lam] = float(row["S_link"])
    gains: list[dict[str, object]] = []
    for (panel, split), by_lambda in sorted(values.items()):
        if target_lambda not in by_lambda or comparison_lambda not in by_lambda:
            errors.append(f"incomplete ODME lambda pair for {panel}/{split}")
            continue
        target = by_lambda[target_lambda]
        comparison = by_lambda[comparison_lambda]
        gains.append(
            {
                "panel": panel,
                "split": split,
                "target_lambda": target_lambda,
                "comparison_lambda": comparison_lambda,
                "target_S_link": target,
                "comparison_S_link": comparison,
                "S_link_gain": target - comparison,
            }
        )
    return gains, errors


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run(traffic_root: Path, config_path: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    if output_root.exists():
        raise ValueError("four-task audit output root already exists; use a new path")
    config = json.loads(config_path.read_text())
    errors: list[str] = []
    input_hashes: dict[str, str] = {config_path.name: _sha256(config_path)}

    def checked_path(spec: dict[str, object], path_key: str, sha_key: str, label: str) -> Path:
        path = traffic_root / str(spec[path_key])
        actual = _sha256(path) if path.is_file() else "MISSING"
        input_hashes[str(spec[path_key])] = actual
        if actual != spec[sha_key]:
            errors.append(f"{label} SHA mismatch")
        return path

    official_head = subprocess.check_output(
        ["git", "-C", str(traffic_root / "official"), "rev-parse", "HEAD"], text=True
    ).strip()
    if official_head != config["official_code_commit"]:
        errors.append("official code commit mismatch")

    expected_panels = set(config["panels"])
    state_spec = config["state_physics"]
    state_receipt_path = checked_path(state_spec, "receipt_path", "receipt_sha256", "State/Physics receipt")
    state_metrics_path = checked_path(
        state_spec, "panel_regime_metrics_path", "panel_regime_metrics_sha256", "State panel-regime metrics"
    )
    state_aggregate_path = checked_path(
        state_spec, "aggregate_metrics_path", "aggregate_metrics_sha256", "State aggregate metrics"
    )
    state_receipt = json.loads(state_receipt_path.read_text())
    state_rows = _load_csv(state_metrics_path)
    state_aggregate = _load_csv(state_aggregate_path)
    state_combinations = {(row["split"], row["panel"], row["regime"]) for row in state_rows}
    expected_state_combinations = {
        (split, panel, regime)
        for split in SPLITS
        for panel in expected_panels
        for regime in {"R1", "R2", "R3"}
    }
    state_target_cells = sum(int(row["n_target_cells"]) for row in state_rows)
    if (
        state_receipt["status"] != "COMPLETE"
        or len(state_rows) != state_spec["panel_regime_rows"]
        or state_combinations != expected_state_combinations
        or state_target_cells != state_spec["target_cells"]
        or any(int(row["n_target_cells"]) <= 0 for row in state_rows)
        or any(not 0.0 <= float(row["S_state"]) <= 1.0 for row in state_rows)
    ):
        errors.append("State panel-regime coverage contract failed")
    if state_receipt["outputs"]["task1_v32_control_panel_regime_metrics.csv"] != state_spec[
        "panel_regime_metrics_sha256"
    ] or state_receipt["outputs"]["task1_v32_control_aggregate_metrics.csv"] != state_spec[
        "aggregate_metrics_sha256"
    ]:
        errors.append("State receipt does not bind its metric tables")
    overall_rows = {
        row["split"]: row
        for row in state_aggregate
        if row["level"] == "overall" and row["family_id"] == "ALL"
    }
    state_score_checks = {
        "development": (
            state_spec["development_S_state"], state_spec["development_S_FD"]
        ),
        "confirmation": (
            state_spec["confirmation_S_state"], state_spec["confirmation_S_FD"]
        ),
    }
    if set(overall_rows) != SPLITS or any(
        not _close(float(overall_rows[split]["S_state"]), float(scores[0]))
        or not _close(float(overall_rows[split]["S_FD_public"]), float(scores[1]))
        for split, scores in state_score_checks.items()
    ):
        errors.append("State/Physics aggregate scores do not match the frozen contract")
    confirmation_panels = [
        float(row["S_state"])
        for row in state_aggregate
        if row["split"] == "confirmation" and row["level"] == "panel"
    ]
    if (
        len(confirmation_panels) != len(expected_panels)
        or not _close(min(confirmation_panels), state_spec["confirmation_panel_S_state_min"])
        or not _close(max(confirmation_panels), state_spec["confirmation_panel_S_state_max"])
    ):
        errors.append("State cross-panel confirmation range mismatch")
    if (
        state_receipt["public_task3_diagnostic"]["not_a_leaderboard_physics_score"] is not True
        or state_receipt["organizer_only_metrics"] != {"S_LWR": None, "S_physics": None}
    ):
        errors.append("Physics metric boundary is not preserved")

    queue_spec = config["queue"]
    queue_source = checked_path(queue_spec, "source_path", "source_sha256", "Queue source")
    queue_candidate = checked_path(queue_spec, "candidate_path", "candidate_sha256", "Queue candidate")
    queue_local_path = checked_path(
        queue_spec, "local_receipt_path", "local_receipt_sha256", "Queue local evaluator receipt"
    )
    queue_fix_path = checked_path(
        queue_spec, "fix_receipt_path", "fix_receipt_sha256", "Queue fix receipt"
    )
    queue_diff_path = checked_path(
        queue_spec, "whole_table_diff_path", "whole_table_diff_sha256", "Queue whole-table diff"
    )
    queue_local = json.loads(queue_local_path.read_text())
    queue_fix = json.loads(queue_fix_path.read_text())
    queue_diff = json.loads(queue_diff_path.read_text())
    queue_rows, queue_counts, queue_errors = queue_change_counts(queue_source, queue_candidate)
    errors.extend(queue_errors)
    expected_queue_keys = {
        (panel, split) for panel in queue_spec["eligible_panels"] for split in QUEUE_SPLITS
    }
    if (
        queue_rows != queue_spec["rows"]
        or set(queue_counts) != expected_queue_keys
        or any(value != queue_spec["changed_per_eligible_panel_split"] for value in queue_counts.values())
        or sum(queue_counts.values()) != queue_spec["changed_rows"]
        or any(
            sum(value for (panel, row_split), value in queue_counts.items() if row_split == split)
            != queue_spec["changed_per_split"]
            for split in QUEUE_SPLITS
        )
    ):
        errors.append("Queue cross-panel change distribution mismatch")
    if (
        queue_local["status"] != "COMPLETE"
        or queue_local["decision"] != "BUILD_QUEUE_ONLY_CANDIDATE"
        or queue_local["metric_boundary"]["official_S_queue"] is not None
        or not _close(
            float(queue_local["confirmation_scores"]["off_by_one_only"]),
            float(queue_spec["local_confirmation_proxy"]),
        )
    ):
        errors.append("Queue public-train local evaluator contract failed")
    if (
        queue_fix["status"] != "VALID"
        or queue_fix["total_queue_rows"] != queue_spec["rows"]
        or queue_fix["rows_changed_1_to_0"] != queue_spec["changed_rows"]
        or queue_diff["status"] != "VALID"
        or queue_diff["rows_compared"] != 6985307
        or queue_diff["changed_rows_by_task"] != {"queue": queue_spec["changed_rows"]}
        or queue_diff["changed_cells_by_column"] != {"queue_pred": queue_spec["changed_rows"]}
    ):
        errors.append("Queue fix or whole-table isolation contract failed")

    odme_spec = config["odme"]
    odme_receipt_path = checked_path(odme_spec, "receipt_path", "receipt_sha256", "ODME receipt")
    odme_metrics_path = checked_path(odme_spec, "metrics_path", "metrics_sha256", "ODME metrics")
    validation_prediction_path = checked_path(
        odme_spec, "validation_prediction_path", "validation_prediction_sha256", "ODME validation prediction"
    )
    private_prediction_path = checked_path(
        odme_spec, "private_prediction_path", "private_prediction_sha256", "ODME private prediction"
    )
    combined_prediction_path = checked_path(
        odme_spec, "combined_prediction_path", "combined_prediction_sha256", "ODME combined prediction"
    )
    odme_receipt = json.loads(odme_receipt_path.read_text())
    odme_rows = _load_csv(odme_metrics_path)
    odme_gains, odme_errors = odme_panel_gains(
        odme_rows, float(odme_spec["lambda"]), float(odme_spec["comparison_lambda"])
    )
    errors.extend(odme_errors)
    if (
        odme_receipt["status"] != "COMPLETE"
        or set(odme_receipt["panels"]) != expected_panels
        or set(odme_receipt["splits"]) != QUEUE_SPLITS
        or odme_receipt["lambdas"] != [odme_spec["lambda"], odme_spec["comparison_lambda"]]
        or odme_receipt["metric_boundary"]["S_od"] is not None
        or odme_receipt["metric_boundary"]["S_dev"] is not None
        or odme_receipt["metric_boundary"]["S_attr"] is not None
        or odme_receipt["metrics_sha256"] != odme_spec["metrics_sha256"]
        or "nonnegative bounds" not in odme_receipt["solver"]["method"]
    ):
        errors.append("ODME solver, panel, receipt, or metric-boundary contract failed")
    if (
        len(odme_gains) != odme_spec["panel_splits"]
        or {(row["panel"], row["split"]) for row in odme_gains}
        != {(panel, split) for panel in expected_panels for split in QUEUE_SPLITS}
        or any(float(row["S_link_gain"]) <= 0.0 for row in odme_gains)
        or not _close(
            min(float(row["S_link_gain"]) for row in odme_gains),
            float(odme_spec["minimum_panel_S_link_gain"]),
        )
    ):
        errors.append("ODME all-panel S_link stability contract failed")
    overall_odme = {
        (row["split"], float(row["lambda"])): float(row["S_link"])
        for row in odme_rows
        if row["level"] == "overall"
    }
    if (
        not _close(overall_odme[("validation", float(odme_spec["lambda"]))], odme_spec["validation_S_link"])
        or not _close(overall_odme[("private", float(odme_spec["lambda"]))], odme_spec["private_S_link"])
    ):
        errors.append("ODME overall S_link mismatch")
    odme_predictions = _load_csv(combined_prediction_path)
    odme_keys = {
        (row["panel"], row["departure_time"], row["path_id"], row["origin_zone"], row["destination_zone"])
        for row in odme_predictions
    }
    odme_values = [float(row["path_flow"]) for row in odme_predictions]
    if (
        len(odme_predictions) != odme_spec["rows"]
        or len(odme_keys) != len(odme_predictions)
        or {row["panel"] for row in odme_predictions} != expected_panels
        or any(not math.isfinite(value) or value < 0.0 for value in odme_values)
        or odme_receipt["prediction_sha256"]["validation/lambda=5"]
        != odme_spec["validation_prediction_sha256"]
        or odme_receipt["prediction_sha256"]["private/lambda=5"]
        != odme_spec["private_prediction_sha256"]
    ):
        errors.append("ODME nonnegative prediction-table contract failed")
    if validation_prediction_path.stat().st_size <= 0 or private_prediction_path.stat().st_size <= 0:
        errors.append("ODME split prediction file is empty")

    if any(config["information_boundary"].values()):
        errors.append("four-task contract permits hidden information")

    output_root.mkdir(parents=True)
    queue_output = output_root / "queue_changes_by_panel_split.csv"
    with queue_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["panel", "split", "changed_1_to_0"])
        writer.writeheader()
        writer.writerows(
            {
                "panel": panel,
                "split": split,
                "changed_1_to_0": count,
            }
            for (panel, split), count in sorted(queue_counts.items())
        )
    odme_output = output_root / "odme_panel_split_gains.csv"
    with odme_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(odme_gains[0]))
        writer.writeheader()
        writer.writerows(odme_gains)
    matrix_output = output_root / "four_task_baseline_matrix.csv"
    matrix_rows = [
        {
            "task": "state",
            "status": "BASELINE_COMPLETE",
            "method": "deployment-faithful frozen-profile V32 interpolation",
            "local_component": "S_state",
            "development_or_validation": state_spec["development_S_state"],
            "confirmation_or_private": state_spec["confirmation_S_state"],
            "cross_corridor_evidence": "10 panels x 3 regimes x 2 holdouts; zero missing",
            "hidden_metrics": "none",
        },
        {
            "task": "queue",
            "status": "BASELINE_COMPLETE",
            "method": "V32 onset-horizon off-by-one correction",
            "local_component": "released-observation Queue proxy; official S_queue withheld",
            "development_or_validation": queue_local["confirmation_scores"]["v32_bug_anchor"],
            "confirmation_or_private": queue_local["confirmation_scores"]["off_by_one_only"],
            "cross_corridor_evidence": "8 eligible panels x 2 splits x 10 isolated changes",
            "hidden_metrics": "S_queue=null",
        },
        {
            "task": "physics",
            "status": "PUBLIC_COMPONENT_ONLY",
            "method": "official public triangular FD branch over frozen State control",
            "local_component": "S_FD",
            "development_or_validation": state_spec["development_S_FD"],
            "confirmation_or_private": state_spec["confirmation_S_FD"],
            "cross_corridor_evidence": "10 panels x 3 regimes x 2 holdouts",
            "hidden_metrics": "S_LWR=null; S_physics=null",
        },
        {
            "task": "odme",
            "status": "BASELINE_COMPLETE",
            "method": "lambda=5 prior-regularized nonnegative least squares",
            "local_component": "S_link",
            "development_or_validation": odme_spec["validation_S_link"],
            "confirmation_or_private": odme_spec["private_S_link"],
            "cross_corridor_evidence": "10 panels x 2 splits; every lambda5 delta positive",
            "hidden_metrics": "S_od=null; S_dev=null; S_attr=null",
        },
    ]
    with matrix_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix_rows[0]))
        writer.writeheader()
        writer.writerows(matrix_rows)
    receipt: dict[str, object] = {
        "status": "VALID" if not errors else "FAIL",
        "experiment": "four_task_baseline_audit_v1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "tasks_verified": ["state", "queue", "physics", "odme"],
        "errors": errors,
        "coverage": {
            "state_panel_regime_holdouts": len(state_rows),
            "state_target_cells": state_target_cells,
            "queue_rows": queue_rows,
            "queue_changed_rows": sum(queue_counts.values()),
            "queue_eligible_panel_splits": len(queue_counts),
            "odme_rows": len(odme_predictions),
            "odme_panel_splits": len(odme_gains),
            "odme_all_panel_split_gains_positive": bool(odme_gains)
            and all(float(row["S_link_gain"]) > 0.0 for row in odme_gains),
        },
        "component_metrics": {
            "state": state_score_checks,
            "queue": {
                "official_S_queue": None,
                "confirmation_proxy": queue_local["confirmation_scores"]["off_by_one_only"],
            },
            "physics": {
                "development_S_FD": state_spec["development_S_FD"],
                "confirmation_S_FD": state_spec["confirmation_S_FD"],
                "S_LWR": None,
                "S_physics": None,
            },
            "odme": {
                "validation_S_link": odme_spec["validation_S_link"],
                "private_S_link": odme_spec["private_S_link"],
                "minimum_panel_S_link_gain": min(float(row["S_link_gain"]) for row in odme_gains),
                "S_od": None,
                "S_dev": None,
                "S_attr": None,
            },
        },
        "information_boundary": {
            "hidden_state_targets_used": False,
            "official_queue_truth_used": False,
            "organizer_boundary_flows_used": False,
            "hidden_odme_metrics_used": False,
        },
        "official_code_commit": official_head,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": input_hashes,
        "outputs": {
            queue_output.name: _sha256(queue_output),
            odme_output.name: _sha256(odme_output),
            matrix_output.name: _sha256(matrix_output),
        },
        "decision": "D30_FOUR_TASK_BASELINES_EVIDENCED",
    }
    receipt_path = output_root / "four_task_baseline_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "four_task_baseline_contract_v1.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    receipt = run(args.traffic_root.resolve(), args.config.resolve(), args.output_root.resolve())
    if receipt["status"] != "VALID":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
