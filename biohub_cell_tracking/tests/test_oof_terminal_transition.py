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
from record_oof_recovery_launch import record_launch  # noqa: E402
from record_oof_terminal import record_terminal  # noqa: E402
from validate_oof_recovery import preflight  # noqa: E402
from validate_oof_receipt import OFFICIAL_METRIC_COMMIT, OFFICIAL_METRIC_HASHES  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class OOFTerminalTransitionTests(unittest.TestCase):
    def test_live_parent_to_bound_recovery_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folds = [
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
            parent_protocol = root / "parent.json"
            write_json(
                parent_protocol,
                {"training": {"epochs": 12}, "folds": folds},
            )
            protocol = {
                "training": {"epochs": 1},
                "recovery_parent": {"protocol_sha256": digest(parent_protocol)},
                "runtime_budget": {
                    "passes_prelaunch_runtime_gate": True,
                    "estimated_total_seconds_with_reserve": 33000.0,
                    "estimated_total_hours_with_reserve": 33000.0 / 3600,
                    "headroom_hours": (43200.0 - 33000.0) / 3600,
                },
                "folds": folds,
            }
            protocol_path = root / "recovery_protocol.json"
            write_json(protocol_path, protocol)
            source = root / "recovery.py"
            source.write_text(
                "PROTOCOL = "
                + repr(protocol)
                + "\nSOURCE_PROTOCOL_SHA256 = "
                + repr(digest(protocol_path))
                + "\nMETHOD = 'budgeted_embryo_oof_1ep_recovery'\n",
                encoding="utf-8",
            )
            metadata = root / "metadata.json"
            write_json(
                metadata,
                {
                    "id": "owner/recovery",
                    "is_private": True,
                    "enable_gpu": True,
                    "enable_internet": False,
                    "code_file": source.name,
                    "competition_sources": [
                        "biohub-cell-tracking-during-development"
                    ],
                },
            )
            parent_status = root / "parent_status.json"
            write_json(
                parent_status,
                {
                    "checked_at_utc": "2026-09-09T11:00:00+00:00",
                    "kernel": "owner/parent",
                    "status": "RUNNING",
                    "failure_message": None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                },
            )
            activity = root / "activity.json"
            write_json(
                activity,
                {
                    "kernel": "owner/parent",
                    "script_version_id": 111,
                    "source": "Official authenticated Kaggle Notebook UI Logs page",
                    "classification": "ACTIVE_BUT_RUNTIME_INFEASIBLE",
                    "activity_observations": [
                        {"runtime_seconds": 43190.0, "log_items": 8000}
                    ],
                    "projection": {
                        "assessment": "runtime_infeasible",
                        "projected_training_hours_two_folds": 53.2,
                    },
                    "intervention": {
                        "parallel_rerun_allowed": False,
                        "cancelled": False,
                    },
                },
            )
            output_dir = root / "parent_output"
            output_dir.mkdir()
            (output_dir / "fold_0_train.log").write_text(
                "partial\n", encoding="utf-8"
            )
            ledger = root / "ledger.csv"
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
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(
                    {
                        "experiment_id": "BH-0002",
                        "kaggle_kernel": "owner/parent",
                        "code_version": "parent-hash",
                        "offline_score": "pending",
                        "runtime_seconds": "",
                        "promotion_gate": "diagnostic only",
                        "outcome": "RUNNING_RUNTIME_AT_RISK",
                        "notes": "parent",
                    }
                )
                writer.writerow(
                    {
                        "experiment_id": "BH-0003",
                        "kaggle_kernel": "owner/recovery",
                        "code_version": digest(source),
                        "offline_score": "pending",
                        "runtime_seconds": "",
                        "promotion_gate": "diagnostic only",
                        "outcome": "PREPARED_NOT_LAUNCHED",
                        "notes": "recovery",
                    }
                )
            terminal_receipt = root / "terminal.json"

            live = preflight(
                protocol_path,
                source,
                metadata,
                parent_protocol,
                parent_status,
                terminal_receipt,
            )
            self.assertTrue(live["valid"])
            self.assertFalse(live["launch_allowed"])

            write_json(
                parent_status,
                {
                    "checked_at_utc": "2026-09-09T11:09:30+00:00",
                    "kernel": "owner/parent",
                    "status": "CANCEL_ACKNOWLEDGED",
                    "failure_message": None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                },
            )
            terminal = record_terminal(
                parent_status,
                activity,
                output_dir,
                ledger,
                terminal_receipt,
                "BH-0002",
            )
            self.assertEqual(terminal["ledger_outcome"], "FAILED_RUNTIME_LIMIT")

            ready = preflight(
                protocol_path,
                source,
                metadata,
                parent_protocol,
                parent_status,
                terminal_receipt,
            )
            self.assertTrue(ready["valid"])
            self.assertTrue(ready["launch_allowed"])
            self.assertTrue(ready["terminal_evidence_valid"])
            preflight_path = root / "preflight.json"
            write_json(preflight_path, ready)

            remote_source = root / "pulled_recovery.py"
            remote_source.write_bytes(source.read_bytes())
            recovery_status = root / "recovery_status.json"
            write_json(
                recovery_status,
                {
                    "checked_at_utc": "2026-09-09T11:12:00+00:00",
                    "kernel": "owner/recovery",
                    "status": "RUNNING",
                    "failure_message": None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                },
            )
            launch_receipt = root / "launch.json"
            launch = record_launch(
                preflight_path,
                source,
                remote_source,
                metadata,
                recovery_status,
                ledger,
                launch_receipt,
                222,
                "https://www.kaggle.com/code/owner/recovery/edit/run/222",
                "BH-0003",
            )
            self.assertEqual(launch["ledger_outcome"], "RUNNING")
            with ledger.open(encoding="utf-8", newline="") as handle:
                rows = {row["experiment_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["BH-0002"]["outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertEqual(rows["BH-0003"]["outcome"], "RUNNING")
            self.assertEqual(
                launch["local_source_sha256"],
                launch["pulled_remote_source_sha256"],
            )

            run_dir = root / "recovery_output"
            run_dir.mkdir()
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
                        "holdout_summary": {
                            "n": 1,
                            "score": 0.40 + 0.01 * fold_id,
                        },
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
                    "total_seconds": 33000.0,
                    "folds": folds,
                    "per_sample": samples,
                    "combined_holdout_summary": {"n": 2, "score": 0.405},
                },
            )
            completion_status = root / "recovery_completion_status.json"
            write_json(
                completion_status,
                {
                    "checked_at_utc": "2026-09-09T20:00:00+00:00",
                    "kernel": "owner/recovery",
                    "status": "COMPLETE",
                    "failure_message": None,
                    "log_api_error": None,
                    "source": "Official Kaggle kernel status and execution log APIs",
                    "script_version_id": 222,
                    "run_url": "https://www.kaggle.com/code/owner/recovery/edit/run/222",
                },
            )
            final_binding, exit_code = finalize_recovery(
                run_dir,
                protocol_path,
                preflight_path,
                launch_receipt,
                recovery_status,
                completion_status,
                source,
                remote_source,
                metadata,
                root / "recovery_validation.json",
                root / "recovery_analysis.json",
                root / "recovery_finalization.json",
                root / "recovery_finalization_binding.json",
                ledger,
                "BH-0003",
            )
            self.assertEqual(exit_code, 0, final_binding)
            self.assertEqual(
                final_binding["status"], "accepted_recovery_oof_finalization"
            )
            self.assertFalse(final_binding["competition_submission_authorized"])
            with ledger.open(encoding="utf-8", newline="") as handle:
                rows = {row["experiment_id"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["BH-0002"]["outcome"], "FAILED_RUNTIME_LIMIT")
            self.assertEqual(rows["BH-0003"]["outcome"], "OOF_VALIDATED_DIAGNOSTIC")
            self.assertEqual(rows["BH-0003"]["offline_score"], "0.405000000")


if __name__ == "__main__":
    unittest.main()
