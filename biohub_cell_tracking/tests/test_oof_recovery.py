import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from build_oof_recovery_protocol import build  # noqa: E402
from validate_oof_recovery import preflight  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RecoveryProtocolTests(unittest.TestCase):
    def test_live_telemetry_builds_reserved_sub_12_hour_budget(self):
        parent = {
            "folds": [{"fold": 0}, {"fold": 1}],
            "training": {"epochs": 12},
            "runtime_budget": {"estimated_inference_seconds": 2400.0},
            "limitations": [],
        }
        activity = {
            "script_version_id": 123,
            "checked_at_utc": "2026-09-09T00:00:00Z",
            "latest_ui_observation": {
                "median_seconds_per_batch": 5.49,
                "batches_per_epoch": 1454,
            },
        }
        protocol = build(parent, "a" * 64, activity)
        self.assertEqual(protocol["training"]["epochs"], 1)
        self.assertEqual(
            protocol["recovery_parent"]["protocol_sha256"], "a" * 64
        )
        budget = protocol["runtime_budget"]
        self.assertTrue(budget["passes_prelaunch_runtime_gate"])
        self.assertLess(budget["estimated_total_seconds_with_reserve"], 12 * 3600)
        self.assertGreater(budget["headroom_seconds"], 0)

    def test_preflight_blocks_live_parent_and_requires_bound_terminal_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "parent.json"
            parent.write_text(
                json.dumps({"training": {"epochs": 12}}) + "\n",
                encoding="utf-8",
            )
            protocol = {
                "training": {"epochs": 1},
                "recovery_parent": {"protocol_sha256": digest(parent)},
                "runtime_budget": {
                    "passes_prelaunch_runtime_gate": True,
                    "estimated_total_seconds_with_reserve": 30000.0,
                    "estimated_total_hours_with_reserve": 30000.0 / 3600,
                    "headroom_hours": (43200.0 - 30000.0) / 3600,
                },
            }
            protocol_path = root / "protocol.json"
            protocol_path.write_text(json.dumps(protocol) + "\n", encoding="utf-8")
            source_path = root / "source.py"
            source_path.write_text(
                "PROTOCOL = "
                + repr(protocol)
                + "\nSOURCE_PROTOCOL_SHA256 = "
                + repr(digest(protocol_path))
                + "\nMETHOD = 'budgeted_embryo_oof_1ep_recovery'\n",
                encoding="utf-8",
            )
            metadata_path = root / "kernel-metadata.json"
            metadata_path.write_text(
                json.dumps(
                    {
                        "is_private": True,
                        "enable_gpu": True,
                        "enable_internet": False,
                        "code_file": source_path.name,
                        "competition_sources": [
                            "biohub-cell-tracking-during-development"
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            status_path = root / "status.json"
            status_path.write_text(
                '{"status":"RUNNING","kernel":"owner/kernel"}\n',
                encoding="utf-8",
            )
            terminal_evidence_path = root / "terminal.json"
            waiting = preflight(
                protocol_path,
                source_path,
                metadata_path,
                parent,
                status_path,
                terminal_evidence_path,
            )
            self.assertTrue(waiting["valid"])
            self.assertFalse(waiting["launch_allowed"])
            self.assertEqual(waiting["status"], "ready_waiting_current_terminal")

            status_path.write_text(
                '{"status":"ERROR","kernel":"owner/kernel"}\n',
                encoding="utf-8",
            )
            missing_evidence = preflight(
                protocol_path,
                source_path,
                metadata_path,
                parent,
                status_path,
                terminal_evidence_path,
            )
            self.assertFalse(missing_evidence["valid"])
            self.assertFalse(missing_evidence["launch_allowed"])

            terminal_evidence_path.write_text(
                json.dumps(
                    {
                        "status": "accepted_terminal_failure",
                        "kernel": "owner/kernel",
                        "official_terminal_status": "ERROR",
                        "official_status_receipt_sha256": digest(status_path),
                        "recovery_authorized": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            ready = preflight(
                protocol_path,
                source_path,
                metadata_path,
                parent,
                status_path,
                terminal_evidence_path,
            )
            self.assertTrue(ready["valid"])
            self.assertTrue(ready["launch_allowed"])
            self.assertEqual(ready["status"], "ready_to_launch")

            status_path.write_text(
                '{"status":"COMPLETE","kernel":"owner/kernel"}\n',
                encoding="utf-8",
            )
            complete = preflight(
                protocol_path,
                source_path,
                metadata_path,
                parent,
                status_path,
                terminal_evidence_path,
            )
            self.assertTrue(complete["valid"])
            self.assertFalse(complete["launch_allowed"])
            self.assertEqual(
                complete["status"], "awaiting_completed_output_validation"
            )

            protocol["training"]["learning_rate"] = 0.5
            protocol_path.write_text(json.dumps(protocol) + "\n", encoding="utf-8")
            source_path.write_text(
                "PROTOCOL = "
                + repr(protocol)
                + "\nSOURCE_PROTOCOL_SHA256 = "
                + repr(digest(protocol_path))
                + "\nMETHOD = 'budgeted_embryo_oof_1ep_recovery'\n",
                encoding="utf-8",
            )
            changed = preflight(
                protocol_path,
                source_path,
                metadata_path,
                parent,
                status_path,
                terminal_evidence_path,
            )
            self.assertFalse(changed["valid"])
            self.assertFalse(changed["single_variable_contract"])
            self.assertIn(
                "recovery changes operational fields beyond training.epochs",
                changed["errors"],
            )


if __name__ == "__main__":
    unittest.main()
