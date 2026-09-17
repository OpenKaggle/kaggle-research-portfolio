import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from task1_grouped_baseline import _fd_score, _fd_sums, _state_score, temporal_prediction  # noqa: E402


class Task1GroupedBaselineTest(unittest.TestCase):
    def setUp(self):
        timestamps = pd.date_range("2031-01-01", periods=288, freq="5min", tz="UTC")
        self.masked = pd.DataFrame(
            {
                "timestamp": timestamps,
                "slot": range(288),
                "link_id": ["a"] * 288,
                "speed_kmh": [np.nan] * 6 + [80.0] * 282,
                "flow_vph": [np.nan] * 6 + [1600.0] * 282,
            }
        )
        self.prior = self.masked.copy()
        self.prior["speed_kmh"] = 70.0
        self.prior["flow_vph"] = 1400.0
        self.parameters = pd.DataFrame(
            {
                "link_id": ["a"],
                "lanes": [2.0],
                "free_speed_kmh": [100.0],
                "capacity_vph": [4000.0],
                "k_jam": [200.0],
            }
        )

    def test_temporal_interpolation_is_fixed_without_truth(self):
        links, prediction = temporal_prediction(self.masked, self.prior, self.parameters)
        self.assertEqual(links, ["a"])
        np.testing.assert_array_equal(prediction["speed_kmh"][:6, 0], np.full(6, 80.0))
        np.testing.assert_array_equal(prediction["flow_vph"][:6, 0], np.full(6, 1600.0))

    def test_state_score_uses_official_formula(self):
        score = _state_score(speed_sq=25.0 * 4, flow_sq=100.0 * 4, n=4)
        self.assertAlmostEqual(score["rmse_speed_kmh"], 5.0)
        self.assertAlmostEqual(score["rmse_flow_vph_per_lane"], 10.0)
        self.assertAlmostEqual(score["S_state"], 0.54 * 0.8 + 0.46 * (1 - 10 / 600))

    def test_fd_exact_free_flow_identity_scores_one(self):
        speed = np.array([[100.0]])
        flow = np.array([[2000.0]])
        num, den, rows = _fd_sums(speed, flow, np.array([[True]]), ["a"], self.parameters)
        self.assertEqual(rows, 1)
        self.assertAlmostEqual(num, 0.0)
        self.assertAlmostEqual(_fd_score(num, den, 0, 1), 1.0)

    def test_empty_road_guard_is_exactly_official_threshold(self):
        self.assertEqual(_fd_score(0.0, 1.0, 3, 10), 0.0)
        self.assertEqual(_fd_score(0.0, 1.0, 2, 10), 1.0)


if __name__ == "__main__":
    unittest.main()
