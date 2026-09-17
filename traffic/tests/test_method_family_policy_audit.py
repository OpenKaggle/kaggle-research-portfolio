import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from method_family_policy_audit import consecutive_in_task_stream  # noqa: E402


class MethodFamilyPolicyAuditTest(unittest.TestCase):
    def test_consecutive_attempts_ignore_other_task_streams_only(self):
        rows = [
            {"experiment": "state_a", "task": "state"},
            {"experiment": "queue_a", "task": "queue"},
            {"experiment": "state_b", "task": "state"},
            {"experiment": "state_c", "task": "state"},
        ]
        self.assertTrue(consecutive_in_task_stream(rows, "state", ["state_a", "state_b"]))
        self.assertFalse(consecutive_in_task_stream(rows, "state", ["state_a", "state_c"]))
        self.assertFalse(consecutive_in_task_stream(rows, "odme", ["missing_a", "missing_b"]))


if __name__ == "__main__":
    unittest.main()
