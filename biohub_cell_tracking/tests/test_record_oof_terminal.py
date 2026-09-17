import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from record_oof_terminal import record_terminal, sha256  # noqa: E402


FIELDS = [
    "experiment_id",
    "kaggle_kernel",
    "runtime_seconds",
    "outcome",
    "notes",
]


class RecordOOFTerminalTests(unittest.TestCase):
    def make_fixture(self, root: Path, status: str):
        status_path = root / "status.json"
        status_path.write_text(
            json.dumps(
                {
                    "checked_at_utc": "2026-09-09T12:00:00+00:00",
                    "kernel": "owner/kernel",
                    "status": status,
                    "failure_message": "Notebook exceeded allowed compute"
                    if status == "ERROR"
                    else None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        activity_path = root / "activity.json"
        activity_path.write_text(
            json.dumps(
                {
                    "kernel": "owner/kernel",
                    "script_version_id": 123,
                    "source": "Official authenticated Kaggle Notebook UI Logs page",
                    "classification": "ACTIVE_BUT_RUNTIME_INFEASIBLE",
                    "activity_observations": [
                        {"runtime_seconds": 43199.0, "log_items": 7000}
                    ],
                    "projection": {
                        "assessment": "runtime_infeasible",
                        "projected_training_hours_two_folds": 53.2,
                    },
                    "intervention": {
                        "parallel_rerun_allowed": False,
                        "cancelled": False,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        output_dir = root / "output"
        output_dir.mkdir()
        (output_dir / "fold_0_train.log").write_text("partial log\n", encoding="utf-8")
        ledger_path = root / "ledger.csv"
        with ledger_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "experiment_id": "BH-0002",
                    "kaggle_kernel": "owner/kernel",
                    "runtime_seconds": "",
                    "outcome": "RUNNING_RUNTIME_AT_RISK",
                    "notes": "existing",
                }
            )
        return status_path, activity_path, output_dir, ledger_path

    def test_live_status_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status, activity, output_dir, ledger = self.make_fixture(root, "RUNNING")
            receipt = root / "receipt.json"
            before = ledger.read_bytes()
            with self.assertRaisesRegex(ValueError, "non-failed status"):
                record_terminal(
                    status, activity, output_dir, ledger, receipt, "BH-0002"
                )
            self.assertEqual(ledger.read_bytes(), before)
            self.assertFalse(receipt.exists())

    def test_error_freezes_evidence_and_updates_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status, activity, output_dir, ledger = self.make_fixture(root, "ERROR")
            receipt_path = root / "receipt.json"
            receipt = record_terminal(
                status, activity, output_dir, ledger, receipt_path, "BH-0002"
            )
            self.assertEqual(receipt["status"], "accepted_terminal_failure")
            self.assertEqual(receipt["ledger_outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertEqual(receipt["official_status_receipt_sha256"], sha256(status))
            self.assertEqual(receipt["evidence_files"][0]["name"], "fold_0_train.log")
            with ledger.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertEqual(row["runtime_seconds"], "43199.0")
            self.assertIn("official terminal status ERROR", row["notes"])

    def test_cancel_acknowledged_at_runtime_limit_is_terminal_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status, activity, output_dir, ledger = self.make_fixture(
                root, "CANCEL_ACKNOWLEDGED"
            )
            receipt_path = root / "receipt.json"
            receipt = record_terminal(
                status, activity, output_dir, ledger, receipt_path, "BH-0002"
            )
            self.assertEqual(
                receipt["failure_kind"],
                "official_runtime_limit_cancel_acknowledged",
            )
            self.assertEqual(receipt["ledger_outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertTrue(receipt["runtime_limit_evidence"])
            with ledger.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertIn(
                "official terminal status CANCEL_ACKNOWLEDGED", row["notes"]
            )


if __name__ == "__main__":
    unittest.main()
