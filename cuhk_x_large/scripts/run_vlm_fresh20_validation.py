#!/usr/bin/env python3
"""Run the pre-frozen, genuinely unseen 20-row VLM screen exactly once."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from pathlib import Path

import mlx.core as mx
import pandas as pd
from mlx_vlm import apply_chat_template, generate, load


SEED = 20260910
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


def exact_positive_sign_p(positive: int, negative: int) -> float | None:
    discordant = positive + negative
    if discordant == 0:
        return None
    return sum(math.comb(discordant, k) for k in range(positive, discordant + 1)) / (2**discordant)


def comparison(frame: pd.DataFrame) -> dict[str, object]:
    vlm_correct = int(frame["correct"].sum())
    parent_correct = int(frame["subject_disjoint_parent_correct"].sum())
    return {
        "rows": int(len(frame)),
        "vlm_correct": vlm_correct,
        "parent_correct": parent_correct,
        "net_correct": vlm_correct - parent_correct,
        "vlm_accuracy": vlm_correct / len(frame) if len(frame) else None,
        "parent_accuracy": parent_correct / len(frame) if len(frame) else None,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    selection_path = root / "artifacts/manifests/vlm_fresh20_validation.csv"
    protocol_path = root / "reports/vlm_fresh20_frozen_protocol.json"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    visual_manifest_path = root / "cache/harn_visual_manifest.json"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    output_path = root / "artifacts/vlm/qwen3_vl_4b_fresh20_v1.jsonl"
    report_path = root / "reports/qwen3_vl_4b_fresh20_v1_summary.json"
    if output_path.exists() or report_path.exists():
        raise FileExistsError("Fresh20 is immutable and single-run only")

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN_BEFORE_FIRST_EVER_VLM_INFERENCE":
        raise ValueError("Fresh20 protocol status mismatch")
    if sha256(selection_path) != protocol["selection_file_sha256"]:
        raise ValueError("Fresh20 selection hash mismatch")
    selection = pd.read_csv(selection_path, dtype=str, keep_default_na=False)
    if (
        len(selection) != 20
        or selection["qa_id"].tolist() != protocol["selected_qa_ids"]
        or selection["path"].tolist() != protocol["selected_clips"]
    ):
        raise ValueError("Fresh20 selection content mismatch")

    historical_ids: set[str] = set()
    historical_clips: set[str] = set()
    for item in protocol["freshness"]["historical_artifacts_frozen_at_selection"]:
        path = root / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Historical VLM artifact changed after freeze: {item['path']}")
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            historical_ids.add(str(row.get("qa_id", "")))
            historical_clips.add(str(row.get("path", "")))
    if set(selection["qa_id"]) & historical_ids or set(selection["path"]) & historical_clips:
        raise ValueError("Fresh20 QA or clip existed in historical VLM artifacts")

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    qa = selection.merge(qa, on=["qa_id", "category", "path"], validate="one_to_one")
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
        video_path = root / "data/raw/visual_harn" / video_relative_path
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
                raise ValueError("video SHA-256 differs from frozen selection")
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
            prompt = template.format(question=row.question, options=options, allowed="/".join(allowed))
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
                inference_seconds = time.perf_counter() - inference_started if inference_started else 0.0
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
            f"{position}/20 {row.qa_id} task={row.category} subject={row.subject} "
            f"read={read_status} parse={parse_status} pred={prediction or 'INVALID'} "
            f"answer={row.answer} correct={item['correct']} parent_correct={item['subject_disjoint_parent_correct']} "
            f"failure={failure_type} seconds={item['runtime_seconds']:.2f}",
            flush=True,
        )
        if implementation_failures > 1:
            stopped_early = True
            break

    frame = pd.DataFrame(results)
    valid = frame[frame["parse_status"] == "PASS"].copy()
    subject_order = protocol["selection_policy"]["subjects"]
    cohort = {subject: "first_five" if i < 5 else "second_five" for i, subject in enumerate(subject_order)}
    valid["cohort"] = valid["subject"].map(cohort)
    subject_stats = valid.groupby("subject").apply(comparison, include_groups=False).to_dict()
    subject_deltas = {subject: int(values["net_correct"]) for subject, values in subject_stats.items()}
    positive = sum(delta > 0 for delta in subject_deltas.values())
    negative = sum(delta < 0 for delta in subject_deltas.values())
    ties = sum(delta == 0 for delta in subject_deltas.values())
    sign_p = exact_positive_sign_p(positive, negative)
    by_task = {task: comparison(group) for task, group in valid.groupby("category")}
    by_cohort = {name: comparison(group) for name, group in valid.groupby("cohort")}
    implementation_gate = implementation_failures <= 1 and not stopped_early and len(results) == 20
    primary_gate = sign_p is not None and sign_p <= 0.05
    no_negative_subject_gate = negative == 0 and len(subject_deltas) == 10
    task_gate = set(by_task) == {"single", "object_interaction"} and all(
        values["net_correct"] > 0 for values in by_task.values()
    )
    cohort_gate = set(by_cohort) == {"first_five", "second_five"} and all(
        values["net_correct"] > 0 for values in by_cohort.values()
    )
    screen_pass = all([implementation_gate, primary_gate, no_negative_subject_gate, task_gate, cohort_gate])
    decision = "SCREEN_PASS_LARGER_FRESH_VALIDATION_REQUIRED" if screen_pass else "REJECT_AND_REFREEZE_VLM"
    report = {
        "experiment": "qwen3_vl_4b_fresh20_v1",
        "freshness_status": "20_QA_AND_CLIPS_FIRST_EVER_VLM_INFERENCE",
        "protocol_sha256": sha256(protocol_path),
        "selection_sha256": sha256(selection_path),
        "processed_rows": len(results),
        "valid_predictions": len(valid),
        "invalid_outputs": int((frame["failure_type"] == "parse_invalid").sum()),
        "implementation_failures": implementation_failures,
        "stopped_early": stopped_early,
        "overall": comparison(valid),
        "by_task": by_task,
        "by_fixed_subject_cohort": by_cohort,
        "by_subject": subject_stats,
        "subject_sign_test": {
            "positive_subjects": positive,
            "negative_subjects": negative,
            "tied_subjects": ties,
            "one_sided_exact_positive_sign_p": sign_p,
        },
        "precommitted_gate_results": {
            "implementation_gate": implementation_gate,
            "primary_subject_sign_p_le_0_05": primary_gate,
            "no_negative_subject": no_negative_subject_gate,
            "both_tasks_net_positive": task_gate,
            "both_fixed_cohorts_net_positive": cohort_gate,
            "all_gates": screen_pass,
        },
        "decision": decision,
        "candidate": "NONE",
        "submission": "PROHIBITED",
        "next_step": (
            "Freeze a larger genuinely fresh subject-disjoint validation set before any promotion."
            if screen_pass
            else "Keep VLM direct/router direction frozen; do not mine this screen for a new rule."
        ),
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
    print(json.dumps(report, indent=2))
    print(f"report_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
