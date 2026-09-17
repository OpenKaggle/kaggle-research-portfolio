import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from campaign_readiness_audit import (  # noqa: E402
    lifecycle,
    next_checkpoint,
    readiness_status,
    timestamps_monotonic,
)


class CampaignLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.deadline = datetime(2026, 11, 7, 6, 55, tzinfo=timezone.utc)

    def test_phase_boundaries(self):
        cases = [
            (-31, "RESEARCH_BEFORE_D30"),
            (-30, "D30_BASELINES_COMPLETE"),
            (-14, "D14_CANDIDATE_FROZEN"),
            (-7, "D7_REPRODUCTION_ONLY"),
            (-3, "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"),
            (0, "CLOSED"),
        ]
        for days, expected in cases:
            with self.subTest(days=days):
                phase, _ = lifecycle(self.deadline + __import__("datetime").timedelta(days=days), self.deadline)
                self.assertEqual(phase, expected)

    def test_rejects_naive_datetimes(self):
        with self.assertRaises(ValueError):
            lifecycle(datetime(2026, 9, 9), self.deadline)

    def test_next_checkpoint_advances_at_each_boundary(self):
        timedelta = __import__("datetime").timedelta
        before_d30 = self.deadline - timedelta(days=31)
        _, gates = lifecycle(before_d30, self.deadline)
        self.assertEqual(next_checkpoint(before_d30, gates), gates["D30"].isoformat())
        self.assertEqual(next_checkpoint(gates["D30"], gates), gates["D14"].isoformat())
        self.assertEqual(next_checkpoint(gates["D14"], gates), gates["D7"].isoformat())
        self.assertEqual(next_checkpoint(gates["D7"], gates), gates["D3"].isoformat())
        self.assertEqual(next_checkpoint(gates["D3"], gates), gates["deadline"].isoformat())
        self.assertIsNone(next_checkpoint(gates["deadline"], gates))

    def test_ledger_timestamps_must_be_aware_and_monotonic(self):
        ordered = [{"at": "2026-09-09T10:00:00Z"}, {"at": "2026-09-09T18:01:00+08:00"}]
        reversed_rows = list(reversed(ordered))
        self.assertTrue(timestamps_monotonic(ordered, "at"))
        self.assertFalse(timestamps_monotonic(reversed_rows, "at"))
        self.assertFalse(timestamps_monotonic([{"at": "2026-09-09T10:00:00"}], "at"))

    def test_d3_preselection_status_allows_only_the_pending_selection_check(self):
        pending = [{"requirement": "D3_final_selection_control", "status": "FAIL"}]
        self.assertEqual(
            readiness_status(pending, "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"),
            "READY_FOR_FINAL_SELECTION",
        )
        pending.append({"requirement": "current_best_artifact_integrity", "status": "FAIL"})
        self.assertEqual(readiness_status(pending, "D3_BUGFIX_AND_FINAL_SELECTION_ONLY"), "FAIL")
        self.assertEqual(readiness_status(pending[:1], "CLOSED"), "FAIL")


if __name__ == "__main__":
    unittest.main()
