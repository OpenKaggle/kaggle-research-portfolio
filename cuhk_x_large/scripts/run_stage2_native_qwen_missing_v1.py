#!/usr/bin/env python3
"""Run the frozen all-missing-skeleton HARn/single Qwen gate offline."""

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

import pandas as pd


SEED = 20260911
EXPECTED_PROTOCOL_SHA = "201f85ed09a8ac3d49d0361cb6cf98a0523b4fc76bc9b3615da0cbfb34b2ce23"
EXPECTED_OOF_SHA = "8cf9879a1e147456db67dffe3246bb108e2816170dc787347ce24e93a8f7d1b7"


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
    original_connection = socket.create_connection

    class BlockedSocket(original_socket):
        def connect(self, address: object) -> None:
            raise RuntimeError(f"Network disabled for Stage2-native Qwen gate: {address}")

        def connect_ex(self, address: object) -> int:
            raise RuntimeError(f"Network disabled for Stage2-native Qwen gate: {address}")

    def blocked_connection(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network disabled for Stage2-native Qwen gate")

    socket.socket = BlockedSocket
    socket.create_connection = blocked_connection
    try:
        socket.create_connection(("example.invalid", 443), timeout=0.01)
        probe_blocked = False
    except RuntimeError:
        probe_blocked = True
    return {
        "hf_hub_offline": os.environ["HF_HUB_OFFLINE"],
        "transformers_offline": os.environ["TRANSFORMERS_OFFLINE"],
        "socket_probe_blocked": probe_blocked,
        "original_socket_type": str(original_socket),
        "original_connection": str(original_connection),
    }


def parse_prediction(raw: str) -> str:
    text = raw.strip().upper()
    if re.fullmatch(r"[ABCD]", text):
        return text
    matches = re.findall(r"(?<![A-Z])[ABCD](?![A-Z])", text)
    return matches[0] if len(set(matches)) == 1 else ""


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    protocol_path = root / "reports/stage2_native_qwen_missing_sensor_v1_protocol.json"
    cohort_path = root / "artifacts/manifests/stage2_native_qwen_missing_sensor_v1.csv"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    oof_path = root / "artifacts/oof/stage2_native_v1_oof.csv"
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    log_path = root / "artifacts/vlm/stage2_native_qwen_missing_sensor_v1.jsonl"
    report_path = root / "reports/stage2_native_qwen_missing_sensor_v1_validation.json"

    if sha256(protocol_path) != EXPECTED_PROTOCOL_SHA:
        raise ValueError("Frozen Qwen protocol hash mismatch")
    if sha256(oof_path) != EXPECTED_OOF_SHA:
        raise ValueError("Owned Stage2 OOF hash mismatch")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN_BEFORE_QWEN_INFERENCE":
        raise ValueError("Qwen protocol is not frozen")
    if sha256(cohort_path) != protocol["selection"]["manifest_sha256"]:
        raise ValueError("Frozen cohort hash mismatch")
    for relative, digest in protocol["inputs"].items():
        if sha256(root / relative) != digest:
            raise ValueError(f"Frozen input hash mismatch: {relative}")
    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    inference = protocol["inference"]
    if (
        model_manifest.get("repo_id") != inference["model"]
        or model_manifest.get("revision") != inference["revision"]
        or model_manifest.get("license") != inference["license"]
    ):
        raise ValueError("Pinned local Qwen model identity mismatch")
    for item in model_manifest["files"]:
        local = model_path / item["path"]
        if not local.is_file() or sha256(local) != item["sha256"]:
            raise ValueError(f"Pinned model file missing or changed: {local}")

    cohort = pd.read_csv(cohort_path, dtype=str, keep_default_na=False)
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    oof = pd.read_csv(oof_path, dtype=str, keep_default_na=False)
    screen = cohort.merge(
        train[["qa_id", "question", "A", "B", "C", "D", "answer"]],
        on="qa_id",
        validate="one_to_one",
    ).merge(
        oof[["qa_id", "semantic_base_prediction", "stage2_prediction"]],
        on="qa_id",
        validate="one_to_one",
    )
    if len(screen) != protocol["selection"]["rows"] or not (
        screen["semantic_base_prediction"] == screen["stage2_prediction"]
    ).all():
        raise ValueError("Missing-sensor screen is not the frozen Stage2 base-fallback cohort")

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
        if not set(completed).issubset(set(screen["qa_id"])):
            raise ValueError("Prediction log contains a row outside the frozen cohort")

    pending = screen[~screen["qa_id"].isin(completed)]
    print(json.dumps({"selected": len(screen), "complete": len(completed), "pending": len(pending)}), flush=True)
    started = time.perf_counter()
    model, processor = load(str(model_path), trust_remote_code=False)
    prompt_template = inference["prompt_template"]
    for position, row in enumerate(pending.itertuples(index=False), start=1):
        video_path = root / row.video_relative_path
        if not video_path.is_file() or sha256(video_path) != row.video_sha256:
            raise ValueError(f"Frozen video missing or changed: {video_path}")
        options = "\n".join(f"{label}. {getattr(row, label)}" for label in "ABCD")
        prompt = prompt_template.format(question=row.question, options=options)
        formatted = apply_chat_template(
            processor,
            model.config,
            prompt,
            num_images=0,
            num_audios=0,
            video=[str(video_path)],
            fps=float(inference["fps"]),
            enable_thinking=False,
        )
        mx.random.seed(SEED + position)
        item_started = time.perf_counter()
        raw = ""
        error = ""
        try:
            response = generate(
                model,
                processor,
                formatted,
                video=[str(video_path)],
                fps=float(inference["fps"]),
                temperature=float(inference["temperature"]),
                max_tokens=int(inference["max_tokens"]),
                verbose=False,
                enable_thinking=False,
            )
            raw = response.text
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        prediction = parse_prediction(raw) if not error else ""
        record = {
            "qa_id": row.qa_id,
            "path": row.path,
            "subject": int(row.subject),
            "subject_half": row.subject_half,
            "historically_observed_by_any_vlm": row.historically_observed_by_any_vlm.lower() == "true",
            "video_relative_path": row.video_relative_path,
            "video_sha256": row.video_sha256,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "raw_output": raw,
            "prediction": prediction,
            "parse_valid": bool(prediction),
            "error": error,
            "runtime_seconds": time.perf_counter() - item_started,
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        completed[row.qa_id] = record
        print(
            f"{position}/{len(pending)} {row.qa_id} pred={prediction or 'INVALID'} "
            f"seconds={record['runtime_seconds']:.2f}",
            flush=True,
        )

    results = pd.DataFrame([completed[qa_id] for qa_id in screen["qa_id"]])
    evaluation = screen[[
        "qa_id", "answer", "semantic_base_prediction", "subject_half",
        "historically_observed_by_any_vlm",
    ]].merge(results[["qa_id", "prediction", "parse_valid", "error"]], on="qa_id", validate="one_to_one")
    evaluation["qwen_correct"] = evaluation["prediction"] == evaluation["answer"]
    evaluation["base_correct"] = evaluation["semantic_base_prediction"] == evaluation["answer"]
    evaluation["historically_observed_by_any_vlm"] = evaluation["historically_observed_by_any_vlm"].map(
        lambda value: str(value).lower() == "true"
    )

    def metrics(frame: pd.DataFrame) -> dict[str, object]:
        return {
            "rows": int(len(frame)),
            "valid": int(frame["parse_valid"].sum()),
            "valid_rate": float(frame["parse_valid"].mean()),
            "qwen_correct": int(frame["qwen_correct"].sum()),
            "qwen_accuracy": float(frame["qwen_correct"].mean()),
            "base_correct": int(frame["base_correct"].sum()),
            "base_accuracy": float(frame["base_correct"].mean()),
            "net_gain": int(frame["qwen_correct"].sum() - frame["base_correct"].sum()),
        }

    overall = metrics(evaluation)
    by_half = {name: metrics(group) for name, group in evaluation.groupby("subject_half", sort=True)}
    by_history = {
        ("historically_observed" if observed else "historically_unobserved"): metrics(group)
        for observed, group in evaluation.groupby("historically_observed_by_any_vlm", sort=True)
    }
    frozen_gate = protocol["gate"]
    checks = {
        "minimum_rows": overall["rows"] >= frozen_gate["minimum_rows"],
        "valid_rate": overall["valid_rate"] >= frozen_gate["valid_rate_min"],
        "accuracy": overall["qwen_accuracy"] >= frozen_gate["accuracy_min"],
        "both_subject_halves_accuracy": set(by_half) == {"first_nine", "second_nine"}
        and all(value["qwen_accuracy"] >= frozen_gate["both_subject_halves_accuracy_min"] for value in by_half.values()),
        "does_not_reduce_core_oof": overall["net_gain"] >= 0,
    }
    passed = all(checks.values())
    report = {
        "experiment": protocol["experiment"],
        "decision": "PASS_ENABLE_QWEN_FOR_MISSING_SENSOR_HARN_SINGLE" if passed else "REJECT_KEEP_QWEN_DIAGNOSTIC_ONLY",
        "passed": passed,
        "test_qa_read": False,
        "test_prediction_written": False,
        "candidate_csv_written": False,
        "submission_performed": False,
        "network_isolation": network,
        "validation": {"overall": overall, "by_subject_half": by_half, "by_historical_visibility": by_history},
        "gate": {"frozen": frozen_gate, "checks": checks, "passed": passed},
        "artifacts": {
            "protocol_sha256": sha256(protocol_path),
            "cohort_sha256": sha256(cohort_path),
            "owned_oof_sha256": sha256(oof_path),
            "prediction_log_sha256": sha256(log_path),
            "code_sha256": sha256(Path(__file__)),
        },
        "versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
        },
        "inference_runtime_seconds": float(results["runtime_seconds"].sum()),
        "incremental_runtime_seconds": time.perf_counter() - started,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
