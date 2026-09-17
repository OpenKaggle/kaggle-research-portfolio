import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finalize_oof_recovery import finalize_recovery  # noqa: E402
from validate_oof_receipt import OFFICIAL_METRIC_COMMIT, OFFICIAL_METRIC_HASHES  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class FinalizeOOFRecoveryTests(unittest.TestCase):
    def make_fixture(self, root: Path):
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
        write_json(protocol_path, protocol)
        write_json(run_dir / "budgeted_oof_protocol.json", protocol)

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
        write_json(
            run_dir / "budgeted_oof_receipt.json",
            {
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
            },
        )

        local_source = root / "recovery.py"
        local_source.write_text("print('recovery')\n", encoding="utf-8")
        remote_source = root / "pulled.py"
        remote_source.write_bytes(local_source.read_bytes())
        metadata_path = root / "metadata.json"
        write_json(
            metadata_path,
            {
                "id": "owner/recovery",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": False,
            },
        )
        preflight_path = root / "preflight.json"
        write_json(
            preflight_path,
            {
                "valid": True,
                "launch_allowed": True,
                "terminal_evidence_valid": True,
                "protocol_sha256": digest(protocol_path),
                "source_sha256": digest(local_source),
                "metadata_sha256": digest(metadata_path),
            },
        )
        launch_status_path = root / "launch_status.json"
        write_json(
            launch_status_path,
            {
                "source": "Official Kaggle kernel status and execution log APIs",
                "kernel": "owner/recovery",
                "status": "RUNNING",
                "failure_message": None,
            },
        )
        launch_receipt_path = root / "launch.json"
        run_url = "https://www.kaggle.com/code/owner/recovery/edit/run/456"
        write_json(
            launch_receipt_path,
            {
                "status": "accepted_recovery_launch",
                "experiment_id": "BH-0003",
                "kernel": "owner/recovery",
                "script_version_id": 456,
                "run_url": run_url,
                "local_source_sha256": digest(local_source),
                "pulled_remote_source_sha256": digest(remote_source),
                "metadata_sha256": digest(metadata_path),
                "preflight_sha256": digest(preflight_path),
                "official_status_receipt_sha256": digest(launch_status_path),
                "competition_submission_authorized": False,
            },
        )
        completion_status_path = root / "completion_status.json"
        write_json(
            completion_status_path,
            {
                "source": "Official Kaggle kernel status and execution log APIs",
                "kernel": "owner/recovery",
                "status": "COMPLETE",
                "failure_message": None,
                "log_api_error": None,
                "script_version_id": 456,
                "run_url": run_url,
            },
        )
        ledger_path = root / "ledger.csv"
        fields = [
            "experiment_id",
            "kaggle_kernel",
            "code_version",
            "offline_score",
            "runtime_seconds",
            "promotion_gate",
            "outcome",
            "notes",
        ]
        with ledger_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "experiment_id": "BH-0003",
                    "kaggle_kernel": "owner/recovery",
                    "code_version": digest(local_source),
                    "offline_score": "pending",
                    "runtime_seconds": "",
                    "promotion_gate": "diagnostic only",
                    "outcome": "RUNNING",
                    "notes": "bound launch",
                }
            )
        return {
            "run_dir": run_dir,
            "protocol": protocol_path,
            "preflight": preflight_path,
            "launch": launch_receipt_path,
            "launch_status": launch_status_path,
            "completion": completion_status_path,
            "local": local_source,
            "remote": remote_source,
            "metadata": metadata_path,
            "ledger": ledger_path,
        }

    def call(self, root: Path, fixture: dict):
        return finalize_recovery(
            fixture["run_dir"],
            fixture["protocol"],
            fixture["preflight"],
            fixture["launch"],
            fixture["launch_status"],
            fixture["completion"],
            fixture["local"],
            fixture["remote"],
            fixture["metadata"],
            root / "validation.json",
            root / "analysis.json",
            root / "finalization.json",
            root / "binding.json",
            fixture["ledger"],
        )

    def test_rejects_different_completed_version_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.make_fixture(root)
            completion = json.loads(fixture["completion"].read_text(encoding="utf-8"))
            completion["script_version_id"] = 999
            write_json(fixture["completion"], completion)
            before = fixture["ledger"].read_bytes()
            with self.assertRaisesRegex(ValueError, "script version differs"):
                self.call(root, fixture)
            self.assertEqual(fixture["ledger"].read_bytes(), before)
            self.assertFalse((root / "binding.json").exists())
            self.assertFalse((root / "validation.json").exists())

    def test_finalizes_only_bound_recovery_as_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.make_fixture(root)
            binding, exit_code = self.call(root, fixture)
            self.assertEqual(exit_code, 0, binding)
            self.assertEqual(binding["status"], "accepted_recovery_oof_finalization")
            self.assertEqual(binding["ledger_outcome"], "OOF_VALIDATED_DIAGNOSTIC")
            self.assertFalse(binding["competition_submission_authorized"])
            self.assertFalse(binding["promotion_authorized"])
            with fixture["ledger"].open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["outcome"], "OOF_VALIDATED_DIAGNOSTIC")
            self.assertEqual(row["offline_score"], "0.405000000")
            self.assertEqual(
                binding["oof_receipt_sha256"],
                digest(fixture["run_dir"] / "budgeted_oof_receipt.json"),
            )


if __name__ == "__main__":
    unittest.main()
