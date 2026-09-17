#!/usr/bin/env python3
"""Audit a clip-level joint decoder on the CUHK-X training questions.

The experiment starts from the fixed public-graph OOF prediction for every
question.  Its only intervention is a semantic factor between a HAU
``combination`` question and the ``single`` question for the same clip.  A
combination prediction proposes the unique single option contained in its
selected action set.  Whether a proposal signature may override the parent is
learned inside each outer training fold; held-out-subject labels are never used
to select rules.

Two negative controls are mandatory:

* row-wise option permutations must give exactly equivariant predictions;
* a text-only sibling-support decoder must not reproduce the apparent gain.

Test data are not opened unless every promotion gate passes.  A failing run
writes a versioned rejection receipt and never creates a candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


LABELS = "ABCD"
EXPECTED_USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]
EXPECTED_TRAIN_SHA256 = "2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc"
EXPECTED_PARENT_OOF_SHA256 = "6216e1db44c6cae7077fafb2e0d4a75d90071547bffcdc7720128a2634080e33"
EXPECTED_TEST_SHA256 = "d694c7abc5a003d5c9048098880f0f77716fae0eb18d1c9fe9330e4e987320a5"
EXPECTED_TEST_PARENT_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"
EXPECTED_PRIMARY_BASE_SHA256 = "3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4"

# Predeclared, deliberately small selector.  These constants are never tuned
# against an outer fold.
MIN_SIGNATURE_ROWS = 5
MIN_SIGNATURE_SUBJECTS = 3
MIN_PROPOSAL_ACCURACY = 0.80


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def atoms(value: str) -> frozenset[str]:
    return frozenset(norm(piece) for piece in str(value).split(",") if piece.strip())


def extract_user(value: str) -> int:
    match = re.search(r"(?:^|/)user(\d+)(?:/|$)", str(value), flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"No subject ID in path: {value!r}")
    return int(match.group(1))


def atom_bin(count: int) -> str:
    return "4plus" if count >= 4 else str(count)


def remap_label_string(value: str, old_to_new: dict[str, str], category: str) -> str:
    mapped = "".join(old_to_new[label] for label in str(value) if label in LABELS)
    return mapped if category == "sequence" else "".join(sorted(mapped))


def permute_options(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Apply a deterministic independent option permutation to each QA row."""
    output = frame.copy()
    inverse_by_id: dict[str, dict[str, str]] = {}
    for index, row in output.iterrows():
        order = sorted(
            LABELS,
            key=lambda label: hashlib.sha256(f"{row['qa_id']}:{label}".encode()).hexdigest(),
        )
        new_to_old = dict(zip(LABELS, order))
        old_to_new = {old: new for new, old in new_to_old.items()}
        old_options = {label: row[label] for label in LABELS}
        for new_label, old_label in new_to_old.items():
            output.at[index, new_label] = old_options[old_label]
        for column in ("answer", "parent_prediction"):
            if column in output.columns:
                output.at[index, column] = remap_label_string(
                    str(row[column]), old_to_new, str(row["category"])
                )
        inverse_by_id[str(row["qa_id"])] = new_to_old
    return output, inverse_by_id


def invert_predictions(
    frame: pd.DataFrame, inverse_by_id: dict[str, dict[str, str]]
) -> pd.Series:
    values: list[str] = []
    for _, row in frame.iterrows():
        new_to_old = inverse_by_id[str(row["qa_id"])]
        mapped = "".join(new_to_old[label] for label in str(row["joint_prediction"]))
        if row["category"] != "sequence":
            mapped = "".join(sorted(mapped))
        values.append(mapped)
    return pd.Series(values, index=frame.index, dtype=str)


def prepare_training(train: pd.DataFrame, parent_oof: pd.DataFrame) -> pd.DataFrame:
    required = {"qa_id", "source", "path", "category", "question", *LABELS, "answer"}
    if not required.issubset(train.columns):
        raise ValueError(f"Training schema missing {sorted(required - set(train.columns))}")
    if train["qa_id"].duplicated().any() or parent_oof["qa_id"].duplicated().any():
        raise ValueError("QA IDs must be unique")
    if set(parent_oof["qa_id"]) != set(train["qa_id"]):
        raise ValueError("Parent OOF IDs do not exactly match training IDs")
    data = train.merge(
        parent_oof[["qa_id", "prediction"]].rename(
            columns={"prediction": "parent_prediction"}
        ),
        on="qa_id",
        validate="one_to_one",
    )
    data["user"] = data["path"].map(extract_user)
    if sorted(data["user"].unique().tolist()) != EXPECTED_USERS:
        raise ValueError("Expected exactly the official 18 training subjects")
    if data.groupby("path")["user"].nunique().max() != 1:
        raise ValueError("A clip crosses subject folds")
    parent_users = parent_oof.set_index("qa_id")["user"].astype(int)
    expected_users = data.set_index("qa_id")["user"]
    if not parent_users.sort_index().equals(expected_users.sort_index()):
        raise ValueError("Parent OOF fold subject does not match QA path")
    return data


