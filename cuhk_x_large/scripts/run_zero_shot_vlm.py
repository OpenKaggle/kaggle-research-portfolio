#!/usr/bin/env python3
"""Deterministic zero-shot VLM validation on CRC-checked recovered HARn videos."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import time
from pathlib import Path

import mlx.core as mx
import pandas as pd
from mlx_vlm import apply_chat_template, generate, load


SEED = 20260909
FPS = 1.0
MAX_TOKENS = 8
MODEL_REPO = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
MODEL_REVISION = "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b"
MODEL_LICENSE = "apache-2.0"
ACTION_PROMPT_TEMPLATE = """Classify the main human action shown in the video.
{question}
{options}
Reply with exactly one capital letter from {allowed}. Do not add punctuation or explanation."""
OBJECT_PROMPT_TEMPLATE = """Classify the main object the person is interacting with in the video.
{question}
{options}
Reply with exactly one capital letter from {allowed}. Do not add punctuation or explanation."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(f"{SEED}:{value}".encode()).hexdigest()


def select_rows(frame: pd.DataFrame, limit: int, qa_id: str | None) -> pd.DataFrame:
    if qa_id:
        chosen = frame[frame["qa_id"] == qa_id]
        if len(chosen) != 1:
            raise ValueError(f"Expected exactly one recovered HARn/single row for {qa_id}")
        return chosen.copy()
    if limit <= 0 or limit >= len(frame):
        return frame.sort_values("qa_id").copy()

    candidates = frame.copy()
    candidates["action"] = candidates["path"].str.split("/").str[1]
    candidates["subject"] = candidates["path"].str.extract(r"/(user\d+)/")
    candidates["stable_key"] = candidates["qa_id"].map(stable_key)
    candidates = candidates.sort_values(["stable_key", "qa_id"])
    selected: list[int] = []
    used_subjects: set[str] = set()

    # First cover every recovered action once. Within each action, prefer a new subject.
    for action in sorted(candidates["action"].unique()):
        group = candidates[candidates["action"] == action]
        fresh = group[~group["subject"].isin(used_subjects)]
        row = (fresh if not fresh.empty else group).iloc[0]
        selected.append(int(row.name))
        used_subjects.add(str(row["subject"]))
        if len(selected) == limit:
            break

    # Then expand subject coverage before filling any remaining positions.
    remaining = candidates.drop(index=selected)
    if len(selected) < limit:
        for index, row in remaining.iterrows():
            if str(row["subject"]) not in used_subjects:
                selected.append(int(index))
                used_subjects.add(str(row["subject"]))
                if len(selected) == limit:
                    break
    if len(selected) < limit:
        for index in remaining.index:
            if int(index) not in selected:
                selected.append(int(index))
                if len(selected) == limit:
                    break
    return frame.loc[selected].copy()


def parse_prediction(raw: str, allowed: list[str]) -> str:
    text = raw.strip().upper()
    exact = re.fullmatch(r"[ABCD]", text)
    if exact and exact.group(0) in allowed:
        return exact.group(0)
    matches = [token for token in re.findall(r"(?<![A-Z])[ABCD](?![A-Z])", text) if token in allowed]
    return matches[0] if len(set(matches)) == 1 else ""


def modality_path(root: Path, unit: str, available: dict[str, dict[str, str]]) -> tuple[str, Path]:
    for modality in ("Depth_Color", "IR", "Depth"):
        if modality in available[unit]:
            path = root / "data/raw/visual_prefix" / available[unit][modality]
            if path.is_file():
                return modality, path
    raise FileNotFoundError(f"No recovered video for {unit}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=18, help="0 means all recovered HARn/single rows")
    parser.add_argument("--qa-id", default=None, help="Run one exact recovered validation row")
    parser.add_argument("--category", choices=("single", "object_interaction"), default="single")
    parser.add_argument("--run-name", default="qwen3_vl_4b_zero_shot_v1")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    video_manifest_path = root / "cache/partial_visual_manifest.json"
    output_path = root / f"artifacts/vlm/{args.run_name}.jsonl"
    report_path = root / f"reports/{args.run_name}_summary.json"

    if not model_manifest_path.is_file():
        raise FileNotFoundError("Pinned model manifest is missing; finish and verify model download first")
    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != MODEL_LICENSE
    ):
        raise ValueError("Model manifest does not match the pinned public model")

    video_manifest = json.loads(video_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, str]] = {}
    for item in video_manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item["path"]
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    eligible = qa[
        (qa["source"] == "HARn")
        & (qa["category"] == args.category)
        & (qa["path"].isin(available))
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
            prompt_template = ACTION_PROMPT_TEMPLATE if args.category == "single" else OBJECT_PROMPT_TEMPLATE
            prompt = prompt_template.format(
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
            error = ""
            raw = ""
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
                "subject": re.search(r"/(user\d+)/", row["path"]).group(1),
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

    results = [completed[str(qa_id)] for qa_id in selected["qa_id"]]
    result_frame = pd.DataFrame(results)
    valid = result_frame[result_frame["prediction"] != ""]
    by_action = valid.groupby("action")["correct"].agg(["count", "mean"])
    by_subject = valid.groupby("subject")["correct"].agg(["count", "mean"])
    report = {
        "experiment": args.run_name,
        "task": f"zero-shot HARn {args.category} recognition",
        "selection": "all recovered actions once, then new subjects, stable SHA-256 order; limit<=0 selects all",
        "seed": SEED,
        "fps": FPS,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "prompt_template_sha256": hashlib.sha256(
            (ACTION_PROMPT_TEMPLATE if args.category == "single" else OBJECT_PROMPT_TEMPLATE).encode()
        ).hexdigest(),
        "eligible_rows": int(len(eligible)),
        "selected_rows": int(len(results)),
        "valid_predictions": int(len(valid)),
        "errors": int((result_frame["error"] != "").sum()),
        "accuracy": float(valid["correct"].mean()) if len(valid) else None,
        "action_coverage": int(result_frame["action"].nunique()),
        "subject_coverage": int(result_frame["subject"].nunique()),
        "by_action": {
            action: {"count": int(values["count"]), "accuracy": float(values["mean"])}
            for action, values in by_action.iterrows()
        },
        "by_subject": {
            subject: {"count": int(values["count"]), "accuracy": float(values["mean"])}
            for subject, values in by_subject.iterrows()
        },
        "selected_qa_ids": result_frame["qa_id"].tolist(),
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
            "python": platform.python_version(),
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "pandas": pd.__version__,
        },
        "code_sha256": sha256(Path(__file__)),
        "total_inference_runtime_seconds": float(result_frame["runtime_seconds"].sum()),
        "incremental_runtime_seconds": time.perf_counter() - started,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
