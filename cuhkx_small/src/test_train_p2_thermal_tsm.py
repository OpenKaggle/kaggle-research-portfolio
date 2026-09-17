#!/usr/bin/env python3
"""Tests for the clean-room P2 Thermal model and loader.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch

from train_p2_thermal_tsm import (
    DEFAULT_CONFIG,
    FOLD_SUBJECTS,
    SEED,
    Clip,
    ProgressWriter,
    ThermalClipDataset,
    ThermalMobileNetV3Small,
    bind_output_directory,
    build_run_binding,
    canonical_json_sha256,
    configure_cpu_threads,
    deterministic_checkpoint_replay,
    discover_clips,
    midpoint_segment_indices,
    resize_center_pad,
    load_fold_receipt,
    save_fold_receipt,
    save_checkpoint,
    temporal_shift,
    train_variant,
)


class P2ThermalTSMTest(unittest.TestCase):
    def test_discovery_rejects_quarantined_public_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "public_mirror" / "Thermal"
            root.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "quarantined public_mirror"):
                discover_clips(root)

    def test_discovery_training_checkpoint_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "Thermal"
            for label in range(40):
                clip = root / f"action_{label:02d}" / "user6" / "clip1"
                clip.mkdir(parents=True)
                for frame in range(3):
                    array = np.full((20, 24), label + frame, dtype=np.uint8)
                    Image.fromarray(array).save(clip / f"frame_{frame:04d}.jpg")
            clips = discover_clips(root)
            self.assertEqual(40, len(clips))
            frames, label = ThermalClipDataset(clips, 8, 32)[0]
            self.assertEqual((8, 1, 32, 32), tuple(frames.shape))
            self.assertEqual(0, label)
            with torch.inference_mode():
                comparator = ThermalMobileNetV3Small(
                    use_tsm=False, use_frame_difference=False
                )
                candidate = ThermalMobileNetV3Small(
                    use_tsm=True, use_frame_difference=True
                )
                self.assertEqual((1, 40), tuple(comparator(frames.unsqueeze(0)).shape))
                self.assertEqual((1, 40), tuple(candidate(frames.unsqueeze(0)).shape))

            config = {
                "segments": 2,
                "image_size": 16,
                "epochs": 1,
                "batch_size": 8,
                "learning_rate": 3e-4,
                "weight_decay": 1e-4,
                "label_smoothing": 0.1,
            }
            initial = copy.deepcopy(ThermalMobileNetV3Small().state_dict())
            epoch_progress: list[dict[str, float | int]] = []
            trained = train_variant(
                clips,
                clips[:4],
                config,
                torch.device("cpu"),
                seed=20260911,
                use_tsm=True,
                use_frame_difference=True,
                initial_state=initial,
                progress_callback=epoch_progress.append,
            )
            self.assertEqual(trained["history"], epoch_progress)
            checkpoint = Path(temporary) / "checkpoint.pt"
            save_checkpoint(checkpoint, trained["state_dict"], config)
            self.assertLess(checkpoint.stat().st_size, 95_000_000)
            replay = deterministic_checkpoint_replay(checkpoint, clips[:8])
            self.assertTrue(replay["byte_identical"])

    def test_run_binding_progress_and_fold_receipt_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "HAR" / "data" / "Thermal"
            root.mkdir(parents=True)
            frame = root / "frame.jpg"
            Image.fromarray(np.zeros((4, 4), dtype=np.uint8)).save(frame)
            clips = [
                Clip(
                    key=f"action_{label:02d}/user{subject}/clip1",
                    subject=subject,
                    label=label,
                    frames=(frame,),
                )
                for subject in [*range(1, 10), *range(16, 25)]
                for label in range(40)
            ]
            extraction_path = base / "extraction.json"
            extraction_path.write_text('{"receipt":"one"}\n', encoding="utf-8")
            extraction = {
                "selection": {
                    "files": len(clips),
                    "payload_bytes": frame.stat().st_size * len(clips),
                }
            }
            binding = build_run_binding(
                root=root,
                extraction_report_path=extraction_path,
                extraction=extraction,
                clips=clips,
                config=dict(DEFAULT_CONFIG),
                max_folds=2,
                device=torch.device("cpu"),
                cpu_thread_control={
                    "requested": {
                        "torch_threads": None,
                        "torch_interop_threads": None,
                    },
                    "effective": {
                        "torch_threads": 8,
                        "torch_interop_threads": 4,
                    },
                    "explicitly_configured": False,
                },
            )
            repeated = build_run_binding(
                root=root,
                extraction_report_path=extraction_path,
                extraction=extraction,
                clips=clips,
                config=dict(DEFAULT_CONFIG),
                max_folds=2,
                device=torch.device("cpu"),
                cpu_thread_control=binding["binding"]["cpu_thread_control"],
            )
            self.assertEqual(binding, repeated)
            self.assertEqual([6, 18], binding["binding"]["fold_order"])
            self.assertEqual(
                binding["run_fingerprint"],
                canonical_json_sha256(binding["binding"]),
            )

            output = base / "output"
            binding_path = bind_output_directory(output, binding)
            self.assertEqual(binding_path, bind_output_directory(output, binding))
            changed_threads = build_run_binding(
                root=root,
                extraction_report_path=extraction_path,
                extraction=extraction,
                clips=clips,
                config=dict(DEFAULT_CONFIG),
                max_folds=2,
                device=torch.device("cpu"),
                cpu_thread_control={
                    "requested": {
                        "torch_threads": 5,
                        "torch_interop_threads": 2,
                    },
                    "effective": {
                        "torch_threads": 5,
                        "torch_interop_threads": 2,
                    },
                    "explicitly_configured": True,
                },
            )
            self.assertNotEqual(
                binding["run_fingerprint"], changed_threads["run_fingerprint"]
            )
            with self.assertRaisesRegex(ValueError, "different P2 run"):
                bind_output_directory(output, changed_threads)

            extraction_path.write_text('{"receipt":"changed"}\n', encoding="utf-8")
            changed = build_run_binding(
                root=root,
                extraction_report_path=extraction_path,
                extraction=extraction,
                clips=clips,
                config=dict(DEFAULT_CONFIG),
                max_folds=2,
                device=torch.device("cpu"),
                cpu_thread_control=binding["binding"]["cpu_thread_control"],
            )
            with self.assertRaisesRegex(ValueError, "different P2 run"):
                bind_output_directory(output, changed)

            progress = ProgressWriter(
                output / "progress.json", str(binding["run_fingerprint"])
            )
            progress.emit(
                "epoch_complete",
                fold=0,
                valid_subject=FOLD_SUBJECTS[0],
                variant="comparator",
                epoch=1,
                train_loss=1.0,
                train_accuracy=0.5,
                test_data_read=True,
                run_fingerprint="must-not-override-binding",
                sequence=999,
            )
            progress_payload = json.loads(
                (output / "progress.json").read_text(encoding="utf-8")
            )
            self.assertEqual("epoch_complete", progress_payload["event"])
            self.assertFalse(progress_payload["test_data_read"])
            self.assertEqual(
                binding["run_fingerprint"], progress_payload["run_fingerprint"]
            )
            self.assertEqual(1, progress_payload["sequence"])
            self.assertFalse((output / "progress.json.partial").exists())

            result = {
                "fold": 0,
                "valid_subject": 6,
                "subject_overlap": 0,
                "clip_overlap": 0,
                "accuracy_gain": 0.02,
            }
            receipt = output / "folds/fold_00_subject_06.json"
            save_fold_receipt(
                receipt,
                str(binding["run_fingerprint"]),
                0,
                6,
                SEED,
                result,
            )
            self.assertEqual(
                result,
                load_fold_receipt(
                    receipt,
                    str(binding["run_fingerprint"]),
                    0,
                    6,
                    SEED,
                ),
            )
            receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertFalse(receipt_payload["learned_weights_saved"])
            self.assertEqual([], list((output / "folds").glob("*.pt")))
            receipt_payload["result"]["accuracy_gain"] = 0.99
            receipt.write_text(json.dumps(receipt_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "receipt binding failed"):
                load_fold_receipt(
                    receipt,
                    str(binding["run_fingerprint"]),
                    0,
                    6,
                    SEED,
                )

    def test_cpu_thread_control_default_and_explicit(self) -> None:
        with (
            patch("train_p2_thermal_tsm.torch.set_num_threads") as set_threads,
            patch(
                "train_p2_thermal_tsm.torch.set_num_interop_threads"
            ) as set_interop,
            patch(
                "train_p2_thermal_tsm.torch.get_num_threads", return_value=7
            ),
            patch(
                "train_p2_thermal_tsm.torch.get_num_interop_threads",
                return_value=3,
            ),
        ):
            default = configure_cpu_threads(None, None)
            set_threads.assert_not_called()
            set_interop.assert_not_called()
            self.assertFalse(default["explicitly_configured"])
            self.assertEqual(
                {"torch_threads": 7, "torch_interop_threads": 3},
                default["effective"],
            )

            explicit = configure_cpu_threads(5, 2)
            set_interop.assert_called_once_with(2)
            set_threads.assert_called_once_with(5)
            self.assertTrue(explicit["explicitly_configured"])
            self.assertEqual(
                {"torch_threads": 5, "torch_interop_threads": 2},
                explicit["requested"],
            )

        with self.assertRaisesRegex(ValueError, "must be positive"):
            configure_cpu_threads(0, None)

    def test_sampling_padding_difference_channels_and_shift(self) -> None:
        self.assertEqual(
            [0, 0, 0, 1, 1, 2, 2, 2], midpoint_segment_indices(3, 8)
        )
        image = Image.fromarray(np.zeros((20, 40), dtype=np.uint8))
        self.assertEqual((32, 32), resize_center_pad(image, 32).size)

        model = ThermalMobileNetV3Small(
            use_tsm=True, use_frame_difference=True
        )
        frames = torch.tensor([[[[[0.25]]], [[[0.75]]]]])
        channels = model.input_channels(frames)
        self.assertEqual(0.50, float(channels[0, 1, 1, 0, 0]))
        self.assertEqual(0.00, float(channels[0, 1, 2, 0, 0]))

        values = torch.arange(1 * 3 * 8).view(3, 8, 1, 1).float()
        shifted = temporal_shift(values, batch_size=1, segments=3).view(1, 3, 8)
        self.assertEqual(8.0, float(shifted[0, 0, 0]))
        self.assertEqual(0.0, float(shifted[0, 2, 0]))
        self.assertEqual(0.0, float(shifted[0, 0, 1]))
        self.assertEqual(1.0, float(shifted[0, 1, 1]))


if __name__ == "__main__":
    unittest.main()
