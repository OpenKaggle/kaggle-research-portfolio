import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from task1_source_coverage_audit import source_counts  # noqa: E402


class SourceCountsTest(unittest.TestCase):
    def test_classifies_temporal_and_profile_cells(self):
        timestamp = pd.date_range("2031-01-01", periods=20, freq="5min", tz="UTC")
        frame = pd.DataFrame(
            {
                "timestamp": timestamp,
                "link_id": ["a"] * 20,
                "speed_kmh": [80.0] + [np.nan] * 19,
                "flow_vph": [1000.0] + [np.nan] * 19,
                "is_score_eligible": True,
            }
        )
        counts = source_counts(frame)
        self.assertEqual(counts["target_cells"], 19)
        self.assertEqual(counts["temporal_complete"], 12)
        self.assertEqual(counts["spatial_fallback"], 0)
        self.assertEqual(counts["profile_any_channel"], 7)


if __name__ == "__main__":
    unittest.main()
