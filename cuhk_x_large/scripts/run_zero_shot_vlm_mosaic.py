#!/usr/bin/env python3
"""Deterministic single-video 2x2 mosaic validation for synchronized HARn views."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import time
from pathlib import Path

import mlx.core as mx
import pandas as pd
from mlx_vlm import apply_chat_template, generate, load

from run_zero_shot_vlm import (
    FPS,
    MAX_TOKENS,
    MODEL_LICENSE,
    MODEL_REPO,
    MODEL_REVISION,
    SEED,
    parse_prediction,
    select_rows,
    sha256,
)
from run_zero_shot_vlm_multiview import MODALITIES


MAX_PIXELS = 448 * 336
PROMPT_TEMPLATE = """The video is a synchronized three-panel non-RGB view of one human action: top-left is depth-colorized, top-right is infrared, bottom-left is raw depth, and bottom-right is blank. Use evidence shared across the three panels.
Classify the main human action.
{question}
{options}
Reply with exactly one capital letter from {allowed}. Do not add punctuation or explanation."""


def probe(path: Path) -> dict[str, object]:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames,duration",
        "-of", "json", str(path),
    ]
    payload = json.loads(subprocess.run(command, check=True, capture_output=True, text=True).stdout)
    streams = payload.get("streams", [])
    if len(streams) != 1:
        raise ValueError(f"Expected one video stream: {path}")
    return streams[0]


def build_mosaic(inputs: list[Path], output: Path) -> dict[str, object]:
    metadata = [probe(path) for path in inputs]
    keys = ("width", "height", "r_frame_rate", "nb_frames", "duration")
    if any(tuple(item.get(key) for key in keys) != tuple(metadata[0].get(key) for key in keys) for item in metadata[1:]):
        raise ValueError(f"Synchronized streams do not have identical geometry/timing: {inputs}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file():
        command = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
        for path in inputs:
            command.extend(["-i", str(path)])
        command.extend(
            [
                "-filter_complex",
                "[0:v][1:v][2:v]xstack=inputs=3:layout=0_0|w0_0|0_h0:fill=black:shortest=1[v]",
                "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
            ]
        )
        subprocess.run(command, check=True)
    result = probe(output)
    if (
        int(result["width"]) != 2 * int(metadata[0]["width"])
        or int(result["height"]) != 2 * int(metadata[0]["height"])
        or result["r_frame_rate"] != metadata[0]["r_frame_rate"]
        or result["nb_frames"] != metadata[0]["nb_frames"]
    ):
        raise ValueError(f"Mosaic geometry/timing mismatch: {output}")
    return {"inputs": metadata, "output": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=18, help="0 means all eligible rows")
    parser.add_argument("--qa-id", default=None)
    parser.add_argument("--run-name", default="qwen3_vl_4b_mosaic_balanced18_v1")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    manifest_path = root / "cache/partial_visual_manifest.json"
    single_view_path = root / "artifacts/vlm/qwen3_vl_4b_zero_shot_full122_v1.jsonl"
    multiview_path = root / "artifacts/vlm/qwen3_vl_4b_multiview_full112_v1.jsonl"
    mosaic_root = root / "cache/visual_mosaic_train"
    output_path = root / f"artifacts/vlm/{args.run_name}.jsonl"
    report_path = root / f"reports/{args.run_name}_summary.json"

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != MODEL_LICENSE
    ):
        raise ValueError("Pinned model manifest mismatch")
    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, str]] = {}
    for item in items:
        available.setdefault(item["unit"], {})[item["modality"]] = item["path"]
    complete = {
        unit for unit, modalities in available.items() if all(name in modalities for name in MODALITIES)
    }
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    eligible = qa[
        (qa["source"] == "HARn") & (qa["category"] == "single") & qa["path"].isin(complete)
    ].copy()
    selected = select_rows(eligible, args.limit, args.qa_id)
    if selected.empty:
        raise ValueError("No eligible mosaic rows")

    completed: dict[str, dict[str, object]] = {}
    if output_path.is_file():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
    pending = selected[~selected["qa_id"].isin(completed)]
    print(json.dumps({"eligible": len(eligible), "selected": len(selected), "pending": len(pending)}), flush=True)

    started = time.perf_counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not pending.empty:
        mx.random.seed(SEED)
        model, processor = load(str(model_path), trust_remote_code=False)
        for position, (_, row) in enumerate(pending.iterrows(), start=1):
            allowed = [label for label in "ABCD" if row[label]]
            options = "\n".join(f"{label}. {row[label]}" for label in allowed)
            prompt = PROMPT_TEMPLATE.format(
                question=row["question"], options=options, allowed="/".join(allowed)
            )
            inputs = [
                root / "data/raw/visual_prefix" / available[row["path"]][modality]
                for modality in MODALITIES
            ]
            mosaic_path = mosaic_root / f"{row['qa_id']}.mp4"
            media_metadata = build_mosaic(inputs, mosaic_path)
            formatted = apply_chat_template(
                processor,
                model.config,
                prompt,
                num_images=0,
                num_audios=0,
                video=[str(mosaic_path)],
                fps=FPS,
                max_pixels=MAX_PIXELS,
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
                    video=[str(mosaic_path)],
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
                "subject": re.search(r"/(user\d+)/", row["path"]).group(1),
                "action": row["path"].split("/")[1],
                "input_modalities": list(MODALITIES),
                "input_sha256": [sha256(path) for path in inputs],
                "mosaic_relative_path": str(mosaic_path.relative_to(root)),
                "mosaic_sha256": sha256(mosaic_path),
                "media_metadata": media_metadata,
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

    results = pd.DataFrame(completed[str(qa_id)] for qa_id in selected["qa_id"])
    valid = results[(results["prediction"] != "") & (results["error"] == "")].copy()
    single_view = pd.read_json(single_view_path, lines=True)[["qa_id", "prediction", "correct"]].rename(
        columns={"prediction": "single_view_prediction", "correct": "single_view_correct"}
    )
    multiview = pd.read_json(multiview_path, lines=True)[["qa_id", "prediction", "correct"]].rename(
        columns={"prediction": "multiview_prediction", "correct": "multiview_correct"}
    )
    matched = results.merge(single_view, on="qa_id", validate="one_to_one").merge(
        multiview, on="qa_id", validate="one_to_one"
    )
    ffmpeg_version = subprocess.run(
        ["ffmpeg", "-version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]
    report = {
        "experiment": args.run_name,
        "task": "zero-shot single-video 2x2 mosaic HARn single recognition",
        "layout": "Depth_Color top-left; IR top-right; Depth bottom-left; blank bottom-right",
        "selection": "same frozen action-first, then subject-spread selector; all three modalities required",
        "seed": SEED,
        "fps": FPS,
        "max_pixels": MAX_PIXELS,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.0,
        "eligible_rows": int(len(eligible)),
        "selected_rows": int(len(results)),
        "valid_predictions": int(len(valid)),
        "empty_predictions": int(results["prediction"].eq("").sum()),
        "errors": int(results["error"].ne("").sum()),
        "accuracy": float(valid["correct"].mean()) if len(valid) else None,
        "matched_single_view_accuracy": float(matched["single_view_correct"].mean()),
        "matched_multiview_accuracy": float(matched["multiview_correct"].mean()),
        "agreement_with_multiview": int((matched["prediction"] == matched["multiview_prediction"]).sum()),
        "mosaic_only_correct_vs_single": int((matched["correct"] & ~matched["single_view_correct"].astype(bool)).sum()),
        "single_only_correct_vs_mosaic": int((~matched["correct"] & matched["single_view_correct"].astype(bool)).sum()),
        "action_coverage": int(results["action"].nunique()),
        "subject_coverage": int(results["subject"].nunique()),
        "selected_qa_ids": results["qa_id"].tolist(),
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "manifest_sha256": sha256(model_manifest_path),
        },
        "preprocessing": {
            "ffmpeg": ffmpeg_version,
            "codec": "libx264",
            "preset": "veryfast",
            "crf": 18,
            "pixel_format": "yuv420p",
        },
        "inputs": {
            "training_qa_sha256": sha256(qa_path),
            "partial_visual_manifest_sha256": sha256(manifest_path),
            "single_view_log_sha256": sha256(single_view_path),
            "multiview_log_sha256": sha256(multiview_path),
            "prediction_log_sha256": sha256(output_path),
        },
        "versions": {
            "python": platform.python_version(),
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "pandas": pd.__version__,
        },
        "code_sha256": sha256(Path(__file__)),
        "total_inference_runtime_seconds": float(results["runtime_seconds"].sum()),
        "incremental_runtime_seconds": time.perf_counter() - started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
