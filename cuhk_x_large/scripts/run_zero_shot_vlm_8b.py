#!/usr/bin/env python3
"""Deterministic 8B zero-shot validation on the frozen recovered HARn videos."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

import mlx.core as mx
import pandas as pd
from mlx_vlm import apply_chat_template, generate, load

from run_zero_shot_vlm import (
    ACTION_PROMPT_TEMPLATE,
    FPS,
    MAX_TOKENS,
    SEED,
    modality_path,
    parse_prediction,
    select_rows,
    sha256,
)


MODEL_REPO = "mlx-community/Qwen3-VL-8B-Instruct-4bit"
MODEL_REVISION = "defcdea7cc7a4b0858fea563cbbce171d328e457"
MODEL_LICENSE = "apache-2.0"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=18, help="0 means all recovered HARn/single rows")
    parser.add_argument("--qa-id", default=None)
    parser.add_argument("--run-name", default="qwen3_vl_8b_zero_shot_balanced18_v1")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    model_path = root / "cache/models/Qwen3-VL-8B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_8b_mlx_model_manifest.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    video_manifest_path = root / "cache/partial_visual_manifest.json"
    output_path = root / f"artifacts/vlm/{args.run_name}.jsonl"
    report_path = root / f"reports/{args.run_name}_summary.json"

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != MODEL_LICENSE
        or model_manifest.get("gated") is not False
    ):
        raise ValueError("8B model manifest does not match the pinned public model")
    video_manifest = json.loads(video_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, str]] = {}
    for item in video_manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item["path"]
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    eligible = qa[
        (qa["source"] == "HARn")
        & (qa["category"] == "single")
        & qa["path"].isin(available)
    ].copy()
    selected = select_rows(eligible, args.limit, args.qa_id)
    if selected.empty:
        raise ValueError("No eligible rows selected")

    completed: dict[str, dict[str, object]] = {}
    if output_path.is_file():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
    pending = selected[~selected["qa_id"].isin(completed)].copy()
    print(
        json.dumps(
            {
                "eligible": len(eligible),
                "selected": len(selected),
                "already_complete": len(selected) - len(pending),
                "pending": len(pending),
            }
        ),
        flush=True,
    )

    started = time.perf_counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not pending.empty:
        mx.random.seed(SEED)
        model, processor = load(str(model_path), trust_remote_code=False)
        for position, (_, row) in enumerate(pending.iterrows(), start=1):
            allowed = [label for label in "ABCD" if str(row[label]).strip()]
            options = "\n".join(f"{label}. {row[label]}" for label in allowed)
            prompt = ACTION_PROMPT_TEMPLATE.format(
                question=row["question"], options=options, allowed="/".join(allowed)
            )
            modality, video_path = modality_path(root, row["path"], available)
            formatted = apply_chat_template(
                processor,
                model.config,
                prompt,
                num_images=0,
                num_audios=0,
                video=[str(video_path)],
                fps=FPS,
                enable_thinking=False,
            )
            item_started = time.perf_counter()
            raw = ""
            error = ""
            try:
                response = generate(
                    model,
                    processor,
                    formatted,
                    video=[str(video_path)],
                    fps=FPS,
                    temperature=0.0,
                    max_tokens=MAX_TOKENS,
                    verbose=False,
                    enable_thinking=False,
                )
                raw = response.text
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            prediction = parse_prediction(raw, allowed) if not error else ""
            item = {
                "qa_id": row["qa_id"],
                "path": row["path"],
                "category": row["category"],
                "subject": row["path"].split("/")[2],
                "action": row["path"].split("/")[1],
                "modality": modality,
                "video_relative_path": str(video_path.relative_to(root)),
                "video_sha256": sha256(video_path),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "answer": row["answer"],
                "raw_output": raw,
                "prediction": prediction,
                "correct": bool(prediction == row["answer"]),
                "error": error,
                "runtime_seconds": time.perf_counter() - item_started,
            }
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            completed[str(row["qa_id"])] = item
            print(
                f"{position}/{len(pending)} {row['qa_id']} pred={prediction or 'INVALID'} "
                f"answer={row['answer']} correct={item['correct']} seconds={item['runtime_seconds']:.2f}",
                flush=True,
            )

    result_frame = pd.DataFrame(completed[str(qa_id)] for qa_id in selected["qa_id"])
    valid = result_frame[(result_frame["prediction"] != "") & (result_frame["error"] == "")]
    by_action = valid.groupby("action")["correct"].agg(["count", "mean"])
    by_subject = valid.groupby("subject")["correct"].agg(["count", "mean"])
    report = {
        "experiment": args.run_name,
        "task": "zero-shot HARn single recognition; exact 8B/4B protocol match",
        "selection": "same stable action-first and subject-spread selector as the archived 4B route",
        "seed": SEED,
        "fps": FPS,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "prompt_template_sha256": hashlib.sha256(ACTION_PROMPT_TEMPLATE.encode()).hexdigest(),
        "eligible_rows": int(len(eligible)),
        "selected_rows": int(len(result_frame)),
        "valid_predictions": int(len(valid)),
        "errors": int((result_frame["error"] != "").sum()),
        "accuracy": float(valid["correct"].mean()) if len(valid) else None,
        "action_coverage": int(result_frame["action"].nunique()),
        "subject_coverage": int(result_frame["subject"].nunique()),
        "worst_action_accuracy": float(by_action["mean"].min()) if len(by_action) else None,
        "worst_subject_accuracy": float(by_subject["mean"].min()) if len(by_subject) else None,
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "manifest_sha256": sha256(model_manifest_path),
        },
        "inputs": {
            "training_qa_sha256": sha256(qa_path),
            "partial_visual_manifest_sha256": sha256(video_manifest_path),
            "prediction_log_sha256": sha256(output_path),
        },
        "versions": {
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "pandas": pd.__version__,
        },
        "code_sha256": sha256(Path(__file__)),
        "total_inference_runtime_seconds": float(result_frame["runtime_seconds"].sum()),
        "incremental_runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
