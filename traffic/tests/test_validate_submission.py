from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from validate_submission import HEADER, validate  # noqa: E402


class ValidateSubmissionTests(unittest.TestCase):
    def _write(self, root: Path, name: str, rows: list[list[object]]) -> Path:
        path = root / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(rows)
        return path

    def test_valid_complete_task_domains(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            submission = self._write(
                root,
                "submission.csv",
                [
                    [1, "state", 80.0, 2000.0, 0, 0],
                    [2, "queue", 0, 0, 1, 0],
                    [3, "odme", 0, 0, 0, 12.5],
                ],
            )
            report = validate(submission)
            self.assertEqual(report["status"], "VALID")
            self.assertEqual(report["rows"], 3)
            self.assertEqual(report["task_rows"], {"state": 1, "queue": 1, "odme": 1})

    def test_rejects_duplicate_or_noncontiguous_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            submission = self._write(
                Path(temp),
                "submission.csv",
                [[1, "queue", 0, 0, 0, 0], [1, "queue", 0, 0, 1, 0]],
            )
            with self.assertRaisesRegex(ValueError, "expected submission_id 2"):
                validate(submission)

    def test_rejects_nonfinite_and_inactive_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nonfinite = self._write(root, "nonfinite.csv", [[1, "state", "nan", 1, 0, 0]])
            with self.assertRaisesRegex(ValueError, "not finite"):
                validate(nonfinite)
            inactive = self._write(root, "inactive.csv", [[1, "queue", 3, 0, 1, 0]])
            with self.assertRaisesRegex(ValueError, "inactive queue fields"):
                validate(inactive)

    def test_checks_key_row_count_and_task_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            submission = self._write(root, "submission.csv", [[1, "queue", 0, 0, 1, 0]])
            key = root / "submission_key.csv"
            key.write_text("submission_id,task\n1,state\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "submission key mismatch"):
                validate(submission, key)


if __name__ == "__main__":
    unittest.main()
