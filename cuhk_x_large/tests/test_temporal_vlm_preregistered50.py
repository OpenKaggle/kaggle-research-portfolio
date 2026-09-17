from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_temporal_vlm_preregistered50.py"
SPEC = importlib.util.spec_from_file_location("temporal_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TemporalSamplingTest(unittest.TestCase):
    def test_uniform_budget_and_endpoints(self) -> None:
        indices = MODULE.uniform_indices(101, 16)
        self.assertEqual(len(indices), 16)
        self.assertEqual(indices[0], 0)
        self.assertEqual(indices[-1], 100)
        self.assertEqual(indices, sorted(set(indices)))

    def test_localized_budget_order_and_bounds(self) -> None:
        indices = MODULE.localized_indices(101, [2, 6])
        self.assertEqual(len(indices), 16)
        self.assertEqual(indices, sorted(set(indices)))
        self.assertGreaterEqual(min(indices), 0)
        self.assertLess(max(indices), 101)

    def test_last_locator_marker_wins(self) -> None:
        self.assertEqual(MODULE.parse_locations("guess LOC: 1,2\nLOC: 4,6"), [4, 6])
        self.assertEqual(MODULE.parse_locations("no marker"), [])

    def test_exact_answer_parsing(self) -> None:
        allowed = list("ABCD")
        self.assertEqual(MODULE.parse_answer("reason\nFINAL: C", "single", allowed), "C")
        self.assertEqual(MODULE.parse_answer("FINAL: AC", "multi", allowed), "AC")
        self.assertEqual(MODULE.parse_answer("FINAL: CA", "multi", allowed), "")
        self.assertEqual(MODULE.parse_answer("FINAL: BDCA", "sequence", allowed), "BDCA")


if __name__ == "__main__":
    unittest.main()
