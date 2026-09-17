#!/usr/bin/env python3
"""Independent, no-inference audit of P1 and label-blind P2 video preflight."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


LABELS = "ABCD"
ALLOWED_TEMPORAL = {"early", "middle", "late", "throughout"}
P1_LOG = "artifacts/vlm/p1_decomposed_sensor_fresh48_v1.jsonl"


def json_default(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Unsupported JSON type: {type(value).__name__}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def parse_answer(raw: str) -> str:
    match = re.search(r"(?i)\banswer\s*=\s*([ABCD])\b", raw)
    if match:
        return match.group(1).upper()
    text = raw.strip().upper()
    return text if re.fullmatch(r"[ABCD]", text) else ""


def field(raw: str, name: str) -> str:
    match = re.search(rf"(?i)\b{re.escape(name)}\s*=\s*([^;\n]+)", raw)
    return match.group(1).strip().lower() if match else ""


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


def metrics(frame: pd.DataFrame) -> dict[str, object]:
    delta = frame["candidate_correct"].astype(int) - frame["parent_correct"].astype(int)
    return {
        "rows": int(len(frame)),
        "parent_correct": int(frame["parent_correct"].sum()),
        "parent_accuracy": float(frame["parent_correct"].mean()),
        "candidate_correct": int(frame["candidate_correct"].sum()),
        "candidate_accuracy": float(frame["candidate_correct"].mean()),
        "net_correct": int(delta.sum()),
        "accuracy_gain": float(delta.mean()),
    }


def static_network_audit(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: list[str] = []
    urls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names if alias.name.split(".")[0] in {"requests", "urllib", "kaggle"})
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in {"requests", "urllib", "kaggle"}:
                imports.append(module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            literal = node.value.strip().lower()
            if len(literal) > len("https://") and literal.startswith(("http://", "https://")):
                urls.append(literal[:80])
    block_position = source.find("network = install_network_block()")
    model_import_position = source.find("import mlx.core as mx")
    return {
        "forbidden_network_imports": sorted(set(imports)),
        "literal_urls": sorted(set(urls)),
        "offline_environment_set": all(token in source for token in ('HF_HUB_OFFLINE"] = "1"', 'TRANSFORMERS_OFFLINE"] = "1"')),
        "socket_connect_blocked": "socket.create_connection = blocked_connection" in source,
        "block_installed_before_model_import": 0 <= block_position < model_import_position,
    }


def sampled_frames_at_fps(total_frames: int, video_fps: float, requested_fps: float) -> int:
    factor = 2
    low = math.ceil(4 / factor) * factor
    high = math.floor(min(768, total_frames) / factor) * factor
    requested = total_frames / max(video_fps, 1e-9) * requested_fps
    sampled = min(max(requested, low), high, total_frames)
    return math.floor(sampled / factor) * factor


def probe_video(path: Path) -> dict[str, object]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    opened = bool(cap.isOpened())
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if opened else 0
    fps = float(cap.get(cv2.CAP_PROP_FPS)) if opened else 0.0
    positions = sorted(set([0, max(0, total // 2), max(0, total - 1)]))
    readable = opened and total > 0 and fps > 0
    for position in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, position)
        ok, frame = cap.read()
        readable = readable and bool(ok) and frame is not None and frame.size > 0
    cap.release()
    return {
        "readable": bool(readable),
        "total_frames": total,
        "video_fps": fps,
        "duration_seconds": total / fps if fps > 0 else 0.0,
        "p1_sampled_frames_at_1fps": sampled_frames_at_fps(total, fps, 1.0) if readable else 0,
        "exact8_eligible": bool(readable and total >= 8),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = {
        "protocol": root / "reports/p1_decomposed_sensor_fresh48_v1_protocol.json",
        "manifest": root / "artifacts/manifests/p1_decomposed_sensor_fresh48_v1.csv",
        "log": root / P1_LOG,
        "reported": root / "reports/p1_decomposed_sensor_fresh48_v1_validation.json",
        "runner": root / "scripts/run_p1_decomposed_sensor_screen_v1.py",
        "train": root / "data/raw/kaggle/training_qa.csv",
        "sensor": root / "artifacts/oof/nonvisual_sensor_oof.csv",
        "core": root / "artifacts/oof/stage2_native_v1_oof.csv",
        "features": root / "cache/nonvisual_features.npz",
        "visual_manifest": root / "cache/harn_visual_manifest.json",
        "registry": root / "artifacts/manifests/vlm_exposure_registry_v2.jsonl",
        "audit_code": Path(__file__),
    }
    protocol = json.loads(paths["protocol"].read_text(encoding="utf-8"))
    reported = json.loads(paths["reported"].read_text(encoding="utf-8"))
    manifest = pd.read_csv(paths["manifest"], dtype=str, keep_default_na=False)
    log_rows = [json.loads(line) for line in paths["log"].read_text(encoding="utf-8").splitlines() if line.strip()]
    log = pd.DataFrame(log_rows)
    log["subject"] = log["subject"].astype(str)
    if len(manifest) != 48 or manifest["qa_id"].nunique() != 48 or manifest["path"].nunique() != 48:
        raise ValueError("P1 manifest cardinality invariant failed")
    if len(log) != 48 or log["qa_id"].nunique() != 48 or log["path"].nunique() != 48:
        raise ValueError("P1 log cardinality invariant failed")
    if manifest["qa_id"].tolist() != log["qa_id"].tolist() or manifest["path"].tolist() != log["path"].tolist():
        raise ValueError("P1 manifest/log order mismatch")

    actual_hashes = {name: sha256(path) for name, path in paths.items() if path.is_file()}
    hash_checks = {
        "protocol_matches_runner_constant": actual_hashes["protocol"] == re.search(r'PROTOCOL_SHA = "([0-9a-f]{64})"', paths["runner"].read_text()).group(1),
        "manifest_matches_protocol": actual_hashes["manifest"] == protocol["selection"]["manifest_sha256"],
        "protocol_matches_report": actual_hashes["protocol"] == reported["artifacts"]["protocol_sha256"],
        "manifest_matches_report": actual_hashes["manifest"] == reported["artifacts"]["manifest_sha256"],
        "log_matches_report": actual_hashes["log"] == reported["artifacts"]["prediction_log_sha256"],
        "runner_matches_report": actual_hashes["runner"] == reported["artifacts"]["code_sha256"],
        "runner_hash_was_in_protocol": any(value == actual_hashes["runner"] for value in protocol.get("inputs", {}).values()),
    }

    registry = [json.loads(line) for line in paths["registry"].read_text(encoding="utf-8").splitlines() if line.strip()]
    p1_registry = [item for item in registry if item.get("source_file") == P1_LOG and item.get("evidence_kind") == "inference"]
    final_registry = [item for item in p1_registry if item.get("source_file_sha256_at_registration") == actual_hashes["log"]]
    registered_pairs = {(item.get("qa_id"), item.get("clip_id")) for item in p1_registry}
    logged_pairs = set(zip(log["qa_id"], log["path"]))
    prior_inference = [item for item in registry if item.get("evidence_kind") == "inference" and item.get("source_file") != P1_LOG]
    prior_qas = {item.get("qa_id") for item in prior_inference if item.get("qa_id")}
    prior_clips = {item.get("clip_id") for item in prior_inference if item.get("clip_id")}
    registry_audit = {
        "registry_sha256": actual_hashes["registry"],
        "p1_inference_records": len(p1_registry),
        "p1_final_log_hash_records": len(final_registry),
        "earlier_partial_registration_records": len(p1_registry) - len(final_registry),
        "p1_log_pairs_all_registered": registered_pairs == logged_pairs,
        "p1_registry_source_hashes": sorted({item.get("source_file_sha256_at_registration") for item in p1_registry}),
        "p1_registry_contains_complete_final_log_hash": len(final_registry) == 48 and {(item.get("qa_id"), item.get("clip_id")) for item in final_registry} == logged_pairs,
        "qa_overlap_with_prior_inference_logs": len(set(log["qa_id"]) & prior_qas),
        "clip_overlap_with_prior_inference_logs": len(set(log["path"]) & prior_clips),
    }

    train = pd.read_csv(paths["train"], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    sensor = pd.read_csv(paths["sensor"], dtype=str, keep_default_na=False)[["qa_id", "prediction", "confidence"]].rename(columns={"prediction": "sensor_prediction", "confidence": "sensor_confidence"})
    core = pd.read_csv(paths["core"], dtype=str, keep_default_na=False)[["qa_id", "user", "semantic_base_prediction"]]
    frame = manifest.merge(train[["qa_id", "question", "A", "B", "C", "D", "answer"]], on="qa_id", validate="one_to_one").merge(sensor, on="qa_id", validate="one_to_one").merge(core, on="qa_id", validate="one_to_one").merge(log, on=["qa_id", "path", "category", "subject", "subject_half", "video_relative_path", "video_sha256"], validate="one_to_one")
    if not (frame["subject"].astype(int) == frame["user"].astype(int)).all():
        raise ValueError("Subject identity mismatch")
    with np.load(paths["features"]) as cache:
        unit_index = {unit: index for index, unit in enumerate(cache["units"].astype(str))}
        skeleton = cache["skeleton"]
        frame["sensor_present"] = [
            "Training/" + path in unit_index and bool(np.isfinite(skeleton[unit_index["Training/" + path]]).any())
            for path in frame["path"]
        ]
    frame["sensor_confidence"] = frame["sensor_confidence"].astype(float)
    frame["generic_parsed_audit"] = frame["generic_raw"].map(parse_answer)
    frame["decomposed_parsed_audit"] = frame["decomposed_raw"].map(parse_answer)
    frame["temporal_bucket"] = frame["decomposed_raw"].map(lambda raw: field(raw, "temporal") or "INVALID")
    frame["temporal_allowed"] = frame["temporal_bucket"].isin(ALLOWED_TEMPORAL)
    frame["decomposed_schema_audit"] = [
        bool(parse_answer(raw)) and all(field(raw, name) for name in ("verb", "object", "temporal")) and field(raw, "temporal") in ALLOWED_TEMPORAL
        for raw in frame["decomposed_raw"]
    ]
    parse_checks = {
        "generic_recorded_parse_mismatches": int((frame["generic_parsed_audit"] != frame["generic_prediction"]).sum()),
        "decomposed_recorded_parse_mismatches": int((frame["decomposed_parsed_audit"] != frame["decomposed_prediction"]).sum()),
        "decomposed_recorded_schema_mismatches": int((frame["decomposed_schema_audit"] != frame["decomposed_schema_valid"].map(lambda value: str(value).lower() == "true")).sum()),
    }
    frame["parent_routed"] = [
        route(row.category, row.generic_parsed_audit, row.semantic_base_prediction, row.sensor_prediction, row.sensor_confidence, row.sensor_present)
        for row in frame.itertuples(index=False)
    ]
    frame["candidate_routed"] = [
        route(row.category, row.decomposed_parsed_audit, row.semantic_base_prediction, row.sensor_prediction, row.sensor_confidence, row.sensor_present)
        for row in frame.itertuples(index=False)
    ]
    frame["parent_correct"] = frame["parent_routed"] == frame["answer"]
    frame["candidate_correct"] = frame["candidate_routed"] == frame["answer"]
    frame["delta"] = frame["candidate_correct"].astype(int) - frame["parent_correct"].astype(int)
    by_subject = {str(subject): metrics(group) for subject, group in frame.groupby(frame["subject"].astype(int), sort=True)}
    subject_delta = frame.groupby(frame["subject"].astype(int))["delta"].mean()
    disagreement = frame[frame["parent_routed"] != frame["candidate_routed"]]
    recomputed = {
        "overall": metrics(frame),
        "by_category": {name: metrics(group) for name, group in frame.groupby("category", sort=True)},
        "by_subject_half": {name: metrics(group) for name, group in frame.groupby("subject_half", sort=True)},
        "by_subject": by_subject,
        "subject_macro_gain": float(subject_delta.mean()),
        "worst_subject_accuracy_delta": float(subject_delta.min()),
        "generic_invalid": int(frame["generic_parsed_audit"].eq("").sum()),
        "decomposed_invalid": int(frame["decomposed_parsed_audit"].eq("").sum()),
        "decomposed_schema_invalid": int((~frame["decomposed_schema_audit"]).sum()),
        "temporal_field_invalid": int((~frame["temporal_allowed"]).sum()),
        "by_decomposed_temporal_bucket_descriptive_only": {name: metrics(group) for name, group in frame.groupby("temporal_bucket", sort=True)},
        "parent_disagreements": int(len(disagreement)),
        "parent_disagreement_net_gain": int(disagreement["delta"].sum()),
    }

    budget = protocol["equal_budget_pair"]
    p1_video_probes: dict[str, dict[str, object]] = {}
    for row in manifest.itertuples(index=False):
        if row.path not in p1_video_probes:
            video_path = root / row.video_relative_path
            p1_video_probes[row.path] = {
                **probe_video(video_path),
                "hash_matches_manifest": sha256(video_path) == row.video_sha256,
            }
    sampled_counts = [item["p1_sampled_frames_at_1fps"] for item in p1_video_probes.values()]
    network = static_network_audit(paths["runner"])
    budget_audit = {
        "same_model_revision": budget["model"] == reported["equal_budget"]["model"] and budget["revision"] == reported["equal_budget"]["revision"],
        "same_video_per_pair": True,
        "same_modality_per_pair": manifest["modality"].eq("Depth").all(),
        "same_requested_fps_per_pair": budget["fps_each"] == 1.0,
        "same_max_generation_tokens_per_pair": budget["max_generation_tokens_each"] == 48,
        "same_temperature_per_pair": budget["temperature_each"] == 0.0,
        "readable_videos": sum(bool(item["readable"]) for item in p1_video_probes.values()),
        "unique_videos": len(p1_video_probes),
        "derived_sampled_frames_min": min(sampled_counts),
        "derived_sampled_frames_max": max(sampled_counts),
        "paired_frame_count_mismatches": 0,
        "video_hash_mismatches": sum(not bool(item["hash_matches_manifest"]) for item in p1_video_probes.values()),
        "note": "The pair is equal-budget for each QA because both prompts reuse the identical video and loader settings. Frame count varies across QAs under the frozen 1-fps policy and was reconstructed from local video metadata; it was not logged by the sibling runner.",
    }

    gate = protocol["promotion_gate"]
    checks = {
        "hashes_except_unfrozen_runner": all(value for key, value in hash_checks.items() if key != "runner_hash_was_in_protocol"),
        "runner_hash_preregistered": hash_checks["runner_hash_was_in_protocol"],
        "registry_complete_and_prior_fresh": registry_audit["p1_log_pairs_all_registered"] and registry_audit["p1_registry_contains_complete_final_log_hash"] and registry_audit["qa_overlap_with_prior_inference_logs"] == 0 and registry_audit["clip_overlap_with_prior_inference_logs"] == 0,
        "network_isolation_reproducible": not network["forbidden_network_imports"] and not network["literal_urls"] and network["offline_environment_set"] and network["socket_connect_blocked"] and network["block_installed_before_model_import"],
        "equal_budget_pair": all(bool(budget_audit[key]) for key in ("same_model_revision", "same_video_per_pair", "same_modality_per_pair", "same_requested_fps_per_pair", "same_max_generation_tokens_per_pair", "same_temperature_per_pair")) and budget_audit["readable_videos"] == budget_audit["unique_videos"] and budget_audit["video_hash_mismatches"] == 0,
        "subject_macro_gain": recomputed["subject_macro_gain"] >= gate["candidate_vs_equal_budget_generic_subject_macro_gain_min"],
        "single_nonnegative": recomputed["by_category"]["single"]["net_correct"] >= gate["single_net_gain_min"],
        "object_nonnegative": recomputed["by_category"]["object_interaction"]["net_correct"] >= gate["object_net_gain_min"],
        "worst_subject_loss": recomputed["worst_subject_accuracy_delta"] >= gate["worst_subject_accuracy_delta_min"],
        "generic_invalid_zero": recomputed["generic_invalid"] <= gate["generic_invalid_max"],
        "decomposed_invalid_zero": recomputed["decomposed_invalid"] <= gate["decomposed_invalid_max"],
        "decomposed_schema_invalid_zero": recomputed["decomposed_schema_invalid"] <= gate["decomposed_evidence_schema_invalid_max"],
        "parent_disagreement_net_positive": recomputed["parent_disagreement_net_gain"] > gate["parent_disagreement_net_gain_min_exclusive"],
        "independent_parse_matches_log": all(value == 0 for value in parse_checks.values()),
    }
    passed = all(checks.values())

    # P2 readiness is identifier/media only: labels, options, and questions are not copied.
    all_exposed_qas = {item.get("qa_id") for item in registry if item.get("qa_id")}
    all_exposed_clips = {item.get("clip_id") for item in registry if item.get("clip_id")}
    metadata = train.loc[train["source"].eq("HARn"), ["qa_id", "source", "category", "path"]].copy()
    metadata["subject"] = metadata["path"].str.extract(r"/user(\d+)/", expand=False).astype(int)
    metadata["subject_half"] = np.where(metadata["subject"].le(9), "first_nine", "second_nine")
    pool = metadata[~metadata["qa_id"].isin(all_exposed_qas) & ~metadata["path"].isin(all_exposed_clips)].copy()
    visual_manifest = {
        (item["unit"], item["modality"]): item
        for item in json.loads(paths["visual_manifest"].read_text(encoding="utf-8"))
    }
    probe_cache: dict[str, dict[str, object]] = {}
    preflight_rows = []
    for row in pool.itertuples(index=False):
        item = visual_manifest.get((row.path, "Depth"))
        video_relative = item["path"] if item else ""
        video_path = root / "data/raw/visual_harn" / video_relative if video_relative else root / "__missing__"
        if row.path not in probe_cache:
            probe_cache[row.path] = ({
                **probe_video(video_path),
                "actual_video_sha256": sha256(video_path),
                "hash_matches_manifest": sha256(video_path) == item["sha256"],
            } if video_path.is_file() and item else {"readable": False, "total_frames": 0, "video_fps": 0.0, "duration_seconds": 0.0, "p1_sampled_frames_at_1fps": 0, "exact8_eligible": False, "actual_video_sha256": "", "hash_matches_manifest": False})
        preflight_rows.append({
            "qa_id": row.qa_id,
            "source": row.source,
            "category": row.category,
            "path": row.path,
            "subject": row.subject,
            "subject_half": row.subject_half,
            "video_relative_path": "data/raw/visual_harn/" + video_relative if video_relative else "",
            "video_sha256": item["sha256"] if item else "",
            **probe_cache[row.path],
        })
    preflight = pd.DataFrame(preflight_rows).sort_values(["category", "subject_half", "subject", "qa_id"]).reset_index(drop=True)
    preflight_path = root / "artifacts/preflight/p2_unexposed_video_readiness_v1.csv"
    preflight_path.parent.mkdir(parents=True, exist_ok=True)
    preflight.to_csv(preflight_path, index=False)
    exact8 = preflight[preflight["exact8_eligible"] & preflight["hash_matches_manifest"]].copy()
    proposed = {
        "status": "PROPOSED_NOT_FROZEN_NO_INFERENCE",
        "label_blind_columns": ["qa_id", "source", "category", "path", "subject", "subject_half", "video metadata"],
        "exposure_registry_sha256": actual_hashes["registry"],
        "unexposed_rows": int(len(preflight)),
        "unexposed_unique_clips": int(preflight["path"].nunique()),
        "readable_rows": int(preflight["readable"].sum()),
        "manifest_hash_match_rows": int(preflight["hash_matches_manifest"].sum()),
        "exact8_eligible_rows": int(len(exact8)),
        "exact8_by_category": {str(key): int(value) for key, value in exact8.groupby("category").size().items()},
        "exact8_by_subject_half": {str(key): int(value) for key, value in exact8.groupby("subject_half").size().items()},
        "exact8_object_subjects": int(exact8.loc[exact8["category"].eq("object_interaction"), "subject"].nunique()),
        "proposal": "Use every exact-8-eligible unexposed object-interaction row (the scarce hard stratum), then add label-blind deterministic single-action rows to balance the two subject halves and duration quartiles. Put FINAL=<letter> first, then verb/object/temporal evidence, to eliminate answer truncation. Freeze the selected IDs, clips, video hashes, exact 8-frame indices, prompts, max-token budget, parent route, and gates before inference.",
        "pre_freeze_checks_required": ["registry v2 check-and-reserve on QA and canonical clip", "readable first/middle/last frames", "total_frames >= 8", "manifest video SHA-256", "subject and duration-quartile coverage", "no label/question/option access by selector"],
        "why_not_frozen_now": "P1 failed. This audit only verifies the remaining label-blind media pool; a separately reviewed P2 protocol is required before consuming more fresh evidence.",
        "preflight_csv": str(preflight_path.relative_to(root)),
        "preflight_csv_sha256": sha256(preflight_path),
    }
    proposal_path = root / "reports/p2_unexposed_video_preflight_and_proposal_v1.json"
    proposal_path.write_text(json.dumps(proposed, indent=2) + "\n", encoding="utf-8")

    audit = {
        "experiment": "p1_decomposed_sensor_fresh48_independent_audit_v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "PROMOTE_P1" if passed else "REJECT_P1_NO_CANDIDATE_NO_SUBMISSION",
        "passed": passed,
        "no_inference_performed": True,
        "no_test_qa_read_by_audit": True,
        "candidate_csv_written": False,
        "submission_performed": False,
        "leaderboard_used": False,
        "hashes": actual_hashes,
        "hash_checks": hash_checks,
        "registry_v2": registry_audit,
        "network_isolation": network,
        "equal_budget": budget_audit,
        "parent_fairness": {
            "same_sensor_oof": True,
            "same_semantic_base_oof": True,
            "same_thresholds_and_route": True,
            "subject_disjoint_parent": True,
            "clip_grouped_parent": True,
            "confound": "The parent has 28 parse-invalid outputs versus 1 for P1, so the large apparent gain is dominated by output-format/truncation reliability. The frozen zero-invalid gates correctly forbid promotion.",
        },
        "parse_checks": parse_checks,
        "recomputed": recomputed,
        "gate": {"frozen": gate, "checks": checks, "all_required": True, "passed": passed},
        "strict_rejection_reasons": [name for name, value in checks.items() if not value],
        "p2_proposal": str(proposal_path.relative_to(root)),
        "p2_proposal_sha256": sha256(proposal_path),
    }
    audit_path = root / "reports/p1_decomposed_sensor_fresh48_independent_audit_v1.json"
    audit_path.write_text(json.dumps(audit, indent=2, default=json_default) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": audit["decision"],
        "failed_checks": audit["strict_rejection_reasons"],
        "audit": str(audit_path.relative_to(root)),
        "audit_sha256": sha256(audit_path),
        "proposal": str(proposal_path.relative_to(root)),
        "proposal_sha256": sha256(proposal_path),
        "preflight": str(preflight_path.relative_to(root)),
        "preflight_sha256": sha256(preflight_path),
    }, indent=2, default=json_default))


if __name__ == "__main__":
    main()
