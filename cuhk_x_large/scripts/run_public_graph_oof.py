#!/usr/bin/env python3
"""Run leave-one-subject-out OOF for the public Fususu clip-graph decoder.

The decoder source is loaded from the downloaded Apache-2.0 Kaggle notebook only
after its SHA-256 is verified. OOF predictions and labels stay under the ignored
``artifacts/`` directory; only aggregate metrics are written to ``reports/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import pandas as pd


EXPECTED_NOTEBOOK_SHA256 = "38811edf7312f8c5ff5af73278568092de762a85885f22dce0fbb5af595fea15"
EXPECTED_USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_user(path: str) -> int:
    match = re.search(r"(?:^|/)user(\d+)(?:/|$)", path, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"No subject ID in path: {path!r}")
    return int(match.group(1))


def load_public_decoder(notebook_path: Path):
    assert sha256(notebook_path) == EXPECTED_NOTEBOOK_SHA256, "Public notebook hash changed"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    matches = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if "class ClipGraphDecoder" in source:
            matches.append(source)
    assert len(matches) == 1, f"Expected one decoder cell, found {len(matches)}"
    decoder_source = matches[0].split("graph_decoder =", 1)[0]
    namespace = {"pd": pd, "Path": Path}
    exec(compile(decoder_source, str(notebook_path), "exec"), namespace)
    return namespace["ClipGraphDecoder"], namespace["clip_key"]


def main() -> None:
    campaign_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--train", type=Path, default=campaign_root / "data/raw/kaggle/training_qa.csv"
    )
    parser.add_argument(
        "--notebook",
        type=Path,
        default=campaign_root
        / "public_baselines/phuongncn_lb_0_77777/lb-0-77777-exact-submission-research-handoff.ipynb",
    )
    parser.add_argument(
        "--oof-output",
        type=Path,
        default=campaign_root / "artifacts/oof/public_graph_leave_one_subject_out.csv",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=campaign_root / "reports/public_graph_oof_summary.json",
    )
    args = parser.parse_args()

    started = time.perf_counter()
    decoder_type, clip_key = load_public_decoder(args.notebook)
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    train["user"] = train["path"].map(extract_user)
    assert sorted(train["user"].unique().tolist()) == EXPECTED_USERS
    train["clip_key"] = train["path"].map(clip_key)
    assert train.groupby("clip_key")["user"].nunique().max() == 1, "A clip crosses subjects"

    fold_outputs = []
    for held_user in EXPECTED_USERS:
        fit = train.loc[train["user"] != held_user].drop(columns=["user", "clip_key"])
        validation = train.loc[train["user"] == held_user].drop(columns=["user", "clip_key"])
        predictions = decoder_type().fit(fit).predict(validation)
        fold = validation[["qa_id", "source", "category", "answer"]].merge(
            predictions, on="qa_id", how="left", validate="one_to_one"
        )
        assert fold["prediction"].notna().all()
        fold["user"] = held_user
        fold["correct"] = fold["prediction"] == fold["answer"]
        fold_outputs.append(fold)

    oof = pd.concat(fold_outputs, ignore_index=True)
    assert len(oof) == len(train)
    assert oof["qa_id"].is_unique
    by_user = (
        oof.groupby("user")["correct"]
        .agg(rows="size", accuracy="mean")
        .reset_index()
        .to_dict(orient="records")
    )
    by_slice = (
        oof.groupby(["source", "category"])["correct"]
        .agg(rows="size", accuracy="mean")
        .reset_index()
        .to_dict(orient="records")
    )
    runtime = time.perf_counter() - started
    summary = {
        "experiment": "public_fususu_compact_graph_leave_one_subject_out",
        "source_notebook_sha256": EXPECTED_NOTEBOOK_SHA256,
        "data_sha256": sha256(args.train),
        "rows": int(len(oof)),
        "subjects": EXPECTED_USERS,
        "folds": len(EXPECTED_USERS),
        "clip_grouping_enforced": True,
        "overall_accuracy": float(oof["correct"].mean()),
        "worst_subject_accuracy": float(min(item["accuracy"] for item in by_user)),
        "best_subject_accuracy": float(max(item["accuracy"] for item in by_user)),
        "runtime_seconds": runtime,
        "by_user": by_user,
        "by_source_category": by_slice,
    }

    args.oof_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    oof.to_csv(args.oof_output, index=False)
    args.summary_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

