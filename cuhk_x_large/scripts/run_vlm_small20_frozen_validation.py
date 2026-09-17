#!/usr/bin/env python3
"""Run the pre-frozen 20-row one-video/one-question VLM validation exactly once."""

from __future__ import annotations

import hashlib
import json
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


def parse_prediction(raw: str, allowed: list[str]) -> str:
    text = raw.strip().upper()
    if re.fullmatch(r"[ABCD]", text) and text in allowed:
        return text
    matches = [token for token in re.findall(r"(?<![A-Z])[ABCD](?![A-Z])", text) if token in allowed]
    return matches[0] if len(set(matches)) == 1 else ""


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    selection_path = root / "artifacts/manifests/vlm_small20_validation.csv"
    protocol_path = root / "reports/vlm_small20_frozen_protocol.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    visual_manifest_path = root / "cache/partial_visual_manifest.json"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    output_path = root / "artifacts/vlm/qwen3_vl_4b_small20_frozen_v1.jsonl"
    report_path = root / "reports/qwen3_vl_4b_small20_frozen_v1_summary.json"

    if output_path.exists() or report_path.exists():
        raise FileExistsError("Frozen audit is single-run only; output already exists")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN_BEFORE_INFERENCE":
        raise ValueError("Protocol was not frozen before inference")
    if sha256(selection_path) != protocol["selection_file_sha256"]:
        raise ValueError("Frozen selection hash mismatch")
    selection = pd.read_csv(selection_path, dtype=str, keep_default_na=False)
    if len(selection) != 20 or selection["qa_id"].tolist() != protocol["selected_qa_ids"]:
        raise ValueError("Frozen selection content mismatch")

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    qa = selection.merge(qa, on=["qa_id", "category", "path"], validate="one_to_one")
    if len(qa) != 20:
        raise ValueError("Official QA join mismatch")
    visual_manifest = json.loads(visual_manifest_path.read_text(encoding="utf-8"))
    videos = {(item["unit"], item["modality"]): item for item in visual_manifest}

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != "apache-2.0"
    ):
        raise ValueError("Pinned model manifest mismatch")

    mx.random.seed(SEED)
    model, processor = load(str(model_path), trust_remote_code=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    implementation_failures = 0
    stopped_early = False
    run_started = time.perf_counter()
    for position, row in enumerate(qa.itertuples(index=False), start=1):
        item_started = time.perf_counter()
        video_relative_path = videos[(row.path, row.modality)]["path"]
        video_path = root / "data/raw/visual_prefix" / video_relative_path
        read_started = time.perf_counter()
        read_status = "PASS"
        parse_status = "NOT_RUN"
        failure_type = "none"
        error = ""
        raw = ""
        prediction = ""
        video_digest = ""
        try:
            if not video_path.is_file() or video_path.stat().st_size <= 0:
                raise FileNotFoundError(video_path)
            video_digest = sha256(video_path)
            if video_digest != row.video_manifest_sha256:
                raise ValueError("video SHA-256 differs from frozen manifest")
        except Exception as exc:
            read_status = "FAIL"
            failure_type = "read_error"
            error = f"{type(exc).__name__}: {exc}"
            implementation_failures += 1
        read_seconds = time.perf_counter() - read_started

        inference_seconds = 0.0
        inference_started: float | None = None
        prompt_digest = ""
        if read_status == "PASS":
            allowed = [label for label in "ABCD" if str(getattr(row, label)).strip()]
            options = "\n".join(f"{label}. {getattr(row, label)}" for label in allowed)
            template = ACTION_PROMPT_TEMPLATE if row.category == "single" else OBJECT_PROMPT_TEMPLATE
            prompt = template.format(
                question=row.question,
                options=options,
                allowed="/".join(allowed),
            )
            prompt_digest = hashlib.sha256(prompt.encode()).hexdigest()
            try:
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
                inference_started = time.perf_counter()
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
                inference_seconds = time.perf_counter() - inference_started
                raw = response.text
                prediction = parse_prediction(raw, allowed)
                parse_status = "PASS" if prediction else "INVALID_OUTPUT"
                if not prediction:
                    failure_type = "parse_invalid"
            except Exception as exc:
                inference_seconds = (
                    time.perf_counter() - inference_started
                    if inference_started is not None
                    else 0.0
                )
                parse_status = "NOT_RUN"
                failure_type = "inference_error"
                error = f"{type(exc).__name__}: {exc}"
                implementation_failures += 1

        item = {
            "position": position,
            "qa_id": row.qa_id,
            "category": row.category,
            "subject": row.subject,
            "action": row.action,
            "path": row.path,
            "modality": row.modality,
            "video_relative_path": str(video_path.relative_to(root)),
            "video_sha256": video_digest,
            "prompt_sha256": prompt_digest,
            "read_status": read_status,
            "read_seconds": read_seconds,
            "raw_output": raw,
            "parse_status": parse_status,
            "prediction": prediction,
            "answer": row.answer,
            "correct": bool(prediction and prediction == row.answer),
            "subject_disjoint_parent_prediction": row.subject_disjoint_parent_prediction,
            "subject_disjoint_parent_correct": bool(row.subject_disjoint_parent_prediction == row.answer),
            "inference_seconds": inference_seconds,
            "runtime_seconds": time.perf_counter() - item_started,
            "failure_type": failure_type,
            "error": error,
        }
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        results.append(item)
        print(
            f"{position}/20 {row.qa_id} task={row.category} read={read_status} "
            f"parse={parse_status} pred={prediction or 'INVALID'} answer={row.answer} "
            f"correct={item['correct']} failure={failure_type} seconds={item['runtime_seconds']:.2f}",
            flush=True,
        )
        if implementation_failures > 1:
            stopped_early = True
            break

    frame = pd.DataFrame(results)
    valid = frame[frame["parse_status"] == "PASS"].copy()
    subjects = protocol["selection_policy"]["subjects"]
    cohort_by_subject = {subject: "first_five" if i < 5 else "second_five" for i, subject in enumerate(subjects)}
    valid["cohort"] = valid["subject"].map(cohort_by_subject)

    def comparison(group: pd.DataFrame) -> dict[str, object]:
        vlm_correct = int(group["correct"].sum())
        parent_correct = int(group["subject_disjoint_parent_correct"].sum())
        return {
            "rows": int(len(group)),
            "vlm_correct": vlm_correct,
            "parent_correct": parent_correct,
            "net_correct": vlm_correct - parent_correct,
            "vlm_accuracy": vlm_correct / len(group) if len(group) else None,
            "parent_accuracy": parent_correct / len(group) if len(group) else None,
        }

    by_task = {category: comparison(group) for category, group in valid.groupby("category")}
    by_cohort = {cohort: comparison(group) for cohort, group in valid.groupby("cohort")}
    stability_gate = (
        set(by_task) == {"single", "object_interaction"}
        and all(item["net_correct"] > 0 for item in by_task.values())
        and set(by_cohort) == {"first_five", "second_five"}
        and all(item["net_correct"] > 0 for item in by_cohort.values())
    )
    implementation_failure_rate = implementation_failures / 20
    implementation_gate = implementation_failure_rate <= 0.05 and not stopped_early
    report = {
        "experiment": "qwen3_vl_4b_small20_frozen_v1",
        "protocol_sha256": sha256(protocol_path),
        "selection_sha256": sha256(selection_path),
        "planned_rows": 20,
        "processed_rows": len(results),
        "valid_predictions": len(valid),
        "invalid_outputs": int((frame["failure_type"] == "parse_invalid").sum()),
        "implementation_failures": implementation_failures,
        "implementation_failure_rate_on_planned_batch": implementation_failure_rate,
        "implementation_gate": "PASS" if implementation_gate else "FAIL_REPAIR_REQUIRED",
        "stopped_early": stopped_early,
        "overall": comparison(valid),
        "by_task": by_task,
        "by_fixed_subject_cohort": by_cohort,
        "cross_task_and_cohort_stability_gate": stability_gate,
        "label_free_test_rule_defined_by_this_audit": False,
        "candidate_decision": "NO_PROPOSAL",
        "candidate_reason": (
            "The audit is diagnostic only and defines no new label-free test-time override rule. "
            "The 0.78070 public score is contextual and is not directly comparable to this local batch."
        ),
        "online_anchor_public_score_context": "0.78070",
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "manifest_sha256": sha256(model_manifest_path),
            "seed": SEED,
            "fps": FPS,
            "max_tokens": MAX_TOKENS,
            "temperature": 0.0,
        },
        "prediction_log_sha256": sha256(output_path),
        "code_sha256": sha256(Path(__file__)),
        "runtime_seconds": time.perf_counter() - run_started,
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"report_sha256={sha256(report_path)}", flush=True)


if __name__ == "__main__":
    main()
