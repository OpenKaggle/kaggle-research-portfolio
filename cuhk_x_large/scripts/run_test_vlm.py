#!/usr/bin/env python3
"""Run the validation-qualified zero-shot VLM method on official test videos."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path, PurePosixPath

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
    OBJECT_PROMPT_TEMPLATE,
    SEED,
    parse_prediction,
    sha256,
)


def unit_from_path(value: str) -> str:
    parts = PurePosixPath(value).parts
    if len(parts) < 2 or parts[0] != "large_model_track_test":
        raise ValueError(f"Unexpected test path: {value}")
    return "/".join(parts[:2])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", choices=("single", "object_interaction"), default="single")
    parser.add_argument("--run-name", default="qwen3_vl_4b_test_harn_single_v1")
    parser.add_argument("--visual-manifest", default="test_visual_manifest.json")
    parser.add_argument("--visual-root", default="data/raw/visual_test")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    visual_manifest_path = root / "cache" / args.visual_manifest
    visual_root = root / args.visual_root
    qa_path = root / "data/raw/kaggle/test_qa.csv"
    sensor_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    parent_path = root / "candidates/public_fususu_077777.csv"
    output_path = root / f"artifacts/vlm/{args.run_name}.jsonl"
    report_path = root / f"reports/{args.run_name}_summary.json"

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != MODEL_LICENSE
    ):
        raise ValueError("Model manifest does not match the validation-qualified model")
    visual_manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, str]] = {}
    for item in visual_manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item["path"]
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    intended = qa[(qa["source"] == "HARn") & (qa["category"] == args.category)].copy()
    intended["unit"] = intended["path"].map(unit_from_path)
    missing = sorted(set(intended["unit"]) - set(available))
    if missing and not args.allow_partial:
        raise ValueError(f"Missing official test video units: {missing}")
    selected = intended[intended["unit"].isin(available)].copy()
    if selected.empty:
        raise ValueError("No test rows have a recovered video")

    completed: dict[str, dict[str, object]] = {}
    if output_path.is_file():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
    pending = selected[~selected["qa_id"].isin(completed)]
    print(json.dumps({"selected": len(selected), "already_complete": len(selected) - len(pending), "pending": len(pending)}), flush=True)

    started = time.perf_counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not pending.empty:
        mx.random.seed(SEED)
        model, processor = load(str(model_path), trust_remote_code=False)
        for position, (_, row) in enumerate(pending.iterrows(), start=1):
            allowed = [label for label in "ABCD" if str(row[label]).strip()]
            options = "\n".join(f"{label}. {row[label]}" for label in allowed)
            prompt_template = ACTION_PROMPT_TEMPLATE if args.category == "single" else OBJECT_PROMPT_TEMPLATE
            prompt = prompt_template.format(question=row["question"], options=options, allowed="/".join(allowed))
            modality = next((name for name in ("Depth_Color", "IR", "Depth") if name in available[row["unit"]]), None)
            if modality is None:
                raise FileNotFoundError(f"No supported video modality for {row['unit']}")
            video_path = visual_root / available[row["unit"]][modality]
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
                "unit": row["unit"],
                "category": args.category,
                "modality": modality,
                "video_relative_path": str(video_path.relative_to(root)),
                "video_sha256": sha256(video_path),
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "raw_output": raw,
                "prediction": prediction,
                "error": error,
                "runtime_seconds": time.perf_counter() - item_started,
            }
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            completed[str(row["qa_id"])] = item
            print(f"{position}/{len(pending)} {row['qa_id']} pred={prediction or 'INVALID'} seconds={item['runtime_seconds']:.2f}", flush=True)

    results = pd.DataFrame(completed[str(qa_id)] for qa_id in selected["qa_id"])
    if (results["prediction"] == "").any() or (results["error"] != "").any():
        raise ValueError("Test inference has invalid or failed outputs; no candidate may be built")
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(columns={"prediction": "parent_prediction"})
    sensor = pd.read_csv(sensor_path, dtype=str, keep_default_na=False)
    sensor = sensor[(sensor["source"] == "HARn") & (sensor["category"] == args.category)].rename(
        columns={"prediction": "sensor_prediction"}
    )
    comparison = results.merge(parent, on="qa_id", validate="one_to_one").merge(
        sensor[["qa_id", "sensor_prediction", "confidence", "sensor_present"]],
        on="qa_id",
        validate="one_to_one",
    )
    sensor_present = comparison["sensor_present"].str.lower().eq("true")
    consensus = sensor_present & (comparison["prediction"] == comparison["sensor_prediction"])
    consensus_override = consensus & (comparison["prediction"] != comparison["parent_prediction"])
    report = {
        "experiment": args.run_name,
        "task": f"test-time zero-shot HARn {args.category} recognition",
        "intended_rows": int(len(intended)),
        "rows": int(len(results)),
        "coverage": float(len(results) / len(intended)),
        "missing_units": missing,
        "valid_predictions": int(len(results)),
        "errors": 0,
        "prediction_distribution": results["prediction"].value_counts().sort_index().to_dict(),
        "sensor_present_rows": int(sensor_present.sum()),
        "sensor_vlm_consensus_rows": int(consensus.sum()),
        "sensor_vlm_consensus_differs_parent_rows": int(consensus_override.sum()),
        "consensus_override_qa_ids": comparison.loc[consensus_override, "qa_id"].tolist(),
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "manifest_sha256": sha256(model_manifest_path),
        },
        "inputs": {
            "test_qa_sha256": sha256(qa_path),
            "test_visual_manifest_sha256": sha256(visual_manifest_path),
            "parent_sha256": sha256(parent_path),
            "sensor_predictions_sha256": sha256(sensor_path),
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
