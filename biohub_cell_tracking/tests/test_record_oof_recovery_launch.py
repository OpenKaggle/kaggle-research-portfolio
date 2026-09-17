import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from record_oof_recovery_launch import record_launch  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecordOOFRecoveryLaunchTests(unittest.TestCase):
    def make_fixture(self, root: Path, launch_allowed: bool):
        local = root / "recovery.py"
        local.write_text("print('recovery')\n", encoding="utf-8")
        remote = root / "pulled.py"
        remote.write_bytes(local.read_bytes())
        metadata = root / "metadata.json"
        metadata.write_text(
            json.dumps(
                {
                    "id": "owner/recovery",
                    "is_private": True,
                    "enable_gpu": True,
                    "enable_internet": False,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        preflight = root / "preflight.json"
        preflight.write_text(
            json.dumps(
                {
                    "valid": True,
                    "launch_allowed": launch_allowed,
                    "terminal_evidence_valid": launch_allowed,
                    "source_sha256": digest(local),
                    "metadata_sha256": digest(metadata),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        status = root / "status.json"
        status.write_text(
            json.dumps(
                {
                    "checked_at_utc": "2026-09-09T13:00:00+00:00",
                    "kernel": "owner/recovery",
                    "status": "RUNNING",
                    "failure_message": None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = root / "ledger.csv"
        fields = ["experiment_id", "kaggle_kernel", "code_version", "outcome", "notes"]
        with ledger.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "experiment_id": "BH-0003",
                    "kaggle_kernel": "owner/recovery",
                    "code_version": digest(local),
                    "outcome": "PREPARED_NOT_LAUNCHED",
                    "notes": "prepared",
                }
            )
        return preflight, local, remote, metadata, status, ledger

    def test_rejects_unapproved_preflight_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.make_fixture(root, False)
            receipt = root / "launch.json"
            before = paths[-1].read_bytes()
            with self.assertRaisesRegex(ValueError, "does not authorize"):
                record_launch(
                    *paths,
                    receipt,
                    456,
                    "https://www.kaggle.com/code/owner/recovery/edit/run/456",
                    "BH-0003",
                )
            self.assertEqual(paths[-1].read_bytes(), before)
            self.assertFalse(receipt.exists())

    def test_binds_pulled_source_status_and_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.make_fixture(root, True)
            receipt_path = root / "launch.json"
            receipt = record_launch(
                *paths,
                receipt_path,
                456,
                "https://www.kaggle.com/code/owner/recovery/edit/run/456",
                "BH-0003",
            )
            self.assertEqual(receipt["status"], "accepted_recovery_launch")
            self.assertEqual(
                receipt["local_source_sha256"],
                receipt["pulled_remote_source_sha256"],
            )
            self.assertFalse(receipt["competition_submission_authorized"])
            with paths[-1].open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "RUNNING")
            self.assertIn("official recovery run 456", row["notes"])


if __name__ == "__main__":
    unittest.main()
