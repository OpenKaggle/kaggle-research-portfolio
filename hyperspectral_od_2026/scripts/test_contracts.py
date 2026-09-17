#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = load_module("hsi_baseline", ROOT / "kaggle_notebook" / "hsi_2026_yolo_baseline.py")
validator = load_module("submission_validator", ROOT / "scripts" / "validate_submission.py")


class CubeTests(unittest.TestCase):
    def test_band_order_matches_row_major_filter_cell(self) -> None:
        image = np.arange(8 * 8, dtype=np.uint16).reshape(8, 8)
        cube = baseline.x2cube(image)
        self.assertEqual(cube.shape, (2, 2, 16))
        np.testing.assert_array_equal(cube[0, 0], image[:4, :4].reshape(-1))
        np.testing.assert_array_equal(cube[1, 1], image[4:8, 4:8].reshape(-1))

    def test_non_multiple_of_four_fails(self) -> None:
        with self.assertRaises(ValueError):
            baseline.x2cube(np.zeros((7, 8), dtype=np.uint16))


class SubmissionTests(unittest.TestCase):
    def write_csv(self, directory: Path, header: list[str], rows: list[list[object]]) -> Path:
        path = directory / "submission.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_correct_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(
                Path(tmp),
                validator.EXPECTED_COLUMNS,
                [[0, "1000", 2, 0.95, 1, 2, 10, 12], [1, "1000", 2, 0.50, 3, 4, 8, 9]],
            )
            result = validator.validate(path)
            self.assertEqual(result["rows"], 2)

    def test_missing_id_column_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(
                Path(tmp),
                validator.EXPECTED_COLUMNS[1:],
                [["1000", 2, 0.95, 1, 2, 10, 12]],
            )
            with self.assertRaisesRegex(ValueError, "header mismatch"):
                validator.validate(path)

    def test_noncontiguous_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(
                Path(tmp), validator.EXPECTED_COLUMNS, [[1, "1000", 2, 0.95, 1, 2, 10, 12]]
            )
            with self.assertRaisesRegex(ValueError, "contiguous"):
                validator.validate(path)

    def test_invalid_box_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_csv(
                Path(tmp), validator.EXPECTED_COLUMNS, [[0, "1000", 2, 0.95, 10, 2, 1, 12]]
            )
            with self.assertRaisesRegex(ValueError, "invalid box"):
                validator.validate(path)


if __name__ == "__main__":
    unittest.main()

