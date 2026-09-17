#!/usr/bin/env python3

from __future__ import annotations

import json
import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "public_assets/trm_source"))
from blindspot_exact_overlay import (  # noqa: E402
    RULES,
    apply_overlay,
    matching_predictions,
    reconstruct_centered_square_perimeters,
    reconstruct_centered_square_perimeters_with_trace,
    scale_by_distinct_color_count,
    unique_prediction,
)


class DevelopmentBlindspotTests(unittest.TestCase):
    def load_task(self, task_id: str) -> dict:
        path = ROOT / "evaluator_only/development_stable_v2/tasks" / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_palette_count_scale_on_every_pair(self) -> None:
        task = self.load_task("d4b1c2b1")
        for pair in task["train"] + task["test"]:
            self.assertEqual(scale_by_distinct_color_count(pair["input"]), pair["output"])

    def test_palette_count_synthetic_counterexample(self) -> None:
        self.assertEqual(
            scale_by_distinct_color_count([[1, 2]]),
            [[1, 1, 2, 2], [1, 1, 2, 2]],
        )
        self.assertEqual(scale_by_distinct_color_count([[1, 1]]), [[1, 1]])

    @staticmethod
    def mirror(grid: list[list[int]]) -> list[list[int]]:
        return [row[::-1] for row in grid]

    @classmethod
    def dihedral_transforms(cls, grid: list[list[int]]) -> list[list[list[int]]]:
        rotations = [grid]
        for _ in range(3):
            rotations.append(cls.rotate90(rotations[-1]))
        return rotations + [cls.mirror(value) for value in rotations]

    def test_palette_count_dihedral_and_color_equivariance(self) -> None:
        task = self.load_task("d4b1c2b1")
        for pair in task["train"] + task["test"]:
            for transformed_input, transformed_output in zip(
                self.dihedral_transforms(pair["input"]),
                self.dihedral_transforms(pair["output"]),
                strict=True,
            ):
                self.assertEqual(
                    scale_by_distinct_color_count(transformed_input), transformed_output
                )
            self.assertEqual(
                scale_by_distinct_color_count(self.permute_colors(pair["input"])),
                self.permute_colors(pair["output"]),
            )

    def test_palette_count_dimension_guard(self) -> None:
        at_limit = [[(row + column) % 3 for column in range(10)] for row in range(10)]
        prediction = scale_by_distinct_color_count(at_limit)
        self.assertEqual((len(prediction), len(prediction[0])), (30, 30))
        above_limit = [[(row + column) % 4 for column in range(8)] for row in range(8)]
        self.assertIsNone(scale_by_distinct_color_count(above_limit))

    def test_square_perimeter_reconstruction_on_every_pair(self) -> None:
        task = self.load_task("4290ef0e")
        for pair in task["train"] + task["test"]:
            self.assertEqual(reconstruct_centered_square_perimeters(pair["input"]), pair["output"])

    def test_same_color_singleton_component_is_not_center(self) -> None:
        task = self.load_task("4290ef0e")
        prediction, trace = reconstruct_centered_square_perimeters_with_trace(task["test"][0]["input"])
        self.assertEqual(prediction, task["test"][0]["output"])
        self.assertIsNone(trace["center_color"])
        self.assertEqual(trace["assignments"]["6"]["radius"], 3)
        self.assertEqual(trace["assignments"]["4"]["radius"], 5)

    @staticmethod
    def rotate90(grid: list[list[int]]) -> list[list[int]]:
        return [list(row) for row in zip(*grid[::-1])]

    @staticmethod
    def permute_colors(grid: list[list[int]]) -> list[list[int]]:
        return [[(3 * value + 1) % 10 for value in row] for row in grid]

    def test_square_perimeter_dihedral_and_color_equivariance(self) -> None:
        task = self.load_task("4290ef0e")
        for pair in task["train"] + task["test"]:
            for transformed_input, transformed_output in zip(
                self.dihedral_transforms(pair["input"]),
                self.dihedral_transforms(pair["output"]),
                strict=True,
            ):
                self.assertEqual(
                    reconstruct_centered_square_perimeters(transformed_input),
                    transformed_output,
                )
            self.assertEqual(
                reconstruct_centered_square_perimeters(self.permute_colors(pair["input"])),
                self.permute_colors(pair["output"]),
            )

    def test_square_perimeter_rejects_non_unique_semantics(self) -> None:
        prediction, trace = reconstruct_centered_square_perimeters_with_trace(
            [[0, 1], [1, 0]]
        )
        self.assertIsNone(prediction)
        self.assertEqual(trace["rejected"], "background_not_strict_mode")

        prediction, trace = reconstruct_centered_square_perimeters_with_trace(
            [[0, 0, 0], [0, 1, 0], [0, 0, 2]]
        )
        self.assertIsNone(prediction)
        self.assertEqual(trace["rejected"], "multiple_global_singletons")

    def test_square_perimeter_abstains_when_padding_removes_assignment_clue(self) -> None:
        pair = self.load_task("4290ef0e")["test"][0]
        background = 1
        width = len(pair["input"][0]) + 10
        padded = [[background] * width for _ in range(5)]
        padded += [[background] * 5 + row + [background] * 5 for row in pair["input"]]
        padded += [[background] * width for _ in range(5)]
        prediction, trace = reconstruct_centered_square_perimeters_with_trace(padded)
        self.assertIsNone(prediction)
        self.assertEqual(trace["rejected"], "ambiguous_minimum_penalty_completion")

    def test_matching_requires_every_demonstration_and_unique_rule_output(self) -> None:
        task = self.load_task("d4b1c2b1")
        perturbed = copy.deepcopy(task)
        original = perturbed["train"][0]["output"][0][0]
        perturbed["train"][0]["output"][0][0] = (original + 1) % 10
        self.assertEqual(
            matching_predictions(
                perturbed,
                perturbed["test"][0]["input"],
                ("scale_by_distinct_color_count",),
            ),
            {},
        )
        agreed, reasons = unique_prediction({"a": [[1]], "b": [[1]]})
        self.assertEqual(agreed, [[1]])
        self.assertEqual(reasons, ["a", "b"])
        ambiguous, reasons = unique_prediction({"a": [[1]], "b": [[2]]})
        self.assertIsNone(ambiguous)
        self.assertEqual(reasons, [])

    def test_official_challenges_have_at_least_two_demonstrations(self) -> None:
        for name in ("training", "evaluation", "test"):
            challenges = json.loads(
                (
                    ROOT
                    / "official/competition_files"
                    / f"arc-agi_{name}_challenges.json"
                ).read_text(encoding="utf-8")
            )
            self.assertGreaterEqual(min(len(task["train"]) for task in challenges.values()), 2)

    def test_overlay_changes_only_the_two_blindspots(self) -> None:
        challenges = json.loads(
            (ROOT / "kaggle_runs/development_stable_v2/benchmark_challenges.json").read_text(
                encoding="utf-8"
            )
        )
        base = json.loads(
            (ROOT / "kaggle_runs/development_stable_v2/nvarc_kgmon.json").read_text(
                encoding="utf-8"
            )
        )
        submission, receipt = apply_overlay(challenges, base, tuple(RULES))
        self.assertEqual(receipt["changed_attempt_2_outputs"], 2)
        changed = {
            row["task_id"]
            for row in receipt["rows"]
            if row["decision"] == "unique_exact_rule_replaces_attempt_2"
        }
        self.assertEqual(changed, {"d4b1c2b1", "4290ef0e"})
        for task_id, rows in base.items():
            for output_index, row in enumerate(rows):
                self.assertEqual(
                    submission[task_id][output_index]["attempt_1"], row["attempt_1"]
                )
                if task_id not in changed:
                    self.assertEqual(submission[task_id][output_index], row)


if __name__ == "__main__":
    unittest.main()
