import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from submission_attribution_audit import exact_gain, nested_value  # noqa: E402


class SubmissionAttributionAuditTest(unittest.TestCase):
    def test_decimal_gain_closes_without_float_rounding(self):
        self.assertEqual(exact_gain("0.71846", "0.74210"), "0.02364")
        self.assertEqual(exact_gain("0.74210", "0.74733"), "0.00523")
        self.assertEqual(exact_gain("0.71846", "0.74733"), "0.02887")

    def test_nested_hidden_metric_lookup_requires_exact_path(self):
        document = {"metric_boundary": {"S_od": None}}
        self.assertIsNone(nested_value(document, ["metric_boundary", "S_od"]))
        with self.assertRaises(KeyError):
            nested_value(document, ["metric_boundary", "S_attr"])


if __name__ == "__main__":
    unittest.main()
