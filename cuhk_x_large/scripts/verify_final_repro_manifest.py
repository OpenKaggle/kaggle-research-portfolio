#!/usr/bin/env python3
"""Independently verify a frozen CUHK-X Large reproducibility manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


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


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema")
    version_match = re.search(r"_v(\d+)\.json$", manifest_path.name)
    if version_match and manifest.get("snapshot_version") != int(version_match.group(1)):
        raise ValueError("Versioned manifest snapshot_version does not match its filename")
    if manifest["competition"]["deadline_utc"] != "2026-09-15T15:55:00Z":
        raise ValueError("Competition deadline mismatch")
    if not manifest["competition"].get("external_registration_complete"):
        raise ValueError("Official registration is not recorded as complete")
    if [item["ref"] for item in manifest["selected_submissions"]] != [56122653, 56108595]:
        raise ValueError("Selected submission refs mismatch")

    seen = set()
    for item in manifest["artifact_inventory"]:
        relative = item["path"]
        if relative in seen:
            raise ValueError(f"Duplicate artifact: {relative}")
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Artifact size mismatch: {relative}")
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Artifact hash mismatch: {relative}")

    test = pd.read_csv(
        root / "data/raw/kaggle/test_qa.csv",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )
    for selected in manifest["selected_submissions"]:
        path = root / selected["file"]
        candidate = pd.read_csv(path, dtype=str, keep_default_na=False)
        if list(candidate.columns) != ["qa_id", "prediction"]:
            raise ValueError(f"Candidate schema mismatch: {selected['file']}")
        if candidate["qa_id"].tolist() != test["qa_id"].tolist() or len(candidate) != 682:
            raise ValueError(f"Candidate ID/order mismatch: {selected['file']}")
        if not all(
            valid_prediction(prediction, category)
            for prediction, category in zip(candidate["prediction"], test["category"])
        ):
            raise ValueError(f"Candidate grammar mismatch: {selected['file']}")
        if sha256(path) != selected["sha256"]:
            raise ValueError(f"Selected candidate hash mismatch: {selected['file']}")

    owned = manifest.get("owned_stage2_candidate")
    if not owned or owned.get("status") != "VALIDATED_NOT_SUBMITTED":
        raise ValueError("Owned Stage2 candidate status mismatch")
    if owned.get("package_status") != "TECHNICAL_RAW_INPUT_PASS_GOVERNANCE_BLOCKED":
        raise ValueError("Owned Stage2 package boundary mismatch")
    if owned.get("finalist_ready") is not False:
        raise ValueError("Owned Stage2 candidate must not be marked finalist-ready")
    owned_path = root / owned["file"]
    owned_candidate = pd.read_csv(owned_path, dtype=str, keep_default_na=False)
    if list(owned_candidate.columns) != ["qa_id", "prediction"]:
        raise ValueError("Owned Stage2 candidate schema mismatch")
    if owned_candidate["qa_id"].tolist() != test["qa_id"].tolist() or len(owned_candidate) != 682:
        raise ValueError("Owned Stage2 candidate ID/order mismatch")
    if not all(
        valid_prediction(prediction, category)
        for prediction, category in zip(owned_candidate["prediction"], test["category"])
    ):
        raise ValueError("Owned Stage2 candidate grammar mismatch")
    if sha256(owned_path) != owned["sha256"]:
        raise ValueError("Owned Stage2 candidate hash mismatch")
    governance = manifest.get("governance_boundaries", {})
    if governance.get("status") != "UNRESOLVED_HUMAN_OR_ORGANIZER_CONFIRMATION_REQUIRED":
        raise ValueError("Finalist governance boundary was incorrectly marked resolved")
    if governance.get("not_counted_as_technical_pass") is not True:
        raise ValueError("Governance boundary must remain separate from the technical pass")
    if governance.get("conservative_post_competition_package_deadline_utc") != "2026-09-17T15:55:00Z":
        raise ValueError("Conservative post-competition package deadline mismatch")
    if not governance.get("post_competition_deadline_policy", "").startswith("Operationally resolved"):
        raise ValueError("Post-competition deadline policy is not operationally resolved")
    if not governance.get("small_llm_scope", "").startswith("Resolved by separation"):
        raise ValueError("Small/Large LLM scope separation mismatch")
    expected_release_blockers = [
        "Explicit participant approval to publish the clean-room source subset under Apache-2.0",
        "Confirm organizer-delivery terms for participant-trained model files derived from non-redistributable data",
    ]
    if governance.get("unresolved_release_blockers") != expected_release_blockers:
        raise ValueError("Finalist release-license blockers mismatch")

    package_audit = json.loads(
        (root / "reports/stage2_owned_package_control_audit_v1.json").read_text(encoding="utf-8")
    )
    package_checks = package_audit.get("checks", {})
    if package_audit.get("decision") != "PASS_TECHNICAL_RAW_PACKAGE_BLOCK_RELEASE_LICENSE_REVIEW":
        raise ValueError("Owned package audit decision mismatch")
    if package_checks.get("technical_raw_package_ready") is not True:
        raise ValueError("Owned raw package is not technically ready")
    if package_checks.get("finalist_license_layers_resolved") is not False:
        raise ValueError("Finalist license boundary was incorrectly marked resolved")
    if package_checks.get("finalist_package_ready") is not False:
        raise ValueError("Finalist package was incorrectly marked ready")

    qwen_manifest_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    qwen_manifest = json.loads(qwen_manifest_path.read_text(encoding="utf-8"))
    qwen_root = Path(qwen_manifest["resolved_local_path"])
    for item in qwen_manifest["files"]:
        path = qwen_root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Qwen file size mismatch: {item['path']}")
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Qwen file hash mismatch: {item['path']}")

    with (root / "experiment_log.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows[0]) != 16 or any(len(row) != 16 for row in rows):
        raise ValueError("Experiment log column invariant failed")
    submission_refs = {row[12] for row in rows[1:] if row[12]}
    if not {"56122653", "56108595"}.issubset(submission_refs):
        raise ValueError("Selected refs are absent from experiment log")

    output_name = manifest_path.name.replace("manifest", "verification", 1)
    output_path = root / "reports" / output_name
    result = {
        "status": "PASS",
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path.relative_to(root)),
        "manifest_sha256": sha256(manifest_path),
        "artifact_files_verified": len(manifest["artifact_inventory"]),
        "qwen_model_files_verified": len(qwen_manifest["files"]),
        "selected_candidates_verified": len(manifest["selected_submissions"]),
        "owned_stage2_candidate_verified": True,
        "owned_stage2_raw_technical_pass": True,
        "finalist_governance_resolved": False,
        "experiment_log_rows": len(rows) - 1,
        "verifier_code_sha256": sha256(Path(__file__)),
    }
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    print(f"verification_report_sha256={sha256(output_path)}", flush=True)


if __name__ == "__main__":
    main()
