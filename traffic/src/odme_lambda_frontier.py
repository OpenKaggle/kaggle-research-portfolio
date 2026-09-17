#!/usr/bin/env python3
"""Audit a one-parameter ODME regularization frontier on released evidence.

Only S_link is locally scoreable.  The withheld S_od, S_dev, and S_attr remain
explicitly unknown; this script never treats a locally reconstructed reference
as ground truth.
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
from scipy.optimize import lsq_linear
from scipy.sparse.linalg import LinearOperator


HERE = Path(__file__).resolve().parent
OFFICIAL_SRC = HERE.parent / "official" / "src"
sys.path.insert(0, str(OFFICIAL_SRC))

from task4.build_task4_odme_artifacts import (  # noqa: E402
    load_operator,
    released_counts,
    released_prior,
)


DEFAULT_LAMBDAS = (0.05, 1.0, 5.0, 20.0, 50.0)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _anchor(
    release: Path,
    panel: str,
    split: str,
    path_ids: list[str],
    base: pd.DataFrame,
) -> tuple[np.ndarray, str]:
    prior = released_prior(release, panel, split)
    if prior is not None and len(prior) and "path_flow" in prior.columns:
        prior = prior.copy()
        prior["path_id"] = prior.path_id.astype(str)
        values = (
            prior.set_index("path_id")
            .reindex(path_ids)
            .path_flow.pipe(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            .to_numpy(dtype=float)
        )
        if np.abs(values).sum() > 0:
            departure = (
                str(prior.departure_time.iloc[0])
                if "departure_time" in prior.columns
                else str(base.departure_time.fillna(f"{split.upper()}-PM").iloc[0])
            )
            return values, departure
    return (
        base.base_flow.to_numpy(dtype=float),
        str(base.departure_time.fillna(f"{split.upper()}-PM").iloc[0]),
    )


def _solve(
    A: np.ndarray,
    counts: np.ndarray,
    anchor: np.ndarray,
    reg_lambda: float,
    tolerance: float = 1e-8,
    lsmr_tolerance: float = 1e-8,
    max_iterations: int = 300,
) -> np.ndarray:
    """Matrix-free bounded least squares equivalent to augmented dense NNLS."""
    scale = np.sqrt(reg_lambda)
    n_counts, n_paths = A.shape

    def matvec(values: np.ndarray) -> np.ndarray:
        return np.concatenate((A @ values, scale * values))

    def rmatvec(values: np.ndarray) -> np.ndarray:
        return A.T @ values[:n_counts] + scale * values[n_counts:]

    operator = LinearOperator(
        (n_counts + n_paths, n_paths),
        matvec=matvec,
        rmatvec=rmatvec,
        dtype=float,
    )
    result = lsq_linear(
        operator,
        np.concatenate((counts, scale * anchor)),
        bounds=(0.0, np.inf),
        method="trf",
        lsq_solver="lsmr",
        tol=tolerance,
        lsmr_tol=lsmr_tolerance,
        max_iter=max_iterations,
    )
    if not result.success:
        raise RuntimeError(
            f"matrix-free ODME solve failed: status={result.status} message={result.message}"
        )
    return result.x


def run(
    release: Path,
    output_root: Path,
    lambdas: tuple[float, ...],
    splits: tuple[str, ...],
    selected_panels: set[str] | None,
    control_lambda: float = 20.0,
    tolerance: float = 1e-8,
    lsmr_tolerance: float = 1e-8,
    max_iterations: int = 300,
) -> dict[str, object]:
    started = time.perf_counter()
    manifest = json.loads((release / "config" / "corridors.json").read_text(encoding="utf-8"))
    panel_records = manifest["panels"]
    if selected_panels:
        unknown = selected_panels - {record["corridor_id"] for record in panel_records}
        if unknown:
            raise ValueError(f"unknown panels: {sorted(unknown)}")
        panel_records = [record for record in panel_records if record["corridor_id"] in selected_panels]

    metric_rows = []
    prediction_parts: dict[tuple[str, float], list[pd.DataFrame]] = {
        (split, reg_lambda): [] for split in splits for reg_lambda in lambdas
    }
    for record in panel_records:
        panel = record["corridor_id"]
        family = record["family_id"]
        path_ids, link_ids, A, paths, base = load_operator(
            release / "corridors" / panel / "network"
        )
        link_index = {link: index for index, link in enumerate(link_ids)}
        for split in splits:
            count_frame = released_counts(release, panel, split)
            if count_frame is None:
                raise FileNotFoundError(f"{panel}/{split}: released link counts are missing")
            count_frame = count_frame.copy()
            count_frame["link_id"] = count_frame.link_id.astype(str)
            scored_links = [link for link in count_frame.link_id if link in link_index]
            scored_indices = [link_index[link] for link in scored_links]
            A_score = A[scored_indices]
            counts = (
                count_frame.set_index("link_id")
                .reindex(scored_links)["count"]
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=float)
            )
            anchor, departure_time = _anchor(release, panel, split, path_ids, base)
            denom_counts = max(float(counts.sum()), 1e-9)
            denom_anchor = max(float(np.abs(anchor).sum()), 1e-9)
            for reg_lambda in lambdas:
                print(
                    f"[ODME frontier] panel={panel} split={split} lambda={reg_lambda:g} "
                    f"paths={len(path_ids)} counted_links={len(scored_links)}",
                    flush=True,
                )
                solved = _solve(
                    A_score,
                    counts,
                    anchor,
                    reg_lambda,
                    tolerance=tolerance,
                    lsmr_tolerance=lsmr_tolerance,
                    max_iterations=max_iterations,
                )
                loaded = A_score @ solved
                s_link = max(0.0, 1.0 - float(np.abs(loaded - counts).sum()) / denom_counts)
                prior_l1_ratio = float(np.abs(solved - anchor).sum()) / denom_anchor
                metric_rows.append(
                    {
                        "level": "panel",
                        "panel": panel,
                        "family_id": family,
                        "split": split,
                        "lambda": reg_lambda,
                        "n_paths": len(path_ids),
                        "n_counted_links": len(scored_links),
                        "S_link": s_link,
                        "prior_l1_ratio": prior_l1_ratio,
                        "total_flow_ratio_to_prior": float(solved.sum()) / max(float(anchor.sum()), 1e-9),
                        "zero_path_fraction": float(np.mean(solved <= 1e-12)),
                    }
                )
                prediction = paths[["path_id", "origin_zone", "destination_zone"]].copy()
                prediction.insert(0, "departure_time", departure_time)
                prediction.insert(0, "panel", panel)
                prediction["path_flow"] = solved
                prediction_parts[(split, reg_lambda)].append(prediction)

    panel_metrics = pd.DataFrame(metric_rows)
    family_rows = []
    for (split, reg_lambda, family), group in panel_metrics.groupby(
        ["split", "lambda", "family_id"], sort=True
    ):
        family_rows.append(
            {
                "level": "family",
                "panel": None,
                "family_id": family,
                "split": split,
                "lambda": reg_lambda,
                "n_paths": int(group.n_paths.sum()),
                "n_counted_links": int(group.n_counted_links.sum()),
                "S_link": float(group.S_link.mean()),
                "prior_l1_ratio": float(group.prior_l1_ratio.mean()),
                "total_flow_ratio_to_prior": float(group.total_flow_ratio_to_prior.mean()),
                "zero_path_fraction": float(group.zero_path_fraction.mean()),
            }
        )
    family_metrics = pd.DataFrame(family_rows)
    overall_rows = []
    for (split, reg_lambda), group in family_metrics.groupby(["split", "lambda"], sort=True):
        overall_rows.append(
            {
                "level": "overall",
                "panel": None,
                "family_id": "ALL",
                "split": split,
                "lambda": reg_lambda,
                "n_paths": int(group.n_paths.sum()),
                "n_counted_links": int(group.n_counted_links.sum()),
                "S_link": float(group.S_link.mean()),
                "prior_l1_ratio": float(group.prior_l1_ratio.mean()),
                "total_flow_ratio_to_prior": float(group.total_flow_ratio_to_prior.mean()),
                "zero_path_fraction": float(group.zero_path_fraction.mean()),
            }
        )
    overall_metrics = pd.DataFrame(overall_rows)
    metrics = pd.concat([panel_metrics, family_metrics, overall_metrics], ignore_index=True)

    output_root.mkdir(parents=True, exist_ok=True)
    metrics_path = output_root / "odme_lambda_frontier_metrics.csv"
    metrics.to_csv(metrics_path, index=False)
    prediction_hashes = {}
    for (split, reg_lambda), pieces in prediction_parts.items():
        label = format(reg_lambda, "g").replace(".", "p")
        path = output_root / f"odme_{split}_lambda_{label}.csv"
        pd.concat(pieces, ignore_index=True).to_csv(path, index=False)
        prediction_hashes[f"{split}/lambda={reg_lambda:g}"] = _sha256(path)

    baseline_lambda = control_lambda
    decision = "AUDIT_ONLY_NO_CONTROL_COMPARISON"
    candidates = []
    if baseline_lambda in lambdas:
        overall_index = overall_metrics.set_index(["split", "lambda"])
        panel_index = panel_metrics.set_index(["split", "lambda", "panel"])
        for reg_lambda in lambdas:
            if reg_lambda == baseline_lambda:
                continue
            split_gains = []
            panel_gains = []
            prior_increases = []
            for split in splits:
                candidate = overall_index.loc[(split, reg_lambda)]
                baseline = overall_index.loc[(split, baseline_lambda)]
                split_gains.append(float(candidate.S_link - baseline.S_link))
                prior_increases.append(float(candidate.prior_l1_ratio - baseline.prior_l1_ratio))
                for record in panel_records:
                    panel = record["corridor_id"]
                    panel_gains.append(
                        float(
                            panel_index.loc[(split, reg_lambda, panel), "S_link"]
                            - panel_index.loc[(split, baseline_lambda, panel), "S_link"]
                        )
                    )
            candidates.append(
                {
                    "lambda": reg_lambda,
                    "minimum_split_S_link_gain": min(split_gains),
                    "minimum_panel_S_link_gain": min(panel_gains),
                    "maximum_prior_l1_ratio_increase": max(prior_increases),
                }
            )
        safe = [
            candidate
            for candidate in candidates
            if candidate["minimum_split_S_link_gain"] >= 0.005
            and candidate["minimum_panel_S_link_gain"] >= -0.01
            and candidate["maximum_prior_l1_ratio_increase"] <= 0.10
        ]
        decision = "LOCAL_FRONTIER_CANDIDATE_EXISTS" if safe else "KEEP_CONTROL_LAMBDA"

    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    receipt = {
        "status": "COMPLETE",
        "question": "Can changing only ODME regularization lambda improve released-count fit robustly without a large move away from the weak prior?",
        "splits": list(splits),
        "panels": [record["corridor_id"] for record in panel_records],
        "lambdas": list(lambdas),
        "control_lambda": control_lambda,
        "metric_boundary": {
            "S_link": "official locally scoreable component; 25% of Task 4",
            "S_od": None,
            "S_dev": None,
            "S_attr": None,
            "warning": "A better S_link does not imply a better total ODME score.",
        },
        "solver": {
            "method": "scipy lsq_linear TRF with matrix-free augmented ridge operator and nonnegative bounds",
            "tolerance": tolerance,
            "lsmr_tolerance": lsmr_tolerance,
            "max_iterations": max_iterations,
        },
        "control_comparisons": candidates,
        "decision_rule": "A local frontier candidate needs >=0.005 S_link gain on every split, no panel worse than -0.01, and <=0.10 increase in mean L1 distance-to-prior ratio; any remote test still requires a separate preregistered total-score gate.",
        "decision": decision,
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": peak_mb,
        "metrics_sha256": _sha256(metrics_path),
        "prediction_sha256": prediction_hashes,
    }
    receipt_path = output_root / "odme_lambda_frontier_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--lambda", dest="lambdas", type=float, action="append")
    parser.add_argument("--split", dest="splits", choices=["train", "validation", "private"], action="append")
    parser.add_argument("--panel", action="append")
    parser.add_argument("--control-lambda", type=float, default=20.0)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    parser.add_argument("--lsmr-tolerance", type=float, default=1e-8)
    parser.add_argument("--max-iterations", type=int, default=300)
    args = parser.parse_args()
    lambdas = tuple(args.lambdas or DEFAULT_LAMBDAS)
    if any(value <= 0 for value in lambdas):
        raise ValueError("all lambda values must be positive")
    if args.control_lambda <= 0:
        raise ValueError("control lambda must be positive")
    if args.tolerance <= 0 or args.lsmr_tolerance <= 0:
        raise ValueError("solver tolerances must be positive")
    if args.max_iterations <= 0:
        raise ValueError("max iterations must be positive")
    splits = tuple(args.splits or ("validation", "private"))
    print(
        json.dumps(
            run(
                args.release_root.resolve(),
                args.output_root.resolve(),
                lambdas,
                splits,
                set(args.panel) if args.panel else None,
                args.control_lambda,
                args.tolerance,
                args.lsmr_tolerance,
                args.max_iterations,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
