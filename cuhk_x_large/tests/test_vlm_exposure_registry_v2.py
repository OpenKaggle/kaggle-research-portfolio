from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/vlm_exposure_registry_v2.py"
SPEC = importlib.util.spec_from_file_location("vlm_exposure_registry_v2", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ExposureRegistryTest(unittest.TestCase):
    def test_scan_is_append_only_idempotent_and_projects_no_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            log = root / "artifacts/vlm/run.jsonl"
            protocol = root / "reports/fresh_protocol.json"
            manifest = root / "artifacts/manifests/fresh.csv"
            registry = root / "artifacts/manifests/vlm_exposure_registry_v2.jsonl"
            write(
                log,
                json.dumps(
                    {
                        "qa_id": "training_0001",
                        "path": "HARn/Act/user1/1-1-1",
                        "prediction": "SECRET_PREDICTION",
                        "decomposed_prediction": "SECRET_DECOMPOSED_PREDICTION",
                        "answer": "SECRET_LABEL",
                        "correct": True,
                        "raw_output": "SECRET_RAW",
                    }
                )
                + "\n",
            )
            write(
                protocol,
                json.dumps(
                    {
                        "selected_qa_ids": ["training_0002"],
                        "selected_clips": ["HARn/Act/user2/1-1-2"],
                    }
                ),
            )
            write(manifest, "qa_id,path\ntraining_0003,HARn/Act/user3/1-1-3\n")

            first = MODULE.append_scan(root, registry)
            first_bytes = registry.read_bytes()
            second = MODULE.append_scan(root, registry)
            self.assertEqual(first["records_appended"], 3)
            self.assertEqual(second["records_appended"], 0)
            self.assertEqual(registry.read_bytes(), first_bytes)
            self.assertNotIn(b"SECRET_PREDICTION", first_bytes)
            self.assertNotIn(b"SECRET_DECOMPOSED_PREDICTION", first_bytes)
            self.assertNotIn(b"SECRET_LABEL", first_bytes)
            self.assertNotIn(b"SECRET_RAW", first_bytes)
            records = MODULE.load_registry(registry)
            inference = next(row for row in records if row["qa_id"] == "training_0001")
            self.assertTrue(inference["has_prediction"])
            self.assertEqual(inference["clip_id"], "HARn/Act/user1/1-1-1")

            write(
                log,
                log.read_text(encoding="utf-8")
                + json.dumps({"qa_id": "training_0004", "path": "HARn/Act/user4/1-1-4", "error": "failed"})
                + "\n",
            )
            third = MODULE.append_scan(root, registry)
            self.assertEqual(third["records_appended"], 1)
            self.assertTrue(registry.read_bytes().startswith(first_bytes))

    def test_conflict_gate_matches_qa_and_modality_invariant_clip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            registry = root / "artifacts/manifests/vlm_exposure_registry_v2.jsonl"
            write(
                root / "artifacts/vlm/run.jsonl",
                json.dumps({"qa_id": "training_0042", "path": "HARn/Act/user7/5-2-1", "prediction": "B"}) + "\n",
            )
            MODULE.append_scan(root, registry)
            conflict = root / "candidate_conflict.csv"
            write(conflict, "qa_id,path\ntraining_0042,HARn/Act/user7/5-2-1/Thermal/Thermal.mp4\n")
            report = MODULE.conflict_report(MODULE.load_registry(registry), conflict)
            self.assertEqual(report["decision"], "REJECT_CONFLICT")
            self.assertEqual(report["qa_conflict_count"], 1)
            self.assertEqual(report["clip_conflict_count"], 1)
            self.assertTrue(report["qa_conflicts"][0]["has_prediction_in_registry"])

            fresh = root / "candidate_fresh.json"
            write(
                fresh,
                json.dumps(
                    {
                        "selected_qa_ids": ["training_9999"],
                        "selected_clips": ["HARn/New/user9/9-9-9"],
                    }
                ),
            )
            clean_report = MODULE.conflict_report(MODULE.load_registry(registry), fresh)
            self.assertEqual(clean_report["decision"], "PASS_FRESH")

    def test_empty_or_unparseable_cohort_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.json"
            write(empty, json.dumps({"notes": "no identifiers"}))
            with self.assertRaisesRegex(ValueError, "No QA or clip identifiers"):
                MODULE.conflict_report([], empty)

    def test_clean_check_reserves_atomically_and_blocks_the_next_thread(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            registry = root / "artifacts/manifests/vlm_exposure_registry_v2.jsonl"
            first = root / "candidate_a.csv"
            second = root / "candidate_b.csv"
            row = "qa_id,path\ntraining_0777,HARn/New/user7/7-7-7\n"
            write(first, row)
            write(second, row)
            before = registry.read_bytes() if registry.exists() else b""

            first_report = MODULE.check_and_reserve(root, registry, first)
            after_first = registry.read_bytes()
            second_report = MODULE.check_and_reserve(root, registry, second)

            self.assertEqual(first_report["decision"], "PASS_FRESH_RESERVED")
            self.assertEqual(first_report["reservation_records_appended"], 1)
            self.assertTrue(after_first.startswith(before))
            self.assertEqual(second_report["decision"], "REJECT_CONFLICT")
            self.assertEqual(second_report["reservation_records_appended"], 0)
            self.assertEqual(registry.read_bytes(), after_first)

    def test_registry_summary_counts_cross_log_overlap(self) -> None:
        records = [
            {
                "source_file": "artifacts/vlm/a.jsonl",
                "qa_id": "training_1",
                "clip_id": "HARn/A/user1/x",
                "evidence_kind": "inference",
                "has_prediction": True,
            },
            {
                "source_file": "artifacts/vlm/b.jsonl",
                "qa_id": "training_1",
                "clip_id": "HARn/A/user1/x",
                "evidence_kind": "inference",
                "has_prediction": False,
            },
        ]
        summary = MODULE.registry_summary(records)
        self.assertEqual(summary["qa_ids_in_multiple_inference_logs"], 1)
        self.assertEqual(summary["clip_ids_in_multiple_inference_logs"], 1)
        self.assertEqual(summary["top_pairwise_overlaps"][0]["qa_overlap"], 1)
        self.assertEqual(summary["top_pairwise_overlaps"][0]["clip_overlap"], 1)


if __name__ == "__main__":
    unittest.main()
