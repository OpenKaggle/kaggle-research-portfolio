import sys
import unittest
from pathlib import Path

import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from queue_ongoing_trend_ablation import forecast  # noqa: E402


class OngoingTrendForecastTest(unittest.TestCase):
    def test_changes_only_nonqueued_crossing_links_when_enabled(self):
        history = pd.DataFrame(
            {
                "window_id": ["w"] * 8,
                "timestamp": pd.date_range("2031-01-01", periods=4, freq="5min", tz="UTC").tolist() * 2,
                "link_id": ["queued"] * 4 + ["crossing"] * 4,
                "speed_kmh": [50, 50, 50, 50, 80, 75, 70, 65],
                "is_score_eligible": True,
            }
        )
        template = pd.DataFrame(
            {
                "window_id": ["w"] * 12,
                "timestamp": list(pd.date_range("2031-01-01 00:20", periods=6, freq="5min", tz="UTC")) * 2,
                "link_id": ["queued"] * 6 + ["crossing"] * 6,
            }
        )
        thresholds = {"queued": 60.0, "crossing": 60.0}
        control = forecast(history, template, "queue_ongoing", thresholds, [], 0)
        enabled = forecast(history, template, "queue_ongoing", thresholds, [], 2)
        self.assertEqual(int(control[control.link_id == "queued"].queue_pred.sum()), 6)
        self.assertEqual(int(enabled[enabled.link_id == "queued"].queue_pred.sum()), 6)
        self.assertEqual(int(control[control.link_id == "crossing"].queue_pred.sum()), 0)
        self.assertEqual(int(enabled[enabled.link_id == "crossing"].queue_pred.sum()), 5)

    def test_onset_is_invariant_to_trend_horizon(self):
        template = pd.DataFrame(
            {
                "window_id": ["w"] * 12,
                "timestamp": list(pd.date_range("2031-01-01", periods=6, freq="5min", tz="UTC")) * 2,
                "link_id": ["a"] * 6 + ["b"] * 6,
            }
        )
        history = pd.DataFrame()
        a = forecast(history, template, "queue_onset", {}, ["a", "b"], 0)
        b = forecast(history, template, "queue_onset", {}, ["a", "b"], 6)
        pd.testing.assert_frame_equal(a, b)
        self.assertEqual(int(a.queue_pred.sum()), 2)


if __name__ == "__main__":
    unittest.main()
