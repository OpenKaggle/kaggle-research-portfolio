import sys
import unittest
from enum import Enum
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sync_kernel_status import build_receipt  # noqa: E402


class WorkerStatus(Enum):
    RUNNING = 1


class SyncKernelStatusTests(unittest.TestCase):
    def test_compact_receipt_with_empty_live_log(self):
        receipt = build_receipt(
            "owner/kernel", WorkerStatus.RUNNING, "", "", "2026-09-08T00:00:00+00:00"
        )
        self.assertEqual(receipt["status"], "RUNNING")
        self.assertIsNone(receipt["failure_message"])
        self.assertFalse(receipt["log_available"])
        self.assertEqual(receipt["log_tail"], [])

    def test_log_receipt_is_bounded_and_hashed(self):
        logs = "\n".join(f"line {index}" for index in range(50))
        receipt = build_receipt(
            "owner/kernel", WorkerStatus.RUNNING, None, logs, "2026-09-08T00:00:00+00:00"
        )
        self.assertTrue(receipt["log_available"])
        self.assertEqual(receipt["log_lines"], 50)
        self.assertEqual(len(receipt["log_tail"]), 30)
        self.assertEqual(receipt["log_tail"][0], "line 20")
        self.assertEqual(len(receipt["log_sha256"]), 64)

    def test_binds_kernel_script_version_and_run_url(self):
        run_url = "https://www.kaggle.com/code/owner/kernel/edit/run/456"
        receipt = build_receipt(
            "owner/kernel",
            WorkerStatus.RUNNING,
            None,
            None,
            "2026-09-08T00:00:00+00:00",
            456,
            run_url,
        )
        self.assertEqual(receipt["script_version_id"], 456)
        self.assertEqual(receipt["run_url"], run_url)

    def test_rejects_mismatched_run_url(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_receipt(
                "owner/kernel",
                WorkerStatus.RUNNING,
                None,
                None,
                "2026-09-08T00:00:00+00:00",
                456,
                "https://www.kaggle.com/code/owner/other/edit/run/999",
            )


if __name__ == "__main__":
    unittest.main()
