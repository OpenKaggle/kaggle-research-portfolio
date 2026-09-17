import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from task1_grouped_v32_control import _nearest_within, v32_prediction  # noqa: E402


class V32PredictionTest(unittest.TestCase):
    def test_nearest_fill_respects_limit_and_prefers_previous_on_tie(self):
        observed = np.full((30, 1), np.nan)
        observed[0, 0] = 10.0
        observed[20, 0] = 30.0
        nearest = _nearest_within(observed, limit=6)
        self.assertEqual(nearest[6, 0], 10.0)
        self.assertTrue(np.isnan(nearest[7, 0]))
        self.assertTrue(np.isnan(nearest[10, 0]))
        self.assertEqual(nearest[14, 0], 30.0)
        self.assertEqual(nearest[26, 0], 30.0)
        self.assertTrue(np.isnan(nearest[27, 0]))
        self.assertEqual(_nearest_within(observed, limit=12)[10, 0], 10.0)

    def test_long_gap_uses_frozen_profile_and_stays_finite(self):
        timestamps = pd.date_range("2031-02-03", periods=288, freq="5min", tz="UTC")
        masked = pd.DataFrame(
            {
                "timestamp": timestamps,
                "slot": range(288),
                "link_id": ["a"] * 288,
                "speed_kmh": np.nan,
                "flow_vph": np.nan,
            }
        )
        shape = (7, 288, 1)
        profile = {
            "speed_mean": np.full(shape, 75.0),
            "speed_count": np.ones(shape, dtype=int),
            "speed_fallback": np.array([70.0]),
            "flow_mean": np.full(shape, 1500.0),
            "flow_count": np.ones(shape, dtype=int),
            "flow_fallback": np.array([1400.0]),
        }
        parameters = pd.DataFrame(
            {
                "link_id": ["a"], "lanes": [3.0], "free_speed_kmh": [100.0],
                "capacity_vph": [6000.0], "k_jam": [300.0],
            }
        )
        prediction = v32_prediction(masked, ["a"], profile, parameters)
        np.testing.assert_allclose(prediction["speed_kmh"], 75.0)
        np.testing.assert_allclose(prediction["flow_vph"], 1500.0)


if __name__ == "__main__":
    unittest.main()
