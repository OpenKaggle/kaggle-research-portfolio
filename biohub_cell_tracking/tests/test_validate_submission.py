from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "src" / "validate_submission.py"
SPEC = importlib.util.spec_from_file_location("validate_submission", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_rows(path: Path, rows: list[list[object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(MODULE.COLUMNS)
        writer.writerows(rows)


class ValidateSubmissionTest(unittest.TestCase):
    def test_valid_graph(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submission.csv"
            write_rows(
                path,
                [
                    [0, "movie", "node", 1, 0, 1, 2, 3, -1, -1],
                    [1, "movie", "node", 2, 1, 1, 2, 4, -1, -1],
                    [2, "movie", "edge", -1, -1, -1, -1, -1, 1, 2],
                ],
            )
            report = MODULE.validate(path, {"movie"}, {"movie": (2, 4, 8, 8)})
            self.assertTrue(report["valid"])
            self.assertEqual(report["topology"]["movie"]["edges"], 1)

    def test_rejects_dangling_and_noncontiguous(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            write_rows(
                path,
                [
                    [0, "movie", "node", 1, 0, 1, 2, 3, -1, -1],
                    [2, "movie", "edge", -1, -1, -1, -1, -1, 1, 9],
                ],
            )
            report = MODULE.validate(path, {"movie"}, {})
            self.assertFalse(report["valid"])
            self.assertTrue(any("not contiguous" in error for error in report["errors"]))
            self.assertTrue(any("dangling" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
