#!/usr/bin/env python3
"""Recompute the local V3 dependency evidence without any network access."""

from __future__ import annotations

import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
RECEIPT_PATH = ROOT / "paper/results/v3_dependency_local_evidence_2026-09-09.json"


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class V3DependencyLocalEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))

    def test_source_identity_hashes(self) -> None:
        source = self.receipt["source_dataset"]
        root = ROOT / source["local_bundle"]
        for relative, expected in source["identity_files"].items():
            self.assertEqual(digest(root / relative), expected, relative)
        self.assertEqual(source["exact_kaggle_asset_public_access"], "UNKNOWN")
        self.assertEqual(source["exact_kaggle_asset_license"], "UNKNOWN")

    def test_bootstrap_metadata_identity_and_public_snapshot(self) -> None:
        expected = self.receipt["bootstrap_kernel"]["local_metadata"]
        path = ROOT / expected["path"]
        self.assertEqual(digest(path), expected["sha256"])
        metadata = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["id"], expected["id"])
        self.assertEqual(metadata["id_no"], expected["id_no"])
        self.assertIs(metadata["is_private"], False)

    def test_bootstrap_notebook_is_exact_and_clean(self) -> None:
        expected = self.receipt["bootstrap_kernel"]["local_notebook"]
        path = ROOT / expected["path"]
        self.assertEqual(digest(path), expected["sha256"])
        notebook = json.loads(path.read_text(encoding="utf-8"))
        code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        outputs = sum(len(cell.get("outputs", [])) for cell in code_cells)
        execution_counts = sum(cell.get("execution_count") is not None for cell in code_cells)
        self.assertEqual(len(code_cells), expected["code_cells"])
        self.assertEqual(outputs, expected["outputs"])
        self.assertEqual(execution_counts, expected["execution_counts"])

    def test_claim_boundary_remains_fail_closed(self) -> None:
        bootstrap = self.receipt["bootstrap_kernel"]
        self.assertEqual(bootstrap["exact_kaggle_asset_license"], "UNKNOWN")
        boundary = self.receipt["claim_boundary"].lower()
        for phrase in ("does not prove", "does not supply", "does not authorize"):
            self.assertIn(phrase, boundary)


if __name__ == "__main__":
    unittest.main()
