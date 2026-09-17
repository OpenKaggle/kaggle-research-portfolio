#!/usr/bin/env python3
"""Regression checks for the Writeup evidence and final-binding auditor."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile


def run(auditor: pathlib.Path, contract: pathlib.Path, should_pass: bool) -> dict:
    completed = subprocess.run(
        [sys.executable, str(auditor), str(contract)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert (completed.returncode == 0) is should_pass
    return json.loads(completed.stdout if should_pass else completed.stderr)


def main() -> None:
    paper = pathlib.Path(__file__).resolve().parents[1]
    auditor = paper / "tools/audit_writeup.py"
    with tempfile.TemporaryDirectory(prefix="arc2-writeup-audit-") as raw:
        root = pathlib.Path(raw)
        text = """# Title

## Abstract
[PENDING result]

## Introduction
Intro.

## Prior work
Prior.

## Approach
Approach.

## Results
Measured claim. [Source](https://example.com/source)

## Conclusion
Conclusion.
"""
        writeup = root / "writeup.md"
        writeup.write_text(text, encoding="utf-8")
        registry = root / "registry.md"
        registry.write_text("| ID | Fact |\n| --- | --- |\n| A1 | fact |\n", encoding="utf-8")
        dimensions = {
            name: {"status": "partial", "evidence_ids": ["A1"], "gap": "test"}
            for name in ("Accuracy", "Universality", "Progress", "Theory", "Completeness", "Novelty")
        }
        contract = {
            "schema_version": 1,
            "status": "DRAFT",
            "project_root": ".",
            "writeup_path": "writeup.md",
            "writeup_bytes": len(text.encode()),
            "writeup_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "maximum_words": 1500,
            "local_safety_target_words": 1450,
            "evidence_registry_path": "registry.md",
            "required_sections": [
                {"name": name, "heading_patterns": [f"^{pattern}$"]}
                for name, pattern in (
                    ("Abstract", "abstract"),
                    ("Introduction", "introduction"),
                    ("Prior Work", "prior work"),
                    ("Approach", "approach"),
                    ("Results", "results"),
                    ("Conclusion", "conclusion")
                )
            ],
            "rubric_dimensions": dimensions,
            "required_claim_bindings": [
                {"claim_id": "c1", "text_contains": "Measured claim", "evidence_ids": ["A1"]}
            ],
            "platform_word_count": None,
            "final_bindings": {}
        }
        contract_path = root / "contract.json"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        draft = run(auditor, contract_path, True)
        assert draft["passes"] is True
        assert draft["final_ready"] is False
        assert draft["placeholders"] == 1
        assert draft["training_performance_mentions"] == 0

        training_text = text.replace(
            "Measured claim.",
            "Measured claim. Development accuracy was 48/50.",
        )
        writeup.write_text(training_text, encoding="utf-8")
        contract["writeup_bytes"] = len(training_text.encode())
        contract["writeup_sha256"] = hashlib.sha256(training_text.encode()).hexdigest()
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        training_result = run(auditor, contract_path, False)
        assert "train_performance_reported" in {
            item["code"] for item in training_result["violations"]
        }

        writeup.write_text(text, encoding="utf-8")
        contract["writeup_bytes"] = len(text.encode())
        contract["writeup_sha256"] = hashlib.sha256(text.encode()).hexdigest()

        contract["status"] = "FINAL_SUBMISSION_READY"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        final = run(auditor, contract_path, False)
        codes = {item["code"] for item in final["violations"]}
        assert "final_placeholders_present" in codes
        assert "unsupported_final_dimensions" in codes
        assert "missing_platform_word_count" in codes
        assert "incomplete_final_bindings" in codes

    print("writeup audit regression passed")


if __name__ == "__main__":
    main()
