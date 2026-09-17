import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from task1_smoothing_ablation import density_smoothing_variants  # noqa: E402


class DensitySmoothingVariantsTest(unittest.TestCase):
    def test_zero_alpha_is_exactly_the_input_flow_and_all_speeds_match(self):
        with TemporaryDirectory() as temp_dir:
            network = Path(temp_dir)
            pd.DataFrame(
                {"link_id": ["a", "b"], "free_speed_kmh": [100, 100], "capacity_vph": [10000, 10000]}
            ).to_csv(network / "fd_parameters.csv", index=False)
            base = {
                "speed_kmh": np.array([[50.0, 60.0], [40.0, 55.0], [45.0, 50.0]]),
                "flow_vph": np.array([[1000.0, 1100.0], [900.0, 950.0], [1050.0, 1000.0]]),
            }
            variants = density_smoothing_variants(base, ["a", "b"], network)
            np.testing.assert_array_equal(variants["density_smoothing_a0.00"]["flow_vph"], base["flow_vph"])
            for variant in variants.values():
                np.testing.assert_array_equal(variant["speed_kmh"], base["speed_kmh"])


if __name__ == "__main__":
    unittest.main()
