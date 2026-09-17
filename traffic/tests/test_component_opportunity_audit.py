import sys
import unittest
from pathlib import Path

import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from component_opportunity_audit import (  # noqa: E402
    SUBMISSION_COST_FLOOR_TOTAL,
    build_opportunities,
)


class ComponentOpportunityAuditTest(unittest.TestCase):
    def test_separates_observable_ceiling_from_unobservable_weight(self):
        status = {
            "component_baselines": {
                "state": {"confirmation_S_state": 0.91},
                "physics_public_diagnostic": {"confirmation_S_FD": 0.98},
            }
        }
        metrics = pd.DataFrame(
            [
                {"level": "overall", "split": "validation", "lambda": 5.0, "S_link": 0.99},
                {"level": "overall", "split": "private", "lambda": 5.0, "S_link": 0.98},
            ]
        )
        nonlinear = {"confirmation": {"delta_S_state": 0.004, "delta_S_FD": 0.002}}
        rows = build_opportunities(status, metrics, nonlinear).set_index("component")
        self.assertAlmostEqual(rows.loc["state", "observable_remaining_total_ceiling"], 0.0315)
        self.assertAlmostEqual(rows.loc["odme_s_link", "observable_remaining_total_ceiling"], 0.001)
        self.assertTrue(pd.isna(rows.loc["queue", "observable_remaining_total_ceiling"]))
        self.assertEqual(rows.independent_family_ready.sum(), 0)
        self.assertEqual(SUBMISSION_COST_FLOOR_TOTAL, 0.0035)


if __name__ == "__main__":
    unittest.main()
