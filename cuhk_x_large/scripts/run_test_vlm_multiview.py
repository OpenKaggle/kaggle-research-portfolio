#!/usr/bin/env python3
"""Run the validation-qualified three-view Qwen3-VL method on official test clips."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import time
from pathlib import Path, PurePosixPath

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
    sha256,
)
from run_zero_shot_vlm_multiview import MODALITIES, PROMPT_TEMPLATE


RUN_NAME = "qwen3_vl_4b_test_harn_single_multiview_v1"


def unit_from_path(value: str) -> str:
    parts = PurePosixPath(value).parts
    if len(parts) < 2 or parts[0] != "large_model_track_test":
        raise ValueError(f"Unexpected test path: {value}")
    return "/".join(parts[:2])


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    visual_manifest_path = root / "cache/partial_test_visual_manifest.json"
    visual_root = root / "data/raw/visual_test_prefix"
    qa_path = root / "data/raw/kaggle/test_qa.csv"
    parent_path = root / "candidates/public_fususu_077777.csv"
    base_path = root / "candidates/visual_sensor_consensus_v1.csv"
    rf_path = root / "artifacts/predictions/nonvisual_sensor_test.csv"
    et_path = root / "artifacts/predictions/harn_multimodal_extratrees_test.csv"
    single_view_path = root / "artifacts/vlm/qwen3_vl_4b_test_harn_single_v1.jsonl"
    validation_path = root / "reports/qwen3_vl_4b_multiview_full112_v1_summary.json"
    output_path = root / f"artifacts/vlm/{RUN_NAME}.jsonl"
    report_path = root / f"reports/{RUN_NAME}_summary.json"

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if not (
        validation["valid_predictions"] == 112
        and validation["errors"] == 0
        and validation["accuracy"] > validation["matched_single_view_accuracy"]
        and validation["multiview_only_correct"] > validation["single_view_only_correct"]
    ):
        raise ValueError("Three-view validation gate failed")
    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != MODEL_LICENSE
    ):
        raise ValueError("Pinned model manifest mismatch")

    manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8"))
    available: dict[str, dict[str, str]] = {}
    for item in manifest:
        available.setdefault(item["unit"], {})[item["modality"]] = item["path"]
    complete = {
        unit for unit, modalities in available.items() if all(name in modalities for name in MODALITIES)
    }
    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    intended = qa[(qa["source"] == "HARn") & (qa["category"] == "single")].copy()
    intended["unit"] = intended["path"].map(unit_from_path)
    selected = intended[intended["unit"].isin(complete)].sort_values("qa_id").copy()
    if selected.empty:
        raise ValueError("No official test rows have all three visual modalities")

    completed: dict[str, dict[str, object]] = {}
    if output_path.is_file():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
    pending = selected[~selected["qa_id"].isin(completed)]
    print(json.dumps({"intended": len(intended), "selected": len(selected), "pending": len(pending)}), flush=True)

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
            video_paths = [
                visual_root / available[row["unit"]][modality] for modality in MODALITIES
            ]
            if not all(path.is_file() for path in video_paths):
                raise FileNotFoundError(row["unit"])
            formatted = apply_chat_template(
                processor,
                model.config,
                prompt,
                num_images=0,
                num_audios=0,
                video=[str(path) for path in video_paths],
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
                    video=[str(path) for path in video_paths],
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
                "category": "single",
                "modalities": list(MODALITIES),
                "video_relative_paths": [str(path.relative_to(root)) for path in video_paths],
                "video_sha256": [sha256(path) for path in video_paths],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "raw_output": raw,
                "prediction": prediction,
                "error": error,
                "runtime_seconds": time.perf_counter() - item_started,
            }
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            completed[str(row["qa_id"])] = item
            print(
                f"{position}/{len(pending)} {row['qa_id']} pred={prediction or 'INVALID'} "
                f"seconds={item['runtime_seconds']:.2f}",
                flush=True,
            )

    results = pd.DataFrame(completed[str(qa_id)] for qa_id in selected["qa_id"])
    invalid = results[(results["prediction"] == "") | (results["error"] != "")].copy()
    if len(invalid):
        report = {
            "experiment": RUN_NAME,
            "task": "test-time synchronized Depth_Color+IR+Depth HARn single recognition",
            "intended_rows": int(len(intended)),
            "rows_attempted": int(len(results)),
            "coverage_attempted": float(len(results) / len(intended)),
            "valid_predictions": int(len(results) - len(invalid)),
            "empty_predictions": int(results["prediction"].eq("").sum()),
            "errors": int(results["error"].ne("").sum()),
            "invalid_evidence": invalid[
                ["qa_id", "prediction", "raw_output", "error", "runtime_seconds"]
            ].to_dict(orient="records"),
            "candidate_eligible": False,
            "decision": "REJECTED_STABILITY: repeated empty outputs from the same three-view preprocessing root; stop without retry and build no candidate",
            "model": {
                "repo_id": MODEL_REPO,
                "revision": MODEL_REVISION,
                "license": MODEL_LICENSE,
                "manifest_sha256": sha256(model_manifest_path),
            },
            "inputs": {
                "test_qa_sha256": sha256(qa_path),
                "test_visual_manifest_sha256": sha256(visual_manifest_path),
                "validation_report_sha256": sha256(validation_path),
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
        print(json.dumps(report, indent=2), flush=True)
        print(f"report_sha256={sha256(report_path)}", flush=True)
        return
    parent = pd.read_csv(parent_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "parent_prediction"}
    )
    base = pd.read_csv(base_path, dtype=str, keep_default_na=False).rename(
        columns={"prediction": "base_prediction"}
    )
    rf = pd.read_csv(rf_path, dtype=str, keep_default_na=False)
    rf = rf[(rf["source"] == "HARn") & (rf["category"] == "single")].copy()
    rf["rf_present"] = rf["sensor_present"].str.lower().eq("true")
    rf = rf[["qa_id", "prediction", "confidence", "rf_present"]].rename(
        columns={"prediction": "rf_prediction", "confidence": "rf_confidence"}
    )
    et = pd.read_csv(et_path, dtype=str, keep_default_na=False)
    et = et[et["category"] == "single"].copy()
    et["et_present"] = et["sensor_present"].str.lower().eq("true")
    et = et[["qa_id", "prediction", "confidence", "et_present"]].rename(
        columns={"prediction": "et_prediction", "confidence": "et_confidence"}
    )
    single_view = pd.DataFrame(
        json.loads(line)
        for line in single_view_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )[["qa_id", "prediction"]].rename(columns={"prediction": "single_view_prediction"})
    comparison = (
        results[["qa_id", "prediction"]].rename(columns={"prediction": "multiview_prediction"})
        .merge(parent, on="qa_id", validate="one_to_one")
        .merge(base, on="qa_id", validate="one_to_one")
        .merge(rf, on="qa_id", validate="one_to_one")
        .merge(et, on="qa_id", validate="one_to_one")
        .merge(single_view, on="qa_id", how="left", validate="one_to_one")
    )
    comparison["triple_consensus"] = (
        comparison["rf_present"]
        & comparison["et_present"]
        & (comparison["multiview_prediction"] == comparison["rf_prediction"])
        & (comparison["multiview_prediction"] == comparison["et_prediction"])
    )
    comparison["triple_differs_parent"] = comparison["triple_consensus"] & (
        comparison["multiview_prediction"] != comparison["parent_prediction"]
    )
    comparison["triple_differs_base"] = comparison["triple_consensus"] & (
        comparison["multiview_prediction"] != comparison["base_prediction"]
    )
    report = {
        "experiment": RUN_NAME,
        "task": "test-time synchronized Depth_Color+IR+Depth HARn single recognition",
        "intended_rows": int(len(intended)),
        "rows": int(len(results)),
        "coverage": float(len(results) / len(intended)),
        "valid_predictions": int(len(results)),
        "errors": 0,
        "prediction_distribution": results["prediction"].value_counts().sort_index().to_dict(),
        "agreement_with_single_view_rows": int(
            (comparison["multiview_prediction"] == comparison["single_view_prediction"]).sum()
        ),
        "triple_consensus_rows": int(comparison["triple_consensus"].sum()),
        "triple_consensus_differs_parent_rows": int(comparison["triple_differs_parent"].sum()),
        "triple_consensus_differs_base_rows": int(comparison["triple_differs_base"].sum()),
        "triple_consensus_evidence": comparison.loc[
            comparison["triple_consensus"],
            [
                "qa_id", "parent_prediction", "base_prediction", "multiview_prediction",
                "single_view_prediction", "rf_prediction", "rf_confidence",
                "et_prediction", "et_confidence", "triple_differs_parent", "triple_differs_base",
            ],
        ].fillna("").to_dict(orient="records"),
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": MODEL_LICENSE,
            "manifest_sha256": sha256(model_manifest_path),
        },
        "inputs": {
            "test_qa_sha256": sha256(qa_path),
            "test_visual_manifest_sha256": sha256(visual_manifest_path),
            "validation_report_sha256": sha256(validation_path),
            "parent_sha256": sha256(parent_path),
            "base_sha256": sha256(base_path),
            "rf_test_sha256": sha256(rf_path),
            "et_test_sha256": sha256(et_path),
            "single_view_log_sha256": sha256(single_view_path),
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
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
