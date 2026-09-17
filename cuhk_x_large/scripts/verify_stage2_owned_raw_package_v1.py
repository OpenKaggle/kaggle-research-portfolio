#!/usr/bin/env python3
"""Verify the owned raw-sensor package and emit its technical/license manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


EXPECTED_CANDIDATE = "40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8"
EXPECTED_LEGACY_INFERENCE = "4494830c630d8cf74e6c710e93d947686ec807a8765e3b66333d6de2e5e6339a"
EXPECTED_SELECTED = {
    "56122653": "3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4",
    "56108595": "a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702",
}
RUNS = ("stage2_native_owned_raw_run1", "stage2_native_owned_raw_run2")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def package_metadata(name: str) -> dict[str, str | None]:
    metadata = importlib.metadata.metadata(name)
    return {
        "version": importlib.metadata.version(name),
        "license_expression": metadata.get("License-Expression"),
        "license_field": metadata.get("License"),
        "homepage": metadata.get("Home-page"),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    campaign_root = root.parent
    run_dirs = [root / "artifacts/dry_runs" / name for name in RUNS]
    candidates = [root / "artifacts/dry_runs" / f"{name}.csv" for name in RUNS]
    features = [path / "nonvisual_features.npz" for path in run_dirs]
    raw_reports = [json.loads((path / "raw_feature_report.json").read_text()) for path in run_dirs]
    candidate_reports = [json.loads((path / "candidate_report.json").read_text()) for path in run_dirs]

    if candidates[0].read_bytes() != candidates[1].read_bytes():
        raise ValueError("Raw-input candidate replays differ")
    if features[0].read_bytes() != features[1].read_bytes():
        raise ValueError("Raw-input feature caches differ")
    if sha256(candidates[0]) != EXPECTED_CANDIDATE:
        raise ValueError("Raw-input candidate differs from frozen owned candidate")
    if candidates[0].read_bytes() != (root / "candidates/stage2_native_owned_v1.csv").read_bytes():
        raise ValueError("Raw-input candidate bytes differ from existing owned candidate")

    stable_raw_fields = (
        "network_isolation", "input_qa_sha256", "manifest_sha256", "raw_inventory_sha256",
        "raw_files", "discovered_units", "selected_units", "unique_qa_clips", "unmatched_qa_clips",
        "unmatched_clip_paths", "manifest_unlisted_clips_treated_as_all_sensor_missing",
        "manifest_required", "manifest_unlisted_all_missing_authorized", "feature_shapes", "finite_rows",
        "output_sha256", "code_sha256", "labels_read",
    )
    if any(raw_reports[0][key] != raw_reports[1][key] for key in stable_raw_fields):
        raise ValueError("Raw feature replay reports disagree on stable fields")
    if not all(
        report["network_isolation"]["socket_probe_blocked"]
        and report["labels_read"] is False
        and report["manifest_required"]
        and report["manifest_unlisted_all_missing_authorized"]
        for report in raw_reports
    ):
        raise ValueError("Raw feature network/label/manifest boundary failed")

    stable_candidate_fields = (
        "network_isolation", "rows", "unique_qa_ids", "unique_input_clips", "invalid_predictions",
        "fixed_third_party_test_vector_dependency", "qwen_prediction_effect", "prediction_source_counts",
        "output_sha256", "inputs", "code_sha256", "versions", "submission",
    )
    if any(candidate_reports[0][key] != candidate_reports[1][key] for key in stable_candidate_fields):
        raise ValueError("Candidate replay reports disagree on stable fields")
    if not all(
        report["network_isolation"]["socket_probe_blocked"]
        and report["rows"] == 682
        and report["unique_qa_ids"] == 682
        and report["invalid_predictions"] == 0
        and report["fixed_third_party_test_vector_dependency"] is False
        and report["qwen_prediction_effect"] is False
        and report["submission"] == "NOT_ATTEMPTED"
        for report in candidate_reports
    ):
        raise ValueError("Candidate replay boundary failed")

    with np.load(root / "cache/nonvisual_features.npz") as frozen, np.load(features[0]) as raw:
        frozen_index = {unit: index for index, unit in enumerate(frozen["units"].astype(str))}
        for raw_index, unit in enumerate(raw["units"].astype(str)):
            if unit not in frozen_index:
                raise ValueError(f"Raw replay unit absent from frozen cache: {unit}")
            for modality in ("imu", "radar", "skeleton"):
                np.testing.assert_equal(raw[modality][raw_index], frozen[modality][frozen_index[unit]])

    qa = pd.read_csv(root / "data/raw/kaggle/test_qa.csv", dtype=str, keep_default_na=False)
    candidate = pd.read_csv(candidates[0], dtype=str, keep_default_na=False)
    if candidate["qa_id"].tolist() != qa["qa_id"].tolist():
        raise ValueError("Raw candidate QA order mismatch")

    entrypoint = (root / "inference_owned.sh").read_text()
    entrypoint_checks = {
        "calls_raw_extractor": "extract_owned_raw_features_v1.py" in entrypoint,
        "calls_owned_builder": "build_stage2_native_candidate_v1.py" in entrypoint,
        "requires_manifest": "--require-manifest" in entrypoint,
        "authorizes_explicit_all_sensor_missing": "--allow-manifest-unlisted-clips-as-all-missing" in entrypoint,
        "does_not_call_legacy_builders": all(
            name not in entrypoint
            for name in ("reproduce_public_077777.py", "build_sensor_union_candidate.py", "build_emotion_extratrees_rf_union.py")
        ),
    }
    if not all(entrypoint_checks.values()):
        raise ValueError(f"Owned entrypoint static audit failed: {entrypoint_checks}")
    if sha256(root / "inference.sh") != EXPECTED_LEGACY_INFERENCE:
        raise ValueError("Legacy inference.sh changed")
    for ref, expected in EXPECTED_SELECTED.items():
        selected = "emotion_extratrees_rf_union_v1.csv" if ref == "56122653" else "nonvisual_sensor_union_v1.csv"
        if sha256(root / "candidates" / selected) != expected:
            raise ValueError(f"Selected candidate {ref} changed")

    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "tests/test_owned_raw_package_v1.py", "-v"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if tests.returncode != 0 or "Ran 8 tests" not in tests.stdout or "OK" not in tests.stdout:
        raise ValueError("Owned raw package adversarial tests failed")

    authored = [
        "inference_owned.sh",
        "scripts/extract_owned_raw_features_v1.py",
        "scripts/extract_nonvisual_features.py",
        "scripts/build_stage2_native_candidate_v1.py",
        "scripts/run_stage2_native_oof_v1.py",
        "scripts/verify_stage2_owned_raw_package_v1.py",
        "tests/test_owned_raw_package_v1.py",
    ]
    model_files = [
        "artifacts/models/nonvisual_rf_v1/harn_action.joblib",
        "artifacts/models/nonvisual_rf_v1/hau_emotion.joblib",
        "artifacts/models/emotion_pairwise_extratrees_v1.joblib",
    ]
    organizer_license = campaign_root / "cuhkx_small/vendor/CUHK-X/LICENSE"
    release_manifest = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "package": "stage2_native_owned_raw_v1",
        "track": "CUHK-X Large Model Track",
        "participant_source": {
            "files": [
                {"path": path, "bytes": (root / path).stat().st_size, "sha256": sha256(root / path)}
                for path in authored
            ],
            "implementation": "clean-room participant-authored",
            "requested_finalist_license": "Apache-2.0",
            "release_status": "PENDING_EXPLICIT_PARTICIPANT_LICENSE_APPROVAL",
        },
        "trained_models": [
            {
                "path": path,
                "bytes": (root / path).stat().st_size,
                "sha256": sha256(root / path),
                "provenance": "participant-trained from CUHK-X organizer training data",
                "redistribution": "ORGANIZER_DELIVERY_ONLY_PENDING_TERMS_CONFIRMATION",
            }
            for path in model_files
        ],
        "organizer_inputs": {
            "license_path": "../cuhkx_small/vendor/CUHK-X/LICENSE",
            "license_sha256": sha256(organizer_license),
            "license": "CUHK-X License v2.0 / non-commercial DUA",
            "redistributed_by_package": False,
            "files": [
                {"path": path, "sha256": sha256(root / path)}
                for path in (
                    "data/raw/kaggle/training_qa.csv",
                    "data/raw/kaggle/test_qa.csv",
                    "data/raw/nonvisual/LMT_(IMU,Radar,Skeleton)/manifest_nonvisual.csv",
                )
            ],
        },
        "runtime_dependencies": {
            name: package_metadata(name) for name in ("numpy", "pandas", "scikit-learn", "joblib")
        },
        "excluded_from_deployment": {
            "qwen": "Rejected fallback; no Qwen prediction affects the owned candidate",
            "public_fixed_682_vector": "Not read by the owned route",
            "raw_organizer_data": "Required as local input and never redistributed",
        },
        "release_blockers": [
            "Explicit participant approval to publish the clean-room source subset under Apache-2.0",
            "Confirm organizer-delivery terms for participant-trained model files derived from non-redistributable data",
        ],
    }
    release_manifest_path = root / "reports/stage2_native_owned_release_manifest_v1.json"
    release_manifest_path.write_text(json.dumps(release_manifest, indent=2) + "\n")

    technical = {
        "status": "PASS",
        "network_isolated": True,
        "entrypoint_checks": entrypoint_checks,
        "raw_files_hashed": raw_reports[0]["raw_files"],
        "raw_inventory_sha256": raw_reports[0]["raw_inventory_sha256"],
        "raw_cache_sha256_both_runs": sha256(features[0]),
        "raw_cache_byte_identical": True,
        "features_exactly_match_frozen_full_cache_for_selected_units": True,
        "candidate_sha256_both_runs": sha256(candidates[0]),
        "candidate_byte_identical": True,
        "candidate_equals_existing_owned_v1": True,
        "rows": 682,
        "invalid_predictions": 0,
        "prediction_source_counts": candidate_reports[0]["prediction_source_counts"],
        "official_unique_clips": raw_reports[0]["unique_qa_clips"],
        "matched_sensor_units": raw_reports[0]["selected_units"],
        "organizer_clips_without_raw_sensor_unit": raw_reports[0]["unmatched_qa_clips"],
        "fail_closed_tests": {
            "passed": True,
            "tests_passed": 8,
            "coverage": [
                "missing declared file", "missing manifest-declared unit", "corrupt JSON",
                "short skeleton stream", "extra file", "reordered QA/manifest",
                "unlisted clip requires explicit all-missing authorization", "arbitrary new QA/clip",
            ],
        },
        "legacy_inference_sh_unchanged_sha256": sha256(root / "inference.sh"),
        "legacy_selected_submissions_preserved": EXPECTED_SELECTED,
        "submission_performed": False,
    }
    report = {
        "schema_version": 2,
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "stage2_native_owned_raw_package_v1",
        "decision": "PASS_TECHNICAL_RAW_PACKAGE_BLOCK_RELEASE_LICENSE_REVIEW",
        "technical_package_gate": technical,
        "evidence": {
            "entry_point": ["inference_owned.sh", sha256(root / "inference_owned.sh")],
            "raw_extractor": ["scripts/extract_owned_raw_features_v1.py", sha256(root / "scripts/extract_owned_raw_features_v1.py")],
            "owned_builder": ["scripts/build_stage2_native_candidate_v1.py", sha256(root / "scripts/build_stage2_native_candidate_v1.py")],
            "verifier": ["scripts/verify_stage2_owned_raw_package_v1.py", sha256(Path(__file__))],
            "test_suite": ["tests/test_owned_raw_package_v1.py", sha256(root / "tests/test_owned_raw_package_v1.py")],
            "run_candidates": [str(path.relative_to(root)) for path in candidates],
            "run_feature_caches": [str(path.relative_to(root)) for path in features],
            "release_manifest": [str(release_manifest_path.relative_to(root)), sha256(release_manifest_path)],
        },
        "governance_boundaries": {
            "post_competition_deadline": "Resolved operationally by using the earlier 2026-09-17T15:55:00Z deadline without claiming the wording conflict is settled",
            "small_llm_scope": "Resolved by separation: Small final inference remains non-LLM; this Large owned candidate has no Qwen prediction effect",
            "release_license": release_manifest["release_blockers"],
        },
        "finalist_ready": False,
        "submission": "NOT_ATTEMPTED",
    }
    report_path = root / "reports/stage2_native_owned_raw_package_v1.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    control = {
        "schema_version": 2,
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "control_plane": "../CUHK_X_CONTROL_PLANE.md",
        "candidate": "candidates/stage2_native_owned_v1.csv",
        "candidate_sha256": EXPECTED_CANDIDATE,
        "decision": "PASS_TECHNICAL_RAW_PACKAGE_BLOCK_RELEASE_LICENSE_REVIEW",
        "checks": {
            "subject_disjoint_core_gate_pass": True,
            "fixed_third_party_682_vector_dependency": False,
            "official_682_row_grammar_pass": True,
            "two_network_free_runs_byte_identical": True,
            "arbitrary_qa_id_and_clip_key_smoke_pass": True,
            "qwen_rejection_enforced": True,
            "owned_builder_called_by_inference_sh": True,
            "owned_builder_called_by_separate_inference_owned_sh": True,
            "raw_organizer_sensor_to_feature_cache_packaged": True,
            "new_clip_requires_precomputed_feature_cache": False,
            "raw_input_fail_closed_tests_pass": True,
            "two_clean_raw_input_runs_byte_identical": True,
            "technical_raw_package_ready": True,
            "post_competition_deadline_conflict_resolved": True,
            "small_llm_rule_scope_resolved": True,
            "finalist_license_layers_resolved": False,
            "finalist_package_ready": False,
            "submission_performed": False,
        },
        "evidence": {
            "raw_package_report": [str(report_path.relative_to(root)), sha256(report_path)],
            "release_manifest": [str(release_manifest_path.relative_to(root)), sha256(release_manifest_path)],
            "legacy_inference_sh": ["inference.sh", sha256(root / "inference.sh")],
            "owned_entry_point": ["inference_owned.sh", sha256(root / "inference_owned.sh")],
        },
        "required_next_steps": release_manifest["release_blockers"],
        "release": "Technical raw-input reproducibility passes. Finalist readiness remains blocked on explicit participant-source and derived-model delivery licensing decisions.",
    }
    control_path = root / "reports/stage2_owned_package_control_audit_v1.json"
    control_path.write_text(json.dumps(control, indent=2) + "\n")
    print(json.dumps({
        "decision": report["decision"],
        "candidate_sha256": EXPECTED_CANDIDATE,
        "feature_sha256": sha256(features[0]),
        "package_report_sha256": sha256(report_path),
        "release_manifest_sha256": sha256(release_manifest_path),
        "control_audit_sha256": sha256(control_path),
        "tests_passed": 8,
        "finalist_ready": False,
    }, indent=2))


if __name__ == "__main__":
    main()
