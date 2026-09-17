import sys
import unittest
from pathlib import Path

import numpy as np


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from task1_nonlinear_residual_ablation import _endpoint_features  # noqa: E402


class EndpointFeaturesTest(unittest.TestCase):
    def test_uses_only_visible_neighbors_and_slopes(self):
        observed = np.array([[10.0], [np.nan], [14.0], [np.nan], [np.nan], [20.0], [24.0]])
        target = np.array([[False], [True], [False], [True], [True], [False], [False]])
        left, right, ld, rd, left_slope, right_slope = _endpoint_features(observed, target)
        np.testing.assert_allclose(left, [10.0, 14.0, 14.0])
        np.testing.assert_allclose(right, [14.0, 20.0, 20.0])
        np.testing.assert_allclose(ld, [1.0, 1.0, 2.0])
        np.testing.assert_allclose(rd, [1.0, 2.0, 1.0])
        self.assertTrue(np.isnan(left_slope[0]))
        np.testing.assert_allclose(left_slope[1:], [2.0, 2.0])
        np.testing.assert_allclose(right_slope, [2.0, 4.0, 4.0])


if __name__ == "__main__":
    unittest.main()
