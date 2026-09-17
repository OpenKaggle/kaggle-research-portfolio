import csv
import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from four_task_baseline_audit import (  # noqa: E402
    normalize_timestamp,
    odme_panel_gains,
    parse_queue_window,
    queue_change_counts,
)


class FourTaskBaselineAuditTest(unittest.TestCase):
    def test_queue_changes_are_attributed_to_panel_and_split(self):
        self.assertEqual(
            parse_queue_window("Q2_D12_I405_N_private_001"),
            ("D12_I405_N", "private"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            candidate = root / "candidate.csv"
            fieldnames = ["window_id", "timestamp", "link_id", "queue_pred"]
            rows = [
                {
                    "window_id": "Q2_D7_I10_E_validation_001",
                    "timestamp": "2031-03-01T00:00:00Z",
                    "link_id": "L1",
                    "queue_pred": "1",
                },
                {
                    "window_id": "Q2_D7_I10_E_validation_001",
                    "timestamp": "2031-03-01T00:05:00Z",
                    "link_id": "L1",
                    "queue_pred": "0",
                },
            ]
            for path, changed in ((source, False), (candidate, True)):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                if changed:
                    text = path.read_text()
                    path.write_text(
                        text.replace("2031-03-01T00:00:00Z", "2031-03-01 00:00:00+00:00")
                        .replace(",1\n", ",0\n", 1)
                    )
            count, changes, errors = queue_change_counts(source, candidate)
            self.assertEqual(count, 2)
            self.assertEqual(changes, {("D7_I10_E", "validation"): 1})
            self.assertEqual(errors, [])

    def test_queue_timestamp_normalization_requires_timezone(self):
        self.assertEqual(
            normalize_timestamp("2031-03-01 00:00:00+00:00"),
            normalize_timestamp("2031-03-01T00:00:00Z"),
        )
        with self.assertRaises(ValueError):
            normalize_timestamp("2031-03-01 00:00:00")

    def test_odme_gains_require_a_paired_lambda_per_panel_split(self):
        rows = [
            {"level": "panel", "panel": "P1", "split": "validation", "lambda": "5", "S_link": "0.9"},
            {"level": "panel", "panel": "P1", "split": "validation", "lambda": "20", "S_link": "0.8"},
            {"level": "overall", "panel": "", "split": "validation", "lambda": "5", "S_link": "0.9"},
        ]
        gains, errors = odme_panel_gains(rows, 5.0, 20.0)
        self.assertEqual(errors, [])
        self.assertEqual(len(gains), 1)
        self.assertAlmostEqual(gains[0]["S_link_gain"], 0.1)
        incomplete, errors = odme_panel_gains(rows[:1], 5.0, 20.0)
        self.assertEqual(incomplete, [])
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
