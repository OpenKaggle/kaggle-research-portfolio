import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from system_implementation_manifest_audit import (  # noqa: E402
    MANIFEST_COLUMNS,
    discover_manifest,
    run,
    verify_current_manifest,
)


class SystemImplementationManifestAuditTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "traffic"
        for directory in ("config", "src", "tests", "artifacts/core", "official"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "run.py").write_text("print('entry')\n")
        (self.root / "requirements.lock").write_text("example==1.0\n")
        (self.root / "src" / "worker.py").write_text("VALUE = 1\n")
        (self.root / "tests" / "test_worker.py").write_text("# test\n")
        (self.root / "README.md").write_text("reproducible\n")
        self.core_receipt = self.root / "artifacts" / "core" / "receipt.json"
        self.core_receipt.write_text(json.dumps({"status": "VALID", "errors": []}) + "\n")
        self.config_path = self.root / "config" / "system_implementation_manifest_v1.json"
        self.config = {
            "version": "system_implementation_manifest_v1",
            "official_code_commit": "abc123",
            "manifest_rules": [
                {"category": "entrypoint", "pattern": "run.py", "expected_count": 1},
                {"category": "environment", "pattern": "requirements.lock", "expected_count": 1},
                {"category": "config", "pattern": "config/*.json", "expected_count": 1},
                {"category": "source", "pattern": "src/*.py", "expected_count": 1},
                {"category": "test", "pattern": "tests/test_*.py", "expected_count": 1},
                {"category": "documentation", "pattern": "README.md", "expected_count": 1},
            ],
            "canonical_receipts": [
                {"path": "artifacts/core/receipt.json", "status": "VALID"}
            ],
            "forbidden_path_prefixes": ["data/", "official/", "public_notebooks/"],
            "information_boundary": {
                "competition_data_read": False,
                "submission_artifact_read": False,
                "hidden_label_or_metric_read": False,
                "external_action_performed": False,
            },
        }
        self.config_path.write_text(json.dumps(self.config) + "\n")

    def tearDown(self):
        self.temporary.cleanup()

    def test_run_creates_closed_manifest_and_verifies_current_files(self):
        output = self.root / "artifacts" / "manifest"
        with patch("system_implementation_manifest_audit.subprocess.check_output", return_value="abc123\n"):
            receipt = run(self.root, self.config_path, output)
        self.assertEqual(receipt["status"], "VALID")
        self.assertEqual(receipt["files_hashed"], 7)
        self.assertEqual(receipt["canonical_receipts_verified"], 1)
        self.assertEqual(verify_current_manifest(self.root, output / "system_implementation_manifest_receipt.json"), [])
        with (output / "system_implementation_manifest.csv").open(newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(reader.fieldnames, MANIFEST_COLUMNS)
            self.assertEqual(len(list(reader)), 7)

    def test_verifier_detects_source_drift(self):
        output = self.root / "artifacts" / "manifest"
        with patch("system_implementation_manifest_audit.subprocess.check_output", return_value="abc123\n"):
            run(self.root, self.config_path, output)
        (self.root / "src" / "worker.py").write_text("VALUE = 2\n")
        errors = verify_current_manifest(
            self.root, output / "system_implementation_manifest_receipt.json"
        )
        self.assertIn("system implementation files differ from the recorded manifest", errors)

    def test_discovery_rejects_information_boundary_boundary_paths(self):
        data = self.root / "data"
        data.mkdir()
        (data / "hidden.csv").write_text("secret\n")
        self.config["manifest_rules"].append(
            {"category": "bad", "pattern": "data/*.csv", "expected_count": 1}
        )
        rows, errors, _ = discover_manifest(self.root, self.config)
        self.assertTrue(any("crosses information boundary" in error for error in errors))
        self.assertNotIn("data/hidden.csv", {row["path"] for row in rows})

    def test_receipt_status_mismatch_fails_audit(self):
        self.core_receipt.write_text(json.dumps({"status": "FAIL", "errors": []}) + "\n")
        output = self.root / "artifacts" / "manifest"
        with patch("system_implementation_manifest_audit.subprocess.check_output", return_value="abc123\n"):
            receipt = run(self.root, self.config_path, output)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertTrue(any("status mismatch" in error for error in receipt["errors"]))


if __name__ == "__main__":
    unittest.main()
