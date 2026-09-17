import sys
import unittest
from pathlib import Path

import numpy as np


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from task1_observability_preflight import directional_distances  # noqa: E402


class DirectionalDistancesTest(unittest.TestCase):
    def test_finds_nearest_visible_cell_in_each_direction(self):
        observed = np.array([[True, False, False, True, False]])
        target = np.array([[False, False, True, False, True]])
        upstream, downstream = directional_distances(
            observed, target, np.array([0.0, 0.5, 1.5, 3.0, 4.0])
        )
        np.testing.assert_allclose(upstream, [1.5, 1.0])
        self.assertAlmostEqual(downstream[0], 1.5)
        self.assertTrue(np.isnan(downstream[1]))

    def test_rejects_misaligned_geometry(self):
        with self.assertRaises(ValueError):
            directional_distances(
                np.zeros((2, 3), dtype=bool),
                np.zeros((2, 3), dtype=bool),
                np.array([0.0, 1.0]),
            )


if __name__ == "__main__":
    unittest.main()
