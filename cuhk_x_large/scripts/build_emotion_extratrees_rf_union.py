#!/usr/bin/env python3
"""Add validation-qualified HAU emotion ExtraTrees/RF consensus to the best base."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path

import pandas as pd


BASE_SHA256 = "cec3cde9c7b207c4e202a2623f88213bedccedebc108dd2afcb00782bb101106"
PARENT_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def exact_sign_p(wins: int, losses: int) -> float:
    discordant = wins + losses
    if not discordant:
        return 1.0
    return sum(math.comb(discordant, k) for k in range(wins, discordant + 1)) / (
        2**discordant
    )


def metrics(frame: pd.DataFrame) -> dict[str, object]:
    chosen = frame.copy()
    chosen["expert_correct"] = chosen["et_prediction"] == chosen["answer"]
    chosen["parent_correct"] = chosen["parent_prediction"] == chosen["answer"]
    chosen["delta"] = chosen["expert_correct"].astype(int) - chosen["parent_correct"].astype(int)
    by_user = chosen.groupby("user")["delta"].sum()
    wins = int((chosen["expert_correct"] & ~chosen["parent_correct"]).sum())
    losses = int((~chosen["expert_correct"] & chosen["parent_correct"]).sum())
    return {
        "rows": int(len(chosen)),
        "expert_correct": int(chosen["expert_correct"].sum()),
        "expert_accuracy": float(chosen["expert_correct"].mean()),
        "parent_correct": int(chosen["parent_correct"].sum()),
        "parent_accuracy": float(chosen["parent_correct"].mean()),
        "net_correct_vs_parent": int(chosen["delta"].sum()),
        "subjects": int(chosen["user"].nunique()),
        "worst_subject_net": int(by_user.min()),
        "by_user_net": {str(int(user)): int(value) for user, value in by_user.items()},
        "discordant_wins": wins,
        "discordant_losses": losses,
        "one_sided_exact_sign_p": exact_sign_p(wins, losses),
    }


def valid_prediction(prediction: str, category: str) -> bool:
    if category in {"single", "combination", "emotion", "object_interaction"}:
        return len(prediction) == 1 and prediction in "ABCD"
    if category == "multi":
        return bool(prediction) and prediction == "".join(sorted(set(prediction)))
    if category == "sequence":
        return len(prediction) == 4 and set(prediction) == set("ABCD")
    return False


def main() -> None:
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    parent_path = root / "candidates/public_fususu_077777.csv"
    graph_test_path = root / "artifacts/predictions/public_graph_test.csv"
    base_path = root / "candidates/hau_linked_single_consensus_v1.csv"
    et_oof_path = root / "artifacts/oof/emotion_pairwise_extratrees_oof.csv"
    et_test_path = root / "artifacts/predictions/emotion_pairwise_extratrees_test.csv"
    et_summary_path = root / "reports/emotion_pairwise_extratrees_summary.json"
    rf_oof_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    rf_test_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    output_path = root / "candidates/emotion_extratrees_rf_union_v1.csv"
    report_path = root / "reports/emotion_extratrees_rf_union_v1_candidate.json"

    if sha256(base_path) != BASE_SHA256 or sha256(parent_path) != PARENT_SHA256:
        raise ValueError("Frozen base or parent hash mismatch")
    et_summary = json.loads(et_summary_path.read_text(encoding="utf-8"))
    if et_summary["model"] != {
        "type": "fold-local median imputation + ExtraTreesClassifier",
        "n_estimators": 500,
        "max_features": "sqrt",
        "min_samples_leaf": 2,
        "class_weight": "balanced",
    }:
        raise ValueError("Unexpected ExtraTrees model configuration")

    et_oof = pd.read_csv(et_oof_path, dtype=str, keep_default_na=False).rename(
        columns={
            "prediction": "et_prediction",
            "confidence": "et_confidence",
            "sensor_present": "et_present",
        }
    )
    et_oof["et_present"] = et_oof["et_present"].str.lower().eq("true")
    rf_oof = pd.read_csv(rf_oof_path, dtype=str, keep_default_na=False)
    rf_oof = rf_oof[(rf_oof["source"] == "HAU") & (rf_oof["category"] == "emotion")][
        ["qa_id", "prediction", "confidence"]
    ].rename(columns={"prediction": "rf_prediction", "confidence": "rf_confidence"})
    validation = et_oof.merge(rf_oof, on="qa_id", validate="one_to_one")
    selected = validation[
        validation["et_present"]
        & (validation["et_prediction"] == validation["rf_prediction"])
        & (validation["et_prediction"] != validation["parent_prediction"])
    ].copy()
    overall_metrics = metrics(selected)
    cohort_metrics = {
        "odd_subject_ids": metrics(selected[selected["user"].astype(int) % 2 == 1]),
        "even_subject_ids": metrics(selected[selected["user"].astype(int) % 2 == 0]),
    }
    if not (
        overall_metrics["rows"] >= 100
        and overall_metrics["expert_accuracy"] >= 0.60
        and overall_metrics["net_correct_vs_parent"] > 0
        and overall_metrics["subjects"] == 18
        and overall_metrics["worst_subject_net"] > 0
        and overall_metrics["one_sided_exact_sign_p"] <= 1e-8
        and all(
            value["rows"] >= 40
            and value["net_correct_vs_parent"] > 0
            and value["worst_subject_net"] > 0
            for value in cohort_metrics.values()
        )
    ):
        raise ValueError(
            f"ExtraTrees/RF consensus validation gate failed: {overall_metrics}, {cohort_metrics}"
        )

    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    graph = pd.read_csv(graph_test_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "graph_prediction"}
    )
    et_test = pd.read_csv(et_test_path, dtype=str, keep_default_na=False)[
        ["qa_id", "prediction", "confidence", "sensor_present"]
    ].rename(
        columns={
            "prediction": "et_prediction",
            "confidence": "et_confidence",
            "sensor_present": "et_present",
        }
    )
    et_test["et_present"] = et_test["et_present"].str.lower().eq("true")
    rf_test = pd.read_csv(rf_test_path, dtype=str, keep_default_na=False)
    rf_test = rf_test[(rf_test["source"] == "HAU") & (rf_test["category"] == "emotion")][
        ["qa_id", "prediction", "confidence", "sensor_present"]
    ].rename(
        columns={
            "prediction": "rf_prediction",
            "confidence": "rf_confidence",
            "sensor_present": "rf_present",
        }
    )
    rf_test["rf_present"] = rf_test["rf_present"].str.lower().eq("true")
    test_gate = (
        et_test.merge(rf_test, on="qa_id", validate="one_to_one")
        .merge(parent, on="qa_id", validate="one_to_one")
        .merge(graph, on="qa_id", validate="one_to_one")
    )
    test_gate["accepted"] = (
        test_gate["et_present"]
        & test_gate["rf_present"]
        & (test_gate["et_prediction"] == test_gate["rf_prediction"])
        & (test_gate["et_prediction"] != test_gate["parent_prediction"])
        & (test_gate["et_prediction"] != test_gate["graph_prediction"])
    )
    overrides = test_gate[test_gate["accepted"]].copy()
    if overrides.empty:
        raise ValueError("Validated test gate produced no overrides")

    base = pd.read_csv(base_path, dtype=str, keep_default_na=False)
    if list(base.columns) != ["qa_id", "prediction"] or base["qa_id"].tolist() != test["qa_id"].tolist():
        raise ValueError("Base schema/order mismatch")
    base_map = base.set_index("qa_id")["prediction"].to_dict()
    conflicts = overrides[
        ~overrides.apply(
            lambda row: base_map[row["qa_id"]]
            in {row["parent_prediction"], row["et_prediction"]},
            axis=1,
        )
    ]
    if len(conflicts):
        raise ValueError(f"Independent base conflicts: {conflicts['qa_id'].tolist()}")
    candidate = base.copy()
    for _, row in overrides.iterrows():
        candidate.loc[candidate["qa_id"] == row["qa_id"], "prediction"] = row[
            "et_prediction"
        ]
    if len(candidate) != 682 or candidate["qa_id"].duplicated().any():
        raise ValueError("Candidate row/ID invariant failed")
    if not all(
        valid_prediction(prediction, category)
        for prediction, category in zip(candidate["prediction"], test["category"])
    ):
        raise ValueError("Candidate grammar invalid")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(output_path, index=False)

    comparison = base.rename(columns={"prediction": "base_prediction"}).merge(
        candidate.rename(columns={"prediction": "candidate_prediction"}),
        on="qa_id",
        validate="one_to_one",
    )
    new_rows = comparison[comparison["base_prediction"] != comparison["candidate_prediction"]]
    accepted_new_ids = {
        row["qa_id"]
        for _, row in overrides.iterrows()
        if base_map[row["qa_id"]] != row["et_prediction"]
    }
    if set(new_rows["qa_id"]) != accepted_new_ids or not new_rows.size:
        raise ValueError("Candidate delta does not match new accepted evidence")
    evidence_columns = [
        "qa_id", "parent_prediction", "graph_prediction", "et_prediction", "et_confidence",
        "rf_prediction", "rf_confidence", "et_present", "rf_present", "accepted",
    ]
    report = {
        "experiment": "hau_emotion_extratrees_rf_consensus_union_v1",
        "validation": {
            "design": (
                "18-fold leave-one-subject-out; fold-local median imputation; clips intact; "
                "fixed ExtraTrees and RandomForest agreement"
            ),
            "gate": (
                "real ExtraTrees sensor input; ExtraTrees=RF; differs OOF graph parent; >=100 rows; "
                "accuracy >=0.60; all 18 subjects and every represented subject net positive; "
                "one-sided sign p<=1e-8; fixed odd/even cohorts each >=40 rows and positive"
            ),
            "overall": overall_metrics,
            "fixed_odd_even_subject_cohorts": cohort_metrics,
        },
        "test": {
            "gate": (
                "real ET and RF inputs; ET=RF; differs frozen public parent and separately "
                "reproduced public compact graph"
            ),
            "accepted_rows": int(len(overrides)),
            "accepted_evidence": overrides[evidence_columns].to_dict(orient="records"),
        },
        "candidate": output_path.name,
        "candidate_sha256": sha256(output_path),
        "base_submission_ref": 56122175,
        "base_sha256": sha256(base_path),
        "new_rows_changed_vs_base": int(len(new_rows)),
        "new_rows": new_rows.to_dict(orient="records"),
        "inputs": {
            "training_qa_sha256": sha256(train_path),
            "test_qa_sha256": sha256(test_path),
            "parent_sha256": sha256(parent_path),
            "graph_test_sha256": sha256(graph_test_path),
            "base_sha256": sha256(base_path),
            "et_oof_sha256": sha256(et_oof_path),
            "et_test_sha256": sha256(et_test_path),
            "et_summary_sha256": sha256(et_summary_path),
            "rf_oof_sha256": sha256(rf_oof_path),
            "rf_test_sha256": sha256(rf_test_path),
            "code_sha256": sha256(Path(__file__)),
        },
        "seed": 20260909,
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
