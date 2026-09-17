import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analyze_oof import analyse  # noqa: E402


def protocol():
    return {
        "folds": [
            {
                "fold": 0,
                "train_embryo": "a",
                "validation_embryo": "b",
                "holdout": ["b_1"],
                "holdout_selection_proxy_bytes": {"b_1": 10},
            },
            {
                "fold": 1,
                "train_embryo": "b",
                "validation_embryo": "a",
                "holdout": ["a_1"],
                "holdout_selection_proxy_bytes": {"a_1": 20},
            },
        ]
    }


def row(fold, dataset, node_ratio, edge_fp=1, edge_fn=10):
    return {
        "fold": fold,
        "dataset": dataset,
        "edge_tp": 20,
        "edge_fp": edge_fp,
        "edge_fn": edge_fn,
        "division_tp": 1,
        "division_fp": 0,
        "division_fn": 1,
        "num_pred_nodes": 30,
        "node_recall": 0.8,
        "total_node_ratio": node_ratio,
        "edge_jaccard": 20 / (20 + edge_fp + edge_fn),
        "adj_edge_jaccard": 0.5,
    }


class AnalyseOOFTests(unittest.TestCase):
    def test_rejects_invalid_receipt(self):
        result = analyse({}, protocol(), {"valid": False, "errors": ["bad"]})
        self.assertEqual(result["status"], "rejected")

    def test_selects_node_underprediction_first(self):
        receipt = {
            "per_sample": [row(0, "b_1", -0.2), row(1, "a_1", -0.1)],
            "combined_holdout_summary": {"score": 0.5},
        }
        validation = {"valid": True, "fold_scores": [0.5, 0.55]}
        result = analyse(receipt, protocol(), validation)
        self.assertEqual(
            result["next_experiment"]["single_variable"],
            "detection_threshold_downward_calibration",
        )
        self.assertEqual(result["submission_recommendation"], "diagnostic_only_do_not_submit")

    def test_selects_link_recall_when_counts_are_close(self):
        receipt = {
            "per_sample": [row(0, "b_1", 0.0), row(1, "a_1", 0.01)],
            "combined_holdout_summary": {"score": 0.5},
        }
        validation = {"valid": True, "fold_scores": [0.5, 0.51]}
        result = analyse(receipt, protocol(), validation)
        self.assertEqual(
            result["next_experiment"]["single_variable"], "temporal_link_recall"
        )


if __name__ == "__main__":
    unittest.main()
