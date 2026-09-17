import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from reproduce_current_best import _expect_diff  # noqa: E402


class FrozenReplayContractTest(unittest.TestCase):
    def test_accepts_only_exact_declared_lineage(self):
        config = {
            "current_best": {
                "expected_changed_rows_by_task_from_v32": {"queue": 160, "odme": 70708},
                "expected_changed_cells_by_column_from_v32": {
                    "queue_pred": 160,
                    "path_flow": 70708,
                },
            }
        }
        report = {
            "changed_rows_by_task": {"queue": 160, "odme": 70708},
            "changed_cells_by_column": {"queue_pred": 160, "path_flow": 70708},
        }
        _expect_diff(report, config)
        report["changed_rows_by_task"]["state"] = 1
        with self.assertRaises(ValueError):
            _expect_diff(report, config)


if __name__ == "__main__":
    unittest.main()
