import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finalize_oof import finalize  # noqa: E402
from validate_oof_receipt import (  # noqa: E402
    OFFICIAL_METRIC_COMMIT,
    OFFICIAL_METRIC_HASHES,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalizeOOFTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        run_dir = root / "run"
        run_dir.mkdir()
        protocol = {
            "folds": [
                {
                    "fold": 0,
                    "seed": 11,
                    "train_embryo": "a",
                    "validation_embryo": "b",
                    "train": ["a_1"],
                    "monitor": ["a_2"],
                    "holdout": ["b_1"],
                    "holdout_selection_proxy_bytes": {"b_1": 10},
                },
                {
                    "fold": 1,
                    "seed": 12,
                    "train_embryo": "b",
                    "validation_embryo": "a",
                    "train": ["b_1"],
                    "monitor": ["b_2"],
                    "holdout": ["a_1"],
                    "holdout_selection_proxy_bytes": {"a_1": 20},
                },
            ]
        }
        protocol_path = root / "protocol.json"
        protocol_path.write_text(json.dumps(protocol) + "\n", encoding="utf-8")
        (run_dir / "budgeted_oof_protocol.json").write_text(
            json.dumps(protocol) + "\n", encoding="utf-8"
        )

        folds = []
        samples = []
        for fold_id, dataset in ((0, "b_1"), (1, "a_1")):
            train_log = run_dir / f"fold_{fold_id}_train.log"
            predict_log = run_dir / f"fold_{fold_id}_predict.log"
            train_log.write_text(f"train {fold_id}\n", encoding="utf-8")
            predict_log.write_text(f"predict {fold_id}\n", encoding="utf-8")
            folds.append(
                {
                    "fold": fold_id,
                    "seed": 11 + fold_id,
                    "train_embryo": "a" if fold_id == 0 else "b",
                    "holdout_embryo": "b" if fold_id == 0 else "a",
                    "train_datasets": 1,
                    "monitor_datasets": 1,
                    "holdout_datasets": 1,
                    "weights_sha256": "a" * 64,
                    "train_log_sha256": digest(train_log),
                    "predict_log_sha256": digest(predict_log),
                    "holdout_summary": {"n": 1, "score": 0.40 + 0.01 * fold_id},
                }
            )
            samples.append(
                {
                    "fold": fold_id,
                    "dataset": dataset,
                    "score": 0.40 + 0.01 * fold_id,
                    "edge_tp": 8,
                    "edge_fp": 1,
                    "edge_fn": 2,
                    "division_tp": 1,
                    "division_fp": 0,
                    "division_fn": 1,
                    "node_recall": 0.9,
                    "total_node_ratio": -0.05,
                }
            )
        receipt = {
            "status": "complete",
            "source_protocol_sha256": digest(protocol_path),
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
        (run_dir / "budgeted_oof_receipt.json").write_text(
            json.dumps(receipt) + "\n", encoding="utf-8"
        )
        ledger_path = root / "ledger.csv"
        fieldnames = [
            "experiment_id",
            "offline_score",
            "runtime_seconds",
            "promotion_gate",
            "outcome",
            "notes",
        ]
        with ledger_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "experiment_id": "BH-0002",
                    "offline_score": "pending",
                    "runtime_seconds": "",
                    "promotion_gate": "diagnostic only",
                    "outcome": "RUNNING",
                    "notes": "frozen fixture",
                }
            )
        return run_dir, protocol_path, ledger_path

    def run_finalizer(self, root: Path, run_dir: Path, protocol: Path, ledger: Path):
        return finalize(
            run_dir,
            protocol,
            root / "validation.json",
            root / "analysis.json",
            root / "finalization.json",
            ledger,
            "BH-0002",
        )

    def test_validates_analyzes_and_updates_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, protocol, ledger = self.make_fixture(root)
            report, exit_code = self.run_finalizer(root, run_dir, protocol, ledger)
            self.assertEqual(exit_code, 0, report)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["submission_recommendation"], "diagnostic_only_do_not_submit")
            with ledger.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "OOF_VALIDATED_DIAGNOSTIC")
            self.assertEqual(row["offline_score"], "0.405000000")

    def test_rejects_missing_log_without_changing_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, protocol, ledger = self.make_fixture(root)
            before = ledger.read_bytes()
            (run_dir / "fold_1_predict.log").unlink()
            report, exit_code = self.run_finalizer(root, run_dir, protocol, ledger)
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "rejected")
            self.assertEqual(ledger.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
