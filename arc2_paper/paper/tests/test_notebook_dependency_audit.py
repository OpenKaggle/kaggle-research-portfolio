#!/usr/bin/env python3
"""Regression checks for exact notebook dependency coverage and public binding."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tools.audit_notebook_dependencies import audit  # noqa: E402


def write_json(path: pathlib.Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def binding(path: pathlib.Path, root: pathlib.Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def codes(result: dict) -> set[str]:
    return {item["code"] for item in result["violations"]}


class NotebookDependencyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="arc2-notebook-deps-")
        self.root = pathlib.Path(self.temp.name)
        self.notebook = self.root / "candidate.ipynb"
        write_json(
            self.notebook,
            {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "outputs": [],
                        "source": ["print('clean')"],
                    }
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            },
        )
        self.metadata = self.root / "kernel-metadata.json"
        write_json(
            self.metadata,
            {
                "competition_sources": ["competition/arc"],
                "dataset_sources": ["owner/source"],
                "kernel_sources": ["owner/bootstrap"],
                "model_sources": ["owner/model/1"],
            },
        )
        self.preregistration = self.root / "preregistration.json"
        write_json(self.preregistration, {"status": "FROZEN"})
        self.receipt = self.root / "receipt.json"
        write_json(self.receipt, {"checked": True})
        receipt_binding = binding(self.receipt, self.root)
        self.manifest = {
            "schema_version": 1,
            "status": "READY",
            "project_root": ".",
            "artifacts": {
                "notebook": binding(self.notebook, self.root),
                "kernel_metadata": binding(self.metadata, self.root),
                "preregistration": binding(self.preregistration, self.root),
            },
            "dependencies": [
                {
                    "kind": "competition",
                    "ref": "competition/arc",
                    "status": "JOINED_COMPETITION_SOURCE",
                    "public": None,
                    "license": "Apache-2.0",
                    "receipt": receipt_binding,
                },
                {
                    "kind": "dataset",
                    "ref": "owner/source",
                    "status": "VERIFIED_PUBLIC",
                    "public": True,
                    "license": "MIT-0",
                    "receipt": receipt_binding,
                },
                {
                    "kind": "kernel",
                    "ref": "owner/bootstrap",
                    "status": "VERIFIED_PUBLIC",
                    "public": True,
                    "license": "Apache-2.0",
                    "receipt": receipt_binding,
                },
                {
                    "kind": "model",
                    "ref": "owner/model/1",
                    "status": "VERIFIED_PUBLIC",
                    "public": True,
                    "license": "Apache-2.0",
                    "receipt": receipt_binding,
                },
            ],
        }
        self.manifest_path = self.root / "manifest.json"
        write_json(self.manifest_path, self.manifest)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_complete_inventory_passes(self) -> None:
        result = audit(self.manifest_path)
        self.assertTrue(result["passes"])
        self.assertEqual(result["unresolved_dependencies"], [])

    def test_undeclared_metadata_source_fails(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["dependencies"] = [
            item for item in changed["dependencies"] if item["kind"] != "kernel"
        ]
        write_json(self.manifest_path, changed)
        self.assertIn("metadata_dependency_mismatch", codes(audit(self.manifest_path)))

    def test_unverified_dependency_fails(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["status"] = "BLOCKED_UNVERIFIED_DEPENDENCIES"
        changed["dependencies"][1] = {
            "kind": "dataset",
            "ref": "owner/source",
            "status": "UNVERIFIED",
            "public": None,
            "license": None,
            "receipt": None,
            "local_evidence": binding(self.receipt, self.root),
        }
        write_json(self.manifest_path, changed)
        self.assertIn("dependency_not_verified", codes(audit(self.manifest_path)))

    def test_private_dependency_fails(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["dependencies"][1]["public"] = False
        write_json(self.manifest_path, changed)
        self.assertIn("dependency_not_public", codes(audit(self.manifest_path)))

    def test_hash_drift_fails(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed["artifacts"]["notebook"]["sha256"] = "0" * 64
        write_json(self.manifest_path, changed)
        self.assertIn("artifact_hash_mismatch", codes(audit(self.manifest_path)))

    def test_dirty_notebook_fails(self) -> None:
        dirty = json.loads(self.notebook.read_text(encoding="utf-8"))
        dirty["cells"][0]["execution_count"] = 1
        dirty["cells"][0]["outputs"] = [{"output_type": "stream", "text": ["x"]}]
        write_json(self.notebook, dirty)
        changed = copy.deepcopy(self.manifest)
        changed["artifacts"]["notebook"] = binding(self.notebook, self.root)
        write_json(self.manifest_path, changed)
        result_codes = codes(audit(self.manifest_path))
        self.assertIn("notebook_execution_count", result_codes)
        self.assertIn("notebook_outputs_present", result_codes)


if __name__ == "__main__":
    unittest.main()
