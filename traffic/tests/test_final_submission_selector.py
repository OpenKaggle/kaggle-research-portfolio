import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from final_submission_selector import (  # noqa: E402
    completed_submission,
    late_experiment_violations,
    select_best,
    selection_decision,
    validate_live_timestamp,
    validate_readiness_for_selection,
)


class FinalSubmissionSelectorTest(unittest.TestCase):
    def test_selects_highest_completed_public_candidate(self):
        rows = [
            {"status": "COMPLETE", "public_score": "0.7", "submitted_at_utc": "2026-01-01T00:00:00Z", "submission_id": "1"},
            {"status": "COMPLETE", "public_score": "0.8", "submitted_at_utc": "2026-01-02T00:00:00Z", "submission_id": "2"},
            {"status": "PENDING", "public_score": "0.9", "submitted_at_utc": "2026-01-03T00:00:00Z", "submission_id": "3"},
        ]
        self.assertEqual(select_best(rows)["submission_id"], "2")

    def test_flags_non_bugfix_after_d3(self):
        d3 = datetime(2026, 11, 4, tzinfo=timezone.utc)
        as_of = datetime(2026, 11, 5, tzinfo=timezone.utc)
        rows = [
            {"experiment": "late_model", "started_at_utc": "2026-11-04T12:00:00Z", "status": "COMPLETE"},
            {"experiment": "late_fix", "started_at_utc": "2026-11-04T13:00:00Z", "status": "BUGFIX_VALID"},
        ]
        self.assertEqual([row["experiment"] for row in late_experiment_violations(rows, d3, as_of)], ["late_model"])

    def test_requires_one_completed_fallback_receipt(self):
        rows = [{"submission_id": "7", "status": "COMPLETE"}]
        self.assertIs(completed_submission(rows, 7), rows[0])
        with self.assertRaisesRegex(ValueError, "exactly one row"):
            completed_submission(rows, 8)
        with self.assertRaisesRegex(ValueError, "not complete"):
            completed_submission([{"submission_id": "7", "status": "PENDING"}], 7)

    def test_d3_dry_run_has_unambiguous_next_action(self):
        d3 = datetime(2026, 11, 4, tzinfo=timezone.utc)
        self.assertEqual(
            selection_decision(d3, d3, True, 7),
            "PREVIEW_SUBMISSION_7_D3_REACHED_RERUN_WITHOUT_DRY_RUN",
        )
        self.assertEqual(selection_decision(d3, d3, False, 7), "SELECT_FINAL_SUBMISSION_7")

    def test_live_timestamp_rejects_future_or_stale_claims(self):
        now = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
        self.assertEqual(validate_live_timestamp(now - timedelta(minutes=5), now), 300.0)
        with self.assertRaisesRegex(ValueError, "ahead of the live system clock"):
            validate_live_timestamp(now + timedelta(minutes=2), now)
        with self.assertRaisesRegex(ValueError, "stale relative to the live system clock"):
            validate_live_timestamp(now - timedelta(minutes=16), now)

    def test_non_dry_selection_requires_fresh_d3_preselection_receipt(self):
        d3 = datetime(2026, 11, 4, 6, 55, tzinfo=timezone.utc)
        as_of = d3 + timedelta(minutes=10)
        readiness = {
            "status": "READY_FOR_FINAL_SELECTION",
            "phase": "D3_BUGFIX_AND_FINAL_SELECTION_ONLY",
            "as_of": (as_of - timedelta(minutes=5)).isoformat(),
            "checks_failed": 1,
            "failures": [{"requirement": "D3_final_selection_control"}],
        }
        self.assertEqual(validate_readiness_for_selection(readiness, as_of, d3, False), 300.0)
        readiness["failures"] = [{"requirement": "current_best_artifact_integrity"}]
        with self.assertRaisesRegex(ValueError, "failures beyond pending final selection"):
            validate_readiness_for_selection(readiness, as_of, d3, False)
        readiness["failures"] = [{"requirement": "D3_final_selection_control"}]
        readiness["as_of"] = (d3 - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "requires a D-3 readiness receipt"):
            validate_readiness_for_selection(readiness, as_of, d3, False)


if __name__ == "__main__":
    unittest.main()
