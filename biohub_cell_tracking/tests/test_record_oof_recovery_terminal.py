import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from record_oof_recovery_terminal import (  # noqa: E402
    record_recovery_terminal,
    sha256,
)


FIELDS = [
    "experiment_id",
    "kaggle_kernel",
    "runtime_seconds",
    "outcome",
    "notes",
]


class RecordOOFRecoveryTerminalTests(unittest.TestCase):
    def make_fixture(self, root: Path, status: str = "CANCEL_ACKNOWLEDGED"):
        launch_path = root / "launch.json"
        launch_path.write_text(
            json.dumps(
                {
                    "status": "accepted_recovery_launch",
                    "experiment_id": "BH-0003",
                    "kernel": "owner/recovery",
                    "script_version_id": 456,
                    "run_url": "https://www.kaggle.com/code/owner/recovery/edit/run/456",
                    "competition_submission_authorized": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        status_path = root / "status.json"
        status_path.write_text(
            json.dumps(
                {
                    "checked_at_utc": "2026-09-10T00:00:00+00:00",
                    "kernel": "owner/recovery",
                    "status": status,
                    "failure_message": None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                    "script_version_id": 456,
                    "run_url": "https://www.kaggle.com/code/owner/recovery/edit/run/456",
                    "log_api_error": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        activity_path = root / "activity.json"
        activity_path.write_text(
            json.dumps(
                {
                    "source": "Official authenticated Kaggle Notebook UI Logs page",
                    "kernel": "owner/recovery",
                    "script_version_id": 456,
                    "run_url": "https://www.kaggle.com/code/owner/recovery/edit/run/456",
                    "activity_observations": [{"runtime_seconds": 43199.0}],
                    "intervention": {
                        "parallel_rerun_allowed": False,
                        "cancelled": False,
                        "competition_submission_authorized": False,
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        output_dir = root / "output"
        output_dir.mkdir()
        (output_dir / "fold_0_train.log").write_text(
            "partial recovery log\n", encoding="utf-8"
        )
        (output_dir / "untrusted-extra.txt").write_text("ignored\n", encoding="utf-8")
        ledger_path = root / "ledger.csv"
        with ledger_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerow(
                {
                    "experiment_id": "BH-0003",
                    "kaggle_kernel": "owner/recovery",
                    "runtime_seconds": "",
                    "outcome": "RUNNING",
                    "notes": "launched",
                }
            )
        return status_path, launch_path, activity_path, output_dir, ledger_path

    def test_running_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.make_fixture(root, "RUNNING")
            receipt_path = root / "receipt.json"
            before = paths[-1].read_bytes()
            with self.assertRaisesRegex(ValueError, "non-failed status"):
                record_recovery_terminal(
                    *paths, receipt_path, "BH-0003"
                )
            self.assertEqual(paths[-1].read_bytes(), before)
            self.assertFalse(receipt_path.exists())

    def test_cancel_ack_binds_launch_activity_and_allowed_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.make_fixture(root)
            receipt_path = root / "receipt.json"
            receipt = record_recovery_terminal(
                *paths, receipt_path, "BH-0003"
            )
            self.assertEqual(receipt["status"], "accepted_recovery_terminal_failure")
            self.assertEqual(receipt["ledger_outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertEqual(receipt["launch_receipt_sha256"], sha256(paths[1]))
            self.assertEqual(receipt["activity_receipt_sha256"], sha256(paths[2]))
            self.assertEqual(
                [item["name"] for item in receipt["evidence_files"]],
                ["fold_0_train.log"],
            )
            self.assertFalse(receipt["further_recovery_authorized"])
            self.assertFalse(receipt["competition_submission_authorized"])
            self.assertFalse(receipt["promotion_authorized"])
            with paths[-1].open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertEqual(row["runtime_seconds"], "43199.0")
            self.assertIn("no further recovery", row["notes"])

    def test_wrong_version_or_run_url_is_rejected_without_mutation(self):
        for field, wrong_value in (
            ("script_version_id", 999),
            ("run_url", "https://www.kaggle.com/code/owner/recovery/edit/run/999"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                paths = self.make_fixture(root)
                status = json.loads(paths[0].read_text(encoding="utf-8"))
                status[field] = wrong_value
                paths[0].write_text(json.dumps(status) + "\n", encoding="utf-8")
                receipt_path = root / "receipt.json"
                before = paths[-1].read_bytes()
                with self.assertRaisesRegex(ValueError, field.replace("_", " ")):
                    record_recovery_terminal(
                        *paths, receipt_path, "BH-0003"
                    )
                self.assertEqual(paths[-1].read_bytes(), before)
                self.assertFalse(receipt_path.exists())


if __name__ == "__main__":
    unittest.main()
