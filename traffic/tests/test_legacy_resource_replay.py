import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from legacy_resource_replay import coverage  # noqa: E402


class ResourceBackfillCoverageTest(unittest.TestCase):
    def test_expands_measurement_field_pairs(self):
        rows = [
            {"experiment": "a", "covers_legacy_fields": ["runtime_seconds", "peak_memory_mb"]},
            {"experiment": "b", "covers_legacy_fields": ["peak_memory_mb"]},
        ]
        self.assertEqual(
            coverage(rows),
            {("a", "runtime_seconds"), ("a", "peak_memory_mb"), ("b", "peak_memory_mb")},
        )


if __name__ == "__main__":
    unittest.main()
