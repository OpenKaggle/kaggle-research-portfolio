#!/usr/bin/env python3
"""Regression checks for the exact-file public release auditor."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(auditor: pathlib.Path, manifest: pathlib.Path, should_pass: bool) -> dict:
    completed = subprocess.run(
        [sys.executable, str(auditor), str(manifest)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert (completed.returncode == 0) is should_pass
    return json.loads(completed.stdout if should_pass else completed.stderr)


def main() -> None:
    paper = pathlib.Path(__file__).resolve().parents[1]
    auditor = paper / "tools/audit_release_manifest.py"
    with tempfile.TemporaryDirectory(prefix="arc2-release-audit-") as raw:
        root = pathlib.Path(raw)
        source = b"print('offline and clean')\n"
        (root / "clean.py").write_bytes(source)
        manifest = {
            "schema_version": 1,
            "status": "PRELIMINARY_NOT_FINAL",
            "project_root": ".",
            "files": [
                {
                    "path": "clean.py",
                    "bytes": len(source),
                    "sha256": digest(source),
                    "category": "source",
                    "license": "MIT-0"
                }
            ],
            "external_assets": []
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        valid = run(auditor, manifest_path, True)
        assert valid["passes"] is True
        assert valid["text_files_scanned"] == 1

        leak_dir = root / "kaggle_runs"
        leak_dir.mkdir()
        leaked = b"api_key = 'not-a-real-secret-value'\n"
        (leak_dir / "leak.py").write_bytes(leaked)
        manifest["files"][0] = {
            "path": "kaggle_runs/leak.py",
            "bytes": len(leaked),
            "sha256": digest(leaked),
            "category": "source",
            "license": "MIT-0"
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        invalid = run(auditor, manifest_path, False)
        codes = {item["code"] for item in invalid["violations"]}
        assert "forbidden_path_component" in codes
        assert "forbidden_content" in codes

        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [{"output_type": "stream", "name": "stdout", "text": ["x"]}],
                    "source": ["print('x')"]
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }
        notebook_bytes = json.dumps(notebook).encode()
        (root / "dirty.ipynb").write_bytes(notebook_bytes)
        manifest["files"][0] = {
            "path": "dirty.ipynb",
            "bytes": len(notebook_bytes),
            "sha256": digest(notebook_bytes),
            "category": "notebook",
            "license": "MIT-0"
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        dirty = run(auditor, manifest_path, False)
        dirty_codes = {item["code"] for item in dirty["violations"]}
        assert "notebook_execution_count" in dirty_codes
        assert "notebook_outputs_present" in dirty_codes

        (root / "clean.py").write_bytes(source)
        manifest["status"] = "FINAL_RELEASE_CANDIDATE"
        manifest["files"][0] = {
            "path": "clean.py",
            "bytes": len(source),
            "sha256": digest(source),
            "category": "source",
            "license": "internal pending grant"
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        incomplete_final = run(auditor, manifest_path, False)
        final_codes = {item["code"] for item in incomplete_final["violations"]}
        assert "unresolved_final_license" in final_codes
        assert "missing_final_category" in final_codes
        assert "missing_final_external_assets" in final_codes
        assert "missing_final_bindings" in final_codes

    print("release audit regression passed")


if __name__ == "__main__":
    main()
