#!/usr/bin/env python3
"""Run the immutable HAU temporal-localization comparison; never submit.

The experiment uses one shared, question-conditioned 8-frame localization
call.  The two answer arms then see either 16 uniform frames or 16 frames
dense-sampled around the frozen localizer's indices.  Model and token budgets
are identical between answer arms.  No Kaggle API is called.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd


SEED = 20260911
MODEL_REPO = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
MODEL_REVISION = "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b"
COARSE_FRAMES = 8
FINE_FRAMES = 16
COARSE_MAX_TOKENS = 64
ANSWER_MAX_TOKENS = 32
VIDEO_FPS = 4.0
RUN_PREFIX = "temporal_vlm_preregistered50_instruct4b_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def uniform_indices(total_frames: int, count: int) -> list[int]:
    if total_frames < count:
        raise ValueError(f"Video has only {total_frames} frames; fixed budget requires {count}")
    if count == 1:
        return [total_frames // 2]
    return [round(index * (total_frames - 1) / (count - 1)) for index in range(count)]


def localized_indices(total_frames: int, coarse_locations: list[int]) -> list[int]:
    centers = sorted(set(coarse_locations))[:2]
    if not centers:
        raise ValueError("No parsed coarse location")
    per_center = FINE_FRAMES // len(centers)
    radius = max(per_center, round(total_frames * 0.12))
    picked: list[int] = []
    for coarse_index in centers:
        center = round(coarse_index * (total_frames - 1) / (COARSE_FRAMES - 1))
        start = max(0, center - radius)
        end = min(total_frames - 1, center + radius)
        for offset in range(per_center):
            position = start if per_center == 1 else round(start + offset * (end - start) / (per_center - 1))
            if position not in picked:
                picked.append(position)
    # Deterministically expand around the selected windows if rounding/overlap removed frames.
    candidates = sorted(
        range(total_frames),
        key=lambda value: (min(abs(value - existing) for existing in picked), value),
    )
    for value in candidates:
        if value not in picked:
            picked.append(value)
        if len(picked) == FINE_FRAMES:
            break
    return sorted(picked[:FINE_FRAMES])


def video_metadata(video_path: Path) -> tuple[int, float]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=nb_frames,avg_frame_rate:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    data = json.loads(subprocess.check_output(command, text=True))
    stream = data["streams"][0]
    duration = float(data["format"]["duration"])
    raw_frames = stream.get("nb_frames")
    if raw_frames and str(raw_frames).isdigit():
        frames = int(raw_frames)
    else:
        numerator, denominator = str(stream["avg_frame_rate"]).split("/")
        fps = float(numerator) / float(denominator)
        frames = round(duration * fps)
    if frames <= 0 or duration <= 0:
        raise ValueError(f"Invalid video metadata for {video_path}")
    return frames, duration


def make_sample_video(source: Path, indices: list[int], output: Path) -> None:
    expression = "+".join(f"eq(n,{index})" for index in indices)
    vf = (
        f"select='{expression}',setpts=N/({VIDEO_FPS}*TB),"
        "scale=448:-2:force_original_aspect_ratio=decrease"
    )
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(source),
        "-vf",
        vf,
        "-an",
        "-r",
        str(VIDEO_FPS),
        "-frames:v",
        str(len(indices)),
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]
    subprocess.run(command, check=True)
    observed, _ = video_metadata(output)
    if observed != len(indices):
        raise ValueError(f"Sample video frame count {observed} != {len(indices)}")


def parse_locations(raw: str) -> list[int]:
    matches = re.findall(r"LOC\s*:\s*([0-7])(?:\s*[, ]\s*([0-7]))?", raw.upper())
    if not matches:
        return []
    first, second = matches[-1]
    return sorted(set([int(first)] + ([int(second)] if second else [])))


def parse_answer(raw: str, category: str, allowed: list[str]) -> str:
    matches = re.findall(r"FINAL\s*:\s*([ABCD]{1,4})", raw.upper())
    if not matches:
        return ""
    value = matches[-1]
    if category in {"single", "emotion", "combination"}:
        return value if len(value) == 1 and value in allowed else ""
    if category == "multi":
        return value if value == "".join(sorted(set(value))) and set(value).issubset(allowed) else ""
    if category == "sequence":
        return value if len(value) == len(allowed) and set(value) == set(allowed) else ""
    raise ValueError(category)


def locate_prompt(row: object) -> str:
    options = "\n".join(
        f"{label}. {getattr(row, label)}" for label in "ABCD" if str(getattr(row, label)).strip()
    )
    return f"""You see 8 chronological frames labeled 0 through 7 from a depth video.
