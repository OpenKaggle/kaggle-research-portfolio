import hashlib
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validate_oof_receipt import (  # noqa: E402
    OFFICIAL_METRIC_COMMIT,
    OFFICIAL_METRIC_HASHES,
    validate,
)


def protocol():
    return {
        "folds": [
            {
                "fold": 0,
                "seed": 11,
                "train_embryo": "a",
                "validation_embryo": "b",
                "train": ["a_1"],
                "monitor": ["a_2"],
                "holdout": ["b_1"],
            },
            {
                "fold": 1,
                "seed": 12,
                "train_embryo": "b",
                "validation_embryo": "a",
                "train": ["b_1"],
                "monitor": ["b_2"],
                "holdout": ["a_1"],
            },
        ]
    }


def receipt():
    digest = "a" * 64
    folds = []
    samples = []
    for fold, dataset in ((0, "b_1"), (1, "a_1")):
        folds.append(
            {
                "fold": fold,
                "seed": 11 + fold,
                "train_embryo": "a" if fold == 0 else "b",
                "holdout_embryo": "b" if fold == 0 else "a",
                "train_datasets": 1,
                "monitor_datasets": 1,
                "holdout_datasets": 1,
                "weights_sha256": digest,
                "train_log_sha256": digest,
                "predict_log_sha256": digest,
                "holdout_summary": {"n": 1, "score": 0.4 + 0.01 * fold},
            }
        )
        samples.append({"fold": fold, "dataset": dataset, "edge_tp": 1})
    return {
        "status": "complete",
        "source_protocol_sha256": digest,
        "official_metric_commit": OFFICIAL_METRIC_COMMIT,
        "official_metric_sha256": OFFICIAL_METRIC_HASHES,
        "ground_truth_scope": "official train only",
        "competition_test_accessed": False,
        "visible_test_copies_used_for_monitor_or_holdout": False,
        "total_seconds": 100.0,
        "folds": folds,
        "per_sample": samples,
        "combined_holdout_summary": {"n": 2, "score": 0.405},
    }


class ValidateOOFReceiptTests(unittest.TestCase):
    def test_valid_receipt(self):
        result = validate(receipt(), protocol(), "a" * 64)
        self.assertTrue(result["valid"], result)

    def test_rejects_hidden_test_access(self):
        candidate = receipt()
        candidate["competition_test_accessed"] = True
        result = validate(candidate, protocol(), "a" * 64)
        self.assertFalse(result["valid"])
        self.assertTrue(any("test access" in error for error in result["errors"]))

    def test_rejects_missing_holdout_row_and_nonfinite_score(self):
        candidate = receipt()
        candidate["per_sample"].pop()
        candidate["combined_holdout_summary"]["score"] = math.nan
        result = validate(candidate, protocol(), "a" * 64)
        self.assertFalse(result["valid"])
        self.assertTrue(any("coverage" in error for error in result["errors"]))
        self.assertTrue(any("non-finite" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
