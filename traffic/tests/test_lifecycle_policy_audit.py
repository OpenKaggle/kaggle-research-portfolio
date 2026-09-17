import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from lifecycle_policy_audit import (  # noqa: E402
    classify_experiment,
    experiment_policy_violations,
    lifecycle_phase,
    policy_probes,
    submission_policy_violations,
)


class LifecyclePolicyAuditTest(unittest.TestCase):
    def setUp(self):
        deadline = datetime(2026, 11, 7, 6, 55, tzinfo=timezone.utc)
        self.milestones = {
            "D30": deadline - timedelta(days=30),
            "D14": deadline - timedelta(days=14),
            "D7": deadline - timedelta(days=7),
            "D3": deadline - timedelta(days=3),
            "deadline": deadline,
        }
        self.policy = {
            "category_prefixes": {
                "readiness": ["campaign_readiness_"],
                "reproduction": ["current_best_full_replay_"],
                "integrity_audit": ["evidence_audit_"],
                "bugfix": ["bugfix_"],
                "final_selection": ["final_submission_selection"],
            },
            "allowed_categories": {
                "D14_CANDIDATE_FROZEN": ["readiness", "reproduction", "integrity_audit"],
                "D7_REPRODUCTION_ONLY": ["readiness", "reproduction", "integrity_audit"],
                "D3_BUGFIX_AND_FINAL_SELECTION_ONLY": [
                    "readiness", "reproduction", "integrity_audit", "bugfix", "final_selection"
                ],
                "CLOSED": ["readiness", "integrity_audit"],
            },
            "bugfix_status_prefix": "BUGFIX",
            "final_selection_status": "FINAL_SELECTED",
        }

    def test_phase_boundaries_drive_real_policy(self):
        self.assertEqual(
            lifecycle_phase(self.milestones["D14"], self.milestones),
            "D14_CANDIDATE_FROZEN",
        )
        self.assertEqual(
            lifecycle_phase(self.milestones["D7"], self.milestones),
            "D7_REPRODUCTION_ONLY",
        )
        self.assertEqual(
            lifecycle_phase(self.milestones["D3"], self.milestones),
            "D3_BUGFIX_AND_FINAL_SELECTION_ONLY",
        )

    def test_rejects_tuning_after_freeze_but_allows_reproduction(self):
        as_of = self.milestones["D3"] - timedelta(seconds=1)
        rows = [
            {
                "experiment": "new_model",
                "started_at_utc": self.milestones["D14"].isoformat(),
                "status": "COMPLETE",
            },
            {
                "experiment": "current_best_full_replay_D7",
                "started_at_utc": self.milestones["D7"].isoformat(),
                "status": "REPRODUCED",
            },
        ]
        violations = experiment_policy_violations(rows, as_of, self.milestones, self.policy)
        self.assertEqual([row["name"] for row in violations], ["new_model"])

    def test_d3_allows_only_documented_bugfix_submission(self):
        as_of = self.milestones["deadline"] - timedelta(seconds=1)
        base = {
            "submitted_at_utc": self.milestones["D3"].isoformat(),
            "status": "COMPLETE",
        }
        self.assertEqual(
            submission_policy_violations(
                [{**base, "experiment": "bugfix_schema_guard"}],
                as_of,
                self.milestones,
                self.policy,
            ),
            [],
        )
        self.assertEqual(
            len(
                submission_policy_violations(
                    [{**base, "experiment": "new_model"}],
                    as_of,
                    self.milestones,
                    self.policy,
                )
            ),
            1,
        )

    def test_builtin_probes_cover_all_gate_actions(self):
        probes = policy_probes(self.milestones, self.policy)
        self.assertEqual(len(probes), 8)
        self.assertTrue(all(probes.values()))
        self.assertEqual(classify_experiment("unknown", self.policy), "research_or_candidate")


if __name__ == "__main__":
    unittest.main()
