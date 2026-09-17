#!/usr/bin/env python3
"""Deterministic zero-shot HAU validation on recovered official videos."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import time
from pathlib import Path

import mlx.core as mx
import pandas as pd
from mlx_vlm import apply_chat_template, generate, load

from run_zero_shot_vlm import (
    ACTION_PROMPT_TEMPLATE,
    FPS,
    MAX_TOKENS,
    MODEL_LICENSE,
    MODEL_REPO,
    MODEL_REVISION,
    SEED,
    parse_prediction,
    sha256,
    stable_key,
)


EMOTION_PROMPT_TEMPLATE = """Classify the manner or emotional style in which the action is performed in the video.
{question}
{options}
Reply with exactly one capital letter from {allowed}. Do not add punctuation or explanation."""
MULTI_PROMPT_TEMPLATE = """Identify every listed action that is visibly performed in the video.
{question}
{options}
Reply with only the selected capital letters in alphabetical order, with no spaces or punctuation. Select at least one letter."""
COMBINATION_PROMPT_TEMPLATE = """Identify the pair or combination of actions visibly performed in the video.
{question}
{options}
Reply with exactly one capital letter from {allowed}. Do not add punctuation or explanation."""
SEQUENCE_PROMPT_TEMPLATE = """Determine the chronological order of the four listed actions in the video.
{question}
{options}
Reply with exactly the four capital option letters in chronological order, with no spaces or punctuation."""

PROMPT_TEMPLATES = {
    "single": ACTION_PROMPT_TEMPLATE,
    "emotion": EMOTION_PROMPT_TEMPLATE,
    "multi": MULTI_PROMPT_TEMPLATE,
    "combination": COMBINATION_PROMPT_TEMPLATE,
    "sequence": SEQUENCE_PROMPT_TEMPLATE,
}


def parse_category_prediction(raw: str, category: str, allowed: list[str]) -> str:
    if category in {"single", "emotion", "combination"}:
        return parse_prediction(raw, allowed)
    value = raw.strip().upper()
    if category == "multi":
        if not re.fullmatch(r"[ABCD]{1,4}", value):
            return ""
        if len(set(value)) != len(value) or value != "".join(sorted(value)):
            return ""
        return value if set(value).issubset(allowed) else ""
    if category == "sequence":
        return value if len(value) == len(allowed) and set(value) == set(allowed) else ""
    raise ValueError(category)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=tuple(PROMPT_TEMPLATES), required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    visual_manifest_path = root / "cache/partial_hau_visual_manifest.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    output_path = root / f"artifacts/vlm/{args.run_name}.jsonl"
    report_path = root / f"reports/{args.run_name}_summary.json"
    visual_root = root / "data/raw/visual_hau_prefix"

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != MODEL_LICENSE
    ):
        raise ValueError("Model manifest mismatch")
    visual_manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, str]] = {}
    for item in visual_manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item["path"]
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    eligible = qa[(qa["source"] == "HAU") & (qa["category"] == args.category) & qa["path"].isin(available)].copy()
    eligible["subject"] = eligible["path"].str.extract(r"(user\d+)")
    if args.limit > 0 and args.limit < len(eligible):
        ranked = eligible.assign(stable_key=eligible["qa_id"].map(stable_key)).sort_values(["stable_key", "qa_id"])
        selected_indices = []
        for _, group in ranked.groupby("subject", sort=True):
            selected_indices.append(int(group.index[0]))
            if len(selected_indices) == args.limit:
                break
        if len(selected_indices) < args.limit:
            selected_indices.extend(int(i) for i in ranked.index if int(i) not in selected_indices)
        selected = eligible.loc[selected_indices[: args.limit]].copy()
    else:
        selected = eligible.sort_values("qa_id").copy()
    if selected.empty:
        raise ValueError("No recovered HAU rows selected")

    completed: dict[str, dict[str, object]] = {}
    if output_path.is_file():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
    pending = selected[~selected["qa_id"].isin(completed)]
    print(json.dumps({"eligible": len(eligible), "selected": len(selected), "already_complete": len(selected) - len(pending), "pending": len(pending)}), flush=True)

    started = time.perf_counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not pending.empty:
        mx.random.seed(SEED)
        model, processor = load(str(model_path), trust_remote_code=False)
        for position, (_, row) in enumerate(pending.iterrows(), start=1):
            allowed = [label for label in "ABCD" if str(row[label]).strip()]
            options = "\n".join(f"{label}. {row[label]}" for label in allowed)
            template = PROMPT_TEMPLATES[args.category]
            prompt = template.format(question=row["question"], options=options, allowed="/".join(allowed))
            modality = next((name for name in ("Depth_Color", "IR", "Depth") if name in available[row["path"]]), None)
            if modality is None:
                raise FileNotFoundError(row["path"])
            video_path = visual_root / available[row["path"]][modality]
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
            prediction = parse_category_prediction(raw, args.category, allowed) if not error else ""
            item = {
                "qa_id": row["qa_id"],
                "path": row["path"],
                "category": args.category,
                "subject": row["subject"],
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
            print(f"{position}/{len(pending)} {row['qa_id']} pred={prediction or 'INVALID'} answer={row['answer']} correct={item['correct']} seconds={item['runtime_seconds']:.2f}", flush=True)

    results = pd.DataFrame(completed[str(qa_id)] for qa_id in selected["qa_id"])
    valid = results[(results["prediction"] != "") & (results["error"] == "")]
    by_subject = valid.groupby("subject")["correct"].agg(["count", "mean"])
    template = PROMPT_TEMPLATES[args.category]
    report = {
        "experiment": args.run_name,
        "task": f"zero-shot HAU {args.category} recognition",
        "selection": "all recovered rows unless a stable subject-spread limit is requested",
        "seed": SEED,
        "fps": FPS,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "prompt_template_sha256": hashlib.sha256(template.encode()).hexdigest(),
        "eligible_rows": int(len(eligible)),
        "selected_rows": int(len(results)),
        "subjects": int(results["subject"].nunique()),
        "valid_predictions": int(len(valid)),
        "errors": int((results["error"] != "").sum()),
        "accuracy": float(valid["correct"].mean()) if len(valid) else None,
        "worst_subject_accuracy": float(by_subject["mean"].min()) if len(by_subject) else None,
        "by_subject": {
            subject: {"count": int(values["count"]), "accuracy": float(values["mean"])}
            for subject, values in by_subject.iterrows()
        },
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "manifest_sha256": sha256(model_manifest_path),
        },
        "inputs": {
            "training_qa_sha256": sha256(qa_path),
            "partial_hau_visual_manifest_sha256": sha256(visual_manifest_path),
            "prediction_log_sha256": sha256(output_path),
        },
        "versions": {
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "pandas": pd.__version__,
        },
        "code_sha256": sha256(Path(__file__)),
        "total_inference_runtime_seconds": float(results["runtime_seconds"].sum()),
        "incremental_runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