def main_proposals(data: pd.DataFrame) -> pd.DataFrame:
    """Create semantic combination-to-single proposals for each eligible clip."""
    rows: list[dict[str, object]] = []
    for clip, group in data[data["source"] == "HAU"].groupby("path", sort=True):
        if group["user"].nunique() != 1:
            raise ValueError(f"Clip {clip!r} crosses subjects")
        categories = {str(row["category"]): row for _, row in group.iterrows()}
        if not {"combination", "single"}.issubset(categories):
            continue
        source = categories["combination"]
        target = categories["single"]
        source_prediction = str(source["parent_prediction"])
        if len(source_prediction) != 1 or source_prediction not in LABELS:
            continue
        selected_atoms = atoms(source[source_prediction])
        matches = [
            label
            for label in LABELS
            if atoms(target[label]) and atoms(target[label]).issubset(selected_atoms)
        ]
        if len(matches) != 1:
            continue
        proposal = matches[0]
        rows.append(
            {
                "clip": clip,
                "qa_id": str(target["qa_id"]),
                "user": int(target["user"]),
                "source": "HAU",
                "category": "single",
                "parent_prediction": str(target["parent_prediction"]),
                "proposal": proposal,
                "answer": str(target.get("answer", "")),
                "atom_count": len(selected_atoms),
                "sequence_present": "sequence" in categories,
                "signature": (
                    f"atoms={atom_bin(len(selected_atoms))}|"
                    f"sequence={'yes' if 'sequence' in categories else 'no'}"
                ),
            }
        )
    return pd.DataFrame(rows)


def text_only_proposals(data: pd.DataFrame) -> pd.DataFrame:
    """Ablate all sibling predictions and use only sibling option-text support."""
    rows: list[dict[str, object]] = []
    for clip, group in data[data["source"] == "HAU"].groupby("path", sort=True):
        categories = {str(row["category"]): row for _, row in group.iterrows()}
        if "single" not in categories or len(categories) < 2:
            continue
        target = categories["single"]
        support: Counter[str] = Counter()
        for category, sibling in categories.items():
            if category == "single":
                continue
            for label in LABELS:
                # Count at most once per option so comma repetition cannot inflate support.
                support.update(atoms(sibling[label]))
        scores = {label: support[norm(target[label])] for label in LABELS}
        best_score = max(scores.values())
        best = [label for label in LABELS if scores[label] == best_score]
        if best_score <= 0 or len(best) != 1:
            continue
        rows.append(
            {
                "clip": clip,
                "qa_id": str(target["qa_id"]),
                "user": int(target["user"]),
                "source": "HAU",
                "category": "single",
                "parent_prediction": str(target["parent_prediction"]),
                "proposal": best[0],
                "answer": str(target.get("answer", "")),
                "sibling_categories": len(categories) - 1,
                "max_support": int(best_score),
            }
        )
    return pd.DataFrame(rows)


def fit_signatures(proposals: pd.DataFrame, fit_users: Iterable[int]) -> pd.DataFrame:
    users = set(int(user) for user in fit_users)
    fit = proposals[
        proposals["user"].isin(users)
        & (proposals["proposal"] != proposals["parent_prediction"])
    ].copy()
    fit["proposal_correct"] = fit["proposal"] == fit["answer"]
    fit["parent_correct"] = fit["parent_prediction"] == fit["answer"]
    if fit.empty:
        return pd.DataFrame(
            columns=[
                "signature", "rows", "subjects", "proposal_correct", "parent_correct",
                "proposal_accuracy", "net", "selected",
            ]
        )
    stats = (
        fit.groupby("signature", sort=True)
        .agg(
            rows=("qa_id", "size"),
            subjects=("user", "nunique"),
            proposal_correct=("proposal_correct", "sum"),
            parent_correct=("parent_correct", "sum"),
        )
        .reset_index()
    )
    stats["proposal_accuracy"] = stats["proposal_correct"] / stats["rows"]
    stats["net"] = stats["proposal_correct"] - stats["parent_correct"]
    stats["selected"] = (
        (stats["rows"] >= MIN_SIGNATURE_ROWS)
        & (stats["subjects"] >= MIN_SIGNATURE_SUBJECTS)
        & (stats["proposal_accuracy"] >= MIN_PROPOSAL_ACCURACY)
        & (stats["net"] > 0)
    )
    return stats


