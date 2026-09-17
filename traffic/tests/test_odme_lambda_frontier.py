import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import nnls


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from odme_lambda_frontier import _solve  # noqa: E402


class OdmeMatrixFreeSolveTest(unittest.TestCase):
    def test_matches_dense_augmented_nnls(self):
        A = np.array(
            [
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 1.0, 1.0],
                [1.0, 1.0, 0.0, 0.0],
            ]
        )
        counts = np.array([14.0, 20.0, 12.0])
        anchor = np.array([5.0, 6.0, 7.0, 4.0])
        reg_lambda = 5.0
        dense_A = np.vstack([A, np.sqrt(reg_lambda) * np.eye(A.shape[1])])
        dense_b = np.concatenate([counts, np.sqrt(reg_lambda) * anchor])
        expected, _ = nnls(dense_A, dense_b)
        actual = _solve(A, counts, anchor, reg_lambda)
        np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=1e-7)

    def test_accepts_frozen_solver_settings(self):
        A = np.array([[1.0, 1.0], [1.0, 0.0]])
        counts = np.array([8.0, 3.0])
        anchor = np.array([2.0, 4.0])
        actual = _solve(
            A,
            counts,
            anchor,
            5.0,
            tolerance=1e-9,
            lsmr_tolerance=1e-10,
            max_iterations=200,
        )
        self.assertTrue(np.isfinite(actual).all())
        self.assertTrue((actual >= 0).all())


if __name__ == "__main__":
    unittest.main()
