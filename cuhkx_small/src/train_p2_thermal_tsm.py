#!/usr/bin/env python3
"""Run the preregistered CUHK-X P2 Thermal MobileNetV3-Small comparison.

This clean-room implementation consumes only CRC-verified training frames.  It
refuses known test paths and cannot create a Kaggle submission.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import platform
import random
import re
import resource
import statistics
import sys
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset


SEED = 20260911
FOLD_SUBJECTS = [6, 18, 5, 21]
EXPECTED_CLASSES = set(range(40))
EXPECTED_SUBJECTS = set(range(1, 10)) | set(range(16, 25))
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
DEFAULT_CONFIG = {
    "segments": 8,
    "image_size": 112,
    "epochs": 8,
    "batch_size": 16,
    "learning_rate": 3e-4,
    "weight_decay": 1e-4,
    "label_smoothing": 0.1,
}
GATE = {
    "early_stop_if_both_first_fold_gains_below": 0.01,
    "minimum_median_accuracy_gain": 0.02,
    "minimum_nonnegative_subjects": 3,
    "minimum_worst_subject_gain": -0.02,
    "maximum_fp32_checkpoint_bytes_exclusive": 95_000_000,
    "required_checkpoint_files": 1,
    "required_byte_identical_inference": True,
}


@dataclass(frozen=True)
class Clip:
    key: str
    subject: int
    label: int
    frames: tuple[Path, ...]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def configure_cpu_threads(
    torch_threads: int | None,
    torch_interop_threads: int | None,
) -> dict[str, Any]:
    """Optionally configure PyTorch CPU pools before any parallel work."""
    requested = {
        "torch_threads": torch_threads,
        "torch_interop_threads": torch_interop_threads,
    }
    if any(value is not None and value <= 0 for value in requested.values()):
        raise ValueError("PyTorch thread counts must be positive")
    # Inter-op can only be configured once and before inter-op work begins, so
    # apply it first. The CLI calls this immediately after argument parsing.
    if torch_interop_threads is not None:
        try:
            torch.set_num_interop_threads(torch_interop_threads)
        except RuntimeError as error:
            raise RuntimeError(
                "cannot set PyTorch inter-op threads after parallel work began"
            ) from error
    if torch_threads is not None:
        torch.set_num_threads(torch_threads)
    return {
        "requested": requested,
        "effective": {
            "torch_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
        },
        "explicitly_configured": any(
            value is not None for value in requested.values()
        ),
    }


def parse_label(name: str) -> int:
    match = re.match(r"^(?:action_)?(\d+)(?:_|$)", name, flags=re.IGNORECASE)
    if match is None:
        raise ValueError(f"cannot parse activity label from {name!r}")
    return int(match.group(1))


def parse_subject(name: str) -> int:
    match = re.fullmatch(r"user(\d+)", name, flags=re.IGNORECASE)
    if match is None:
        raise ValueError(f"cannot parse subject from {name!r}")
    return int(match.group(1))


def discover_clips(data_root: Path) -> list[Clip]:
    root = data_root.resolve()
    lowered_parts = {part.lower() for part in root.parts}
    if "public_mirror" in lowered_parts:
        raise ValueError("P2 training refuses quarantined public_mirror paths")
    if "testing" in lowered_parts or "small_model_track_test" in str(root).lower():
        raise ValueError("P2 training refuses known CUHK-X test paths")
    if not root.is_dir():
        raise FileNotFoundError(root)

    clips: list[Clip] = []
    seen: set[str] = set()
    for action_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        label = parse_label(action_dir.name)
        for user_dir in sorted(path for path in action_dir.iterdir() if path.is_dir()):
            subject = parse_subject(user_dir.name)
            grouped: dict[Path, list[Path]] = {}
            for frame in sorted(user_dir.rglob("*")):
                if frame.is_file() and frame.suffix.lower() in IMAGE_SUFFIXES:
                    grouped.setdefault(frame.parent, []).append(frame)
            for clip_dir, frames in sorted(grouped.items(), key=lambda item: str(item[0])):
                key = clip_dir.relative_to(root).as_posix()
                if key in seen:
                    raise ValueError(f"duplicate clip key: {key}")
                seen.add(key)
                clips.append(
                    Clip(
                        key=key,
                        subject=subject,
                        label=label,
                        frames=tuple(sorted(frames)),
                    )
                )
    if not clips:
        raise ValueError(f"no image clips found below {root}")
    labels = {clip.label for clip in clips}
    if not labels <= EXPECTED_CLASSES:
        raise ValueError(f"labels outside 0..39: {sorted(labels - EXPECTED_CLASSES)}")
    return clips


def midpoint_segment_indices(length: int, segments: int) -> list[int]:
    if length <= 0:
        raise ValueError("a clip must contain at least one frame")
    if segments <= 0:
        raise ValueError("segments must be positive")
    return [
        min(length - 1, ((2 * index + 1) * length) // (2 * segments))
        for index in range(segments)
    ]


def resize_center_pad(image: Image.Image, size: int) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError("invalid image dimensions")
    scale = min(size / width, size / height)
    resized_width = max(1, min(size, round(width * scale)))
    resized_height = max(1, min(size, round(height * scale)))
    resized = image.resize(
        (resized_width, resized_height), Image.Resampling.BILINEAR
    )
    canvas = Image.new("L", (size, size), color=0)
    left = (size - resized_width) // 2
    top = (size - resized_height) // 2
    canvas.paste(resized, (left, top))
    return canvas.crop((0, 0, size, size))


class ThermalClipDataset(Dataset[tuple[Tensor, int]]):
    def __init__(self, clips: list[Clip], segments: int, image_size: int) -> None:
        self.clips = clips
        self.segments = segments
        self.image_size = image_size

    def __len__(self) -> int:
        return len(self.clips)

    def __getitem__(self, index: int) -> tuple[Tensor, int]:
        clip = self.clips[index]
        tensors: list[Tensor] = []
        for frame_index in midpoint_segment_indices(len(clip.frames), self.segments):
            with Image.open(clip.frames[frame_index]) as image:
                grayscale = resize_center_pad(image.convert("L"), self.image_size)
                array = np.asarray(grayscale, dtype=np.float32) / 255.0
            tensors.append(torch.from_numpy(array).unsqueeze(0))
        return torch.stack(tensors), clip.label


def audit_images(clips: list[Clip]) -> dict[str, Any]:
    corrupt: list[str] = []
    for clip in clips:
        for frame in clip.frames:
            try:
                with Image.open(frame) as image:
                    image.verify()
            except Exception as exc:  # receipt captures the exact path and error
                corrupt.append(f"{frame}: {type(exc).__name__}: {exc}")
    return {
        "empty_clips": sum(not clip.frames for clip in clips),
        "corrupt_frames": len(corrupt),
        "corrupt_examples": corrupt[:20],
    }


def temporal_shift(features: Tensor, batch_size: int, segments: int) -> Tensor:
    nt, channels, height, width = features.shape
    if nt != batch_size * segments:
        raise ValueError("temporal shift received inconsistent batch/segment shape")
    fold = channels // 8
    if fold == 0:
        return features
    shaped = features.view(batch_size, segments, channels, height, width)
    shifted = torch.zeros_like(shaped)
    shifted[:, :-1, :fold] = shaped[:, 1:, :fold]
    shifted[:, 1:, fold : 2 * fold] = shaped[:, :-1, fold : 2 * fold]
    shifted[:, :, 2 * fold :] = shaped[:, :, 2 * fold :]
    return shifted.view(nt, channels, height, width)


def make_divisible(value: float, divisor: int = 8) -> int:
    rounded = max(divisor, int(value + divisor / 2) // divisor * divisor)
    return rounded if rounded >= 0.9 * value else rounded + divisor


class SqueezeExcitation(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        squeezed = make_divisible(channels / 4)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.reduce = nn.Conv2d(channels, squeezed, 1)
        self.expand = nn.Conv2d(squeezed, channels, 1)
        self.relu = nn.ReLU(inplace=True)
        self.gate = nn.Hardsigmoid(inplace=True)

    def forward(self, features: Tensor) -> Tensor:
        scale = self.pool(features)
        scale = self.relu(self.reduce(scale))
        scale = self.gate(self.expand(scale))
        return features * scale


def conv_norm_act(
    input_channels: int,
    output_channels: int,
    kernel: int,
    stride: int,
    groups: int = 1,
    hard_swish: bool = False,
) -> nn.Sequential:
    padding = (kernel - 1) // 2
    activation: nn.Module = nn.Hardswish(inplace=True) if hard_swish else nn.ReLU(inplace=True)
    return nn.Sequential(
        nn.Conv2d(
            input_channels,
            output_channels,
            kernel,
            stride=stride,
            padding=padding,
            groups=groups,
            bias=False,
        ),
        nn.BatchNorm2d(output_channels),
        activation,
    )


class InvertedResidual(nn.Module):
    def __init__(
        self,
        input_channels: int,
        expanded_channels: int,
        output_channels: int,
        kernel: int,
        stride: int,
        squeeze_excitation: bool,
        hard_swish: bool,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        if expanded_channels != input_channels:
            layers.append(
                conv_norm_act(
                    input_channels,
                    expanded_channels,
                    kernel=1,
                    stride=1,
                    hard_swish=hard_swish,
                )
            )
        layers.append(
            conv_norm_act(
                expanded_channels,
                expanded_channels,
                kernel=kernel,
                stride=stride,
                groups=expanded_channels,
                hard_swish=hard_swish,
            )
        )
        if squeeze_excitation:
            layers.append(SqueezeExcitation(expanded_channels))
        layers.extend(
            [
                nn.Conv2d(expanded_channels, output_channels, 1, bias=False),
                nn.BatchNorm2d(output_channels),
            ]
        )
        self.block = nn.Sequential(*layers)
        self.use_residual = stride == 1 and input_channels == output_channels

    def forward(
        self, features: Tensor, batch_size: int, segments: int, shift: bool
    ) -> Tensor:
        shifted = temporal_shift(features, batch_size, segments) if shift else features
        output = self.block(shifted)
        return shifted + output if self.use_residual else output


class ThermalMobileNetV3Small(nn.Module):
    """MobileNetV3-Small topology with optional clean-room TSM/difference input."""

    CONFIG = [
        (3, 16, 16, True, False, 2),
        (3, 72, 24, False, False, 2),
        (3, 88, 24, False, False, 1),
        (5, 96, 40, True, True, 2),
        (5, 240, 40, True, True, 1),
        (5, 240, 40, True, True, 1),
        (5, 120, 48, True, True, 1),
        (5, 144, 48, True, True, 1),
        (5, 288, 96, True, True, 2),
        (5, 576, 96, True, True, 1),
        (5, 576, 96, True, True, 1),
    ]
    SHIFT_BLOCKS = frozenset({1, 2, 4, 5, 6, 7, 9, 10})

    def __init__(
        self,
        classes: int = 40,
        use_tsm: bool = True,
        use_frame_difference: bool = True,
    ) -> None:
        super().__init__()
        self.use_tsm = use_tsm
        self.use_frame_difference = use_frame_difference
        self.stem = conv_norm_act(3, 16, 3, 2, hard_swish=True)
        blocks: list[InvertedResidual] = []
        input_channels = 16
        for kernel, expansion, output, se, hs, stride in self.CONFIG:
            blocks.append(
                InvertedResidual(
                    input_channels,
                    expansion,
                    output,
                    kernel,
                    stride,
                    se,
                    hs,
                )
            )
            input_channels = output
        self.blocks = nn.ModuleList(blocks)
        self.final = conv_norm_act(96, 576, 1, 1, hard_swish=True)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Linear(576, 1024),
            nn.Hardswish(inplace=True),
            nn.Dropout(p=0.2),
            nn.Linear(1024, classes),
        )

    def input_channels(self, frames: Tensor) -> Tensor:
        if self.use_frame_difference:
            delta = torch.zeros_like(frames)
            delta[:, 1:] = frames[:, 1:] - frames[:, :-1]
            positive = torch.relu(delta)
            negative = torch.relu(-delta)
        else:
            positive = torch.zeros_like(frames)
            negative = torch.zeros_like(frames)
        return torch.cat([frames, positive, negative], dim=2)

    def forward(self, frames: Tensor) -> Tensor:
        if frames.ndim != 5 or frames.shape[2] != 1:
            raise ValueError("expected frames with shape [batch, time, 1, H, W]")
        batch_size, segments = frames.shape[:2]
        features = self.input_channels(frames).flatten(0, 1)
        features = self.stem(features)
        for index, block in enumerate(self.blocks):
            features = block(
                features,
                batch_size,
                segments,
                self.use_tsm and index in self.SHIFT_BLOCKS,
            )
        features = self.final(features)
        features = self.pool(features).flatten(1)
        features = features.view(batch_size, segments, -1).mean(dim=1)
        return self.classifier(features)


# Kept as a concise compatibility name for local tests and checkpoint tooling.
ThermalTSM = ThermalMobileNetV3Small


def class_weights(clips: list[Clip]) -> Tensor:
    counts = np.bincount([clip.label for clip in clips], minlength=40).astype(np.float64)
    weights = np.zeros(40, dtype=np.float32)
    present = counts > 0
    weights[present] = np.sqrt(counts[present].sum() / counts[present])
    weights[present] /= weights[present].mean()
    return torch.from_numpy(weights)


def make_loader(
    clips: list[Clip], config: dict[str, Any], shuffle: bool, seed: int
) -> DataLoader[tuple[Tensor, Tensor]]:
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        ThermalClipDataset(
            clips, int(config["segments"]), int(config["image_size"])
        ),
        batch_size=int(config["batch_size"]),
        shuffle=shuffle,
        num_workers=0,
        generator=generator,
        drop_last=False,
    )


def classification_metrics(targets: list[int], predictions: list[int]) -> dict[str, Any]:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("invalid prediction/target vectors")
    present = sorted(set(targets))
    per_class: dict[str, dict[str, float | int]] = {}
    recalls: list[float] = []
    for label in present:
        indices = [index for index, target in enumerate(targets) if target == label]
        correct = sum(predictions[index] == label for index in indices)
        recall = correct / len(indices)
        recalls.append(recall)
        per_class[str(label)] = {"support": len(indices), "recall": recall}
    return {
        "accuracy": sum(a == b for a, b in zip(targets, predictions)) / len(targets),
        "macro_recall_present_classes": statistics.mean(recalls),
        "present_classes": present,
        "per_class": per_class,
    }


def train_variant(
    train_clips: list[Clip],
    valid_clips: list[Clip],
    config: dict[str, Any],
    device: torch.device,
    seed: int,
    use_tsm: bool,
    use_frame_difference: bool,
    initial_state: dict[str, Tensor],
    progress_callback: Callable[[dict[str, float | int]], None] | None = None,
) -> dict[str, Any]:
    seed_everything(seed)
    model = ThermalMobileNetV3Small(
        use_tsm=use_tsm, use_frame_difference=use_frame_difference
    ).to(device)
    model.load_state_dict(initial_state)
    loss_function = nn.CrossEntropyLoss(
        weight=class_weights(train_clips).to(device),
        label_smoothing=float(config["label_smoothing"]),
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    train_loader = make_loader(train_clips, config, True, seed)
    history: list[dict[str, float | int]] = []
    training_started = time.monotonic()
    for epoch in range(int(config["epochs"])):
        model.train()
        loss_total = 0.0
        examples = 0
        correct = 0
        for frames, labels in train_loader:
            frames = frames.to(device)
            labels = labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(frames)
            loss = loss_function(logits, labels)
            loss.backward()
            optimizer.step()
            loss_total += float(loss.detach()) * len(labels)
            examples += len(labels)
            correct += int((logits.argmax(dim=1) == labels).sum())
        epoch_result: dict[str, float | int] = {
            "epoch": epoch + 1,
            "train_loss": loss_total / examples,
            "train_accuracy": correct / examples,
        }
        history.append(epoch_result)
        if progress_callback is not None:
            progress_callback(dict(epoch_result))
    training_seconds = time.monotonic() - training_started

    valid_loader = make_loader(valid_clips, config, False, seed)
    model.eval()
    predictions: list[int] = []
    targets: list[int] = []
    inference_started = time.monotonic()
    with torch.inference_mode():
        for frames, labels in valid_loader:
            logits = model(frames.to(device))
            predictions.extend(int(value) for value in logits.argmax(dim=1).cpu())
            targets.extend(int(value) for value in labels)
    inference_seconds = time.monotonic() - inference_started
    return {
        "metrics": classification_metrics(targets, predictions),
        "predictions": predictions,
        "targets": targets,
        "history": history,
        "training_seconds": training_seconds,
        "inference_seconds": inference_seconds,
        "inference_milliseconds_per_clip": 1000 * inference_seconds / len(targets),
        "state_dict": {
            key: value.detach().cpu() for key, value in model.state_dict().items()
        },
    }


def dataset_fingerprint(clips: list[Clip], root: Path) -> str:
    digest = hashlib.sha256()
    for clip in sorted(clips, key=lambda item: item.key):
        digest.update(f"{clip.key}\t{clip.subject}\t{clip.label}\n".encode())
        for frame in clip.frames:
            stat = frame.stat()
            digest.update(
                f"{frame.relative_to(root).as_posix()}\t{stat.st_size}\n".encode()
            )
    return digest.hexdigest()


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_data_root_binding(
    clips: list[Clip], root: Path, extraction: dict[str, Any]
) -> dict[str, Any]:
    selection = extraction["selection"]
    frame_count = sum(len(clip.frames) for clip in clips)
    payload_bytes = sum(
        frame.stat().st_size for clip in clips for frame in clip.frames
    )
    subjects = {clip.subject for clip in clips}
    checks = {
        "root_is_thermal": root.name.lower() == "thermal",
        "selected_frame_count": frame_count == int(selection["files"]),
        "selected_payload_bytes": payload_bytes
        == int(selection["payload_bytes"]),
        "official_training_subjects": subjects == EXPECTED_SUBJECTS,
        "all_classes": {clip.label for clip in clips} == EXPECTED_CLASSES,
    }
    if not all(checks.values()):
        raise ValueError(f"data root/extraction report binding failed: {checks}")
    return {
        "checks": checks,
        "frames": frame_count,
        "payload_bytes": payload_bytes,
        "subjects": sorted(subjects),
    }


def build_run_binding(
    *,
    root: Path,
    extraction_report_path: Path,
    extraction: dict[str, Any],
    clips: list[Clip],
    config: dict[str, Any],
    max_folds: int,
    device: torch.device,
    cpu_thread_control: dict[str, Any],
) -> dict[str, Any]:
    root_binding = validate_data_root_binding(clips, root, extraction)
    dataset_digest = dataset_fingerprint(clips, root)
    core = {
        "schema_version": 1,
        "experiment": "CUHK-X-Small-P2-Thermal-TSM",
        "seed": SEED,
        "fold_order": FOLD_SUBJECTS[:max_folds],
        "max_folds": max_folds,
        "config": config,
        "promotion_gate": GATE,
        "data_root": str(root),
        "data_fingerprint": dataset_digest,
        "data_root_binding": root_binding,
        "extraction_report": str(extraction_report_path),
        "extraction_report_sha256": checkpoint_sha256(extraction_report_path),
        "source_sha256": checkpoint_sha256(Path(__file__).resolve()),
        "device": str(device),
        "cpu_thread_control": cpu_thread_control,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "pillow": metadata.version("Pillow"),
        },
        "model": {
            "backbone": "clean-room MobileNetV3-Small",
            "candidate_tsm_blocks": sorted(ThermalMobileNetV3Small.SHIFT_BLOCKS),
            "candidate_channels": [
                "frame",
                "positive_delta",
                "negative_delta",
            ],
            "pretrained_weights": False,
        },
        "test_data_read": False,
    }
    return {
        "format_version": 1,
        "run_fingerprint": canonical_json_sha256(core),
        "binding": core,
    }


def bind_output_directory(output_dir: Path, binding: dict[str, Any]) -> Path:
    path = output_dir / "run_binding.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_core = existing.get("binding")
        if (
            not isinstance(existing_core, dict)
            or existing.get("run_fingerprint")
            != canonical_json_sha256(existing_core)
            or existing != binding
        ):
            raise ValueError("output directory is bound to a different P2 run")
        return path
    write_json_atomic(path, binding)
    return path


class ProgressWriter:
    """Atomically publish the latest train-only progress event."""

    def __init__(self, path: Path, run_fingerprint: str) -> None:
        self.path = path
        self.run_fingerprint = run_fingerprint
        self.sequence = 0

    def emit(self, event: str, **details: Any) -> None:
        self.sequence += 1
        payload = {
            **details,
            "format_version": 1,
            "event": event,
            "sequence": self.sequence,
            "run_fingerprint": self.run_fingerprint,
            "test_data_read": False,
        }
        write_json_atomic(self.path, payload)
        print(json.dumps({"p2_progress": payload}, sort_keys=True), flush=True)


def fold_receipt_path(output_dir: Path, fold_index: int, subject: int) -> Path:
    return output_dir / "folds" / f"fold_{fold_index:02d}_subject_{subject:02d}.json"


def save_fold_receipt(
    path: Path,
    run_fingerprint: str,
    fold_index: int,
    valid_subject: int,
    initialization_seed: int,
    result: dict[str, Any],
) -> None:
    payload = {
        "format_version": 1,
        "status": "COMPLETE_BOTH_ARMS",
        "run_fingerprint": run_fingerprint,
        "fold": fold_index,
        "valid_subject": valid_subject,
        "initialization_seed": initialization_seed,
        "result_sha256": canonical_json_sha256(result),
        "result": result,
        "learned_weights_saved": False,
        "test_data_read": False,
    }
    write_json_atomic(path, payload)


def load_fold_receipt(
    path: Path,
    run_fingerprint: str,
    fold_index: int,
    valid_subject: int,
    initialization_seed: int,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = payload.get("result")
    checks = {
        "format": payload.get("format_version") == 1,
        "status": payload.get("status") == "COMPLETE_BOTH_ARMS",
        "run": payload.get("run_fingerprint") == run_fingerprint,
        "fold": payload.get("fold") == fold_index,
        "subject": payload.get("valid_subject") == valid_subject,
        "seed": payload.get("initialization_seed") == initialization_seed,
        "result": isinstance(result, dict),
        "result_hash": isinstance(result, dict)
        and payload.get("result_sha256") == canonical_json_sha256(result),
        "no_weights": payload.get("learned_weights_saved") is False,
        "no_test": payload.get("test_data_read") is False,
    }
    if not all(checks.values()):
        raise ValueError(f"fold receipt binding failed: {checks}")
    if (
        result.get("fold") != fold_index
        or result.get("valid_subject") != valid_subject
        or result.get("subject_overlap") != 0
        or result.get("clip_overlap") != 0
    ):
        raise ValueError("fold receipt result violates frozen split identity")
    return result


def validate_extraction_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    selection = report.get("selection", {})
    outcomes = report.get("outcomes", {})
    checks = {
        "status": report.get("status") == "EXTRACTED_AND_CRC_VERIFIED",
        "prefix": report.get("prefix") == "HAR/data/Thermal/",
        "frames_per_clip": selection.get("frames_per_clip") == 8,
        "source_groups": selection.get("groups") == 2891,
        "source_files": selection.get("available_files") == 201466,
        "source_payload_bytes": selection.get("available_payload_bytes")
        == 3524685759,
        "all_selected_files_accounted": (
            int(outcomes.get("extracted", 0)) + int(outcomes.get("reused", 0))
            == int(selection.get("files", -1))
        ),
        "test_data_read": report.get("test_data_read") is False,
    }
    if not all(checks.values()):
        raise ValueError(f"extraction report failed P2 guards: {checks}")
    return {"path": str(path.resolve()), "checks": checks, "selection": selection}


def checkpoint_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_checkpoint(
    path: Path, state_dict: dict[str, Tensor], config: dict[str, Any]
) -> None:
    payload = {
        "format_version": 1,
        "family": "clean-room MobileNetV3-Small with Temporal Shift and frame differences",
        "non_llm": True,
        "pretrained_weights": False,
        "classes": 40,
        "model": {"use_tsm": True, "use_frame_difference": True},
        "preprocessing": {
            "segments": int(config["segments"]),
            "sampling": "floor((2k+1)*N/16), k=0..7",
            "image_size": int(config["image_size"]),
            "color_mode": "L",
            "resize": "preserve aspect, center pad, 112x112 crop",
            "channels": ["frame", "positive_delta", "negative_delta"],
        },
        "state_dict": state_dict,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def replay_bytes(checkpoint_path: Path, clips: list[Clip]) -> bytes:
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = ThermalMobileNetV3Small(
        use_tsm=bool(payload["model"]["use_tsm"]),
        use_frame_difference=bool(payload["model"]["use_frame_difference"]),
    )
    model.load_state_dict(payload["state_dict"])
    model.eval()
    config = {
        "segments": int(payload["preprocessing"]["segments"]),
        "image_size": int(payload["preprocessing"]["image_size"]),
        "batch_size": 16,
    }
    loader = make_loader(clips, config, False, SEED)
    predictions: list[int] = []
    with torch.inference_mode():
        for frames, _labels in loader:
            predictions.extend(int(value) for value in model(frames).argmax(dim=1))
    rows = ["clip_key,prediction"] + [
        f"{clip.key},{prediction}" for clip, prediction in zip(clips, predictions)
    ]
    return ("\n".join(rows) + "\n").encode("utf-8")


def deterministic_checkpoint_replay(
    checkpoint_path: Path, clips: list[Clip]
) -> dict[str, Any]:
    first = replay_bytes(checkpoint_path, clips)
    second = replay_bytes(checkpoint_path, clips)
    return {
        "byte_identical": first == second,
        "output_bytes": len(first),
        "output_sha256": hashlib.sha256(first).hexdigest(),
        "clips": len(clips),
    }


def peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def package_metadata(name: str) -> dict[str, str | None]:
    package = metadata.metadata(name)
    return {
        "version": metadata.version(name),
        "license_expression": package.get("License-Expression"),
        "license_field": package.get("License"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data_root", type=Path)
    parser.add_argument("extraction_report", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-folds", type=int, choices=[2, 4], default=2)
    parser.add_argument("--epochs", type=int, default=DEFAULT_CONFIG["epochs"])
    parser.add_argument("--batch-size", type=int, default=DEFAULT_CONFIG["batch_size"])
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    parser.add_argument(
        "--torch-threads",
        type=int,
        default=None,
        help="optionally set PyTorch intra-op CPU threads before parallel work",
    )
    parser.add_argument(
        "--torch-interop-threads",
        type=int,
        default=None,
        help="optionally set PyTorch inter-op CPU threads before parallel work",
    )
    args = parser.parse_args()
    try:
        cpu_thread_control = configure_cpu_threads(
            args.torch_threads, args.torch_interop_threads
        )
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    config = dict(DEFAULT_CONFIG)
    config["epochs"] = args.epochs
    config["batch_size"] = args.batch_size
    if args.epochs <= 0 or args.batch_size <= 0:
        raise SystemExit("epochs and batch size must be positive")
    extraction = validate_extraction_report(args.extraction_report.resolve())

    if args.device == "auto":
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    root = args.data_root.resolve()
    clips = discover_clips(root)
    subjects = {clip.subject for clip in clips}
    missing = set(FOLD_SUBJECTS[: args.max_folds]) - subjects
    if missing:
        raise ValueError(f"missing preregistered subjects: {sorted(missing)}")
    if {clip.label for clip in clips} != EXPECTED_CLASSES:
        raise ValueError("P2 requires all 40 training classes")
    image_audit = audit_images(clips)
    if image_audit["empty_clips"] or image_audit["corrupt_frames"]:
        raise ValueError(f"P2 image audit failed: {image_audit}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    extraction_report_path = args.extraction_report.resolve()
    run_binding = build_run_binding(
        root=root,
        extraction_report_path=extraction_report_path,
        extraction=extraction,
        clips=clips,
        config=config,
        max_folds=args.max_folds,
        device=device,
        cpu_thread_control=cpu_thread_control,
    )
    binding_path = bind_output_directory(output_dir, run_binding)
    run_fingerprint = str(run_binding["run_fingerprint"])
    progress = ProgressWriter(output_dir / "progress.json", run_fingerprint)
    progress.emit(
        "run_started",
        folds=FOLD_SUBJECTS[: args.max_folds],
        completed_fold_receipts=sum(
            fold_receipt_path(output_dir, index, subject).is_file()
            for index, subject in enumerate(FOLD_SUBJECTS[: args.max_folds])
        ),
        cpu_thread_control=cpu_thread_control,
    )

    fold_reports: list[dict[str, Any]] = []
    resumed_folds: list[int] = []
    for fold_index, valid_subject in enumerate(FOLD_SUBJECTS[: args.max_folds]):
        train_clips = [clip for clip in clips if clip.subject != valid_subject]
        valid_clips = [clip for clip in clips if clip.subject == valid_subject]
        if {clip.key for clip in train_clips} & {clip.key for clip in valid_clips}:
            raise AssertionError("clip leakage")
        if {clip.subject for clip in train_clips} & {valid_subject}:
            raise AssertionError("subject leakage")

        initialization_seed = SEED + fold_index
        receipt_path = fold_receipt_path(
            output_dir, fold_index, valid_subject
        )
        if receipt_path.is_file():
            resumed = load_fold_receipt(
                receipt_path,
                run_fingerprint,
                fold_index,
                valid_subject,
                initialization_seed,
            )
            fold_reports.append(resumed)
            resumed_folds.append(fold_index)
            progress.emit(
                "fold_resumed",
                fold=fold_index,
                valid_subject=valid_subject,
                receipt=str(receipt_path),
            )
            continue

        progress.emit(
            "fold_started",
            fold=fold_index,
            valid_subject=valid_subject,
            initialization_seed=initialization_seed,
            train_clips=len(train_clips),
            valid_clips=len(valid_clips),
        )
        seed_everything(initialization_seed)
        initial_state = copy.deepcopy(ThermalMobileNetV3Small().state_dict())
        progress.emit(
            "variant_started",
            fold=fold_index,
            valid_subject=valid_subject,
            variant="comparator",
            epochs=int(config["epochs"]),
        )
        comparator = train_variant(
            train_clips,
            valid_clips,
            config,
            device,
            initialization_seed,
            use_tsm=False,
            use_frame_difference=False,
            initial_state=initial_state,
            progress_callback=lambda epoch, fold=fold_index, subject=valid_subject: progress.emit(
                "epoch_complete",
                fold=fold,
                valid_subject=subject,
                variant="comparator",
                total_epochs=int(config["epochs"]),
                **epoch,
            ),
        )
        progress.emit(
            "variant_started",
            fold=fold_index,
            valid_subject=valid_subject,
            variant="candidate",
            epochs=int(config["epochs"]),
        )
        candidate = train_variant(
            train_clips,
            valid_clips,
            config,
            device,
            initialization_seed,
            use_tsm=True,
            use_frame_difference=True,
            initial_state=initial_state,
            progress_callback=lambda epoch, fold=fold_index, subject=valid_subject: progress.emit(
                "epoch_complete",
                fold=fold,
                valid_subject=subject,
                variant="candidate",
                total_epochs=int(config["epochs"]),
                **epoch,
            ),
        )
        comparator_accuracy = float(comparator["metrics"]["accuracy"])
        candidate_accuracy = float(candidate["metrics"]["accuracy"])
        fold_result = {
            "fold": fold_index,
            "valid_subject": valid_subject,
            "cohort": "users_1_9" if valid_subject <= 9 else "users_16_24",
            "train_clips": len(train_clips),
            "valid_clips": len(valid_clips),
            "subject_overlap": 0,
            "clip_overlap": 0,
            "comparator": {
                "metrics": comparator["metrics"],
                "history": comparator["history"],
                "training_seconds": comparator["training_seconds"],
                "inference_milliseconds_per_clip": comparator[
                    "inference_milliseconds_per_clip"
                ],
            },
            "candidate": {
                "metrics": candidate["metrics"],
                "history": candidate["history"],
                "training_seconds": candidate["training_seconds"],
                "inference_milliseconds_per_clip": candidate[
                    "inference_milliseconds_per_clip"
                ],
            },
            "accuracy_gain": candidate_accuracy - comparator_accuracy,
            "process_peak_rss_bytes": peak_rss_bytes(),
        }
        save_fold_receipt(
            receipt_path,
            run_fingerprint,
            fold_index,
            valid_subject,
            initialization_seed,
            fold_result,
        )
        fold_reports.append(fold_result)
        progress.emit(
            "fold_complete",
            fold=fold_index,
            valid_subject=valid_subject,
            accuracy_gain=fold_result["accuracy_gain"],
            comparator_accuracy=comparator_accuracy,
            candidate_accuracy=candidate_accuracy,
            receipt=str(receipt_path),
        )

    gains = [float(row["accuracy_gain"]) for row in fold_reports]
    early_stop = len(gains) >= 2 and all(
        gain < GATE["early_stop_if_both_first_fold_gains_below"]
        for gain in gains[:2]
    )
    gate_checks: dict[str, bool] = {
        "zero_subject_overlap": all(row["subject_overlap"] == 0 for row in fold_reports),
        "zero_clip_overlap": all(row["clip_overlap"] == 0 for row in fold_reports),
        "first_two_fold_kill_not_triggered": not early_stop,
    }
    checkpoint_report: dict[str, Any] | None = None
    if early_stop:
        decision = "REJECT_P2_EARLY"
    elif args.max_folds == 2:
        decision = "P2_TWO_FOLD_SCREEN_PASSED"
    else:
        gate_checks.update(
            {
                "median_accuracy_gain": statistics.median(gains)
                >= GATE["minimum_median_accuracy_gain"],
                "nonnegative_subjects": sum(gain >= 0 for gain in gains)
                >= GATE["minimum_nonnegative_subjects"],
                "worst_subject_gain": min(gains)
                >= GATE["minimum_worst_subject_gain"],
            }
        )
        if all(gate_checks.values()):
            final_seed = SEED + 100
            seed_everything(final_seed)
            initial_state = copy.deepcopy(ThermalMobileNetV3Small().state_dict())
            final = train_variant(
                clips,
                clips[:16],
                config,
                device,
                final_seed,
                use_tsm=True,
                use_frame_difference=True,
                initial_state=initial_state,
                progress_callback=lambda epoch: progress.emit(
                    "epoch_complete",
                    fold="final_all_subjects",
                    valid_subject=None,
                    variant="final_candidate",
                    total_epochs=int(config["epochs"]),
                    **epoch,
                ),
            )
            checkpoint_path = args.output_dir.resolve() / "checkpoint.pt"
            save_checkpoint(checkpoint_path, final["state_dict"], config)
            replay_clips = [
                clip for clip in clips if clip.subject in set(FOLD_SUBJECTS)
            ]
            replay = deterministic_checkpoint_replay(checkpoint_path, replay_clips)
            checkpoint_report = {
                "files": [checkpoint_path.name],
                "count": 1,
                "bytes": checkpoint_path.stat().st_size,
                "sha256": checkpoint_sha256(checkpoint_path),
                "replay": replay,
            }
            gate_checks.update(
                {
                    "single_checkpoint": checkpoint_report["count"]
                    == GATE["required_checkpoint_files"],
                    "fp32_checkpoint_size": checkpoint_report["bytes"]
                    < GATE["maximum_fp32_checkpoint_bytes_exclusive"],
                    "byte_identical_inference": bool(replay["byte_identical"]),
                }
            )
        decision = "PROMOTE_THERMAL_BASE" if all(gate_checks.values()) else "REJECT_P2"

    model = ThermalMobileNetV3Small()
    report = {
        "decision": decision,
        "submission_eligible": False,
        "submission_created": False,
        "test_data_read": False,
        "route": "P2 Thermal MobileNetV3-Small TSM plus signed frame differences",
        "run_binding": {
            "run_fingerprint": run_fingerprint,
            "path": str(binding_path),
            "sha256": checkpoint_sha256(binding_path),
            "data_root_binding": run_binding["binding"]["data_root_binding"],
            "extraction_report_sha256": run_binding["binding"][
                "extraction_report_sha256"
            ],
            "source_sha256": run_binding["binding"]["source_sha256"],
        },
        "extraction": extraction,
        "data": {
            "root": str(root),
            "fingerprint": dataset_fingerprint(clips, root),
            "clips": len(clips),
            "frames": sum(len(clip.frames) for clip in clips),
            "subjects": sorted(subjects),
            "classes": 40,
            "image_audit": image_audit,
        },
        "fold_order": FOLD_SUBJECTS,
        "folds_run": args.max_folds,
        "resumed_folds": resumed_folds,
        "fold_receipts": [
            {
                "fold": index,
                "valid_subject": subject,
                "path": str(fold_receipt_path(output_dir, index, subject)),
                "sha256": checkpoint_sha256(
                    fold_receipt_path(output_dir, index, subject)
                ),
            }
            for index, subject in enumerate(FOLD_SUBJECTS[: args.max_folds])
        ],
        "config": config,
        "comparator": {
            "backbone": "clean-room MobileNetV3-Small",
            "temporal_pool": "mean logits/features",
            "temporal_shift": False,
            "channels": ["frame", "zero", "zero"],
            "pretrained_weights": False,
        },
        "candidate": {
            "backbone": "identical clean-room MobileNetV3-Small",
            "temporal_pool": "mean features",
            "temporal_shift_blocks": sorted(ThermalMobileNetV3Small.SHIFT_BLOCKS),
            "channels": ["frame", "positive_delta", "negative_delta"],
            "pretrained_weights": False,
            "non_llm": True,
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "fp32_parameter_bytes": sum(
                parameter.numel() * parameter.element_size()
                for parameter in model.parameters()
            ),
        },
        "promotion_gate": GATE,
        "gate_checks": gate_checks,
        "fold_results": fold_reports,
        "checkpoint": checkpoint_report,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "pillow": metadata.version("Pillow"),
            "device": str(device),
            "cpu_thread_control": cpu_thread_control,
            "process_peak_rss_bytes": peak_rss_bytes(),
        },
        "dependency_provenance": {
            "torch": package_metadata("torch"),
            "Pillow": package_metadata("Pillow"),
            "numpy": package_metadata("numpy"),
        },
        "limitations": [
            "P3 missing-modality work is forbidden until P2 passes.",
            "Depth and IR are locked until Thermal passes independently.",
            "No Kaggle submission is authorized by this script.",
        ],
    }
    write_json_atomic(output_dir / "report.json", report)
    progress.emit(
        "run_complete",
        decision=decision,
        folds_run=args.max_folds,
        resumed_folds=resumed_folds,
        report=str(output_dir / "report.json"),
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
