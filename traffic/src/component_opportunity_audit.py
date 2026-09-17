#!/usr/bin/env python3
"""Read-only opportunity audit across the four TrafficFlowBench tasks.

The audit never opens hidden or scored-split truth.  It separates theoretical
headroom from locally observable headroom so an unobservable large task weight
cannot masquerade as evidence for another leaderboard submission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
OFFICIAL_SRC = HERE.parent / "official" / "src"
sys.path.insert(0, str(OFFICIAL_SRC))

from task4.build_task4_odme_artifacts import load_operator, released_counts  # noqa: E402


SUBMISSION_COST_FLOOR_TOTAL = 0.0035


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def scan_odme_structure(release: Path) -> pd.DataFrame:
    """Measure public count-operator identifiability without solving for path flows."""
    manifest = json.loads((release / "config" / "corridors.json").read_text())
    rows: list[dict[str, object]] = []
    for record in manifest["panels"]:
        panel = record["corridor_id"]
        path_ids, link_ids, operator, _, _ = load_operator(
            release / "corridors" / panel / "network"
        )
        link_index = {link: index for index, link in enumerate(link_ids)}
        for split in ("validation", "private"):
            counts = released_counts(release, panel, split)
            if counts is None:
                raise FileNotFoundError(f"{panel}/{split}: released counts unavailable")
            scored = [link for link in counts.link_id.astype(str) if link in link_index]
            matrix = operator[[link_index[link] for link in scored]]
            rank = int(np.linalg.matrix_rank(matrix))
            n_paths = len(path_ids)
            rows.append(
                {
                    "panel": panel,
                    "family_id": record["family_id"],
                    "split": split,
                    "n_paths": n_paths,
                    "n_network_links": len(link_ids),
                    "n_counted_links": len(scored),
                    "operator_rank": rank,
                    "nullity": n_paths - rank,
                    "nullspace_fraction": (n_paths - rank) / n_paths,
                }
            )
    return pd.DataFrame(rows)


def build_opportunities(
    status: dict[str, object],
    odme_metrics: pd.DataFrame,
    nonlinear_receipt: dict[str, object],
) -> pd.DataFrame:
    """Return comparable headroom rows using only already-audited evidence."""
    state = status["component_baselines"]["state"]
    physics = status["component_baselines"]["physics_public_diagnostic"]
    state_score = float(state["confirmation_S_state"])
    fd_score = float(physics["confirmation_S_FD"])
    nonlinear = nonlinear_receipt["confirmation"]
    nonlinear_signal = 0.35 * float(nonlinear["delta_S_state"])
    fd_signal = 0.15 / 3.0 * float(nonlinear["delta_S_FD"])

    current_link = odme_metrics[
        odme_metrics.level.eq("overall") & odme_metrics["lambda"].eq(5.0)
    ]
    if set(current_link.split) != {"validation", "private"}:
        raise ValueError("lambda=5 overall S_link must exist for both scored splits")
    conservative_link_score = float(current_link.S_link.min())
    link_ceiling = 0.20 * 0.25 * (1.0 - conservative_link_score)

    rows = [
        {
            "actionability_rank": 1,
            "component": "state",
            "effective_total_weight": 0.35,
            "local_metric_coverage": 1.0,
            "current_audited_score": state_score,
            "theoretical_total_headroom": 0.35 * (1.0 - state_score),
            "observable_remaining_total_ceiling": 0.35 * (1.0 - state_score),
            "best_recent_total_signal": nonlinear_signal,
            "actionable_local_lower_bound": 0.0,
            "independent_family_ready": False,
            "decision": "HOLD: one-panel nonlinear signal is below the fixed expansion floor and is not an all-panel lower bound",
        },
        {
            "actionability_rank": 2,
            "component": "queue",
            "effective_total_weight": 0.30,
            "local_metric_coverage": 0.0,
            "current_audited_score": np.nan,
            "theoretical_total_headroom": 0.30,
            "observable_remaining_total_ceiling": np.nan,
            "best_recent_total_signal": 0.02364,
            "actionable_local_lower_bound": 0.0,
            "independent_family_ready": False,
            "decision": "HOLD: official labels are withheld and the remaining proxy-selected families failed breadth or development selection",
        },
        {
            "actionability_rank": 3,
            "component": "odme_hidden",
            "effective_total_weight": 0.15,
            "local_metric_coverage": 0.0,
            "current_audited_score": np.nan,
            "theoretical_total_headroom": 0.15,
            "observable_remaining_total_ceiling": np.nan,
            "best_recent_total_signal": 0.00523,
            "actionable_local_lower_bound": 0.0,
            "independent_family_ready": False,
            "decision": "HOLD: S_od/S_dev/S_attr are withheld and the public path system is overwhelmingly underdetermined",
        },
        {
            "actionability_rank": 4,
            "component": "physics_lwr",
            "effective_total_weight": 0.10,
            "local_metric_coverage": 0.0,
            "current_audited_score": np.nan,
            "theoretical_total_headroom": 0.10,
            "observable_remaining_total_ceiling": np.nan,
            "best_recent_total_signal": np.nan,
            "actionable_local_lower_bound": 0.0,
            "independent_family_ready": False,
            "decision": "HOLD: organizer boundary flux is withheld and LWR can move only through Task 1",
        },
        {
            "actionability_rank": 5,
            "component": "physics_fd",
            "effective_total_weight": 0.05,
            "local_metric_coverage": 1.0,
            "current_audited_score": fd_score,
            "theoretical_total_headroom": 0.05 * (1.0 - fd_score),
            "observable_remaining_total_ceiling": 0.05 * (1.0 - fd_score),
            "best_recent_total_signal": fd_signal,
            "actionable_local_lower_bound": 0.0,
            "independent_family_ready": False,
            "decision": "HOLD: FD is already near saturation and is not independently controllable",
        },
        {
            "actionability_rank": 6,
            "component": "odme_s_link",
            "effective_total_weight": 0.05,
            "local_metric_coverage": 1.0,
            "current_audited_score": conservative_link_score,
            "theoretical_total_headroom": link_ceiling,
            "observable_remaining_total_ceiling": link_ceiling,
            "best_recent_total_signal": 0.00523,
            "actionable_local_lower_bound": 0.0,
            "independent_family_ready": False,
            "decision": "STOP TUNING: even perfect S_link can add less than the submission-cost floor",
        },
    ]
    return pd.DataFrame(rows)


def run(
    release: Path,
    status_path: Path,
    odme_metrics_path: Path,
    nonlinear_receipt_path: Path,
    output_root: Path,
) -> dict[str, object]:
    started = time.perf_counter()
    status = json.loads(status_path.read_text())
    nonlinear_receipt = json.loads(nonlinear_receipt_path.read_text())
    odme_metrics = pd.read_csv(odme_metrics_path)
    structure = scan_odme_structure(release)
    opportunities = build_opportunities(status, odme_metrics, nonlinear_receipt)
    qualifies = opportunities[
        opportunities.independent_family_ready.astype(bool)
        & opportunities.actionable_local_lower_bound.ge(SUBMISSION_COST_FLOOR_TOTAL)
    ]

    output_root.mkdir(parents=True, exist_ok=True)
    opportunity_path = output_root / "component_opportunities.csv"
    structure_path = output_root / "odme_identifiability.csv"
    opportunities.to_csv(opportunity_path, index=False)
    structure.to_csv(structure_path, index=False)
    receipt: dict[str, object] = {
        "status": "COMPLETE_READ_ONLY",
        "experiment": "component_opportunity_audit_v1",
        "question": "Does any independent remaining component family have a locally supported total-score lower bound large enough to justify another submission experiment?",
        "data_boundary": {
            "prediction_rows_generated": 0,
            "target_truth_read": False,
            "hidden_labels_reconstructed": False,
            "sources": [
                str(status_path), str(odme_metrics_path),
                str(nonlinear_receipt_path), str(release / "config" / "corridors.json"),
                "released Task 4 path-link operators and count-link IDs",
            ],
        },
        "submission_cost_floor_total": SUBMISSION_COST_FLOOR_TOTAL,
        "submission_cost_floor_basis": "Equivalent to the existing +0.01 State expansion gate multiplied by the official 0.35 State weight.",
        "odme_identifiability": {
            "panel_splits": len(structure),
            "minimum_nullspace_fraction": float(structure.nullspace_fraction.min()),
            "maximum_nullspace_fraction": float(structure.nullspace_fraction.max()),
            "minimum_operator_rank": int(structure.operator_rank.min()),
            "maximum_operator_rank": int(structure.operator_rank.max()),
        },
        "qualifying_independent_families": qualifies.component.tolist(),
        "decision": (
            "PREREGISTER_INDEPENDENT_FAMILY"
            if len(qualifies)
            else "HOLD_LAMBDA5_NO_NEW_EXPERIMENT_OR_SUBMISSION"
        ),
        "interpretation": "Large unobservable task weights are theoretical upside, not a local lower bound. State remains the best future research surface, but no currently defined independent family clears the fixed submission-cost floor.",
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "inputs": {
            status_path.name: _sha256(status_path),
            odme_metrics_path.name: _sha256(odme_metrics_path),
            nonlinear_receipt_path.name: _sha256(nonlinear_receipt_path),
            "corridors.json": _sha256(release / "config" / "corridors.json"),
        },
        "outputs": {
            opportunity_path.name: _sha256(opportunity_path),
            structure_path.name: _sha256(structure_path),
        },
    }
    receipt_path = output_root / "component_opportunity_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--odme-metrics", type=Path, required=True)
    parser.add_argument("--nonlinear-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.release_root.resolve(), args.status.resolve(),
        args.odme_metrics.resolve(), args.nonlinear_receipt.resolve(),
        args.output_root.resolve(),
    )


if __name__ == "__main__":
    main()
