#!/usr/bin/env python3
"""Build a gated HAU single candidate from linked-question structure and sensors.

The structural expert maps the compact-graph prediction for a clip's
``combination`` question to the unique ``single`` option contained in that
predicted action set.  Its source prediction is subject-disjoint OOF on
training data and the frozen public prediction on test data.  A deployment
override additionally requires agreement with the independent sensor expert.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path, PurePosixPath

import pandas as pd


EXPECTED_USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]
PARENT_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"
BASE_SHA256 = "e54652a8746fca7d434a6a4bd162458448e709ff224b074ca37a0f538dec5463"
MODALITIES = {"depth", "depth_color", "ir", "thermal", "imu", "skeleton", "radar"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def clip_key(value: str) -> str:
    parts = list(PurePosixPath(str(value).replace("\\", "/")).parts)
    if (
        len(parts) >= 2
        and parts[-2].lower() in MODALITIES
        and Path(parts[-1]).stem.lower() in MODALITIES
    ):
        parts = parts[:-2]
    return "/".join(parts)


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def atoms(value: str) -> frozenset[str]:
    return frozenset(norm(piece) for piece in str(value).split(",") if piece.strip())


def derive(frame: pd.DataFrame, source_prediction_column: str) -> pd.DataFrame:
    data = frame.copy()
    data["clip_key"] = data["path"].map(clip_key)
    output: list[dict[str, object]] = []
    for clip, group in data[data["source"] == "HAU"].groupby("clip_key"):
        combination = group[group["category"] == "combination"]
        single = group[group["category"] == "single"]
        if len(combination) != 1 or len(single) != 1:
            continue
        source = combination.iloc[0]
        target = single.iloc[0]
        source_prediction = str(source[source_prediction_column])
        present = (
            atoms(source[source_prediction])
            if len(source_prediction) == 1 and source_prediction in "ABCD"
            else frozenset()
        )
        matches = [
            label
            for label in "ABCD"
            if atoms(target[label]) and atoms(target[label]).issubset(present)
        ]
        subject_match = re.search(r"(?:^|/)user(\d+)(?:/|$)", str(target["path"]))
        output.append(
            {
                "clip_key": clip,
                "source_qa_id": source["qa_id"],
                "target_qa_id": target["qa_id"],
                "source_prediction": source_prediction,
                "source_action_set": ", ".join(sorted(present)),
                "structural_prediction": matches[0] if len(matches) == 1 else "",
                "unique": len(matches) == 1,
                "target_parent_prediction": target.get("parent_prediction", ""),
                "answer": target.get("answer", ""),
                "user": int(subject_match.group(1)) if subject_match else None,
            }
        )
    return pd.DataFrame(output)


def accuracy_summary(frame: pd.DataFrame) -> dict[str, object]:
    chosen = frame.copy()
    chosen["correct"] = chosen["structural_prediction"] == chosen["answer"]
    by_user = chosen.groupby("user")["correct"].mean()
    return {
        "rows": int(len(chosen)),
        "correct": int(chosen["correct"].sum()),
        "accuracy": float(chosen["correct"].mean()),
        "subjects": int(chosen["user"].nunique()),
        "worst_subject_accuracy": float(by_user.min()),
    }


def disagreement_summary(frame: pd.DataFrame) -> dict[str, object]:
    chosen = frame.copy()
    chosen["expert_correct"] = chosen["structural_prediction"] == chosen["answer"]
    chosen["parent_correct"] = chosen["target_parent_prediction"] == chosen["answer"]
    chosen["delta"] = chosen["expert_correct"].astype(int) - chosen["parent_correct"].astype(int)
    by_user = chosen.groupby("user")["delta"].sum()
    wins = int(((chosen["expert_correct"]) & (~chosen["parent_correct"])).sum())
    losses = int(((~chosen["expert_correct"]) & (chosen["parent_correct"])).sum())
    discordant = wins + losses
    one_sided_p = (
        sum(math.comb(discordant, k) for k in range(wins, discordant + 1)) / (2**discordant)
        if discordant
        else 1.0
    )
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
        "one_sided_exact_sign_p": one_sided_p,
    }


def main() -> None:
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    graph_oof_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    sensor_oof_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    sensor_test_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    parent_path = root / "candidates/public_fususu_077777.csv"
    base_path = root / "candidates/visual_sensor_consensus_v1.csv"
    output_path = root / "candidates/hau_linked_single_consensus_v1.csv"
    report_path = root / "reports/hau_linked_single_consensus_v1_candidate.json"

    if sha256(parent_path) != PARENT_SHA256 or sha256(base_path) != BASE_SHA256:
        raise ValueError("Frozen parent or submitted base hash mismatch")
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    graph_oof = pd.read_csv(graph_oof_path, dtype=str, keep_default_na=False)
    if len(graph_oof) != len(train) or graph_oof["qa_id"].duplicated().any():
        raise ValueError("Public graph OOF invariant failed")
    train = train.merge(
        graph_oof[["qa_id", "prediction"]].rename(columns={"prediction": "parent_prediction"}),
        on="qa_id",
        validate="one_to_one",
    )
    if sorted(train["path"].str.extract(r"user(\d+)")[0].astype(int).unique()) != EXPECTED_USERS:
        raise ValueError("Unexpected training subjects")
    oof_combination_predictions = train.loc[
        (train["source"] == "HAU") & (train["category"] == "combination"),
        "parent_prediction",
    ]
    oof_single_predictions = train.loc[
        (train["source"] == "HAU") & (train["category"] == "single"),
        "parent_prediction",
    ]
    if not (
        oof_combination_predictions.str.fullmatch(r"[ABCD]").all()
        and oof_single_predictions.str.fullmatch(r"[ABCD]").all()
    ):
        raise ValueError("OOF source/target prediction structure mismatch")

    oracle = derive(train, "answer")
    oracle_unique = oracle[oracle["unique"]].copy()
    oracle_metrics = accuracy_summary(oracle_unique)
    if not (
        oracle_metrics["rows"] >= 600
        and oracle_metrics["accuracy"] == 1.0
        and oracle_metrics["subjects"] == 18
        and oracle_metrics["worst_subject_accuracy"] == 1.0
    ):
        raise ValueError(f"Logical upper-bound gate failed: {oracle_metrics}")

    deployed = derive(train, "parent_prediction")
    deployed_unique = deployed[deployed["unique"]].copy()
    deployed_metrics = accuracy_summary(deployed_unique)
    structural_disagreement = deployed_unique[
        deployed_unique["structural_prediction"] != deployed_unique["target_parent_prediction"]
    ].copy()
    structural_disagreement_metrics = disagreement_summary(structural_disagreement)

    sensor_oof = pd.read_csv(sensor_oof_path, dtype=str, keep_default_na=False)
    sensor_oof = sensor_oof[
        (sensor_oof["source"] == "HAU") & (sensor_oof["category"] == "single")
    ][["qa_id", "prediction", "confidence"]].rename(
        columns={
            "qa_id": "target_qa_id",
            "prediction": "sensor_prediction",
            "confidence": "sensor_confidence",
        }
    )
    consensus_frame = structural_disagreement.merge(
        sensor_oof, on="target_qa_id", validate="one_to_one"
    )
    consensus = consensus_frame[
        consensus_frame["structural_prediction"] == consensus_frame["sensor_prediction"]
    ].copy()
    consensus_metrics = disagreement_summary(consensus)
    cohort_metrics = {
        "odd_subject_ids": disagreement_summary(consensus[consensus["user"] % 2 == 1]),
        "even_subject_ids": disagreement_summary(consensus[consensus["user"] % 2 == 0]),
    }
    if not (
        consensus_metrics["rows"] >= 8
        and consensus_metrics["expert_accuracy"] >= 0.95
        and consensus_metrics["net_correct_vs_parent"] > 0
        and consensus_metrics["worst_subject_net"] > 0
        and consensus_metrics["one_sided_exact_sign_p"] <= 0.01
        and all(
            metrics["rows"] >= 3
            and metrics["expert_accuracy"] >= 0.95
            and metrics["net_correct_vs_parent"] > 0
            for metrics in cohort_metrics.values()
        )
    ):
        raise ValueError(
            f"Deployment consensus gate failed: overall={consensus_metrics}, cohorts={cohort_metrics}"
        )

    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    test_with_parent = test.drop(columns=["prediction"]).merge(
        parent, on="qa_id", validate="one_to_one"
    )
    test_combination_predictions = test_with_parent.loc[
        (test_with_parent["source"] == "HAU")
        & (test_with_parent["category"] == "combination"),
        "parent_prediction",
    ]
    test_single_predictions = test_with_parent.loc[
        (test_with_parent["source"] == "HAU") & (test_with_parent["category"] == "single"),
        "parent_prediction",
    ]
    if not (
        test_combination_predictions.str.fullmatch(r"[ABCD]").all()
        and test_single_predictions.str.fullmatch(r"[ABCD]").all()
    ):
        raise ValueError("Frozen test source/target prediction structure mismatch")
    test_structural = derive(test_with_parent, "parent_prediction")
    test_unique = test_structural[test_structural["unique"]].copy()
    sensor_test = pd.read_csv(sensor_test_path, dtype=str, keep_default_na=False)
    sensor_test = sensor_test[
        (sensor_test["source"] == "HAU") & (sensor_test["category"] == "single")
    ][["qa_id", "prediction", "confidence", "sensor_present"]].rename(
        columns={
            "qa_id": "target_qa_id",
            "prediction": "sensor_prediction",
            "confidence": "sensor_confidence",
        }
    )
    test_gate = test_unique.merge(sensor_test, on="target_qa_id", validate="one_to_one")
    test_gate["sensor_present_bool"] = test_gate["sensor_present"].str.lower().eq("true")
    test_gate["differs_parent"] = (
        test_gate["structural_prediction"] != test_gate["target_parent_prediction"]
    )
    test_gate["sensor_consensus"] = test_gate["sensor_present_bool"] & (
        test_gate["structural_prediction"] == test_gate["sensor_prediction"]
    )
    test_gate["accepted"] = test_gate["differs_parent"] & test_gate["sensor_consensus"]
    overrides = test_gate[test_gate["accepted"]].copy()
    if overrides.empty:
        raise ValueError("Validated gate produced no test override")

    base = pd.read_csv(base_path, dtype=str, keep_default_na=False)
    if list(base.columns) != ["qa_id", "prediction"] or base["qa_id"].tolist() != test["qa_id"].tolist():
        raise ValueError("Submitted base schema/order mismatch")
    candidate = base.copy()
    base_map = base.set_index("qa_id")["prediction"].to_dict()
    for _, row in overrides.iterrows():
        current = base_map[row["target_qa_id"]]
        if current not in {row["target_parent_prediction"], row["structural_prediction"]}:
            raise ValueError(f"Independent base conflict at {row['target_qa_id']}")
        candidate.loc[candidate["qa_id"] == row["target_qa_id"], "prediction"] = row[
            "structural_prediction"
        ]
    category = test.set_index("qa_id")["category"]
    def valid_prediction(qa_id: str, prediction: str) -> bool:
        kind = category[qa_id]
        if kind in {"single", "combination", "emotion", "object_interaction"}:
            return len(prediction) == 1 and prediction in "ABCD"
        if kind == "multi":
            return bool(prediction) and prediction == "".join(sorted(set(prediction)))
        if kind == "sequence":
            return len(prediction) == 4 and set(prediction) == set("ABCD")
        return False

    if not all(
        valid_prediction(qa_id, prediction)
        for qa_id, prediction in zip(candidate["qa_id"], candidate["prediction"])
    ):
        raise ValueError("Candidate grammar invalid")
    if len(candidate) != 682 or candidate["qa_id"].duplicated().any():
        raise ValueError("Candidate row/ID invariant failed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    candidate.to_csv(output_path, index=False)

    comparison = base.rename(columns={"prediction": "base_prediction"}).merge(
        candidate.rename(columns={"prediction": "candidate_prediction"}),
        on="qa_id",
        validate="one_to_one",
    )
    new_rows = comparison[comparison["base_prediction"] != comparison["candidate_prediction"]]
    if len(new_rows) != len(overrides):
        raise ValueError("Candidate delta does not match accepted evidence")
    evidence_columns = [
        "source_qa_id",
        "target_qa_id",
        "source_prediction",
        "source_action_set",
        "target_parent_prediction",
        "structural_prediction",
        "sensor_prediction",
        "sensor_confidence",
        "sensor_present_bool",
        "differs_parent",
        "sensor_consensus",
        "accepted",
    ]
    report = {
        "experiment": "hau_linked_combination_to_single_sensor_consensus_v1",
        "rule": (
            "Use the compact-graph combination prediction as an action set; infer the unique "
            "single option contained in that set; override only when a real independent sensor "
            "prediction agrees and both differ from the frozen parent single answer"
        ),
        "validation": {
            "design": (
                "18-fold leave-one-subject-out graph and sensor predictions; clips intact; "
                "logical mapper has no fitted parameters"
            ),
            "oracle_source_answer_upper_bound": oracle_metrics,
            "oof_structural_unique": deployed_metrics,
            "oof_structural_parent_disagreements": structural_disagreement_metrics,
            "oof_sensor_consensus_parent_disagreements": consensus_metrics,
            "fixed_odd_even_subject_cohorts": cohort_metrics,
            "gate": (
                "at least 8 selected rows; expert accuracy >=0.95; positive net and positive "
                "worst represented-subject net; one-sided exact sign p<=0.01; fixed odd/even "
                "subject cohorts each have at least 3 rows, accuracy >=0.95, and positive net"
            ),
            "accepted_evidence": consensus[
                [
                    "source_qa_id", "target_qa_id", "user", "source_prediction",
                    "source_action_set", "target_parent_prediction", "structural_prediction",
                    "sensor_prediction", "sensor_confidence", "answer",
                ]
            ].to_dict(orient="records"),
        },
        "test": {
            "linked_clips": int(len(test_structural)),
            "unique_structural_rows": int(len(test_unique)),
            "structural_parent_disagreements": int(test_gate["differs_parent"].sum()),
            "accepted_rows": int(len(overrides)),
            "accepted_evidence": overrides[evidence_columns].to_dict(orient="records"),
        },
        "prediction_structure_transport": {
            "oof_combination_one_letter": int(
                oof_combination_predictions.str.fullmatch(r"[ABCD]").sum()
            ),
            "oof_combination_rows": int(len(oof_combination_predictions)),
            "oof_single_one_letter": int(oof_single_predictions.str.fullmatch(r"[ABCD]").sum()),
            "oof_single_rows": int(len(oof_single_predictions)),
            "test_combination_one_letter": int(
                test_combination_predictions.str.fullmatch(r"[ABCD]").sum()
            ),
            "test_combination_rows": int(len(test_combination_predictions)),
            "test_single_one_letter": int(test_single_predictions.str.fullmatch(r"[ABCD]").sum()),
            "test_single_rows": int(len(test_single_predictions)),
        },
        "candidate": output_path.name,
        "candidate_sha256": sha256(output_path),
        "base_submission_ref": 56116980,
        "base_sha256": sha256(base_path),
        "new_rows_changed_vs_base": int(len(new_rows)),
        "new_rows": new_rows.to_dict(orient="records"),
        "inputs": {
            "training_qa_sha256": sha256(train_path),
            "test_qa_sha256": sha256(test_path),
            "public_graph_oof_sha256": sha256(graph_oof_path),
            "sensor_oof_sha256": sha256(sensor_oof_path),
            "sensor_test_sha256": sha256(sensor_test_path),
            "frozen_parent_sha256": sha256(parent_path),
            "submitted_base_sha256": sha256(base_path),
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
