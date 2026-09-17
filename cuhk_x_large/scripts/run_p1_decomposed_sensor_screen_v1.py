#!/usr/bin/env python3
"""Run P1's sole fresh equal-budget generic-vs-decomposed Qwen screen."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import socket
import time
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20260911
PROTOCOL_SHA = "e547c24f90fa412b763fee8437975d58bd1c7cd68fe50a5368d14e60e0ee89c5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def install_network_block() -> dict[str, object]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    original_socket = socket.socket

    class BlockedSocket(original_socket):
        def connect(self, address: object) -> None:
            raise RuntimeError(f"Network disabled for P1 screen: {address}")

        def connect_ex(self, address: object) -> int:
            raise RuntimeError(f"Network disabled for P1 screen: {address}")

    def blocked_connection(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network disabled for P1 screen")

    socket.socket = BlockedSocket
    socket.create_connection = blocked_connection
    try:
        socket.create_connection(("example.invalid", 443), timeout=0.01)
        blocked = False
    except RuntimeError:
        blocked = True
    return {"hf_hub_offline": os.environ["HF_HUB_OFFLINE"], "transformers_offline": os.environ["TRANSFORMERS_OFFLINE"], "socket_probe_blocked": blocked}


def parse_answer(raw: str) -> str:
    match = re.search(r"(?i)\banswer\s*=\s*([ABCD])\b", raw)
    if match:
        return match.group(1).upper()
    text = raw.strip().upper()
    return text if re.fullmatch(r"[ABCD]", text) else ""


def decomposed_schema_valid(raw: str) -> bool:
    return all(re.search(rf"(?i)\b{name}\s*=\s*[^;\n]+", raw) for name in ("verb", "object", "temporal")) and bool(parse_answer(raw))


def test_unit(path: str) -> str:
    return "Training/" + path


def route(category: str, vlm: str, base: str, sensor: str, confidence: float, present: bool) -> str:
    if not vlm:
        return ""
    if category == "single":
        if present and confidence >= 0.15 and sensor == base and sensor != vlm:
            return base
        return vlm
    if category == "object_interaction":
        if present and confidence >= 0.05 and sensor == vlm:
            return vlm
        return base
    raise ValueError(category)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    protocol_path = root / "reports/p1_decomposed_sensor_fresh48_v1_protocol.json"
    manifest_path = root / "artifacts/manifests/p1_decomposed_sensor_fresh48_v1.csv"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    feature_path = root / "cache/nonvisual_features.npz"
    sensor_oof_path = root / "artifacts/oof/nonvisual_sensor_oof.csv"
    core_oof_path = root / "artifacts/oof/stage2_native_v1_oof.csv"
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    log_path = root / "artifacts/vlm/p1_decomposed_sensor_fresh48_v1.jsonl"
    report_path = root / "reports/p1_decomposed_sensor_fresh48_v1_validation.json"
    if report_path.exists():
        raise FileExistsError("P1's sole fresh screen already has a terminal report")
    if sha256(protocol_path) != PROTOCOL_SHA:
        raise ValueError("Frozen P1 protocol hash mismatch")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN_BEFORE_SOLE_FRESH_SCREEN" or sha256(manifest_path) != protocol["selection"]["manifest_sha256"]:
        raise ValueError("P1 protocol/manifest is not frozen")
    for _, (relative, digest) in protocol["inputs"].items():
        if sha256(root / relative) != digest:
            raise ValueError(f"Frozen input hash mismatch: {relative}")
    for source in protocol["selection"]["exclusion_sources"]:
        if sha256(root / source["path"]) != source["sha256"]:
            raise ValueError(f"Exposure source changed after P1 freeze: {source['path']}")

    cohort = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
    selected_ids, selected_paths = set(cohort["qa_id"]), set(cohort["path"])
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        if path == log_path:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if str(item.get("qa_id", "")) in selected_ids or str(item.get("path", "")) in selected_paths:
                raise ValueError(f"Fresh-screen exposure conflict appeared after freeze: {path}")

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    budget = protocol["equal_budget_pair"]
    if model_manifest.get("repo_id") != budget["model"] or model_manifest.get("revision") != budget["revision"]:
        raise ValueError("Pinned model identity mismatch")
    for item in model_manifest["files"]:
        local = model_path / item["path"]
        if not local.is_file() or sha256(local) != item["sha256"]:
            raise ValueError(f"Pinned model file missing/changed: {local}")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    sensor = pd.read_csv(sensor_oof_path, dtype=str, keep_default_na=False)[["qa_id", "prediction", "confidence"]].rename(columns={"prediction": "sensor_prediction", "confidence": "sensor_confidence"})
    core = pd.read_csv(core_oof_path, dtype=str, keep_default_na=False)[["qa_id", "semantic_base_prediction"]]
    screen = cohort.merge(train[["qa_id", "question", "A", "B", "C", "D", "answer"]], on="qa_id", validate="one_to_one").merge(sensor, on="qa_id", validate="one_to_one").merge(core, on="qa_id", validate="one_to_one")
    screen["sensor_confidence"] = screen["sensor_confidence"].astype(float)
    with np.load(feature_path) as cache:
        units = cache["units"].astype(str)
        skeleton = cache["skeleton"]
        index = {unit: position for position, unit in enumerate(units)}
        screen["sensor_present"] = [
            test_unit(path) in index and bool(np.isfinite(skeleton[index[test_unit(path)]]).any())
            for path in screen["path"]
        ]

    network = install_network_block()
    if not network["socket_probe_blocked"]:
        raise RuntimeError("Network isolation probe failed")
    import mlx.core as mx
    from mlx_vlm import apply_chat_template, generate, load

    completed: dict[str, dict[str, object]] = {}
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
        if not set(completed).issubset(selected_ids):
            raise ValueError("P1 log contains rows outside the frozen cohort")
    pending = screen[~screen["qa_id"].isin(completed)]
    print(json.dumps({"selected": len(screen), "complete": len(completed), "pending": len(pending)}), flush=True)
    model, processor = load(str(model_path), trust_remote_code=False)
    started = time.perf_counter()
    for position, row in enumerate(pending.itertuples(index=False), start=1):
        video_path = root / row.video_relative_path
        if not video_path.is_file() or sha256(video_path) != row.video_sha256:
            raise ValueError(f"Frozen video missing/changed: {video_path}")
        options = "\n".join(f"{label}. {getattr(row, label)}" for label in "ABCD")
        prompts = {
            "generic": budget["generic_prompt"].format(question=row.question, options=options),
            "decomposed": budget["decomposed_prompt"].format(question=row.question, options=options),
        }
        pair: dict[str, object] = {}
        for variant, prompt in prompts.items():
            formatted = apply_chat_template(
                processor,
                model.config,
                prompt,
                num_images=0,
                num_audios=0,
                video=[str(video_path)],
                fps=float(budget["fps_each"]),
                enable_thinking=False,
            )
            mx.random.seed(SEED + position)
            inference_started = time.perf_counter()
            raw = ""
            error = ""
            try:
                response = generate(
                    model,
                    processor,
                    formatted,
                    video=[str(video_path)],
                    fps=float(budget["fps_each"]),
                    temperature=float(budget["temperature_each"]),
                    max_tokens=int(budget["max_generation_tokens_each"]),
                    verbose=False,
                    enable_thinking=False,
                )
                raw = response.text
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            pair[f"{variant}_raw"] = raw
            pair[f"{variant}_prediction"] = parse_answer(raw) if not error else ""
            pair[f"{variant}_error"] = error
            pair[f"{variant}_runtime_seconds"] = time.perf_counter() - inference_started
            pair[f"{variant}_prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
        record = {
            "qa_id": row.qa_id,
            "path": row.path,
            "category": row.category,
            "subject": int(row.subject),
            "subject_half": row.subject_half,
            "video_relative_path": row.video_relative_path,
            "video_sha256": row.video_sha256,
            **pair,
            "decomposed_schema_valid": decomposed_schema_valid(str(pair["decomposed_raw"])),
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        completed[row.qa_id] = record
        print(
            f"{position}/{len(pending)} {row.qa_id} {row.category} "
            f"generic={pair['generic_prediction'] or 'INVALID'} decomposed={pair['decomposed_prediction'] or 'INVALID'}",
            flush=True,
        )

    results = pd.DataFrame([completed[qa_id] for qa_id in screen["qa_id"]])
    columns = ["qa_id", "generic_prediction", "decomposed_prediction", "generic_error", "decomposed_error", "decomposed_schema_valid"]
    evaluation = screen.merge(results[columns], on="qa_id", validate="one_to_one")
    evaluation["generic_routed"] = [
        route(row.category, row.generic_prediction, row.semantic_base_prediction, row.sensor_prediction, row.sensor_confidence, row.sensor_present)
        for row in evaluation.itertuples(index=False)
    ]
    evaluation["candidate_routed"] = [
        route(row.category, row.decomposed_prediction, row.semantic_base_prediction, row.sensor_prediction, row.sensor_confidence, row.sensor_present)
        for row in evaluation.itertuples(index=False)
    ]
    evaluation["generic_correct"] = evaluation["generic_routed"] == evaluation["answer"]
    evaluation["candidate_correct"] = evaluation["candidate_routed"] == evaluation["answer"]
    evaluation["delta"] = evaluation["candidate_correct"].astype(int) - evaluation["generic_correct"].astype(int)
    evaluation["raw_generic_correct"] = evaluation["generic_prediction"] == evaluation["answer"]
    evaluation["raw_decomposed_correct"] = evaluation["decomposed_prediction"] == evaluation["answer"]

    def metrics(frame: pd.DataFrame) -> dict[str, object]:
        return {
            "rows": int(len(frame)),
            "generic_correct": int(frame["generic_correct"].sum()),
            "generic_accuracy": float(frame["generic_correct"].mean()),
            "candidate_correct": int(frame["candidate_correct"].sum()),
            "candidate_accuracy": float(frame["candidate_correct"].mean()),
            "net_gain": int(frame["delta"].sum()),
            "accuracy_gain": float(frame["delta"].mean()),
            "raw_generic_accuracy": float(frame["raw_generic_correct"].mean()),
            "raw_decomposed_accuracy": float(frame["raw_decomposed_correct"].mean()),
        }

    overall = metrics(evaluation)
    by_category = {name: metrics(group) for name, group in evaluation.groupby("category", sort=True)}
    by_half = {name: metrics(group) for name, group in evaluation.groupby("subject_half", sort=True)}
    by_subject = {str(subject): metrics(group) for subject, group in evaluation.groupby("subject", sort=True)}
    subject_delta = evaluation.groupby("subject")["delta"].mean()
    disagreement = evaluation[evaluation["candidate_routed"] != evaluation["generic_routed"]]
    promotion = protocol["promotion_gate"]
    generic_invalid = int((evaluation["generic_prediction"] == "").sum())
    decomposed_invalid = int((evaluation["decomposed_prediction"] == "").sum())
    schema_invalid = int((~evaluation["decomposed_schema_valid"].map(lambda value: str(value).lower() == "true")).sum())
    checks = {
        "subject_macro_gain": float(subject_delta.mean()) >= promotion["candidate_vs_equal_budget_generic_subject_macro_gain_min"],
        "single_nonnegative": by_category["single"]["net_gain"] >= promotion["single_net_gain_min"],
        "object_nonnegative": by_category["object_interaction"]["net_gain"] >= promotion["object_net_gain_min"],
        "worst_subject_loss": float(subject_delta.min()) >= promotion["worst_subject_accuracy_delta_min"],
        "generic_invalid_zero": generic_invalid <= promotion["generic_invalid_max"],
        "decomposed_invalid_zero": decomposed_invalid <= promotion["decomposed_invalid_max"],
        "decomposed_schema_invalid_zero": schema_invalid <= promotion["decomposed_evidence_schema_invalid_max"],
        "parent_disagreement_net_positive": int(disagreement["delta"].sum()) > promotion["parent_disagreement_net_gain_min_exclusive"],
    }
    passed = all(checks.values())
    report = {
        "experiment": protocol["experiment"],
        "decision": "PASS_P1_ALLOW_NETWORK_FREE_PACKAGING" if passed else "REJECT_P1_NO_TEST_NO_SUBMISSION",
        "passed": passed,
        "fresh_screen": True,
        "prior_exposure_conflicts": 0,
        "test_qa_read": False,
        "test_prediction_written": False,
        "candidate_csv_written": False,
        "submission_performed": False,
        "network_isolation": network,
        "equal_budget": budget,
        "validation": {
            "overall": overall,
            "by_category": by_category,
            "by_subject_half": by_half,
            "by_subject": by_subject,
            "subject_macro_gain": float(subject_delta.mean()),
            "worst_subject_accuracy_delta": float(subject_delta.min()),
            "generic_invalid": generic_invalid,
            "decomposed_invalid": decomposed_invalid,
            "decomposed_schema_invalid": schema_invalid,
            "parent_disagreements": int(len(disagreement)),
            "parent_disagreement_net_gain": int(disagreement["delta"].sum()),
        },
        "gate": {"frozen": promotion, "checks": checks, "passed": passed},
        "artifacts": {
            "protocol_sha256": sha256(protocol_path),
            "manifest_sha256": sha256(manifest_path),
            "prediction_log_sha256": sha256(log_path),
            "code_sha256": sha256(Path(__file__)),
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
        },
        "total_inference_runtime_seconds": float(results["generic_runtime_seconds"].sum() + results["decomposed_runtime_seconds"].sum()),
        "incremental_runtime_seconds": time.perf_counter() - started,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