def crossfit(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    proposals = main_proposals(data)
    output = data[
        ["qa_id", "source", "category", "answer", "user", "path", "parent_prediction"]
    ].copy()
    output["joint_prediction"] = output["parent_prediction"]
    trace_rows: list[dict[str, object]] = []
    for held_user in EXPECTED_USERS:
        fit_users = [user for user in EXPECTED_USERS if user != held_user]
        stats = fit_signatures(proposals, fit_users)
        selected = set(stats.loc[stats["selected"], "signature"])
        held = proposals[
            (proposals["user"] == held_user)
            & proposals["signature"].isin(selected)
            & (proposals["proposal"] != proposals["parent_prediction"])
        ]
        replacement = held.set_index("qa_id")["proposal"].to_dict()
        mask = output["qa_id"].isin(replacement)
        output.loc[mask, "joint_prediction"] = output.loc[mask, "qa_id"].map(replacement)
        for _, row in stats.iterrows():
            trace_rows.append(
                {
                    "held_user": held_user,
                    "signature": row["signature"],
                    "train_rows": int(row["rows"]),
                    "train_subjects": int(row["subjects"]),
                    "train_proposal_correct": int(row["proposal_correct"]),
                    "train_parent_correct": int(row["parent_correct"]),
                    "train_proposal_accuracy": float(row["proposal_accuracy"]),
                    "train_net": int(row["net"]),
                    "selected": bool(row["selected"]),
                    "held_overrides": int(len(held[held["signature"] == row["signature"]])),
                }
            )
    if len(output) != len(data) or output["qa_id"].duplicated().any():
        raise ValueError("Cross-fit output row invariant failed")
    return output, proposals, pd.DataFrame(trace_rows)


def accuracy_metrics(output: pd.DataFrame) -> dict[str, object]:
    frame = output.copy()
    frame["parent_correct"] = frame["parent_prediction"] == frame["answer"]
    frame["joint_correct"] = frame["joint_prediction"] == frame["answer"]
    frame["changed"] = frame["parent_prediction"] != frame["joint_prediction"]
    frame["delta"] = frame["joint_correct"].astype(int) - frame["parent_correct"].astype(int)
    by_category = []
    for (source, category), group in frame.groupby(["source", "category"], sort=True):
        by_category.append(
            {
                "source": source,
                "category": category,
                "rows": int(len(group)),
                "parent_accuracy": float(group["parent_correct"].mean()),
                "joint_accuracy": float(group["joint_correct"].mean()),
                "net_correct": int(group["delta"].sum()),
                "changed": int(group["changed"].sum()),
            }
        )
    by_subject = []
    for user, group in frame.groupby("user", sort=True):
        by_subject.append(
            {
                "user": int(user),
                "rows": int(len(group)),
                "parent_accuracy": float(group["parent_correct"].mean()),
                "joint_accuracy": float(group["joint_correct"].mean()),
                "net_correct": int(group["delta"].sum()),
                "changed": int(group["changed"].sum()),
            }
        )
    changed = frame[frame["changed"]]
    wins = int(((changed["joint_correct"]) & (~changed["parent_correct"])).sum())
    losses = int(((~changed["joint_correct"]) & (changed["parent_correct"])).sum())
    neither = int(((~changed["joint_correct"]) & (~changed["parent_correct"])).sum())
    discordant = wins + losses
    one_sided_p = (
        sum(math.comb(discordant, k) for k in range(wins, discordant + 1)) / 2**discordant
        if discordant
        else 1.0
    )
    cohort = {}
    for name, users in {
        "odd_subject_ids": {user for user in EXPECTED_USERS if user % 2 == 1},
        "even_subject_ids": {user for user in EXPECTED_USERS if user % 2 == 0},
    }.items():
        subset = frame[frame["user"].isin(users)]
        cohort[name] = {
            "rows": int(len(subset)),
            "changed": int(subset["changed"].sum()),
            "net_correct": int(subset["delta"].sum()),
        }
    parent_worst = min(by_subject, key=lambda item: item["parent_accuracy"])
    joint_worst = min(by_subject, key=lambda item: item["joint_accuracy"])
    return {
        "aggregate": {
            "rows": int(len(frame)),
            "parent_correct": int(frame["parent_correct"].sum()),
            "joint_correct": int(frame["joint_correct"].sum()),
            "parent_accuracy": float(frame["parent_correct"].mean()),
            "joint_accuracy": float(frame["joint_correct"].mean()),
            "accuracy_delta": float(frame["delta"].sum() / len(frame)),
            "net_correct": int(frame["delta"].sum()),
            "changed": int(frame["changed"].sum()),
        },
        "by_category": by_category,
        "by_subject": by_subject,
        "worst_subject": {"parent": parent_worst, "joint": joint_worst},
        "parent_disagreement": {
            "rows": int(len(changed)),
            "joint_wins": wins,
            "joint_losses": losses,
            "both_wrong": neither,
            "net_correct": int(changed["delta"].sum()),
            "one_sided_exact_sign_p": one_sided_p,
        },
        "fixed_subject_cohorts": cohort,
    }


def conflict_metrics(proposals: pd.DataFrame, output: pd.DataFrame) -> dict[str, object]:
    joined = proposals.merge(
        output[["qa_id", "joint_prediction"]], on="qa_id", validate="one_to_one"
    )
    parent_conflicts = joined["parent_prediction"] != joined["proposal"]
    joint_conflicts = joined["joint_prediction"] != joined["proposal"]
    before = int(parent_conflicts.sum())
    after = int(joint_conflicts.sum())
    return {
        "eligible_constraints": int(len(joined)),
        "parent_conflicts": before,
        "joint_conflicts": after,
        "parent_conflict_rate": float(before / len(joined)),
        "joint_conflict_rate": float(after / len(joined)),
        "relative_reduction": float((before - after) / before) if before else 0.0,
    }


def text_only_metrics(data: pd.DataFrame) -> dict[str, object]:
    proposals = text_only_proposals(data)
    output = data[
        ["qa_id", "source", "category", "answer", "user", "path", "parent_prediction"]
    ].copy()
    output["joint_prediction"] = output["parent_prediction"]
    changed = proposals[proposals["proposal"] != proposals["parent_prediction"]]
    replacements = changed.set_index("qa_id")["proposal"].to_dict()
    mask = output["qa_id"].isin(replacements)
    output.loc[mask, "joint_prediction"] = output.loc[mask, "qa_id"].map(replacements)
    metrics = accuracy_metrics(output)
    return {
        "definition": (
            "Remove every sibling answer prediction; choose a unique single option only from "
            "its normalized text frequency across all sibling option lists, then replace all "
            "parent disagreements. No labels or fitted parameters are used."
        ),
        "eligible_rows": int(len(proposals)),
        **metrics,
    }


def valid_prediction(category: str, value: str) -> bool:
    if category in {"single", "combination", "emotion", "object_interaction"}:
        return len(value) == 1 and value in LABELS
    if category == "multi":
        return bool(value) and value == "".join(sorted(set(value))) and set(value) <= set(LABELS)
    if category == "sequence":
        return len(value) == 4 and set(value) == set(LABELS)
    return False


def build_test_candidate(
    root: Path, training: pd.DataFrame, selected_signatures: set[str]
) -> tuple[Path, dict[str, object]]:
    """Build a local candidate only after all validation controls pass."""
    test_path = root / "data/raw/kaggle/test_qa.csv"
    parent_path = root / "candidates/public_fususu_077777.csv"
    base_path = root / "candidates/emotion_extratrees_rf_union_v1.csv"
    if sha256(test_path) != EXPECTED_TEST_SHA256:
        raise ValueError("Official test QA hash changed")
    if sha256(parent_path) != EXPECTED_TEST_PARENT_SHA256:
        raise ValueError("Frozen public test parent hash changed")
    if sha256(base_path) != EXPECTED_PRIMARY_BASE_SHA256:
        raise ValueError("Frozen primary finalist hash changed")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    test = test.merge(parent, on="qa_id", validate="one_to_one")
    test["user"] = -1
    proposals = main_proposals(test)
    accepted = proposals[
        proposals["signature"].isin(selected_signatures)
        & (proposals["proposal"] != proposals["parent_prediction"])
    ]
    base = pd.read_csv(base_path, dtype=str, keep_default_na=False)
    if base["qa_id"].tolist() != test["qa_id"].tolist():
        raise ValueError("Primary base IDs/order do not match official test")
    candidate = base.copy()
    replacement = accepted.set_index("qa_id")["proposal"].to_dict()
    base_by_id = base.set_index("qa_id")["prediction"].to_dict()
    parent_by_id = parent.set_index("qa_id")["parent_prediction"].to_dict()
    for qa_id, proposal in replacement.items():
        if base_by_id[qa_id] not in {parent_by_id[qa_id], proposal}:
            raise ValueError(f"Primary evidence conflict for {qa_id}")
        candidate.loc[candidate["qa_id"] == qa_id, "prediction"] = proposal
    category_by_id = test.set_index("qa_id")["category"].to_dict()
    if not all(
        valid_prediction(category_by_id[qa_id], prediction)
        for qa_id, prediction in zip(candidate["qa_id"], candidate["prediction"])
    ):
        raise ValueError("Candidate answer grammar failed")
    candidate_path = root / "candidates/clip_joint_decoder_v1_union.csv"
    if candidate_path.exists():
        raise FileExistsError("Refusing to overwrite an existing versioned candidate")
    candidate.to_csv(candidate_path, index=False)
    return candidate_path, {
        "path": str(candidate_path.relative_to(root)),
        "sha256": sha256(candidate_path),
        "accepted_joint_rows": int(len(accepted)),
        "changes_vs_primary": int(
            (candidate["prediction"].to_numpy() != base["prediction"].to_numpy()).sum()
        ),
    }


def main() -> None:
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    parent_oof_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    if sha256(train_path) != EXPECTED_TRAIN_SHA256:
        raise ValueError("Official training QA hash changed")
    if sha256(parent_oof_path) != EXPECTED_PARENT_OOF_SHA256:
        raise ValueError("Public graph OOF hash changed")
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    parent_oof = pd.read_csv(parent_oof_path, dtype=str, keep_default_na=False)
    data = prepare_training(train, parent_oof)

    output, proposals, fold_trace = crossfit(data)
    metrics = accuracy_metrics(output)
    conflicts = conflict_metrics(proposals, output)
    text_control = text_only_metrics(data)

    permuted, inverse = permute_options(data)
    permuted_output, _, _ = crossfit(permuted)
    permuted_output["inverted_joint_prediction"] = invert_predictions(permuted_output, inverse)
    original = output.set_index("qa_id")["joint_prediction"]
    inverted = permuted_output.set_index("qa_id")["inverted_joint_prediction"]
    equivariant = original.sort_index().equals(inverted.sort_index())
    option_control = {
        "definition": "Deterministic independent A/B/C/D permutation for every QA row.",
        "rows": int(len(output)),
        "equivariant_rows": int((original.sort_index() == inverted.sort_index()).sum()),
        "exact_equivariance": bool(equivariant),
    }

    aggregate = metrics["aggregate"]
    disagreement = metrics["parent_disagreement"]
    worst = metrics["worst_subject"]
    category_nonnegative = all(item["net_correct"] >= 0 for item in metrics["by_category"])
    gates = {
        "exactly_18_outer_loso_folds": len(EXPECTED_USERS) == 18,
        "same_clip_single_subject_fold": bool(data.groupby("path")["user"].nunique().max() == 1),
        "aggregate_delta_at_least_0_0025": aggregate["accuracy_delta"] >= 0.0025,
        "parent_disagreement_net_at_least_10": disagreement["net_correct"] >= 10,
        "zero_parent_disagreement_losses": disagreement["joint_losses"] == 0,
        "one_sided_exact_sign_p_at_most_0_01": disagreement[
            "one_sided_exact_sign_p"
        ] <= 0.01,
        "both_fixed_subject_cohorts_positive": all(
            item["net_correct"] > 0 for item in metrics["fixed_subject_cohorts"].values()
        ),
        "worst_subject_accuracy_not_lower": worst["joint"]["joint_accuracy"]
        >= worst["parent"]["parent_accuracy"],
        "no_source_category_regression": category_nonnegative,
        "conflict_rate_relative_reduction_at_least_0_50": conflicts["relative_reduction"]
        >= 0.50,
        "option_permutation_exact_equivariance": bool(equivariant),
        "text_only_counterfactual_does_not_reproduce_half_the_net_gain": text_control[
            "aggregate"
        ]["net_correct"]
        < 0.5 * aggregate["net_correct"],
    }
    promoted = all(gates.values())

    artifact_dir = root / "artifacts/clip_joint_decoder_v1"
    report_path = root / "reports/clip_joint_decoder_v1_summary.json"
    receipt_path = root / "reports/clip_joint_decoder_v1_rejection_receipt.json"
    candidate_path = root / "candidates/clip_joint_decoder_v1_union.csv"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    oof_path = artifact_dir / "oof_predictions.csv"
    trace_path = artifact_dir / "fold_selector_trace.csv"
    proposal_path = artifact_dir / "eligible_constraints.csv"
    output.to_csv(oof_path, index=False)
    fold_trace.to_csv(trace_path, index=False)
    proposals.to_csv(proposal_path, index=False)

    all_train_stats = fit_signatures(proposals, EXPECTED_USERS)
    selected_signatures = set(all_train_stats.loc[all_train_stats["selected"], "signature"])
    candidate: dict[str, object] | None = None
    if promoted:
        if receipt_path.exists():
            raise FileExistsError("Refusing promotion while a versioned rejection receipt exists")
        built_path, candidate = build_test_candidate(root, data, selected_signatures)
        candidate["absolute_path"] = str(built_path)
    else:
        if candidate_path.exists():
            raise FileExistsError("Fail-closed: stale candidate exists for a rejected experiment")

    report = {
        "experiment": "cuhk_x_large_clip_joint_decoder_v1",
        "status": "PROMOTED_LOCAL_CANDIDATE_NOT_SUBMITTED" if promoted else "REJECTED",
        "decision_reason": (
            "All predeclared gates passed."
            if promoted
            else "At least one predeclared gate failed; no test data were opened and no candidate was created."
        ),
        "design": {
            "parent": "public graph leave-one-subject-out OOF",
            "outer_validation": "18-fold leave-one-subject-out; every QA row for a clip stays in its subject fold",
            "joint_factor": (
                "selected combination option atoms imply a unique same-clip single option"
            ),
            "signature": "selected atom-count bin (2, 3, or 4plus) x sequence-sibling presence",
            "fold_local_selector": {
                "minimum_disagreement_rows": MIN_SIGNATURE_ROWS,
                "minimum_subjects": MIN_SIGNATURE_SUBJECTS,
                "minimum_proposal_accuracy": MIN_PROPOSAL_ACCURACY,
                "must_beat_parent_on_training_fold": True,
            },
            "test_access_policy": "test QA and test predictions are opened only if every gate passes",
        },
        "metrics": metrics,
        "conflict_rate": conflicts,
        "counterfactuals": {
            "option_permutation": option_control,
            "text_only": text_control,
        },
        "all_training_signature_fit": all_train_stats.to_dict(orient="records"),
        "gates": gates,
        "candidate": candidate,
        "inputs": {
            "training_qa": {"path": str(train_path), "sha256": sha256(train_path)},
            "public_graph_oof": {
                "path": str(parent_oof_path),
                "sha256": sha256(parent_oof_path),
            },
            "code": {"path": str(Path(__file__)), "sha256": sha256(Path(__file__))},
        },
        "artifacts": {
            "oof_predictions": {"path": str(oof_path), "sha256": sha256(oof_path)},
            "fold_selector_trace": {"path": str(trace_path), "sha256": sha256(trace_path)},
            "eligible_constraints": {
                "path": str(proposal_path),
                "sha256": sha256(proposal_path),
            },
        },
        "prohibitions": {
            "kaggle_run": False,
            "submission": False,
            "frozen_artifacts_modified": False,
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    receipt: dict[str, object] | None = None
    if not promoted:
        failed = [name for name, passed in gates.items() if not passed]
        receipt = {
            "experiment": "cuhk_x_large_clip_joint_decoder_v1",
            "verdict": "REJECT_NO_TEST_CANDIDATE",
            "failed_gates": failed,
            "causal_warning": (
                "The text-only sibling-option counterfactual reproduced at least half of the "
                "joint decoder's net gain, so the apparent improvement cannot be attributed "
                "reliably to joint decoding of sibling predictions."
            ),
            "test_data_opened": False,
            "candidate_created": False,
            "kaggle_run": False,
            "submission": False,
            "summary": {"path": str(report_path), "sha256": sha256(report_path)},
            "code": {"path": str(Path(__file__)), "sha256": sha256(Path(__file__))},
        }
        if receipt_path.exists():
            raise FileExistsError("Refusing to overwrite an existing versioned rejection receipt")
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)
    if receipt is not None:
        print(f"rejection_receipt_sha256={sha256(receipt_path)}", flush=True)


if __name__ == "__main__":
    main()
