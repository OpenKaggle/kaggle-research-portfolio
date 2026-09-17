from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "queue_shockwave.py"
SPEC = importlib.util.spec_from_file_location("queue_shockwave", MODULE_PATH)
queue_shockwave = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(queue_shockwave)


class QueueShockwaveTests(unittest.TestCase):
    def test_onset_and_ongoing_forecasts_are_binary_and_guarded(self) -> None:
        times = pd.date_range("2031-03-01T00:00:00Z", periods=4, freq="5min")
        history = pd.DataFrame(
            {
                "window_id": ["onset"] * 8,
                "timestamp": list(times) * 2,
                "link_id": ["L1"] * 4 + ["L2"] * 4,
                "speed_kmh": [85, 78, 71, 65, 100, 100, 100, 100],
                "is_score_eligible": True,
            }
        )
        # Released history ends at T-5; the template begins at T+5.
        future = pd.date_range(times[-1] + pd.Timedelta(minutes=10), periods=6, freq="5min")
        template = pd.DataFrame(
            [("onset", timestamp, link) for timestamp in future for link in ("L1", "L2")],
            columns=["window_id", "timestamp", "link_id"],
        )
        onset = queue_shockwave.forecast_window(
            history, template, "queue_onset", {"L1": 60.0, "L2": 60.0}, {}, {}, onset_top_k=1
        )
        self.assertTrue(set(onset.queue_pred.unique()) <= {0, 1})
        self.assertGreater(onset[onset.link_id == "L1"].queue_pred.sum(), 0)
        self.assertEqual(onset[onset.link_id == "L2"].queue_pred.sum(), 0)

        ongoing_history = history.copy()
        ongoing_history["window_id"] = "ongoing"
        ongoing_history.loc[ongoing_history.link_id == "L2", "speed_kmh"] = [80, 70, 58, 50]
        ongoing_template = template.copy()
        ongoing_template["window_id"] = "ongoing"
        ongoing = queue_shockwave.forecast_window(
            ongoing_history,
            ongoing_template,
            "queue_ongoing",
            {"L1": 60.0, "L2": 60.0},
            {"L2": ["L1"]},
            {},
        )
        self.assertTrue(ongoing[ongoing.link_id == "L2"].queue_pred.eq(1).all())
        self.assertEqual(ongoing.duplicated(["window_id", "timestamp", "link_id"]).sum(), 0)

    def test_nearest_observed_upstream_crosses_latent_links(self) -> None:
        graph = {"L3": ["latent"], "latent": ["L2"], "L2": ["L1"]}
        self.assertEqual(
            queue_shockwave.nearest_observed_upstream("L3", {"L1", "L2", "L3"}, graph), {"L2"}
        )

    def test_onset_fallback_uses_true_t_plus_30_only(self) -> None:
        history_times = pd.date_range("2031-03-01T00:00:00Z", periods=12, freq="5min")
        history = pd.DataFrame(
            {
                "window_id": "flat",
                "timestamp": history_times,
                "link_id": "L1",
                "speed_kmh": 65.0,
                "is_score_eligible": True,
            }
        )
        # Final history timestamp is T-5; requested times are T+5 ... T+30.
        future = pd.date_range(history_times[-1] + pd.Timedelta(minutes=10), periods=6, freq="5min")
        template = pd.DataFrame(
            {"window_id": "flat", "timestamp": future, "link_id": "L1"}
        )
        result = queue_shockwave.forecast_window(
            history, template, "queue_onset", {"L1": 60.0}, {}, {"L1": 0.5}, onset_top_k=1
        )
        positives = result[result.queue_pred.eq(1)]
        self.assertEqual(len(positives), 1)
        self.assertEqual(positives.timestamp.iloc[0], future[-1])


if __name__ == "__main__":
    unittest.main()
