import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from evidence_registry import (  # noqa: E402
    EXPERIMENT_COLUMNS,
    register_final_selection,
    register_readiness,
    register_system_manifest,
    sha256,
)
from campaign_readiness_audit import run as run_readiness  # noqa: E402
from final_submission_selector import run as run_selector  # noqa: E402
from system_implementation_manifest_audit import run as run_system_manifest  # noqa: E402


class EvidenceRegistryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "traffic"
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir(parents=True)
        self.status_path = self.artifacts / "campaign_status.json"
        self.ledger_path = self.artifacts / "experiment_ledger.csv"
        self.submission_path = self.artifacts / "submission_ledger.csv"
        self.status_path.write_text(json.dumps({
            "lifecycle": {},
            "current_best": {"submission_id": 7, "public_score": 0.75, "sha256": "a" * 64},
            "current_candidate": {"fallback_submission_id": 6},
        }) + "\n")
        with self.ledger_path.open("w", newline="") as handle:
            csv.DictWriter(handle, fieldnames=EXPERIMENT_COLUMNS).writeheader()
        self.submission_path.write_text("submission_id,status\n7,COMPLETE\n")

    def tearDown(self):
        self.temporary.cleanup()

    def inputs(self):
        return {
            "campaign_status.json": sha256(self.status_path),
            "experiment_ledger.csv": sha256(self.ledger_path),
            "submission_ledger.csv": sha256(self.submission_path),
        }

    def make_system_manifest(self, name="system_manifest"):
        config_dir = self.root / "config"
        source_dir = self.root / "src"
        official_dir = self.root / "official"
        config_dir.mkdir()
        source_dir.mkdir()
        official_dir.mkdir()
        (source_dir / "worker.py").write_text("VALUE = 1\n")
        config_path = config_dir / "system_implementation_manifest_v1.json"
        config_path.write_text(json.dumps({
            "version": "system_implementation_manifest_v1",
            "official_code_commit": "abc123",
            "manifest_rules": [
                {"category": "config", "pattern": "config/*.json", "expected_count": 1},
                {"category": "source", "pattern": "src/*.py", "expected_count": 1},
            ],
            "canonical_receipts": [],
            "forbidden_path_prefixes": ["data/", "official/", "public_notebooks/"],
            "information_boundary": {
                "competition_data_read": False,
                "submission_artifact_read": False,
                "hidden_label_or_metric_read": False,
                "external_action_performed": False,
            },
        }) + "\n")
        output = self.artifacts / name
        with patch(
            "system_implementation_manifest_audit.subprocess.check_output",
            return_value="abc123\n",
        ):
            run_system_manifest(self.root, config_path, output)
        return output / "system_implementation_manifest_receipt.json", source_dir / "worker.py"

    def test_registers_readiness_and_final_selection_idempotently(self):
        readiness_path = self.artifacts / "campaign_readiness_D3" / "campaign_readiness_receipt.json"
        readiness_path.parent.mkdir()
        readiness = {
            "status": "READY_FOR_FINAL_SELECTION",
            "experiment": "campaign_readiness_D3",
            "as_of": "2026-11-04T15:00:00+08:00",
            "executed_at_utc": "2026-11-04T07:00:01+00:00",
            "phase": "D3_BUGFIX_AND_FINAL_SELECTION_ONLY",
            "checks_passed": 18,
            "checks_warned": 0,
            "checks_failed": 1,
            "archive_sha_verified_now": True,
            "activation": {"requested": True, "observed_as_of_age_seconds": 1.0},
            "failures": [{"requirement": "D3_final_selection_control"}],
            "runtime_seconds": 6.0,
            "peak_memory_mb": 64.0,
            "goal_completion_boundary": "perform final selection",
            "inputs": self.inputs(),
        }
        readiness_path.write_text(json.dumps(readiness) + "\n")
        self.assertEqual(register_readiness(self.root, readiness_path)["status"], "REGISTERED")
        self.assertEqual(register_readiness(self.root, readiness_path)["status"], "ALREADY_REGISTERED")
        status = json.loads(self.status_path.read_text())
        self.assertEqual(status["lifecycle"]["readiness"]["status"], "READY_FOR_FINAL_SELECTION")

        final_path = self.artifacts / "final_submission" / "final_submission_selection_receipt.json"
        final_path.parent.mkdir()
        final = {
            "status": "FINAL_SELECTED",
            "experiment": "final_submission_selection",
            "selection_final": True,
            "external_kaggle_action_performed": False,
            "as_of": "2026-11-04T15:01:00+08:00",
            "executed_at_utc": "2026-11-04T07:01:01+00:00",
            "runtime_seconds": 0.5,
            "peak_memory_mb": 44.0,
            "clock_gate": {
                "live_clock_enforced": True,
                "observed_as_of_age_seconds": 1.0,
                "observed_D3_readiness_age_seconds": 60.0,
            },
            "selected": {"submission_id": 7, "public_score": 0.75, "sha256": "a" * 64},
            "fallback": {"submission_id": 6},
            "inputs": {
                **self.inputs(),
                "readiness_receipt.json": status["lifecycle"]["readiness"]["receipt_sha256"],
            },
        }
        final_path.write_text(json.dumps(final) + "\n")
        self.assertEqual(register_final_selection(self.root, final_path)["status"], "REGISTERED")
        self.assertEqual(register_final_selection(self.root, final_path)["status"], "ALREADY_REGISTERED")
        status = json.loads(self.status_path.read_text())
        self.assertEqual(status["final_selection"]["submission_id"], 7)
        with self.ledger_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["status"] for row in rows], ["READY_FOR_FINAL_SELECTION", "FINAL_SELECTED"])

    def test_rejects_unactivated_or_ungated_receipts(self):
        readiness_path = self.artifacts / "bad_readiness" / "campaign_readiness_receipt.json"
        readiness_path.parent.mkdir()
        readiness_path.write_text(json.dumps({
            "status": "READY",
            "activation": {"requested": False, "observed_as_of_age_seconds": None},
        }) + "\n")
        with self.assertRaisesRegex(ValueError, "not generated in activation mode"):
            register_readiness(self.root, readiness_path)

        final_path = self.artifacts / "bad_final" / "final_submission_selection_receipt.json"
        final_path.parent.mkdir()
        final_path.write_text(json.dumps({
            "status": "FINAL_SELECTED",
            "selection_final": True,
            "external_kaggle_action_performed": False,
            "clock_gate": {"live_clock_enforced": False},
        }) + "\n")
        with self.assertRaisesRegex(ValueError, "did not enforce the live clock"):
            register_final_selection(self.root, final_path)

    def test_existing_receipt_paths_are_immutable(self):
        as_of = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
        readiness_output = self.artifacts / "existing_readiness"
        readiness_output.mkdir()
        (readiness_output / "campaign_readiness_receipt.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "already contains a readiness receipt"):
            run_readiness(self.root, self.root, as_of, readiness_output)

        selector_output = self.artifacts / "existing_selector"
        selector_output.mkdir()
        (selector_output / "final_submission_selection_receipt.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "already contains a selector receipt"):
            run_selector(self.root, as_of, selector_output, True)

    def test_registers_system_manifest_idempotently(self):
        receipt_path, _ = self.make_system_manifest()
        self.assertEqual(register_system_manifest(self.root, receipt_path)["status"], "REGISTERED")
        self.assertEqual(
            register_system_manifest(self.root, receipt_path)["status"], "ALREADY_REGISTERED"
        )
        status = json.loads(self.status_path.read_text())
        self.assertEqual(status["system_implementation_manifest"]["status"], "VALID")
        with self.ledger_path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["experiment"], "system_implementation_manifest_v1")

    def test_rejects_system_manifest_after_source_drift(self):
        receipt_path, source_path = self.make_system_manifest()
        source_path.write_text("VALUE = 2\n")
        with self.assertRaisesRegex(ValueError, "manifest is stale"):
            register_system_manifest(self.root, receipt_path)


if __name__ == "__main__":
    unittest.main()
