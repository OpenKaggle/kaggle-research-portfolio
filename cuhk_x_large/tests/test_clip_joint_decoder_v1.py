#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_clip_joint_decoder_v1.py"
SPEC = importlib.util.spec_from_file_location("clip_joint_decoder_v1", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ClipJointDecoderV1Test(unittest.TestCase):
    def test_atoms_are_normalized_and_deduplicated(self) -> None:
        self.assertEqual(MODULE.atoms(" Stirring, pouring,  Stirring "), {"stirring", "pouring"})

    def test_option_permutation_is_semantically_invertible(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "qa_id": "q1",
                    "source": "HAU",
                    "path": "HAU/user1/clip",
                    "category": "single",
                    "question": "q",
                    "A": "one",
                    "B": "two",
                    "C": "three",
                    "D": "four",
                    "answer": "B",
                    "parent_prediction": "C",
                    "joint_prediction": "B",
                },
                {
                    "qa_id": "q2",
                    "source": "HAU",
                    "path": "HAU/user1/clip",
                    "category": "sequence",
                    "question": "q",
                    "A": "one",
                    "B": "two",
                    "C": "three",
                    "D": "four",
                    "answer": "BDAC",
                    "parent_prediction": "ACDB",
                    "joint_prediction": "BDAC",
                },
            ]
        )
        permuted, inverse = MODULE.permute_options(frame)
        permuted["joint_prediction"] = permuted["answer"]
        restored = MODULE.invert_predictions(permuted, inverse)
        self.assertEqual(restored.tolist(), frame["answer"].tolist())

    def test_selector_uses_only_named_fit_subjects(self) -> None:
        proposals = pd.DataFrame(
            [
                {
                    "qa_id": f"q{i}",
                    "user": user,
                    "signature": "atoms=2|sequence=no",
                    "proposal": "A",
                    "parent_prediction": "B",
                    "answer": answer,
                }
                for i, (user, answer) in enumerate(
                    [(1, "A"), (2, "A"), (3, "A"), (4, "A"), (5, "A"), (6, "B")]
                )
            ]
        )
        without_six = MODULE.fit_signatures(proposals, [1, 2, 3, 4, 5]).iloc[0]
        without_one = MODULE.fit_signatures(proposals, [2, 3, 4, 5, 6]).iloc[0]
        self.assertEqual(int(without_six["proposal_correct"]), 5)
        self.assertEqual(int(without_one["proposal_correct"]), 4)
        self.assertEqual(int(without_one["parent_correct"]), 1)


if __name__ == "__main__":
    unittest.main()
