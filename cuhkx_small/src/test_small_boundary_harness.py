#!/usr/bin/env python3
"""Synthetic tests for the CUHK-X Small fail-closed boundaries.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from small_boundary_harness import (
    DEFAULT_CONFIG,
    DEFAULT_SUBMISSION_LOG,
    audit_inference_sources,
    audit_modality_contract,
    audit_sensor_batch,
    audit_split_records,
    audit_submission_cadence,
    fit_train_robust_scale,
    natural_path_key,
    validate_preregistration,
    validate_release_manifest,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SmallBoundaryHarnessTest(unittest.TestCase):
    def test_frozen_preregistration_and_current_cadence(self) -> None:
        config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(validate_preregistration(config)["passed"])
        cadence = audit_submission_cadence(DEFAULT_SUBMISSION_LOG, 3)
        self.assertTrue(cadence["passed"])
        self.assertEqual({"2026-09-08": 1}, cadence["per_day"])

    def test_subject_and_clip_leakage_fail_closed(self) -> None:
        clean = [
            {"clip_key": "action01/user1/clip1", "subject": 1, "split": "train"},
            {"clip_key": "action01/user2/clip2", "subject": 2, "split": "validation"},
        ]
        self.assertTrue(audit_split_records(clean)["passed"])
        subject_leak = copy.deepcopy(clean)
        subject_leak[1]["subject"] = 1
        self.assertFalse(audit_split_records(subject_leak)["passed"])
        clip_leak = copy.deepcopy(clean)
        clip_leak[1]["clip_key"] = clip_leak[0]["clip_key"]
        self.assertFalse(audit_split_records(clip_leak)["passed"])

    def test_sensor_order_and_scale_drift_fail_closed(self) -> None:
        train = [[0.0, 0.0], [1.0, 2.0], [2.0, 4.0], [3.0, 6.0]]
        scale = fit_train_robust_scale(train, 1e-6)
        clean = audit_sensor_batch([0.0, 0.1, 0.2, 0.3], train, scale, 50.0, 0.05)
        self.assertTrue(clean["passed"])
        reordered = audit_sensor_batch([0.0, 0.2, 0.1, 0.3], train, scale, 50.0, 0.05)
        self.assertFalse(reordered["passed"])
        drift = audit_sensor_batch(
            [0.0, 0.1, 0.2, 0.3],
            [[999.0, 999.0]] * 4,
            scale,
            50.0,
            0.05,
        )
        self.assertFalse(drift["passed"])
        ordered = sorted(["frame10.jpg", "frame2.jpg", "frame1.jpg"], key=natural_path_key)
        self.assertEqual(["frame1.jpg", "frame2.jpg", "frame10.jpg"], ordered)

    def test_missing_modality_requires_exact_mask(self) -> None:
        accepted = audit_modality_contract(
            {"thermal": True, "imu": False},
            {"thermal": 1.0, "imu": 0.0},
            ["thermal", "imu"],
            supports_missing=True,
        )
        self.assertTrue(accepted["passed"])
        silent_zero = audit_modality_contract(
            {"thermal": True, "imu": False},
            {"thermal": 1.0, "imu": 1.0},
            ["thermal", "imu"],
            supports_missing=True,
        )
        self.assertFalse(silent_zero["passed"])
        unsupported = audit_modality_contract(
            {"thermal": True, "imu": False},
            {"thermal": 1.0, "imu": 0.0},
            ["thermal", "imu"],
            supports_missing=False,
        )
        self.assertFalse(unsupported["passed"])

    def test_static_inference_rejects_network_and_llm_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            safe = root / "safe.py"
            unsafe = root / "unsafe.py"
            safe.write_text("import json\nVALUE = 1\n", encoding="utf-8")
            unsafe.write_text("import requests\nfrom transformers import AutoModel\n", encoding="utf-8")
            self.assertTrue(audit_inference_sources([safe], ["transformers"])["passed"])
            result = audit_inference_sources([unsafe], ["transformers"])
            self.assertFalse(result["passed"])
            self.assertEqual(2, len(result["forbidden_imports"]))

    def test_single_checkpoint_release_manifest_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint = root / "model.pt"
            inference = root / "inference.py"
            checkpoint.write_bytes(b"small-checkpoint")
            inference.write_text("import json\n\ndef predict(value):\n    return value\n", encoding="utf-8")
            manifest = {
                "learned_weight_files": ["model.pt"],
                "checkpoint_sha256": digest(checkpoint),
                "quantization": "fp32",
                "uses_llm": False,
                "model_family": "temporal_shift_module",
                "inference_sources": ["inference.py"],
                "forbidden_import_roots": ["transformers", "openai"],
                "asset_inventory": [
                    {
                        "path": "model.pt",
                        "public_url": "https://www.kaggle.com/code/example/finalist",
                        "version": "frozen-v1",
                        "license": "Apache-2.0",
                        "sha256": digest(checkpoint),
                        "status": "APPROVED",
                    },
                    {
                        "path": "inference.py",
                        "public_url": "https://www.kaggle.com/code/example/finalist",
                        "version": "frozen-v1",
                        "license": "Apache-2.0",
                        "sha256": digest(inference),
                        "status": "APPROVED",
                    },
                ],
                "deterministic_output_sha256": ["abc123", "abc123"],
                "test_labels_read": False,
                "network_allowed_at_inference": False,
                "scientific_gate_passed": True,
            }
            self.assertTrue(validate_release_manifest(manifest, root)["passed"])

            second = root / "detector.pt"
            second.write_bytes(b"second-weight-file")
            two_weights = copy.deepcopy(manifest)
            two_weights["learned_weight_files"] = ["model.pt", "detector.pt"]
            self.assertFalse(validate_release_manifest(two_weights, root)["passed"])
            second.unlink()

            bad_license = copy.deepcopy(manifest)
            bad_license["asset_inventory"][0]["status"] = "UNRESOLVED"
            self.assertFalse(validate_release_manifest(bad_license, root)["passed"])

            nondeterministic = copy.deepcopy(manifest)
            nondeterministic["deterministic_output_sha256"] = ["one", "two"]
            self.assertFalse(validate_release_manifest(nondeterministic, root)["passed"])


if __name__ == "__main__":
    unittest.main()
