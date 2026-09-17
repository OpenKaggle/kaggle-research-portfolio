#!/usr/bin/env python3
"""Offline tests for the ImageNet MobileNetV3-Small compatibility audit.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import copy
import unittest

import torch
from torch.nn import functional as F

from audit_imagenet_mobilenet_v3_compatibility import (
    LOCAL_TOTAL_PARAMETERS,
    REFERENCE_TOTAL_PARAMETERS,
    audit_compatibility,
    map_reference_state_dict,
    reference_shape_and_mapping_spec,
)
from train_p2_thermal_tsm import ThermalMobileNetV3Small


class ImageNetMobileNetV3CompatibilityTest(unittest.TestCase):
    def synthetic_reference_state(self) -> dict[str, torch.Tensor]:
        shapes, _mapping = reference_shape_and_mapping_spec()
        state: dict[str, torch.Tensor] = {}
        for index, (key, (shape, kind)) in enumerate(sorted(shapes.items())):
            dtype = torch.long if key.endswith("num_batches_tracked") else torch.float32
            state[key] = torch.full(shape, index + 1, dtype=dtype)
            self.assertIn(kind, {"parameter", "buffer"})
        return state

    def test_exact_nonhead_shape_coverage_and_known_bn_blocker(self) -> None:
        report = audit_compatibility()
        self.assertEqual("GO", report["shape_mapping_decision"])
        self.assertEqual("NO_GO", report["current_class_execution_decision"])
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual([], report["shape_mismatches"])
        self.assertEqual(
            REFERENCE_TOTAL_PARAMETERS,
            report["counts"]["reference_total_parameters"],
        )
        self.assertEqual(
            LOCAL_TOTAL_PARAMETERS,
            report["counts"]["local_total_parameters"],
        )
        self.assertEqual(1.0, report["counts"]["handled_parameter_coverage"])
        self.assertGreaterEqual(
            report["counts"]["direct_copy_parameter_coverage"], 0.9995
        )
        self.assertEqual(432, report["counts"]["transformed_stem_parameter_elements"])
        self.assertTrue(report["execution_blockers"])
        self.assertFalse(report["weight_downloaded"])
        self.assertFalse(report["experiment_results_read"])
        self.assertFalse(report["training_started"])

    def test_head_is_deterministic_and_grayscale_stem_response_preserved(self) -> None:
        reference = self.synthetic_reference_state()
        torch.manual_seed(1)
        first_template = ThermalMobileNetV3Small().state_dict()
        torch.manual_seed(2)
        second_template = ThermalMobileNetV3Small().state_dict()
        mapped = map_reference_state_dict(reference, first_template)
        repeated = map_reference_state_dict(reference, second_template)
        self.assertTrue(
            torch.equal(mapped["classifier.3.weight"], repeated["classifier.3.weight"])
        )
        self.assertTrue(
            torch.equal(mapped["classifier.3.bias"], repeated["classifier.3.bias"])
        )
        self.assertTrue(
            torch.equal(
                mapped["classifier.3.bias"],
                torch.zeros_like(mapped["classifier.3.bias"]),
            )
        )

        reference_stem = reference["features.0.0.weight"]
        mapped_stem = mapped["stem.0.weight"]
        self.assertTrue(torch.equal(mapped_stem[:, 1], torch.zeros_like(mapped_stem[:, 1])))
        self.assertTrue(torch.equal(mapped_stem[:, 2], torch.zeros_like(mapped_stem[:, 2])))

        frame = torch.arange(49, dtype=torch.float32).view(1, 1, 7, 7) / 48
        reference_response = F.conv2d(
            frame.repeat(1, 3, 1, 1), reference_stem, stride=2, padding=1
        )
        semantic_input = torch.cat([frame, torch.zeros_like(frame), torch.zeros_like(frame)], dim=1)
        mapped_response = F.conv2d(
            semantic_input, mapped_stem, stride=2, padding=1
        )
        self.assertTrue(torch.allclose(reference_response, mapped_response))

    def test_b0_and_p2_receive_byte_identical_initial_state(self) -> None:
        reference = self.synthetic_reference_state()
        torch.manual_seed(20260911)
        mapped = map_reference_state_dict(
            reference, ThermalMobileNetV3Small().state_dict()
        )
        b0 = ThermalMobileNetV3Small(use_tsm=False, use_frame_difference=False)
        p2 = ThermalMobileNetV3Small(use_tsm=True, use_frame_difference=True)
        b0.load_state_dict(copy.deepcopy(mapped))
        p2.load_state_dict(copy.deepcopy(mapped))
        for key in b0.state_dict():
            self.assertTrue(torch.equal(b0.state_dict()[key], p2.state_dict()[key]), key)


if __name__ == "__main__":
    unittest.main()
