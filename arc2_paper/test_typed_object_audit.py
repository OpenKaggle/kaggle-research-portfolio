#!/usr/bin/env python3
"""Synthetic evaluator-boundary checks for the one-shot typed-object audit."""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile

from run_typed_object_audit import detached_task, evaluate
from test_typed_object_correspondence import example


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    task = {
        "train": [
            example(6, 7, 1, 1),
            example(7, 6, 4, 3),
            example(8, 8, 2, 5),
        ],
        "test": [example(9, 7, 6, 1)],
    }
    challenge, targets = detached_task(task)
    assert targets == [[[2, 2], [2, 2]]]
    assert set(challenge["test"][0]) == {"input"}

    with tempfile.TemporaryDirectory(prefix="typed-object-audit-test-") as raw:
        root = pathlib.Path(raw)
        task_path = root / "1234abcd.json"
        task_path.write_text(json.dumps(task), encoding="utf-8")
        manifest = {
            "audit": {
                "task_ids": ["1234abcd"],
                "task_file_sha256": {"1234abcd": digest(task_path)},
            }
        }
        rows, traces, challenges = evaluate(manifest, root)
        assert len(rows) == 1
        assert rows[0]["selected"] is True
        assert rows[0]["correct"] is True
        assert traces["1234abcd"]["accepted"] is True
        assert set(challenges["1234abcd"]["test"][0]) == {"input"}

        manifest["audit"]["task_file_sha256"]["1234abcd"] = "0" * 64
        try:
            evaluate(manifest, root)
        except ValueError as error:
            assert "task hash mismatch" in str(error)
        else:
            raise AssertionError("audit accepted a task-file hash mismatch")

    print("typed-object audit boundary regression passed")


if __name__ == "__main__":
    main()
