#!/usr/bin/env python3
"""Regression checks for the aggregate submission-readiness audit."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tools.audit_submission_readiness import audit, readiness_blockers  # noqa: E402


class SubmissionReadinessTest(unittest.TestCase):
    def test_active_manifest_is_structurally_valid_but_not_ready(self) -> None:
        result = audit(ROOT / "paper/manifests/submission_readiness_v1.json")
        self.assertTrue(result["passes"])
        self.assertFalse(result["final_ready"])
        codes = {item["code"] for item in result["blockers"]}
        self.assertEqual(
            codes,
            {
                "writeup_not_final",
                "rubric_dimensions_not_supported",
                "pipeline_incomplete",
                "holdout_contaminated_for_method_generalization",
                "no_verified_eligible_generalization_corpus",
                "release_not_final",
                "dependencies_unresolved",
                "final_bindings_incomplete",
                "platform_receipts_incomplete",
                "authorship_approvals_incomplete",
            },
        )

    def test_all_green_inputs_have_no_blockers(self) -> None:
        writeup = {
            "final_ready": True,
            "rubric_status": {
                name: "supported"
                for name in (
                    "Accuracy",
                    "Universality",
                    "Progress",
                    "Theory",
                    "Completeness",
                    "Novelty",
                )
            },
        }
        pipeline = {"pipeline_complete": True}
        corpus = {
            "status": "VERIFIED_ELIGIBLE_ARC_AGI_2_GENERALIZATION_CORPUS"
        }
        release = {"passes": True, "status": "FINAL_RELEASE_CANDIDATE"}
        dependencies = {"passes": True, "unresolved_dependencies": []}
        bindings = {key: "x" for key in (
            "arc_submission_id",
            "project_url",
            "public_notebook_url",
            "public_notebook_version",
            "source_commit",
            "source_repository_url",
            "writeup_url",
        )}
        for key in ("cover_sha256", "platform_count_receipt_sha256", "submission_sha256"):
            bindings[key] = "a" * 64
        platform = {key: "b" * 64 for key in (
            "cover_attachment_receipt_sha256",
            "paper_submission_receipt_sha256",
        )}
        approvals = {key: True for key in (
            "author_order_frozen",
            "author_ip_approved",
            "employer_not_required_or_approved",
            "final_claim_reviewed",
        )}
        self.assertEqual(
            readiness_blockers(
                writeup,
                pipeline,
                corpus,
                release,
                dependencies,
                bindings,
                platform,
                approvals,
            ),
            [],
        )

    def test_hash_drift_fails_structure(self) -> None:
        source = ROOT / "paper/manifests/submission_readiness_v1.json"
        manifest = json.loads(source.read_text(encoding="utf-8"))
        manifest["project_root"] = str(ROOT)
        manifest["artifacts"]["cover"]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory(prefix="arc2-readiness-") as raw:
            target = pathlib.Path(raw) / "manifest.json"
            target.write_text(json.dumps(manifest), encoding="utf-8")
            result = audit(target)
        self.assertFalse(result["passes"])
        self.assertIn(
            "artifact_hash_mismatch", {item["code"] for item in result["violations"]}
        )

    def test_final_status_rejects_current_blockers(self) -> None:
        source = ROOT / "paper/manifests/submission_readiness_v1.json"
        manifest = json.loads(source.read_text(encoding="utf-8"))
        manifest["project_root"] = str(ROOT)
        manifest["status"] = "FINAL_SUBMISSION_READY"
        with tempfile.TemporaryDirectory(prefix="arc2-readiness-") as raw:
            target = pathlib.Path(raw) / "manifest.json"
            target.write_text(json.dumps(manifest), encoding="utf-8")
            result = audit(target)
        self.assertFalse(result["passes"])
        self.assertFalse(result["final_ready"])
        self.assertIn(
            "final_status_with_blockers", {item["code"] for item in result["violations"]}
        )


if __name__ == "__main__":
    unittest.main()
