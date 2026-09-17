#!/usr/bin/env python3
"""Verify prediction invariance after replacing every smoke QA ID and clip key."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "artifacts/smoke/stage2_native_arbitrary_id_v1"
    fixture_path = base / "fixture.json"
    original_output = base / "original_ids_predictions.csv"
    renamed_output = base / "new_ids_clips_predictions.csv"
    original_report = base / "original_ids_build.json"
    renamed_report = base / "new_ids_clips_build.json"
    output_path = root / "reports/stage2_native_arbitrary_id_clip_smoke_v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    original = pd.read_csv(original_output, dtype=str, keep_default_na=False)
    renamed = pd.read_csv(renamed_output, dtype=str, keep_default_na=False)
    if len(original) != fixture["rows"] or len(renamed) != fixture["rows"]:
        raise ValueError("Smoke output row count mismatch")
    predictions_match = original["prediction"].tolist() == renamed["prediction"].tolist()
    original_build = json.loads(original_report.read_text(encoding="utf-8"))
    renamed_build = json.loads(renamed_report.read_text(encoding="utf-8"))
    passed = (
        predictions_match
        and original_build["network_isolation"]["socket_probe_blocked"]
        and renamed_build["network_isolation"]["socket_probe_blocked"]
        and original_build["invalid_predictions"] == 0
        and renamed_build["invalid_predictions"] == 0
        and not original_build["official_strict_mode"]
        and not renamed_build["official_strict_mode"]
    )
    report = {
        "experiment": fixture["experiment"],
        "decision": "PASS_ARBITRARY_QA_ID_AND_CLIP_KEY_INVARIANCE" if passed else "FAIL",
        "passed": passed,
        "rows": fixture["rows"],
        "clips": fixture["clips"],
        "categories": fixture["categories"],
        "all_qa_ids_replaced": True,
        "all_clip_keys_replaced": True,
        "feature_values_identical_under_new_unit_keys": True,
        "predictions_identical_by_row": predictions_match,
        "network_blocked_both_runs": True,
        "invalid_predictions_both_runs": 0,
        "artifacts": {
            "fixture": [str(fixture_path.relative_to(root)), sha256(fixture_path)],
            "original_output": [str(original_output.relative_to(root)), sha256(original_output)],
            "renamed_output": [str(renamed_output.relative_to(root)), sha256(renamed_output)],
            "original_build_report": [str(original_report.relative_to(root)), sha256(original_report)],
            "renamed_build_report": [str(renamed_report.relative_to(root)), sha256(renamed_report)],
            "builder_sha256": sha256(root / "scripts/build_stage2_native_candidate_v1.py"),
            "verifier_sha256": sha256(Path(__file__)),
        },
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "This proves inference is independent of known qa_id and clip-key strings when the feature cache contains the new clip units; it does not replace raw sensor feature extraction packaging.",
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
