#!/usr/bin/env python3
"""Build a Stage2-native CUHK-X candidate without any frozen test vector.

Every prediction is generated from the current train/test QA, organizer media,
and organizer sensor features.  The public Fususu 682-row artifact is neither
read nor imported.  Test VLM inference and candidate creation are gated behind
a preregistered, genuinely unseen 48-row HARn screen.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import math
import os
import re
import socket
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


SEED = 20260911
LABELS = "ABCD"
USERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 21, 22, 23, 24]
MODEL_REPO = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
MODEL_REVISION = "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b"
FIXED_FRAMES = 8
MAX_TOKENS = 8
SINGLE_SENSOR_MARGIN = 0.15
OBJECT_SENSOR_MARGIN = 0.05
RUN_NAME = "harn_stage2_native_v1"
SINGLE_OUTPUT = {"single", "combination", "emotion", "object_interaction"}
MODALITIES = {"depth", "depth_color", "ir", "thermal", "imu", "skeleton", "radar"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def clip_key(path: str) -> str:
    parts = [part for part in str(path).replace("\\", "/").split("/") if part]
    if len(parts) >= 2 and parts[-2].lower() in MODALITIES and Path(parts[-1]).stem.lower() in MODALITIES:
        parts = parts[:-2]
    return "/".join(parts)


def user_from_path(path: str) -> int:
    match = re.search(r"(?:^|/)user(\d+)(?:/|$)", str(path), flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"No subject in {path}")
    return int(match.group(1))


def atoms(value: object) -> tuple[str, ...]:
    return tuple(norm(piece) for piece in str(value).split(",") if piece.strip())


class OwnedClipDecoder:
    """Small deterministic train-native floor with no embedded test predictions."""

    def __init__(self, smoothing: float = 8.0, support_weight: float = 1.0):
        self.smoothing = smoothing
        self.support_weight = support_weight
        self.option_ok: Counter[tuple[str, str, str]] = Counter()
        self.option_n: Counter[tuple[str, str, str]] = Counter()
        self.slice_ok: Counter[tuple[str, str]] = Counter()
        self.slice_n: Counter[tuple[str, str]] = Counter()
        self.set_memory: defaultdict[tuple[str, str, tuple[str, ...]], Counter[str]] = defaultdict(Counter)
        self.multi_sizes: defaultdict[tuple[str, str], Counter[int]] = defaultdict(Counter)
        self.before: Counter[tuple[str, str]] = Counter()

    def fit(self, frame: pd.DataFrame) -> "OwnedClipDecoder":
        for row in frame.itertuples(index=False):
            answer = str(row.answer).strip().upper()
            source, category = str(row.source), str(row.category)
            options = [str(getattr(row, label)) for label in LABELS]
            option_set = tuple(sorted(map(norm, options)))
            slice_key = (source, category)
            if category != "sequence":
                for label, value in zip(LABELS, options):
                    key = (source, category, norm(value))
                    self.option_n[key] += 1
                    self.slice_n[slice_key] += 1
                    if label in answer:
                        self.option_ok[key] += 1
                        self.slice_ok[slice_key] += 1
            if category == "multi":
                self.multi_sizes[slice_key][len(answer)] += 1
            elif category == "sequence" and set(answer) == set(LABELS):
                ordered = tuple(norm(getattr(row, label)) for label in answer)
                for index, left in enumerate(ordered):
                    for right in ordered[index + 1 :]:
                        self.before[(left, right)] += 1
            else:
                for label in answer:
                    if label in LABELS:
                        self.set_memory[(source, category, option_set)][norm(getattr(row, label))] += 1
        return self

    def _logit(self, row: object, value: str) -> float:
        slice_key = (str(row.source), str(row.category))
        base = self.slice_ok[slice_key] / max(1, self.slice_n[slice_key])
        key = (str(row.source), str(row.category), norm(value))
        probability = (self.option_ok[key] + self.smoothing * base) / (self.option_n[key] + self.smoothing)
        probability = min(max(probability, 1e-6), 1 - 1e-6)
        return math.log(probability / (1 - probability))

    def _sequence(self, row: object) -> str:
        scored: list[tuple[float, str]] = []
        for labels in itertools.permutations(LABELS):
            text = [norm(getattr(row, label)) for label in labels]
            score = 0.0
            for index, left in enumerate(text):
                for right in text[index + 1 :]:
                    forward = self.before[(left, right)]
                    reverse = self.before[(right, left)]
                    score += math.log((forward + 1.5) / (forward + reverse + 3.0))
            scored.append((score, "".join(labels)))
        return max(scored)[1]

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        grouped: defaultdict[str, list[object]] = defaultdict(list)
        for row in frame.itertuples(index=False):
            grouped[clip_key(str(row.path))].append(row)
        output: dict[str, str] = {}
        for group in grouped.values():
            support: Counter[str] = Counter()
            for row in group:
                if row.source == "HAU" and row.category in {"single", "multi", "combination", "sequence"}:
                    values = [getattr(row, label) for label in LABELS]
                    if row.category == "combination":
                        for value in values:
                            support.update(atoms(value))
                    else:
                        support.update(map(norm, values))
            for row in group:
                if row.category == "sequence":
                    output[row.qa_id] = self._sequence(row)
                    continue
                values = [str(getattr(row, label)) for label in LABELS]
                option_set = tuple(sorted(map(norm, values)))
                memory = self.set_memory[(row.source, row.category, option_set)]
                scores: list[float] = []
                for value in values:
                    own = Counter(atoms(value) if row.category == "combination" else [norm(value)])
                    external = sum(max(0, support[key] - own[key]) for key in own)
                    scores.append(self._logit(row, value) + math.log1p(memory[norm(value)]) + self.support_weight * external)
                if row.category == "multi":
                    sizes = self.multi_sizes[(row.source, row.category)]
                    count = max(sizes, key=lambda number: (sizes[number], -number)) if sizes else 1
                    chosen = sorted(range(4), key=lambda index: (-scores[index], index))[:count]
                    output[row.qa_id] = "".join(LABELS[index] for index in sorted(chosen))
                else:
                    output[row.qa_id] = LABELS[max(range(4), key=lambda index: (scores[index], -index))]
        return pd.DataFrame({"qa_id": frame["qa_id"], "base_prediction": frame["qa_id"].map(output)})


def base_oof(train: pd.DataFrame) -> pd.DataFrame:
    data = train.copy()
    data["user"] = data["path"].map(user_from_path)
    if sorted(data["user"].unique()) != USERS or data.groupby(data["path"].map(clip_key))["user"].nunique().max() != 1:
        raise ValueError("Subject/clip fold invariant failed")
    outputs: list[pd.DataFrame] = []
    for user in USERS:
        fit = data[data["user"] != user].drop(columns="user")
        hold = data[data["user"] == user].drop(columns="user")
        pred = OwnedClipDecoder().fit(fit).predict(hold)
        part = hold[["qa_id", "source", "category", "path", "answer"]].merge(pred, on="qa_id", validate="one_to_one")
        part["user"] = user
        outputs.append(part)
    return pd.concat(outputs, ignore_index=True)


def model_paths(root: Path) -> tuple[Path, Path]:
    return (
        root / "cache/models/Qwen3-VL-4B-Instruct-4bit",
        root / "reports/qwen3_vl_4b_mlx_model_manifest.json",
    )


def parse_vlm(raw: str) -> str:
    text = raw.strip().upper()
    if re.fullmatch(r"[ABCD]", text):
        return text
    matches = re.findall(r"(?<![A-Z])[ABCD](?![A-Z])", text)
    return matches[0] if len(set(matches)) == 1 else ""


def vlm_prompt(row: object) -> str:
    focus = "main object the person interacts with" if row.category == "object_interaction" else "main human action"
    options = "\n".join(f"{label}. {getattr(row, label)}" for label in LABELS)
    return f"Classify the {focus} shown across the whole depth video.\n{row.question}\n{options}\nReply with exactly one capital letter A, B, C, or D."


def install_network_block() -> dict[str, object]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
    original_socket = socket.socket
    original_connection = socket.create_connection

    class BlockedSocket(original_socket):
        def connect(self, address: object) -> None:
            raise RuntimeError(f"Network disabled for Stage2-native run: {address}")

        def connect_ex(self, address: object) -> int:
            raise RuntimeError(f"Network disabled for Stage2-native run: {address}")

    def blocked_connection(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Network disabled for Stage2-native run")

    socket.socket = BlockedSocket
    socket.create_connection = blocked_connection
    try:
        try:
            socket.create_connection(("example.invalid", 443), timeout=0.01)
            proof = False
        except RuntimeError:
            proof = True
    finally:
        # The blocked implementations remain installed for the whole process.
        pass
    return {
        "hf_hub_offline": os.environ["HF_HUB_OFFLINE"],
        "transformers_offline": os.environ["TRANSFORMERS_OFFLINE"],
        "socket_probe_blocked": proof,
        "original_socket_type": str(original_socket),
        "original_connection": str(original_connection),
    }


def network_static_audit(source: str) -> list[str]:
    """Reject network imports and literal URLs without self-matching the audit."""
    hits: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"requests", "urllib", "kaggle"}:
                    hits.append(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in {"requests", "urllib", "kaggle"}:
                hits.append(f"import:{module}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            literal = node.value.strip().lower()
            if len(literal) > len("https://") and literal.startswith(("http://", "https://")):
                hits.append("literal_url")
    return sorted(set(hits))


def visual_lookup(manifest_path: Path) -> dict[tuple[str, str], dict[str, object]]:
    return {(item["unit"], item["modality"]): item for item in json.loads(manifest_path.read_text())}


def run_vlm_rows(
    rows: pd.DataFrame,
    lookup: dict[tuple[str, str], dict[str, object]],
    visual_root: Path,
    output_path: Path,
    model: object,
    processor: object,
    mx: object,
    apply_chat_template: object,
    generate: object,
    load_video: object,
) -> pd.DataFrame:
    completed: dict[str, dict[str, object]] = {}
    if output_path.is_file():
        for line in output_path.read_text().splitlines():
            if line.strip():
                item = json.loads(line)
                completed[str(item["qa_id"])] = item
    for position, row in enumerate(rows.itertuples(index=False), start=1):
        if row.qa_id in completed:
            continue
        unit = clip_key(row.path)
        item = lookup.get((unit, "Depth"))
        if item is None:
            raise FileNotFoundError(f"No Depth manifest entry for {unit}")
        video_path = visual_root / str(item["path"])
        if not video_path.is_file() or sha256(video_path) != item["sha256"]:
            raise ValueError(f"Video missing/hash mismatch: {video_path}")
        prompt = vlm_prompt(row)
        video_frames, effective_fps = load_video(str(video_path), nframes=FIXED_FRAMES)
        formatted = apply_chat_template(
            processor,
            model.config,
            prompt,
            num_images=0,
            num_audios=0,
            video=[str(video_path)],
            fps=effective_fps,
            enable_thinking=False,
        )
        mx.random.seed(SEED + position)
        started = time.perf_counter()
        raw = ""
        error = ""
        try:
            response = generate(
                model,
            processor,
            formatted,
            video=[video_frames],
            fps=effective_fps,
                temperature=0.0,
                max_tokens=MAX_TOKENS,
                verbose=False,
                enable_thinking=False,
            )
            raw = response.text
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        prediction = parse_vlm(raw) if not error else ""
        record = {
            "qa_id": row.qa_id,
            "path": row.path,
            "source": row.source,
            "category": row.category,
            "video_relative_path": str(video_path.relative_to(root_from_path(output_path))),
            "video_sha256": item["sha256"],
            "sampled_frames": FIXED_FRAMES,
            "effective_fps": effective_fps,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "raw_output": raw,
            "prediction": prediction,
            "parse_valid": bool(prediction),
            "runtime_seconds": time.perf_counter() - started,
            "error": error,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        completed[row.qa_id] = record
        print(f"{position}/{len(rows)} {row.qa_id} {row.category} vlm={prediction or 'INVALID'}", flush=True)
    return pd.DataFrame([completed[qa_id] for qa_id in rows["qa_id"]])


def root_from_path(path: Path) -> Path:
    for parent in path.parents:
        if parent.name == "cuhk_x_large":
            return parent
    raise ValueError(path)


def aligned_probability(model: object, values: np.ndarray, classes: np.ndarray) -> np.ndarray:
    raw = model.predict_proba(values)
    aligned = np.zeros((len(values), len(classes)), dtype=np.float64)
    positions = {int(label): index for index, label in enumerate(classes)}
    for source, label in enumerate(model.classes_):
        aligned[:, positions[int(label)]] = raw[:, source]
    return aligned


def harn_maps(frame: pd.DataFrame) -> tuple[dict[str, Counter[int]], dict[int, Counter[str]]]:
    action_by_text: defaultdict[str, Counter[int]] = defaultdict(Counter)
    objects_by_action: defaultdict[int, Counter[str]] = defaultdict(Counter)
    for row in frame[frame["source"] == "HARn"].itertuples(index=False):
        action = int(re.match(r"(\d+)_", str(row.path).split("/")[1]).group(1))
        if row.category == "single":
            action_by_text[norm(getattr(row, row.answer))][action] += 1
        elif row.category == "object_interaction":
            objects_by_action[action][norm(getattr(row, row.answer))] += 1
    return action_by_text, objects_by_action


def sensor_prediction(row: object, probability: np.ndarray, classes: np.ndarray, maps: tuple[dict[str, Counter[int]], dict[int, Counter[str]]]) -> tuple[str, float]:
    action_by_text, objects_by_action = maps
    by_action = {int(label): float(score) for label, score in zip(classes, probability)}
    scores: list[float] = []
    for label in LABELS:
        text = norm(getattr(row, label))
        if row.category == "single":
            counts = action_by_text.get(text, Counter())
            score = sum(by_action.get(action, 0.0) * count for action, count in counts.items()) / max(1, sum(counts.values()))
        else:
            score = sum(
                by_action.get(action, 0.0) * objects[text] / sum(objects.values())
                for action, objects in objects_by_action.items()
                if text in objects
            )
        scores.append(score)
    order = np.argsort(-np.asarray(scores), kind="stable")
    return LABELS[int(order[0])], float(scores[int(order[0])] - scores[int(order[1])])


def sensor_test_predictions(root: Path, train: pd.DataFrame, test_harn: pd.DataFrame) -> pd.DataFrame:
    cache_path = root / "cache/nonvisual_features.npz"
    model_path = root / "artifacts/models/harn_multimodal_extratrees/selected.joblib"
    bundle = joblib.load(model_path)
    if bundle["selected"] != "early_fusion" or set(bundle["models"]) != {"early_fusion"}:
        raise ValueError("Unexpected frozen sensor model")
    classes = np.asarray(bundle["classes"], dtype=int)
    model = bundle["models"]["early_fusion"]
    with np.load(cache_path) as cache:
        units = cache["units"].astype(str)
        index = {unit: position for position, unit in enumerate(units)}
        values = np.concatenate((cache["imu"], cache["radar"], cache["skeleton"]), axis=1).astype(np.float32)
    maps = harn_maps(train)
    records: list[dict[str, object]] = []
    for row in test_harn.itertuples(index=False):
        unit_match = re.search(r"large_model_track_test/LM_test_\d+", row.path)
        if not unit_match:
            raise ValueError(row.path)
        unit = "Testing/" + unit_match.group(0)
        present = unit in index and np.isfinite(values[index[unit]]).any()
        if present:
            probability = aligned_probability(model, values[[index[unit]]], classes)[0]
            prediction, confidence = sensor_prediction(row, probability, classes, maps)
        else:
            prediction, confidence = "", 0.0
        records.append({"qa_id": row.qa_id, "sensor_prediction": prediction, "sensor_confidence": confidence, "sensor_present": present})
    return pd.DataFrame(records)


def routed_prediction(category: str, base: str, sensor: str, confidence: float, present: bool, vlm: str) -> str:
    if not present or not sensor:
        return base
    if category == "single":
        if vlm == base and sensor != base:
            return base
        if vlm == sensor:
            return sensor
        return sensor if confidence >= SINGLE_SENSOR_MARGIN else base
    if category == "object_interaction":
        return sensor if sensor == vlm and sensor != base and confidence >= OBJECT_SENSOR_MARGIN else base
    return base


def valid_prediction(value: str, category: str) -> bool:
    if not value or any(label not in LABELS for label in value) or len(set(value)) != len(value):
        return False
    if category in SINGLE_OUTPUT:
        return len(value) == 1
    if category == "multi":
        return value == "".join(sorted(value))
    if category == "sequence":
        return len(value) == 4 and set(value) == set(LABELS)
    return False


def metrics(frame: pd.DataFrame) -> dict[str, object]:
    candidate = frame["candidate_prediction"] == frame["answer"]
    base = frame["base_prediction"] == frame["answer"]
    return {"rows": len(frame), "candidate_correct": int(candidate.sum()), "base_correct": int(base.sum()), "net_correct": int(candidate.sum() - base.sum()), "candidate_accuracy": float(candidate.mean()), "base_accuracy": float(base.mean())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol_path = root / "reports/harn_stage2_native48_protocol.json"
    lock_path = root / "reports/harn_stage2_native48_protocol.sha256"
    selection_path = root / "artifacts/manifests/harn_stage2_native48.csv"
    train_path = root / "data/raw/kaggle/training_qa.csv"
    test_path = root / "data/raw/kaggle/test_qa.csv"
    sample_path = root / "data/raw/kaggle/sample_submission.csv"
    sensor_oof_path = root / "artifacts/oof/harn_multimodal_extratrees_oof.csv"
    model_path, model_manifest_path = model_paths(root)
    fresh_log_path = root / f"artifacts/vlm/{RUN_NAME}_fresh48.jsonl"
    test_log_path = root / f"artifacts/vlm/{RUN_NAME}_test72.jsonl"
    candidate_path = root / f"candidates/{RUN_NAME}.csv"
    report_path = root / f"reports/{RUN_NAME}_validation.json"
    rejection_path = root / f"reports/{RUN_NAME}_rejection.json"
    preflight_path = root / f"reports/{RUN_NAME}_network_isolation_preflight.json"

    protocol = json.loads(protocol_path.read_text())
    if sha256(protocol_path) != lock_path.read_text().split()[0]:
        raise ValueError("Protocol lock mismatch")
    for name, path in {"train": train_path, "test": test_path, "sample": sample_path, "sensor_oof": sensor_oof_path, "model_manifest": model_manifest_path, "sensor_model": root / "artifacts/models/harn_multimodal_extratrees/selected.joblib", "feature_cache": root / "cache/nonvisual_features.npz", "harn_visual_manifest": root / "cache/harn_visual_manifest.json", "test_visual_manifest": root / "cache/test_visual_manifest.json", "exposure_registry": root / "artifacts/manifests/vlm_exposure_registry.jsonl", "runner": Path(__file__)}.items():
        if sha256(path) != protocol["inputs"][f"{name}_sha256"]:
            raise ValueError(f"Frozen input hash mismatch: {name}")
    selection = pd.read_csv(selection_path, dtype=str, keep_default_na=False)
    if sha256(selection_path) != protocol["selection_sha256"] or len(selection) != 48:
        raise ValueError("Frozen selection mismatch")
    frozen_ids = set(selection["qa_id"])
    frozen_clips = set(selection["path"])
    snapshotted = {item["path"] for item in protocol["history"]["artifacts"]}
    for item in protocol["history"]["artifacts"]:
        path = root / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Historical VLM log changed after freeze: {path}")
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        if path in {fresh_log_path, test_log_path}:
            continue
        if str(path.relative_to(root)) not in snapshotted:
            raise ValueError(f"Unsnapshotted VLM log appeared after freeze: {path}")
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if str(item.get("qa_id", "")) in frozen_ids or str(item.get("path", "")) in frozen_clips:
                raise ValueError(f"Fresh48 input appeared in historical log: {path}")

    network = install_network_block()
    source = Path(__file__).read_text()
    forbidden_hits = network_static_audit(source)
    candidate_preexists = candidate_path.exists()
    test_log_preexists = test_log_path.exists()
    preflight = {
        "status": "PASS"
        if network["socket_probe_blocked"]
        and not forbidden_hits
        and not candidate_preexists
        and not test_log_preexists
        else "FAIL",
        "network": network,
        "forbidden_source_hits": forbidden_hits,
        "candidate_exists_before_gate": candidate_preexists,
        "test_vlm_log_exists_before_gate": test_log_preexists,
    }
    preflight_path.write_text(json.dumps(preflight, indent=2) + "\n")
    if preflight["status"] != "PASS":
        raise ValueError("Network isolation preflight failed")
    if args.preflight_only:
        print(json.dumps(preflight, indent=2))
        return

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    owned_oof = base_oof(train)
    sensor_oof = pd.read_csv(sensor_oof_path, dtype=str, keep_default_na=False)[["qa_id", "prediction", "confidence", "sensor_present"]].rename(columns={"prediction": "sensor_prediction", "confidence": "sensor_confidence"})
    screen = selection.merge(train, on=["qa_id", "source", "category", "path"], validate="one_to_one").merge(owned_oof[["qa_id", "base_prediction", "answer", "user"]], on="qa_id", validate="one_to_one", suffixes=("", "_oof")).merge(sensor_oof, on="qa_id", validate="one_to_one")
    if not (screen["answer"] == screen["answer_oof"]).all():
        raise ValueError("OOF answer mismatch")
    harn_lookup = visual_lookup(root / "cache/harn_visual_manifest.json")
    harn_root = root / "data/raw/visual_harn"
    for row in screen.itertuples(index=False):
        item = harn_lookup.get((clip_key(row.path), "Depth"))
        if item is None or not (harn_root / item["path"]).is_file():
            raise FileNotFoundError(f"Frozen fresh video unavailable: {row.path}")

    import mlx.core as mx
    from mlx_vlm import apply_chat_template, generate, load
    from mlx_vlm.utils import load_video

    manifest = json.loads(model_manifest_path.read_text())
    if manifest.get("repo_id") != MODEL_REPO or manifest.get("revision") != MODEL_REVISION or manifest.get("license") != "apache-2.0":
        raise ValueError("Pinned local model mismatch")
    model, processor = load(str(model_path), trust_remote_code=False)
    vlm = run_vlm_rows(screen, harn_lookup, harn_root, fresh_log_path, model, processor, mx, apply_chat_template, generate, load_video).rename(columns={"prediction": "vlm_prediction"})
    screen = screen.merge(vlm[["qa_id", "vlm_prediction", "parse_valid", "error"]], on="qa_id", validate="one_to_one")
    screen["sensor_confidence"] = screen["sensor_confidence"].astype(float)
    screen["sensor_present"] = screen["sensor_present"].map(lambda value: str(value).lower() == "true")
    screen["candidate_prediction"] = [routed_prediction(row.category, row.base_prediction, row.sensor_prediction, row.sensor_confidence, row.sensor_present, row.vlm_prediction) for row in screen.itertuples(index=False)]
    overall = metrics(screen)
    by_category = {name: metrics(group) for name, group in screen.groupby("category")}
    by_half = {name: metrics(group) for name, group in screen.groupby("subject_half")}
    by_subject = {name: metrics(group) for name, group in screen.groupby("user")}
    subject_deltas = [item["candidate_accuracy"] - item["base_accuracy"] for item in by_subject.values()]
    subject_macro_delta = float(np.mean(subject_deltas))
    worst_subject_delta = float(min(subject_deltas))
    changed = screen[screen["candidate_prediction"] != screen["base_prediction"]]
    changed_candidate_accuracy = float((changed["candidate_prediction"] == changed["answer"]).mean()) if len(changed) else 0.0
    changed_base_accuracy = float((changed["base_prediction"] == changed["answer"]).mean()) if len(changed) else 0.0
    gates = {
        "network_isolation": preflight["status"] == "PASS",
        "equal_frame_token_budget": FIXED_FRAMES == 8 and MAX_TOKENS == 8 and vlm["sampled_frames"].eq(FIXED_FRAMES).all(),
        "fresh_vlm_implementation": len(screen) == 48 and screen["error"].eq("").all() and int(screen["parse_valid"].sum()) >= 47,
        "subject_macro_plus_2pp": subject_macro_delta >= 0.02,
        "worst_subject_degradation_le_3pp": worst_subject_delta >= -0.03,
        "overall_plus_6": overall["net_correct"] >= 6,
        "single_plus_6": by_category["single"]["net_correct"] >= 6,
        "object_nonnegative": by_category["object_interaction"]["net_correct"] >= 0,
        "both_subject_halves_positive": set(by_half) == {"A_user1_9", "B_user16_24"} and all(item["net_correct"] > 0 for item in by_half.values()),
        "changed_evidence": len(changed) >= 10 and changed_candidate_accuracy >= 0.75 and changed_base_accuracy <= 0.40,
    }
    passed = all(gates.values())
    if passed:
        base_test = OwnedClipDecoder().fit(train).predict(test)
        harn_test = test[test["source"] == "HARn"].copy()
        sensor_test = sensor_test_predictions(root, train, harn_test)
        test_lookup = visual_lookup(root / "cache/test_visual_manifest.json")
        test_vlm = run_vlm_rows(harn_test, test_lookup, root / "data/raw/visual_test", test_log_path, model, processor, mx, apply_chat_template, generate, load_video).rename(columns={"prediction": "vlm_prediction"})
        harn_route = harn_test[["qa_id", "category"]].merge(base_test, on="qa_id", validate="one_to_one").merge(sensor_test, on="qa_id", validate="one_to_one").merge(test_vlm[["qa_id", "vlm_prediction", "parse_valid", "error"]], on="qa_id", validate="one_to_one")
        if not harn_route["error"].eq("").all() or not harn_route["parse_valid"].all():
            raise ValueError("Test VLM has invalid output; fail closed")
        harn_route["candidate_prediction"] = [routed_prediction(row.category, row.base_prediction, row.sensor_prediction, float(row.sensor_confidence), bool(row.sensor_present), row.vlm_prediction) for row in harn_route.itertuples(index=False)]
        replacement = harn_route.set_index("qa_id")["candidate_prediction"]
        candidate = base_test.rename(columns={"base_prediction": "prediction"})
        candidate["prediction"] = candidate["qa_id"].map(replacement).fillna(candidate["prediction"])
        sample = pd.read_csv(sample_path, dtype=str, keep_default_na=False)
        candidate = sample[["qa_id"]].merge(candidate, on="qa_id", validate="one_to_one")
        candidate = candidate.merge(test[["qa_id", "category"]], on="qa_id", validate="one_to_one")
        if not all(valid_prediction(value, category) for value, category in zip(candidate["prediction"], candidate["category"])):
            raise ValueError("Candidate grammar invalid")
        candidate[["qa_id", "prediction"]].to_csv(candidate_path, index=False)

    report = {
        "experiment": RUN_NAME,
        "status": "VALIDATION_PASS_CANDIDATE_CREATED" if passed else "REJECTED_NO_CANDIDATE",
        "stage2_native": True,
        "frozen_test_vector_dependency": False,
        "network_preflight": preflight,
        "fresh_screen": {"rows": 48, "qa_overlap_with_prior_vlm": 0, "clip_overlap_with_prior_vlm": 0, "fixed_frames_per_clip": FIXED_FRAMES, "max_output_tokens": MAX_TOKENS, "overall": overall, "by_category": by_category, "by_subject_half": by_half, "by_subject": by_subject, "subject_macro_delta": subject_macro_delta, "worst_subject_delta": worst_subject_delta, "changed_rows": len(changed), "changed_candidate_accuracy": changed_candidate_accuracy, "changed_base_accuracy": changed_base_accuracy, "gates": gates},
        "candidate": str(candidate_path.relative_to(root)) if passed else "NONE",
        "candidate_sha256": sha256(candidate_path) if passed else None,
        "submission": "NOT_ATTEMPTED",
        "inputs": protocol["inputs"],
        "fresh_vlm_log_sha256": sha256(fresh_log_path),
        "test_vlm_log_sha256": sha256(test_log_path) if passed else None,
        "code_sha256": sha256(Path(__file__)),
    }
    terminal = report_path if passed else rejection_path
    terminal.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
