#!/usr/bin/env python3
"""Offline shape audit for a future ImageNet-initialized CUHK-X Small arm.

This module intentionally does not import torchvision, access the network,
load a pretrained checkpoint, inspect experiment outputs, or train a model.
It derives the pinned TorchVision v0.15.2 MobileNetV3-Small state shapes from
the public architecture specification and compares them with the clean-room
Thermal model.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
from collections import Counter
from math import prod
from typing import Any

import torch
from torch import Tensor, nn

from train_p2_thermal_tsm import ThermalMobileNetV3Small


REFERENCE_VERSION = "torchvision-v0.15.2"
REFERENCE_SOURCE_URL = (
    "https://raw.githubusercontent.com/pytorch/vision/v0.15.2/"
    "torchvision/models/mobilenetv3.py"
)
REFERENCE_OPS_URL = (
    "https://raw.githubusercontent.com/pytorch/vision/v0.15.2/"
    "torchvision/ops/misc.py"
)
REFERENCE_LICENSE_URL = (
    "https://raw.githubusercontent.com/pytorch/vision/v0.15.2/LICENSE"
)
WEIGHT_IDENTIFIER = "MobileNet_V3_Small_Weights.IMAGENET1K_V1"
WEIGHT_URL = (
    "https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth"
)
WEIGHT_CONTENT_LENGTH = 10_306_551
WEIGHT_FILENAME_HASH_PREFIX = "047dcff4"
REFERENCE_BATCH_NORM = {"eps": 0.001, "momentum": 0.01}
REFERENCE_TOTAL_PARAMETERS = 2_542_856
LOCAL_TOTAL_PARAMETERS = 1_558_856
LOCAL_HEAD_SEED = 20260911
LOCAL_HEAD_NORMAL_STD = 0.01
SOURCE_HEAD_KEYS = {"classifier.3.weight", "classifier.3.bias"}
LOCAL_HEAD_KEYS = {"classifier.3.weight", "classifier.3.bias"}
ALLOWED_TRANSFORMED_KEYS = {"features.0.0.weight"}

# input, kernel, expansion, output, squeeze-excitation, hard-swish, stride.
# This is the width_mult=1.0, non-reduced, non-dilated small configuration.
REFERENCE_CONFIG = [
    (16, 3, 16, 16, True, False, 2),
    (16, 3, 72, 24, False, False, 2),
    (24, 3, 88, 24, False, False, 1),
    (24, 5, 96, 40, True, True, 2),
    (40, 5, 240, 40, True, True, 1),
    (40, 5, 240, 40, True, True, 1),
    (40, 5, 120, 48, True, True, 1),
    (48, 5, 144, 48, True, True, 1),
    (48, 5, 288, 96, True, True, 2),
    (96, 5, 576, 96, True, True, 1),
    (96, 5, 576, 96, True, True, 1),
]


ShapeSpec = dict[str, tuple[tuple[int, ...], str]]
MappingSpec = dict[str, dict[str, str | None]]


def _add(
    shapes: ShapeSpec,
    mapping: MappingSpec,
    source: str,
    destination: str | None,
    shape: tuple[int, ...],
    kind: str,
    operation: str = "copy",
) -> None:
    if source in shapes:
        raise ValueError(f"duplicate reference key: {source}")
    shapes[source] = (shape, kind)
    mapping[source] = {"destination": destination, "operation": operation}


def _add_batch_norm(
    shapes: ShapeSpec,
    mapping: MappingSpec,
    source_prefix: str,
    destination_prefix: str,
    channels: int,
) -> None:
    for suffix, shape, kind in (
        ("weight", (channels,), "parameter"),
        ("bias", (channels,), "parameter"),
        ("running_mean", (channels,), "buffer"),
        ("running_var", (channels,), "buffer"),
        ("num_batches_tracked", (), "buffer"),
    ):
        _add(
            shapes,
            mapping,
            f"{source_prefix}.{suffix}",
            f"{destination_prefix}.{suffix}",
            shape,
            kind,
        )


def _add_conv_norm(
    shapes: ShapeSpec,
    mapping: MappingSpec,
    source_prefix: str,
    destination_prefix: str,
    output_channels: int,
    input_per_group: int,
    kernel: int,
) -> None:
    _add(
        shapes,
        mapping,
        f"{source_prefix}.0.weight",
        f"{destination_prefix}.0.weight",
        (output_channels, input_per_group, kernel, kernel),
        "parameter",
    )
    _add_batch_norm(
        shapes,
        mapping,
        f"{source_prefix}.1",
        f"{destination_prefix}.1",
        output_channels,
    )


def reference_shape_and_mapping_spec() -> tuple[ShapeSpec, MappingSpec]:
    """Return the pinned reference state shapes and semantic local mapping."""
    shapes: ShapeSpec = {}
    mapping: MappingSpec = {}

    _add_conv_norm(shapes, mapping, "features.0", "stem", 16, 3, 3)
    mapping["features.0.0.weight"]["operation"] = "rgb_sum_frame_zero_deltas"

    for block_index, (
        input_channels,
        kernel,
        expanded_channels,
        output_channels,
        use_se,
        _use_hs,
        _stride,
    ) in enumerate(REFERENCE_CONFIG):
        source_block = f"features.{block_index + 1}.block"
        destination_block = f"blocks.{block_index}.block"
        layer_index = 0
        if expanded_channels != input_channels:
            _add_conv_norm(
                shapes,
                mapping,
                f"{source_block}.{layer_index}",
                f"{destination_block}.{layer_index}",
                expanded_channels,
                input_channels,
                1,
            )
            layer_index += 1

        _add_conv_norm(
            shapes,
            mapping,
            f"{source_block}.{layer_index}",
            f"{destination_block}.{layer_index}",
            expanded_channels,
            1,
            kernel,
        )
        layer_index += 1

        if use_se:
            squeezed_channels = max(
                8,
                int(expanded_channels // 4 + 4) // 8 * 8,
            )
            if squeezed_channels < 0.9 * (expanded_channels // 4):
                squeezed_channels += 8
            for source_name, destination_name, shape in (
                (
                    "fc1.weight",
                    "reduce.weight",
                    (squeezed_channels, expanded_channels, 1, 1),
                ),
                ("fc1.bias", "reduce.bias", (squeezed_channels,)),
                (
                    "fc2.weight",
                    "expand.weight",
                    (expanded_channels, squeezed_channels, 1, 1),
                ),
                ("fc2.bias", "expand.bias", (expanded_channels,)),
            ):
                _add(
                    shapes,
                    mapping,
                    f"{source_block}.{layer_index}.{source_name}",
                    f"{destination_block}.{layer_index}.{destination_name}",
                    shape,
                    "parameter",
                )
            layer_index += 1

        # TorchVision nests projection Conv+BN in Conv2dNormActivation.  The
        # clean-room model stores the projection Conv and BN as adjacent layers.
        _add(
            shapes,
            mapping,
            f"{source_block}.{layer_index}.0.weight",
            f"{destination_block}.{layer_index}.weight",
            (output_channels, expanded_channels, 1, 1),
            "parameter",
        )
        _add_batch_norm(
            shapes,
            mapping,
            f"{source_block}.{layer_index}.1",
            f"{destination_block}.{layer_index + 1}",
            output_channels,
        )

    _add_conv_norm(shapes, mapping, "features.12", "final", 576, 96, 1)
    _add(
        shapes,
        mapping,
        "classifier.0.weight",
        "classifier.0.weight",
        (1024, 576),
        "parameter",
    )
    _add(
        shapes,
        mapping,
        "classifier.0.bias",
        "classifier.0.bias",
        (1024,),
        "parameter",
    )
    _add(
        shapes,
        mapping,
        "classifier.3.weight",
        None,
        (1000, 1024),
        "parameter",
        "exclude_1000_class_head",
    )
    _add(
        shapes,
        mapping,
        "classifier.3.bias",
        None,
        (1000,),
        "parameter",
        "exclude_1000_class_head",
    )
    return shapes, mapping


def _elements(shape: tuple[int, ...]) -> int:
    return prod(shape) if shape else 1


def audit_compatibility() -> dict[str, Any]:
    """Audit shapes without loading or fetching a pretrained checkpoint."""
    reference, mapping = reference_shape_and_mapping_spec()
    model = ThermalMobileNetV3Small()
    local_state = model.state_dict()
    local_shapes = {key: tuple(value.shape) for key, value in local_state.items()}
    local_parameters = dict(model.named_parameters())

    mapped_sources = {
        source for source, rule in mapping.items() if rule["destination"] is not None
    }
    mapped_destinations = [
        str(rule["destination"])
        for rule in mapping.values()
        if rule["destination"] is not None
    ]
    eligible_reference = set(reference) - SOURCE_HEAD_KEYS
    eligible_local = set(local_state) - LOCAL_HEAD_KEYS
    shape_mismatches: list[dict[str, Any]] = []
    for source in sorted(mapped_sources):
        destination = str(mapping[source]["destination"])
        source_shape = reference[source][0]
        destination_shape = local_shapes.get(destination)
        if destination_shape != source_shape:
            shape_mismatches.append(
                {
                    "source": source,
                    "destination": destination,
                    "source_shape": source_shape,
                    "destination_shape": destination_shape,
                }
            )

    reference_parameter_elements = sum(
        _elements(shape) for shape, kind in reference.values() if kind == "parameter"
    )
    eligible_parameter_elements = sum(
        _elements(reference[key][0])
        for key in eligible_reference
        if reference[key][1] == "parameter"
    )
    handled_parameter_elements = sum(
        _elements(reference[key][0])
        for key in mapped_sources
        if reference[key][1] == "parameter"
    )
    copied_parameter_elements = sum(
        _elements(reference[key][0])
        for key in mapped_sources
        if reference[key][1] == "parameter"
        and mapping[key]["operation"] == "copy"
    )
    transformed_parameter_elements = sum(
        _elements(reference[key][0])
        for key in mapped_sources
        if reference[key][1] == "parameter"
        and mapping[key]["operation"] == "rgb_sum_frame_zero_deltas"
    )

    local_config = [
        (input_channels, *configuration)
        for input_channels, configuration in zip(
            [16, *[item[2] for item in ThermalMobileNetV3Small.CONFIG[:-1]]],
            ThermalMobileNetV3Small.CONFIG,
        )
    ]
    batch_norm = [
        {
            "module": name,
            "eps": module.eps,
            "momentum": module.momentum,
            "matches_reference": (
                module.eps == REFERENCE_BATCH_NORM["eps"]
                and module.momentum == REFERENCE_BATCH_NORM["momentum"]
            ),
        }
        for name, module in model.named_modules()
        if isinstance(module, nn.BatchNorm2d)
    ]
    operations = Counter(str(rule["operation"]) for rule in mapping.values())
    checks = {
        "reference_config_exact": local_config == REFERENCE_CONFIG,
        "reference_parameter_count_exact": (
            reference_parameter_elements == REFERENCE_TOTAL_PARAMETERS
        ),
        "local_parameter_count_exact": (
            sum(parameter.numel() for parameter in local_parameters.values())
            == LOCAL_TOTAL_PARAMETERS
        ),
        "all_nonhead_reference_state_entries_handled": (
            mapped_sources == eligible_reference
        ),
        "all_nonhead_local_state_entries_filled": (
            set(mapped_destinations) == eligible_local
        ),
        "mapping_destinations_unique": (
            len(mapped_destinations) == len(set(mapped_destinations))
        ),
        "all_mapped_shapes_equal": not shape_mismatches,
        "only_stem_is_transformed": {
            key
            for key, rule in mapping.items()
            if rule["operation"] == "rgb_sum_frame_zero_deltas"
        }
        == ALLOWED_TRANSFORMED_KEYS,
        "only_source_head_is_excluded": {
            key
            for key, rule in mapping.items()
            if rule["operation"] == "exclude_1000_class_head"
        }
        == SOURCE_HEAD_KEYS,
        "handled_parameter_coverage_is_100_percent": (
            handled_parameter_elements == eligible_parameter_elements
        ),
        "direct_copy_parameter_coverage_at_least_99_95_percent": (
            copied_parameter_elements / eligible_parameter_elements >= 0.9995
        ),
    }
    shape_mapping_go = all(checks.values())
    batch_norm_compatible = all(item["matches_reference"] for item in batch_norm)
    blockers: list[str] = []
    if not batch_norm_compatible:
        blockers.append(
            "current clean-room BatchNorm uses eps=1e-5/momentum=0.1; the "
            "isolated ImageNet arm must use eps=0.001/momentum=0.01"
        )
    blockers.extend(
        [
            "full weight SHA-256 is intentionally unknown until action-time download",
            "pretrained-weight/data-derived terms must be recorded before use",
            "the running scratch output directory must never be reused",
        ]
    )
    return {
        "audit": "CUHK-X-Small-ImageNet-MobileNetV3-compatibility",
        "reference": {
            "version": REFERENCE_VERSION,
            "source_url": REFERENCE_SOURCE_URL,
            "ops_url": REFERENCE_OPS_URL,
            "license_url": REFERENCE_LICENSE_URL,
            "weight_identifier": WEIGHT_IDENTIFIER,
            "weight_url": WEIGHT_URL,
            "http_head_content_length": WEIGHT_CONTENT_LENGTH,
            "filename_hash_prefix_not_full_sha256": WEIGHT_FILENAME_HASH_PREFIX,
            "full_weight_sha256": None,
            "batch_norm": REFERENCE_BATCH_NORM,
        },
        "counts": {
            "reference_state_entries": len(reference),
            "eligible_reference_state_entries": len(eligible_reference),
            "mapped_state_entries": len(mapped_sources),
            "eligible_local_state_entries": len(eligible_local),
            "reference_total_parameters": reference_parameter_elements,
            "local_total_parameters": sum(
                parameter.numel() for parameter in local_parameters.values()
            ),
            "eligible_reference_parameter_elements": eligible_parameter_elements,
            "handled_parameter_elements": handled_parameter_elements,
            "direct_copy_parameter_elements": copied_parameter_elements,
            "transformed_stem_parameter_elements": transformed_parameter_elements,
            "handled_parameter_coverage": (
                handled_parameter_elements / eligible_parameter_elements
            ),
            "direct_copy_parameter_coverage": (
                copied_parameter_elements / eligible_parameter_elements
            ),
            "mapping_operations": dict(sorted(operations.items())),
        },
        "checks": checks,
        "shape_mismatches": shape_mismatches,
        "batch_norm_modules": batch_norm,
        "shape_mapping_decision": "GO" if shape_mapping_go else "NO_GO",
        "current_class_execution_decision": (
            "GO" if shape_mapping_go and batch_norm_compatible else "NO_GO"
        ),
        "execution_blockers": blockers,
        "weight_downloaded": False,
        "experiment_results_read": False,
        "training_started": False,
    }


def map_reference_state_dict(
    reference_state: dict[str, Tensor], local_template: dict[str, Tensor]
) -> dict[str, Tensor]:
    """Map a supplied state in memory; this function performs no file access."""
    reference, mapping = reference_shape_and_mapping_spec()
    if set(reference_state) != set(reference):
        missing = sorted(set(reference) - set(reference_state))
        unexpected = sorted(set(reference_state) - set(reference))
        raise ValueError(
            f"reference state keys differ; missing={missing}, unexpected={unexpected}"
        )
    if set(local_template) != {
        key for key in ThermalMobileNetV3Small().state_dict()
    }:
        raise ValueError("local template keys differ from the audited clean-room model")

    output = {key: value.detach().clone() for key, value in local_template.items()}
    head_generator = torch.Generator(device="cpu")
    head_generator.manual_seed(LOCAL_HEAD_SEED)
    output["classifier.3.weight"].normal_(
        mean=0.0,
        std=LOCAL_HEAD_NORMAL_STD,
        generator=head_generator,
    )
    output["classifier.3.bias"].zero_()
    for source, (expected_shape, _kind) in reference.items():
        value = reference_state[source]
        if tuple(value.shape) != expected_shape:
            raise ValueError(
                f"reference tensor {source} has {tuple(value.shape)}, expected {expected_shape}"
            )
        rule = mapping[source]
        destination = rule["destination"]
        if destination is None:
            continue
        destination = str(destination)
        operation = rule["operation"]
        if operation == "copy":
            converted = value.detach().clone()
        elif operation == "rgb_sum_frame_zero_deltas":
            converted = torch.zeros_like(output[destination])
            converted[:, 0] = value.sum(dim=1)
        else:
            raise ValueError(f"unsupported mapping operation: {operation}")
        if tuple(converted.shape) != tuple(output[destination].shape):
            raise ValueError(f"mapped tensor shape differs at {destination}")
        output[destination] = converted.to(dtype=output[destination].dtype)
    return output


def main() -> int:
    report = audit_compatibility()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["shape_mapping_decision"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
