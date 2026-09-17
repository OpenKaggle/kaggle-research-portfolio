from __future__ import annotations

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("hsi_2026_data_mount_smoke_v3.py")
SPEC = importlib.util.spec_from_file_location("hsi_mount_smoke_v3", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class StaticContractTests(unittest.TestCase):
    def test_metadata_disables_accelerators_and_internet(self) -> None:
        metadata = json.loads(Path(__file__).with_name("kernel-metadata.json").read_text())
        self.assertFalse(metadata["enable_gpu"])
        self.assertFalse(metadata["enable_tpu"])
        self.assertFalse(metadata["enable_internet"])
        self.assertEqual(metadata["competition_sources"], [smoke.COMPETITION])
        self.assertEqual(metadata["id"], smoke.KERNEL_REF)

    def test_source_has_no_dynamic_download_or_workload_path(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        for forbidden in ("kagglehub", "competition_download", "subprocess", "ultralytics", ".train(", ".predict("):
            self.assertNotIn(forbidden, source)
        self.assertEqual(
            smoke.INPUT_ROOT,
            Path("/kaggle/input/hyperspectral-object-detection-challenge-2026"),
        )

    def test_exact_7003_path_contract(self) -> None:
        paths = [Path("class.txt"), Path("pseudo_rgb_demo.py"), Path("sample_submission.csv")]
        paths += [Path(f"data_train/data_train/VIS/{index}.png") for index in range(3000)]
        paths += [Path(f"data_train/data_train/Annotations/VIS/{index}.xml") for index in range(3000)]
        paths += [Path(f"data_test/data_test/VIS/{index + 3000}.png") for index in range(1000)]
        summary = smoke.summarize_relative_paths(paths)
        self.assertEqual(summary["counts"], {**smoke.EXPECTED_COUNTS, "unexpected": 0})
        self.assertTrue(summary["train_stems_match"])
        self.assertEqual(summary["metadata_seen"], sorted(smoke.METADATA_FILES))

    def test_unexpected_path_is_fail_closed(self) -> None:
        summary = smoke.summarize_relative_paths([Path("surprise.bin")])
        self.assertEqual(summary["counts"]["unexpected"], 1)
        self.assertEqual(summary["unexpected_examples"], ["surprise.bin"])

    def test_deadline_is_hard_failure(self) -> None:
        with self.assertRaises(smoke.HardTimeout):
            smoke.check_deadline(time.monotonic() - 0.001)

    def test_missing_mount_writes_terminal_failure_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipt.json"
            wrong_root = Path(temporary) / "not-the-contract-root"
            started = time.monotonic()
            receipt = smoke.base_receipt(smoke.utc_now())
            with self.assertRaisesRegex(smoke.ContractViolation, "refusing non-contract root"):
                smoke.run_contract(wrong_root, receipt, started + 1)
            receipt["status"] = "FAIL"
            receipt["failure"] = {
                "stage": "source_attachment",
                "type": "ContractViolation",
                "message": "synthetic missing mount",
            }
            receipt["termination_reason"] = "contract_failure_fail_closed"
            smoke.finalize_receipt(receipt, started)
            self.assertTrue(smoke.emit_receipt(receipt, output))
            stored = json.loads(output.read_text())
            self.assertTrue(stored["terminal"])
            self.assertEqual(stored["status"], "FAIL")
            self.assertFalse(stored["runtime_contract"]["training_started"])
            self.assertFalse(stored["runtime_contract"]["submission_started"])
            self.assertIsNone(stored["kernel_version"])
            self.assertIsNone(stored["control_plane_terminal_status"])
            self.assertIsNone(stored["downloaded_log_sha256"])
            self.assertFalse(stored["source_attachment"]["remote_metadata_verified_before_run"])


if __name__ == "__main__":
    unittest.main()