Use the question and options to identify one or two frame regions that contain the decisive visual evidence.
For sequence questions, span the relevant action interval; for other questions, select the most discriminative moments.
Question: {row.question}
{options}
End with exactly LOC: i,j using one or two indices from 0 to 7."""


def answer_prompt(row: object) -> str:
    allowed = [label for label in "ABCD" if str(getattr(row, label)).strip()]
    options = "\n".join(f"{label}. {getattr(row, label)}" for label in allowed)
    if row.category == "sequence":
        output = "all option letters once, in chronological order"
    elif row.category == "multi":
        output = "all selected option letters in alphabetical order"
    else:
        output = "one option letter"
    return f"""Answer the video question using only visible evidence.
Question: {row.question}
{options}
End with exactly FINAL: <answer>, where <answer> is {output}."""


def vlm_call(
    model: object,
    processor: object,
    prompt: str,
    video: Path,
    max_tokens: int,
    apply_chat_template: Any,
    generate: Any,
) -> tuple[str, float]:
    formatted = apply_chat_template(
        processor,
        model.config,
        prompt,
        num_images=0,
        num_audios=0,
        video=[str(video)],
        fps=VIDEO_FPS,
        enable_thinking=False,
    )
    started = time.perf_counter()
    response = generate(
        model,
        processor,
        formatted,
        video=[str(video)],
        fps=VIDEO_FPS,
        temperature=0.0,
        max_tokens=max_tokens,
        verbose=False,
        enable_thinking=False,
    )
    return response.text, time.perf_counter() - started


def comparison(frame: pd.DataFrame) -> dict[str, object]:
    localized_correct = int(frame["localized_correct"].sum())
    uniform_correct = int(frame["uniform_correct"].sum())
    return {
        "rows": int(len(frame)),
        "localized_correct": localized_correct,
        "uniform_correct": uniform_correct,
        "net_correct": localized_correct - uniform_correct,
        "localized_accuracy": localized_correct / len(frame) if len(frame) else None,
        "uniform_accuracy": uniform_correct / len(frame) if len(frame) else None,
    }


def find_visual_root(root: Path) -> Path:
    candidates = [
        root / "data/raw/visual_hau",
        root / "data/raw/visual_hau_full",
        root / "data/raw/visual_hau_prefix",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("No HAU visual root is available")


def load_jsonl(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    return {
        str(item["qa_id"]): item
        for item in (
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    selection_path = root / "artifacts/manifests/temporal_vlm_preregistered50.csv"
    protocol_path = root / "reports/temporal_vlm_preregistered50_protocol.json"
    lock_path = root / "reports/temporal_vlm_preregistered50_protocol.sha256"
    qa_path = root / "data/raw/kaggle/training_qa.csv"
    parent_path = root / "artifacts/oof/public_graph_leave_one_subject_out.csv"
    model_path = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    model_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    locator_log_path = root / f"artifacts/vlm/{RUN_PREFIX}_locator.jsonl"
    uniform_log_path = root / f"artifacts/vlm/{RUN_PREFIX}_uniform.jsonl"
    localized_log_path = root / f"artifacts/vlm/{RUN_PREFIX}_localized.jsonl"
    report_path = root / f"reports/{RUN_PREFIX}_summary.json"
    rejection_path = root / f"reports/{RUN_PREFIX}_rejection.json"
    candidate_path = root / f"submissions/{RUN_PREFIX}_candidate.csv"
    if report_path.exists() or rejection_path.exists() or candidate_path.exists():
        raise FileExistsError("Temporal-VLM experiment already has a terminal artifact")

    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected_protocol_hash = lock_path.read_text(encoding="utf-8").strip().split()[0]
    if sha256(protocol_path) != expected_protocol_hash:
        raise ValueError("Protocol hash lock mismatch")
    if protocol.get("status") != "FROZEN_BEFORE_ANY_TEMPORAL_LOCALIZATION_OR_NEW_VLM_INFERENCE":
        raise ValueError("Protocol status mismatch")
    if sha256(selection_path) != protocol["selection_file_sha256"]:
        raise ValueError("Frozen selection hash mismatch")
    if sha256(Path(__file__)) != protocol["inputs"]["runner_sha256"]:
        raise ValueError("Runner changed after preregistration")
    if sha256(qa_path) != protocol["inputs"]["training_qa_sha256"]:
        raise ValueError("training_qa.csv changed after preregistration")
    if sha256(parent_path) != protocol["inputs"]["subject_disjoint_parent_oof_sha256"]:
        raise ValueError("Parent OOF changed after preregistration")
    if sha256(model_manifest_path) != protocol["inputs"]["model_manifest_sha256"]:
        raise ValueError("Model manifest changed after preregistration")

    selection = pd.read_csv(selection_path, dtype=str, keep_default_na=False)
    if (
        len(selection) != 50
        or selection["qa_id"].tolist() != protocol["selected_qa_ids"]
        or selection["path"].tolist() != protocol["selected_clips"]
    ):
        raise ValueError("Frozen cohort content mismatch")

    # Revalidate the full historical snapshot and prohibit overlap with any later VLM log.
    selected_ids = set(selection["qa_id"])
    selected_clips = set(selection["path"])
    snapshotted = {item["path"] for item in protocol["freshness"]["historical_artifacts_frozen_at_selection"]}
    for item in protocol["freshness"]["historical_artifacts_frozen_at_selection"]:
        path = root / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Historical VLM artifact changed: {item['path']}")
    own_logs = {locator_log_path, uniform_log_path, localized_log_path}
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        if path in own_logs:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if str(item.get("qa_id", "")) in selected_ids or str(item.get("path", "")) in selected_clips:
                raise ValueError(f"Frozen QA/clip was exposed after preregistration in {path}")
        if str(path.relative_to(root)) not in snapshotted:
            raise ValueError(f"Unsnapshotted VLM log appeared after preregistration: {path}")

    model_manifest = json.loads(model_manifest_path.read_text(encoding="utf-8"))
    if (
        model_manifest.get("repo_id") != MODEL_REPO
        or model_manifest.get("revision") != MODEL_REVISION
        or model_manifest.get("license") != "apache-2.0"
    ):
        raise ValueError("Pinned local model does not match protocol")

    qa = pd.read_csv(qa_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    rows = selection.merge(qa, on=["qa_id", "category", "path"], validate="one_to_one")
    if rows["qa_id"].tolist() != selection["qa_id"].tolist():
        raise ValueError("Merge changed frozen row order")
    visual_root = find_visual_root(root)
    for row in rows.itertuples(index=False):
        video_path = visual_root / row.expected_depth_relpath
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            raise FileNotFoundError(
                f"Frozen video unavailable: {video_path}. Full official HAU Depth extraction is required."
            )

    import mlx.core as mx
    from mlx_vlm import apply_chat_template, generate, load

    completed_locator = load_jsonl(locator_log_path)
    completed_uniform = load_jsonl(uniform_log_path)
    completed_localized = load_jsonl(localized_log_path)
    run_started = time.perf_counter()
    mx.random.seed(SEED)
    model, processor = load(str(model_path), trust_remote_code=False)
    after_load = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="cuhk-temporal-vlm-") as temp_dir:
        temporary = Path(temp_dir)
        for position, row in enumerate(rows.itertuples(index=False), start=1):
            if row.qa_id in completed_locator and row.qa_id in completed_uniform and row.qa_id in completed_localized:
                continue
            source = visual_root / row.expected_depth_relpath
            total_frames, duration = video_metadata(source)
            source_hash = sha256(source)
            coarse_indices = uniform_indices(total_frames, COARSE_FRAMES)
            uniform_fine_indices = uniform_indices(total_frames, FINE_FRAMES)
            coarse_video = temporary / f"{row.qa_id}_coarse.mp4"
            uniform_video = temporary / f"{row.qa_id}_uniform.mp4"
            localized_video = temporary / f"{row.qa_id}_localized.mp4"
            make_sample_video(source, coarse_indices, coarse_video)

            locator_prompt = locate_prompt(row)
            locator_error = ""
            locator_raw = ""
            locator_runtime = 0.0
            locations: list[int] = []
            try:
                mx.random.seed(SEED + position)
                locator_raw, locator_runtime = vlm_call(
                    model,
                    processor,
                    locator_prompt,
                    coarse_video,
                    COARSE_MAX_TOKENS,
                    apply_chat_template,
                    generate,
                )
                locations = parse_locations(locator_raw)
            except Exception as exc:
                locator_error = f"{type(exc).__name__}: {exc}"
            locator_item = {
                "qa_id": row.qa_id,
                "path": row.path,
                "category": row.category,
                "subject": row.subject,
                "subject_half": row.subject_half,
                "source_video_relative_path": str(source.relative_to(root)),
                "source_video_sha256": source_hash,
                "source_total_frames": total_frames,
                "source_duration_seconds": duration,
                "coarse_frame_indices": coarse_indices,
                "coarse_video_sha256": sha256(coarse_video),
                "prompt_sha256": hashlib.sha256(locator_prompt.encode()).hexdigest(),
                "raw_output": locator_raw,
                "locations": locations,
                "parse_valid": bool(locations),
                "runtime_seconds": locator_runtime,
                "error": locator_error,
            }
            with locator_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(locator_item, ensure_ascii=False) + "\n")
            completed_locator[row.qa_id] = locator_item
            if locator_error or not locations:
                print(f"{position}/50 {row.qa_id} locator invalid; no answer arms run", flush=True)
                continue

            local_fine_indices = localized_indices(total_frames, locations)
            make_sample_video(source, uniform_fine_indices, uniform_video)
            make_sample_video(source, local_fine_indices, localized_video)
            prompt = answer_prompt(row)
            allowed = [label for label in "ABCD" if str(getattr(row, label)).strip()]
            for arm, sample_video, frame_indices, completed, output_path in (
                ("uniform", uniform_video, uniform_fine_indices, completed_uniform, uniform_log_path),
                ("localized", localized_video, local_fine_indices, completed_localized, localized_log_path),
            ):
                if row.qa_id in completed:
                    continue
                raw = ""
                runtime = 0.0
                error = ""
                prediction = ""
                try:
                    mx.random.seed(SEED + position)
                    raw, runtime = vlm_call(
                        model,
                        processor,
                        prompt,
                        sample_video,
                        ANSWER_MAX_TOKENS,
                        apply_chat_template,
                        generate,
                    )
                    prediction = parse_answer(raw, row.category, allowed)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                item = {
                    "qa_id": row.qa_id,
                    "path": row.path,
                    "category": row.category,
                    "subject": row.subject,
                    "subject_half": row.subject_half,
                    "arm": arm,
                    "source_video_sha256": source_hash,
                    "frame_indices": frame_indices,
                    "sample_video_sha256": sha256(sample_video),
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "raw_output": raw,
                    "prediction": prediction,
                    "answer": row.answer,
                    "correct": bool(prediction and prediction == row.answer),
                    "subject_disjoint_parent_prediction": row.subject_disjoint_parent_prediction,
                    "subject_disjoint_parent_correct": bool(
                        row.subject_disjoint_parent_prediction == row.answer
                    ),
                    "parse_valid": bool(prediction),
                    "runtime_seconds": runtime,
                    "error": error,
                }
                with output_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
                completed[row.qa_id] = item
            print(
                f"{position}/50 {row.qa_id} task={row.category} loc={locations} "
                f"uniform={completed_uniform.get(row.qa_id, {}).get('prediction', 'INVALID')} "
                f"localized={completed_localized.get(row.qa_id, {}).get('prediction', 'INVALID')}",
                flush=True,
            )

    locators = pd.DataFrame(completed_locator.values())
    uniform = pd.DataFrame(completed_uniform.values())
    localized = pd.DataFrame(completed_localized.values())
    processed = len(uniform) == len(localized) == 50
    if processed:
        joined = uniform[["qa_id", "prediction", "correct", "error", "parse_valid"]].rename(
            columns={
                "prediction": "uniform_prediction",
                "correct": "uniform_correct",
                "error": "uniform_error",
                "parse_valid": "uniform_parse_valid",
            }
        ).merge(
            localized[
                [
                    "qa_id",
                    "prediction",
                    "correct",
                    "error",
                    "parse_valid",
                    "subject_disjoint_parent_prediction",
                    "subject_disjoint_parent_correct",
                ]
            ].rename(
                columns={
                    "prediction": "localized_prediction",
                    "correct": "localized_correct",
                    "error": "localized_error",
                    "parse_valid": "localized_parse_valid",
                }
            ),
            on="qa_id",
            validate="one_to_one",
        ).merge(selection, on="qa_id", validate="one_to_one")
    else:
        joined = pd.DataFrame()

    implementation_gate = bool(
        processed
        and len(locators) == 50
        and int(locators["parse_valid"].sum()) >= 48
        and not locators["error"].astype(bool).any()
        and not uniform["error"].astype(bool).any()
        and not localized["error"].astype(bool).any()
        and uniform["parse_valid"].all()
        and localized["parse_valid"].all()
    )
    if processed:
        overall = comparison(joined)
        by_task = {name: comparison(group) for name, group in joined.groupby("category")}
        by_half = {name: comparison(group) for name, group in joined.groupby("subject_half")}
        temporal = joined[joined["category"].isin(["sequence", "combination", "multi"])]
        temporal_stats = comparison(temporal)
        disagreement = joined[
            joined["localized_prediction"] != joined["subject_disjoint_parent_prediction_y"]
        ].copy()
        disagreement_stats = {
            "rows": int(len(disagreement)),
            "localized_correct": int(disagreement["localized_correct"].sum()),
            "parent_correct": int(disagreement["subject_disjoint_parent_correct"].sum()),
            "localized_accuracy": float(disagreement["localized_correct"].mean()) if len(disagreement) else None,
            "parent_accuracy": float(disagreement["subject_disjoint_parent_correct"].mean()) if len(disagreement) else None,
        }
        primary_gate = temporal_stats["net_correct"] >= 3
        overall_gate = overall["net_correct"] >= 0
        temporal_task_stats = [by_task[name] for name in ("sequence", "combination", "multi")]
        task_gate = all(item["net_correct"] >= 0 for item in temporal_task_stats) and sum(
            item["net_correct"] > 0 for item in temporal_task_stats
        ) >= 2
        half_gate = set(by_half) == {"A_user1_9", "B_user16_24"} and all(
            item["net_correct"] > 0 for item in by_half.values()
        )
        disagreement_gate = bool(
            len(disagreement) >= 10
            and disagreement_stats["localized_accuracy"] >= 0.60
            and disagreement_stats["parent_accuracy"] <= 0.40
        )
    else:
        overall = {}
        by_task = {}
        by_half = {}
        temporal_stats = {}
        disagreement_stats = {}
        primary_gate = overall_gate = task_gate = half_gate = disagreement_gate = False

    operational_seconds = time.perf_counter() - after_load
    operational_gate = operational_seconds <= 7200
    all_gates = all(
        [
            implementation_gate,
            primary_gate,
            overall_gate,
            task_gate,
            half_gate,
            disagreement_gate,
            operational_gate,
        ]
    )
    decision = (
        "VALIDATION_PASS_TEST_FREEZE_REQUIRED"
        if all_gates
        else "REJECT_TEMPORAL_LOCALIZATION_NO_CANDIDATE"
    )
    report = {
        "experiment": RUN_PREFIX,
        "protocol_sha256": sha256(protocol_path),
        "selection_sha256": sha256(selection_path),
        "freshness": "50 QA ids and 50 clips absent from every prior VLM log",
        "model": {
            "repo_id": MODEL_REPO,
            "revision": MODEL_REVISION,
            "license": "apache-2.0",
            "manifest_sha256": sha256(model_manifest_path),
        },
        "budget": {
            "shared_coarse_frames": COARSE_FRAMES,
            "fine_frames_per_arm": FINE_FRAMES,
            "coarse_max_tokens": COARSE_MAX_TOKENS,
            "answer_max_tokens_per_arm": ANSWER_MAX_TOKENS,
            "temperature": 0.0,
        },
        "processed_rows": int(len(uniform)),
        "locator_valid": int(locators["parse_valid"].sum()) if len(locators) else 0,
        "uniform_invalid": int((~uniform["parse_valid"]).sum()) if len(uniform) else 0,
        "localized_invalid": int((~localized["parse_valid"]).sum()) if len(localized) else 0,
        "overall": overall,
        "temporal_primary": temporal_stats,
        "by_task": by_task,
        "by_subject_half": by_half,
        "localized_parent_disagreement": disagreement_stats,
        "gate_results": {
            "implementation": implementation_gate,
            "primary_temporal_plus_3_of_30": primary_gate,
            "overall_nonnegative": overall_gate,
            "temporal_tasks_stable": task_gate,
            "both_subject_halves_positive": half_gate,
            "parent_disagreement": disagreement_gate,
            "runtime_within_2h": operational_gate,
            "all": all_gates,
        },
        "decision": decision,
        "candidate": "NONE; validation pass still requires a separately frozen full-test run",
        "submission": "PROHIBITED_AND_NOT_ATTEMPTED",
        "logs": {
            "locator": str(locator_log_path.relative_to(root)),
            "uniform": str(uniform_log_path.relative_to(root)),
            "localized": str(localized_log_path.relative_to(root)),
        },
        "log_sha256": {
            "locator": sha256(locator_log_path) if locator_log_path.is_file() else None,
            "uniform": sha256(uniform_log_path) if uniform_log_path.is_file() else None,
            "localized": sha256(localized_log_path) if localized_log_path.is_file() else None,
        },
        "versions": {
            "mlx": importlib.metadata.version("mlx"),
            "mlx_vlm": importlib.metadata.version("mlx-vlm"),
            "pandas": pd.__version__,
            "ffmpeg": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        },
        "model_load_seconds": after_load - run_started,
        "operational_seconds_after_model_load": operational_seconds,
        "total_seconds": time.perf_counter() - run_started,
        "code_sha256": sha256(Path(__file__)),
    }
    terminal_path = report_path if all_gates else rejection_path
    terminal_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"terminal_artifact={terminal_path.relative_to(root)} sha256={sha256(terminal_path)}")


if __name__ == "__main__":
    main()
