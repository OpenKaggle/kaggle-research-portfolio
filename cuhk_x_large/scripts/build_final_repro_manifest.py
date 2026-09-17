#!/usr/bin/env python3
"""Freeze the current CUHK-X Large final-candidate reproducibility chain."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SELECTED_SUBMISSIONS = [
    {
        "ref": 56122653,
        "file": "candidates/emotion_extratrees_rf_union_v1.csv",
        "sha256": "3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4",
        "public_score": "0.78070",
        "role": "primary evidence-union candidate",
    },
    {
        "ref": 56108595,
        "file": "candidates/nonvisual_sensor_union_v1.csv",
        "sha256": "a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702",
        "public_score": "0.78070",
        "role": "independent nonvisual fallback",
    },
]

ARTIFACT_GROUPS = {
    "official_metadata_and_feature_inputs": [
        "data/raw/kaggle/training_qa.csv",
        "data/raw/kaggle/test_qa.csv",
        "data/raw/media/HARn.zip",
        "data/raw/media/large_model_track_test.zip",
        "cache/nonvisual_features.npz",
        "cache/partial_visual_manifest.json",
        "cache/partial_test_visual_manifest.json",
        "cache/test_visual_manifest.json",
        "cache/harn_visual_manifest.json",
        "reports/partial_visual_extraction.json",
        "reports/partial_test_visual_extraction.json",
        "reports/test_visual_extraction.json",
        "reports/harn_visual_extraction.json",
        "reports/qwen3_vl_4b_mlx_model_manifest.json",
    ],
    "models": [
        "artifacts/models/nonvisual_rf_v1/hau_action.joblib",
        "artifacts/models/nonvisual_rf_v1/hau_emotion.joblib",
        "artifacts/models/nonvisual_rf_v1/harn_action.joblib",
        "artifacts/models/emotion_pairwise_xgb_v1.joblib",
        "artifacts/models/emotion_pairwise_extratrees_v1.joblib",
    ],
    "oof_and_test_predictions": [
        "artifacts/oof/public_graph_leave_one_subject_out.csv",
        "artifacts/oof/nonvisual_sensor_oof.csv",
        "artifacts/predictions/nonvisual_sensor_test.csv",
        "artifacts/oof/emotion_pairwise_xgb_oof.csv",
        "artifacts/predictions/emotion_pairwise_xgb_test.csv",
        "artifacts/oof/emotion_pairwise_extratrees_oof.csv",
        "artifacts/predictions/emotion_pairwise_extratrees_test.csv",
        "artifacts/vlm/qwen3_vl_4b_zero_shot_full122_v1.jsonl",
        "artifacts/vlm/qwen3_vl_4b_zero_shot_object66_v1.jsonl",
        "artifacts/vlm/qwen3_vl_4b_test_harn_single_v1.jsonl",
        "artifacts/vlm/qwen3_vl_4b_test_harn_object_v1.jsonl",
        "artifacts/vlm/qwen3_vl_4b_test_harn_single_full_v1.jsonl",
        "artifacts/manifests/vlm_small20_validation.csv",
        "artifacts/vlm/qwen3_vl_4b_small20_frozen_v1.jsonl",
        "artifacts/manifests/vlm_fresh20_validation.csv",
        "artifacts/vlm/qwen3_vl_4b_fresh20_v1.jsonl",
        "artifacts/oof/sensor_option_semantics_v1_oof.csv",
        "artifacts/manifests/vlm_exposure_registry.jsonl",
        "artifacts/manifests/vlm_exposure_registry_v2.jsonl",
        "reports/vlm_exposure_registry.jsonl",
        "artifacts/manifests/harn_stage2_native48.csv",
        "artifacts/vlm/harn_stage2_native_v1_fresh48.jsonl",
        "artifacts/oof/stage2_native_v1_oof.csv",
        "artifacts/manifests/stage2_native_qwen_missing_sensor_v1.csv",
        "artifacts/vlm/stage2_native_qwen_missing_sensor_v1.jsonl",
        "artifacts/manifests/p1_decomposed_sensor_fresh48_v1.csv",
        "artifacts/vlm/p1_decomposed_sensor_fresh48_v1.jsonl",
        "artifacts/dry_runs/stage2_native_v1_run1.csv",
        "artifacts/dry_runs/stage2_native_v1_run2.csv",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run1.csv",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run2.csv",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run1/nonvisual_features.npz",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run2/nonvisual_features.npz",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run1/raw_feature_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run2/raw_feature_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run1/candidate_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_v1_run2/candidate_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_run1.csv",
        "artifacts/dry_runs/stage2_native_owned_raw_run2.csv",
        "artifacts/dry_runs/stage2_native_owned_raw_run1/nonvisual_features.npz",
        "artifacts/dry_runs/stage2_native_owned_raw_run2/nonvisual_features.npz",
        "artifacts/dry_runs/stage2_native_owned_raw_run1/raw_feature_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_run2/raw_feature_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_run1/candidate_report.json",
        "artifacts/dry_runs/stage2_native_owned_raw_run2/candidate_report.json",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/fixture.json",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/original_ids_qa.csv",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/new_ids_clips_qa.csv",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/original_units_features.npz",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/new_units_features.npz",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/original_ids_predictions.csv",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/new_ids_clips_predictions.csv",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/original_ids_build.json",
        "artifacts/smoke/stage2_native_arbitrary_id_v1/new_ids_clips_build.json",
        "artifacts/fixtures/stage2_native_owned_raw_v1/fixture.json",
        "artifacts/fixtures/stage2_native_owned_raw_v1/original/qa.csv",
        "artifacts/fixtures/stage2_native_owned_raw_v1/original/sample.csv",
        "artifacts/fixtures/stage2_native_owned_raw_v1/original/predictions.csv",
        "artifacts/fixtures/stage2_native_owned_raw_v1/original/work/nonvisual_features.npz",
        "artifacts/fixtures/stage2_native_owned_raw_v1/original/work/raw_feature_report.json",
        "artifacts/fixtures/stage2_native_owned_raw_v1/original/work/candidate_report.json",
        "artifacts/fixtures/stage2_native_owned_raw_v1/renamed/qa.csv",
        "artifacts/fixtures/stage2_native_owned_raw_v1/renamed/sample.csv",
        "artifacts/fixtures/stage2_native_owned_raw_v1/renamed/predictions.csv",
        "artifacts/fixtures/stage2_native_owned_raw_v1/renamed/work/nonvisual_features.npz",
        "artifacts/fixtures/stage2_native_owned_raw_v1/renamed/work/raw_feature_report.json",
        "artifacts/fixtures/stage2_native_owned_raw_v1/renamed/work/candidate_report.json",
        "artifacts/preflight/p2_unexposed_video_readiness_v1.csv",
    ],
    "candidate_lineage": [
        "candidates/public_fususu_077777.csv",
        "candidates/nonvisual_sensor_union_v1.csv",
        "candidates/visual_sensor_consensus_v1.csv",
        "candidates/visual_sensor_consensus_v2.csv",
        "candidates/hau_linked_single_consensus_v1.csv",
        "candidates/emotion_extratrees_rf_union_v1.csv",
        "candidates/stage2_native_owned_v1.csv",
    ],
    "source_code": [
        "scripts/reproduce_public_077777.py",
        "scripts/extract_nonvisual_features.py",
        "scripts/run_public_graph_oof.py",
        "scripts/run_sensor_oof.py",
        "scripts/run_emotion_pairwise_xgb.py",
        "scripts/run_emotion_pairwise_extratrees.py",
        "scripts/run_zero_shot_vlm.py",
        "scripts/run_test_vlm.py",
        "scripts/range_download.py",
        "scripts/extract_test_visuals.py",
        "scripts/freeze_vlm_small20_validation.py",
        "scripts/run_vlm_small20_frozen_validation.py",
        "scripts/audit_vlm_historical_replay.py",
        "scripts/extract_harn_visuals.py",
        "scripts/freeze_vlm_fresh20_validation.py",
        "scripts/run_vlm_fresh20_validation.py",
        "scripts/run_sensor_option_semantics_v1.py",
        "scripts/freeze_harn_stage2_native48.py",
        "scripts/run_harn_stage2_native_v1.py",
        "scripts/run_stage2_native_oof_v1.py",
        "scripts/freeze_stage2_native_qwen_missing_v1.py",
        "scripts/run_stage2_native_qwen_missing_v1.py",
        "scripts/freeze_p1_decomposed_sensor_screen_v1.py",
        "scripts/run_p1_decomposed_sensor_screen_v1.py",
        "scripts/update_vlm_exposure_registry.py",
        "scripts/sync_shared_vlm_exposure_registry.py",
        "scripts/reserve_vlm_fresh_cohort.py",
        "scripts/audit_p1_and_preflight_p2_v1.py",
        "scripts/build_stage2_native_candidate_v1.py",
        "scripts/prepare_stage2_native_arbitrary_id_smoke.py",
        "scripts/verify_stage2_native_arbitrary_id_smoke.py",
        "scripts/extract_owned_raw_features_v1.py",
        "scripts/prepare_owned_raw_fixture_v1.py",
        "scripts/verify_stage2_owned_raw_package_v1.py",
        "tests/test_owned_raw_package_v1.py",
        "tests/test_harn_stage2_native_v1.py",
        "scripts/analyze_visual_sensor_fusion.py",
        "scripts/build_sensor_union_candidate.py",
        "scripts/build_visual_sensor_candidate.py",
        "scripts/build_visual_sensor_candidate_v2.py",
        "scripts/build_hau_linked_single_consensus.py",
        "scripts/build_emotion_extratrees_rf_union.py",
        "scripts/validate_submission.py",
        "scripts/build_final_repro_manifest.py",
        "scripts/verify_final_repro_manifest.py",
        "inference.sh",
        "inference_owned.sh",
    ],
    "reports_and_receipts": [
        "reports/public_graph_oof_summary.json",
        "reports/nonvisual_sensor_oof_summary.json",
        "reports/emotion_pairwise_xgb_summary.json",
        "reports/emotion_pairwise_extratrees_summary.json",
        "reports/visual_sensor_fusion_subset_summary.json",
        "reports/visual_sensor_object_fusion_subset_summary.json",
        "reports/nonvisual_sensor_union_v1_candidate.json",
        "reports/visual_sensor_consensus_v1_candidate.json",
        "reports/visual_sensor_consensus_v2_candidate.json",
        "reports/hau_linked_single_consensus_v1_candidate.json",
        "reports/emotion_extratrees_rf_union_v1_candidate.json",
        "reports/qwen3_vl_4b_test_harn_single_full_v1_summary.json",
        "reports/vlm_small20_frozen_protocol.json",
        "reports/qwen3_vl_4b_small20_frozen_v1_summary.json",
        "reports/vlm_historical_replay_and_freeze_audit.json",
        "reports/vlm_fresh20_frozen_protocol.json",
        "reports/qwen3_vl_4b_fresh20_v1_summary.json",
        "reports/final_reproducibility_manifest_2026-09-09.json",
        "reports/final_reproducibility_verification_2026-09-09.json",
        "reports/final_reproducibility_manifest_2026-09-09_v2.json",
        "reports/final_reproducibility_verification_2026-09-09_v2.json",
        "reports/final_reproducibility_manifest_2026-09-10_v3.json",
        "reports/final_reproducibility_verification_2026-09-10_v3.json",
        "reports/final_reproducibility_manifest_2026-09-11_v4.json",
        "reports/final_reproducibility_verification_2026-09-11_v4.json",
        "reports/final_reproducibility_manifest_2026-09-11_v5.json",
        "reports/final_reproducibility_verification_2026-09-11_v5.json",
        "reports/final_reproducibility_manifest_2026-09-11_v6.json",
        "reports/final_reproducibility_verification_2026-09-11_v6.json",
        "reports/final_reproducibility_manifest_2026-09-11_v7.json",
        "reports/final_reproducibility_verification_2026-09-11_v7.json",
        "reports/final_reproducibility_manifest_2026-09-11_v8.json",
        "reports/final_reproducibility_verification_2026-09-11_v8.json",
        "reports/cuhk_series_research_and_sprint_plan_2026-09-11.md",
        "reports/sensor_option_semantics_v1_preregistered_protocol.json",
        "reports/sensor_option_semantics_v1_validation.json",
        "reports/sensor_option_semantics_v1_replay_verification.json",
        "reports/harn_stage2_native48_protocol.json",
        "reports/harn_stage2_native48_protocol.sha256",
        "reports/harn_stage2_native_v1_network_isolation_preflight.json",
        "reports/harn_stage2_native_v1_rejection.json",
        "reports/stage2_native_v1_preregistered_protocol.json",
        "reports/stage2_native_v1_oof_validation.json",
        "reports/stage2_native_qwen_missing_sensor_v1_protocol.json",
        "reports/stage2_native_qwen_missing_sensor_v1_validation.json",
        "reports/stage2_native_v1_run1.json",
        "reports/stage2_native_v1_run2.json",
        "reports/stage2_native_v1_network_free_replay_verification.json",
        "reports/stage2_native_arbitrary_id_clip_smoke_v1.json",
        "reports/p1_decomposed_sensor_fresh48_v1_protocol.json",
        "reports/p1_decomposed_sensor_fresh48_v1_validation.json",
        "reports/p1_posthoc_control_plane_audit_exposure_reservation.json",
        "reports/p1_independent_control_audit_v1.json",
        "reports/p1_decomposed_sensor_fresh48_independent_audit_v1.json",
        "reports/vlm_exposure_registry_v2_audit_2026-09-11_p1.json",
        "reports/p2_unexposed_video_preflight_and_proposal_v1.json",
        "reports/stage2_owned_package_control_audit_v1.json",
        "reports/stage2_native_owned_raw_package_v1.json",
        "reports/stage2_native_owned_release_manifest_v1.json",
        "reports/control_plane_snapshot_2026-09-11.md",
        "reports/stage2_native_reproducibility_checklist_v1.md",
        "reports/cuhk_series_intel_delta_2026-09-11.md",
        "official_receipts/2026-09-08T2138Z_initial_verification.md",
        "official_receipts/2026-09-09T0734Z_visual_consensus_submission.md",
        "official_receipts/2026-09-09T1216Z_hau_linked_single_submission.md",
        "official_receipts/2026-09-09T1237Z_emotion_extratrees_submission.md",
        "official_receipts/2026-09-09T1323Z_final_reproducibility_freeze.md",
        "official_receipts/2026-09-09T1334Z_test_archive_complete.md",
        "official_receipts/2026-09-09T1352Z_vlm_replay_freeze.md",
        "official_receipts/2026-09-09T1357Z_final_reproducibility_freeze_v2.md",
        "official_receipts/2026-09-10T1255Z_harn_fresh20_repro.md",
        "official_receipts/2026-09-11T0216Z_final_selection_recheck.md",
        "official_receipts/2026-09-11T0328Z_sensor_option_semantics_v1_pre_fit_failure.md",
        "official_receipts/2026-09-11T0333Z_sensor_option_semantics_v1_pre_result_runtime_abort.md",
        "official_receipts/2026-09-11T0348Z_sensor_option_semantics_v1_report_literal_failure.md",
        "official_receipts/2026-09-11T0352Z_sensor_option_semantics_v1_rejection.md",
        "official_receipts/2026-09-11T0449Z_harn_stage2_native_v1_fail_closed.md",
        "official_receipts/2026-09-11T0422Z_official_team_registration.md",
        "official_receipts/2026-09-11T0443Z_stage2_native_v1_core_pass.md",
        "official_receipts/2026-09-11T0443Z_stage2_native_qwen_missing_sensor_v1_reject.md",
        "official_receipts/2026-09-11T0456Z_stage2_native_v1_network_free_candidate_pass.md",
        "official_receipts/2026-09-11T0456Z_p1_decomposed_sensor_fresh48_reject.md",
        "official_receipts/2026-09-11T0510Z_final_reproducibility_freeze_v5.md",
        "official_receipts/2026-09-11T0519Z_p1_control_plane_audit_reject.md",
        "official_receipts/2026-09-11T0519Z_stage2_owned_package_control_audit.md",
        "official_receipts/2026-09-11T0600Z_stage2_owned_raw_package.md",
        "official_receipts/2026-09-11T0520Z_p1_independent_metrics_audit_reject.md",
        "official_receipts/2026-09-11T0526Z_final_reproducibility_freeze_v6.md",
        "official_receipts/2026-09-11T0537Z_final_reproducibility_freeze_v7.md",
        "official_receipts/2026-09-11T0616Z_final_reproducibility_freeze_v8.md",
        "TECHNICAL_REPORT.md",
        "requirements-repro.txt",
        "README.md",
        "experiment_log.csv",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def valid_prediction(prediction: str, category: str) -> bool:
    if category in {"single", "combination", "emotion", "object_interaction"}:
        return len(prediction) == 1 and prediction in "ABCD"
    if category == "multi":
        return bool(prediction) and prediction == "".join(sorted(set(prediction)))
    if category == "sequence":
        return len(prediction) == 4 and set(prediction) == set("ABCD")
    return False


def validate_candidate(path: Path, test: pd.DataFrame) -> dict[str, object]:
    candidate = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(candidate.columns) != ["qa_id", "prediction"]:
        raise ValueError(f"Bad candidate schema: {path}")
    if candidate["qa_id"].tolist() != test["qa_id"].tolist() or len(candidate) != 682:
        raise ValueError(f"Candidate IDs/order mismatch: {path}")
    if candidate["qa_id"].duplicated().any() or not all(
        valid_prediction(prediction, category)
        for prediction, category in zip(candidate["prediction"], test["category"])
    ):
        raise ValueError(f"Candidate grammar mismatch: {path}")
    return {
        "rows": int(len(candidate)),
        "columns": list(candidate.columns),
        "id_order_matches_official_test": True,
        "category_grammar_pass": True,
        "sha256": sha256(path),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_path = root / "reports/final_reproducibility_manifest_2026-09-11_v9.json"
    test = pd.read_csv(
        root / "data/raw/kaggle/test_qa.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    inventory = []
    seen = set()
    for group, relative_paths in ARTIFACT_GROUPS.items():
        for relative in relative_paths:
            if relative in seen:
                raise ValueError(f"Duplicate artifact entry: {relative}")
            seen.add(relative)
            path = root / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            inventory.append(
                {
                    "group": group,
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    selected_validation = {}
    for item in SELECTED_SUBMISSIONS:
        path = root / item["file"]
        validation = validate_candidate(path, test)
        if validation["sha256"] != item["sha256"]:
            raise ValueError(f"Selected candidate hash mismatch: {item['file']}")
        selected_validation[str(item["ref"])] = validation

    qwen_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    qwen_manifest = json.loads(qwen_manifest_path.read_text(encoding="utf-8"))
    qwen_root = Path(qwen_manifest["resolved_local_path"])
    qwen_verified = []
    for item in qwen_manifest["files"]:
        path = qwen_root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Qwen model file size mismatch: {path}")
        digest = sha256(path)
        if digest != item["sha256"]:
            raise ValueError(f"Qwen model file hash mismatch: {path}")
        qwen_verified.append(item["path"])

    package_names = ["numpy", "pandas", "scikit-learn", "xgboost", "mlx", "mlx-vlm"]
    manifest = {
        "schema_version": 1,
        "snapshot_version": 9,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "supersedes": {
            "manifest": "reports/final_reproducibility_manifest_2026-09-11_v8.json",
            "manifest_sha256": "05f764d46a3fd61f48c9b4bbfca90cc26c130682783f4abba99e5c950fe26c32",
            "reason": "Supersedes v8 to freeze the strengthened owned raw-input verifier, eight fail-closed tests, both byte-identical full official replays, and the explicit release-license manifest; no selected submission or owned candidate changed.",
        },
        "competition": {
            "slug": "cuhk-x-competition-large-model-track",
            "track": "Large Model Track",
            "deadline_utc": "2026-09-15T15:55:00Z",
            "kaggle_team_exact": "Jiayi Du",
            "rules_joined": True,
            "external_registration_complete": True,
            "external_registration_confirmed_utc": "2026-09-11T04:22:09Z",
            "external_registration_receipt": "official_receipts/2026-09-11T0422Z_official_team_registration.md",
            "registered_team": "Jiayi Du",
            "registered_affiliation": "Stiftung Louisenlund",
            "registered_country_region": "Germany",
            "registered_tracks": ["Large Model Track", "Small Model Track"],
            "registered_team_size": 1,
            "registered_faculty_advisor": None,
        },
        "selected_submissions": SELECTED_SUBMISSIONS,
        "selected_candidate_validation": selected_validation,
        "governance_boundaries": {
            "status": "UNRESOLVED_HUMAN_OR_ORGANIZER_CONFIRMATION_REQUIRED",
            "not_counted_as_technical_pass": True,
            "conservative_post_competition_package_deadline_utc": "2026-09-17T15:55:00Z",
            "post_competition_deadline_policy": "Operationally resolved by using the earlier deadline without claiming the conflicting wording is authoritatively settled.",
            "small_llm_scope": "Resolved by separation: Small final inference remains non-LLM; host permission for coding assistants is development-only; the Large owned candidate has no Qwen prediction effect.",
            "license_layers": "Upstream README says MIT; current organizer LICENSE v2 is non-commercial for data/source; finalist participant source is required under Apache-2.0. Release compatibility is not marked passed.",
            "unresolved_release_blockers": [
                "Explicit participant approval to publish the clean-room source subset under Apache-2.0",
                "Confirm organizer-delivery terms for participant-trained model files derived from non-redistributable data",
            ],
        },
        "owned_stage2_candidate": {
            "file": "candidates/stage2_native_owned_v1.csv",
            "sha256": "40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8",
            "status": "VALIDATED_NOT_SUBMITTED",
            "package_status": "TECHNICAL_RAW_INPUT_PASS_GOVERNANCE_BLOCKED",
            "finalist_ready": False,
            "validation": validate_candidate(root / "candidates/stage2_native_owned_v1.csv", test),
            "network_free_replay": "reports/stage2_native_owned_raw_package_v1.json",
        },
        "lineage": [
            {
                "output": "candidates/public_fususu_077777.csv",
                "operation": "exact public Apache-2.0 anchor reproduction",
                "submission_ref": 56107594,
            },
            {
                "output": "candidates/nonvisual_sensor_union_v1.csv",
                "operation": "independent pre-gated HARn single and HAU emotion union",
                "submission_ref": 56108595,
            },
            {
                "output": "candidates/visual_sensor_consensus_v1.csv",
                "operation": "sensor-present zero-shot VLM/sensor consensus over nonvisual union",
                "submission_ref": 56116980,
            },
            {
                "output": "candidates/hau_linked_single_consensus_v1.csv",
                "operation": "HAU combination-to-single structural inference plus sensor agreement",
                "submission_ref": 56122175,
            },
            {
                "output": "candidates/emotion_extratrees_rf_union_v1.csv",
                "operation": "HAU emotion ExtraTrees/RF consensus union over linked/visual base",
                "submission_ref": 56122653,
            },
            {
                "output": "candidates/stage2_native_owned_v1.csv",
                "operation": "self-contained train-native semantic decoder plus owned HARn skeleton RF and HAU emotion ET/RF consensus; no fixed public test vector",
                "submission_ref": None,
            },
        ],
        "post_freeze_research": [
            {
                "experiment": "sensor_option_semantics_triad_v1",
                "decision": "REJECT_NO_TEST_NO_SUBMISSION",
                "report": "reports/sensor_option_semantics_v1_validation.json",
                "test_qa_read": False,
                "test_prediction_written": False,
                "candidate_csv_written": False,
                "submission_performed": False,
            },
            {
                "experiment": "harn_stage2_native_v1",
                "decision": "REJECTED_IMPLEMENTATION_ABORT_NO_CANDIDATE",
                "report": "reports/harn_stage2_native_v1_rejection.json",
                "fresh_rows_planned": 48,
                "fresh_rows_logged": 35,
                "test_prediction_written": False,
                "candidate_csv_written": False,
                "submission_performed": False,
            },
            {
                "experiment": "stage2_native_owned_full_system_v1",
                "decision": "PASS_CORE_AND_DETERMINISTIC_NETWORK_FREE_CANDIDATE",
                "report": "reports/stage2_native_v1_oof_validation.json",
                "candidate": "candidates/stage2_native_owned_v1.csv",
                "candidate_sha256": "40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8",
                "submission_performed": False,
            },
            {
                "experiment": "stage2_native_qwen_missing_sensor_v1",
                "decision": "REJECT_KEEP_QWEN_DIAGNOSTIC_ONLY",
                "report": "reports/stage2_native_qwen_missing_sensor_v1_validation.json",
                "test_qa_read": False,
                "candidate_csv_written": False,
                "submission_performed": False,
            },
            {
                "experiment": "p1_decomposed_sensor_fresh48_v1",
                "decision": "REJECT_P1_CONTROL_AUDIT_NO_RETRY",
                "report": "reports/p1_independent_control_audit_v1.json",
                "test_qa_read": False,
                "candidate_csv_written": False,
                "submission_performed": False,
            },
            {
                "experiment": "stage2_owned_package_control_v1",
                "decision": "PASS_TECHNICAL_RAW_PACKAGE_BLOCK_RELEASE_LICENSE_REVIEW",
                "report": "reports/stage2_owned_package_control_audit_v1.json",
                "raw_organizer_sensor_to_feature_cache_packaged": True,
                "owned_builder_called_by_inference_sh": True,
                "two_clean_raw_replays_byte_identical": True,
                "governance_review_resolved": False,
                "submission_performed": False,
            },
            {
                "experiment": "p1_independent_metrics_recomputation_v1",
                "decision": "REJECT_P1_NO_CANDIDATE_NO_SUBMISSION",
                "report": "reports/p1_decomposed_sensor_fresh48_independent_audit_v1.json",
                "no_inference_performed": True,
                "test_qa_read": False,
                "candidate_csv_written": False,
                "submission_performed": False,
            },
            {
                "experiment": "p2_label_blind_media_readiness_v1",
                "decision": "PROPOSED_NOT_FROZEN_NO_INFERENCE",
                "report": "reports/p2_unexposed_video_preflight_and_proposal_v1.json",
                "eligible_rows_minimum_8_frames": 206,
                "protocol_frozen": False,
                "inference_performed": False,
                "submission_performed": False,
            }
        ],
        "artifact_inventory": inventory,
        "qwen_model_verification": {
            "repo_id": qwen_manifest["repo_id"],
            "revision": qwen_manifest["revision"],
            "license": qwen_manifest["license"],
            "manifest_sha256": sha256(qwen_manifest_path),
            "files_verified": len(qwen_verified),
            "total_bytes": qwen_manifest["total_bytes"],
        },
        "runtime": {
            "python": platform.python_version(),
            "packages": {
                name: importlib.metadata.version(name) for name in package_names
            },
        },
        "verification_command": (
            "../.venv/bin/python scripts/verify_final_repro_manifest.py "
            "reports/final_reproducibility_manifest_2026-09-11_v9.json"
        ),
    }
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(output_path.relative_to(root)),
                "manifest_sha256": sha256(output_path),
                "artifacts": len(inventory),
                "qwen_files_verified": len(qwen_verified),
                "selected_candidates": len(SELECTED_SUBMISSIONS),
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
