#!/usr/bin/env python3
"""Reproduce the public Fususu 0.77777 prediction artifact, failing closed."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
from pathlib import Path


EXPECTED_NOTEBOOK_SHA256 = "38811edf7312f8c5ff5af73278568092de762a85885f22dce0fbb5af595fea15"
EXPECTED_RELEASE_MD5 = "8f997f262e7be646296442148dc8e64f"
EXPECTED_RELEASE_SHA256 = "4e3391e70d0c8ff5a40efb7c317468e8eda3f84e27b40ab3c35ea735352fda9c"
EXPECTED_ROWS = 682
EXPECTED_CLIPS = 208
LABELS = "ABCD"
SINGLE_CATEGORIES = {"single", "combination", "emotion", "object_interaction"}


def digest(path: Path, algorithm: str = "sha256") -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_literal(notebook: Path, name: str) -> str:
    document = json.loads(notebook.read_text(encoding="utf-8"))
    for cell in document.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        module = ast.parse("".join(cell.get("source", [])))
        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = ast.literal_eval(node.value)
                if not isinstance(value, str):
                    raise TypeError(f"{name} is not a string literal")
                return value
    raise KeyError(f"Could not find {name} in {notebook}")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def valid_prediction(value: str, category: str) -> bool:
    if not value or any(char not in LABELS for char in value):
        return False
    if len(set(value)) != len(value):
        return False
    if category in SINGLE_CATEGORIES:
        return len(value) == 1
    if category == "multi":
        return 1 <= len(value) <= 4 and value == "".join(sorted(value))
    if category == "sequence":
        return len(value) == 4 and set(value) == set(LABELS)
    return False


def clip_key(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[:-2])


def main() -> None:
    campaign_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--notebook",
        type=Path,
        default=campaign_root
        / "public_baselines/phuongncn_lb_0_77777/lb-0-77777-exact-submission-research-handoff.ipynb",
    )
    parser.add_argument(
        "--test", type=Path, default=campaign_root / "data/raw/kaggle/test_qa.csv"
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=campaign_root / "data/raw/kaggle/sample_submission.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=campaign_root / "candidates/public_fususu_077777.csv",
    )
    args = parser.parse_args()

    assert digest(args.notebook) == EXPECTED_NOTEBOOK_SHA256, "Public notebook hash changed"
    sample_columns, sample_rows = read_csv(args.sample)
    test_columns, test_rows = read_csv(args.test)
    assert sample_columns == ["qa_id", "prediction"], sample_columns
    assert len(sample_rows) == len(test_rows) == EXPECTED_ROWS
    assert [row["qa_id"] for row in sample_rows] == [row["qa_id"] for row in test_rows]
    assert len({clip_key(row["path"]) for row in test_rows}) == EXPECTED_CLIPS

    released_text = extract_literal(args.notebook, "RELEASED_PREDICTIONS_CSV")
    released_reader = csv.DictReader(io.StringIO(released_text))
    assert list(released_reader.fieldnames or []) == sample_columns
    released_rows = list(released_reader)
    assert len(released_rows) == EXPECTED_ROWS
    released_map = {row["qa_id"]: row["prediction"] for row in released_rows}
    assert len(released_map) == EXPECTED_ROWS

    test_ids = [row["qa_id"] for row in test_rows]
    assert set(released_map) == set(test_ids), "Released IDs differ from official test IDs"
    output_rows = [(row["qa_id"], released_map[row["qa_id"]]) for row in test_rows]
    assert all(
        valid_prediction(prediction, row["category"])
        for row, (_, prediction) in zip(test_rows, output_rows)
    ), "At least one prediction violates its category grammar"

    payload = "qa_id,prediction\n" + "".join(
        f"{qa_id},{prediction}\n" for qa_id, prediction in output_rows
    )
    payload_bytes = payload.encode("utf-8")
    assert hashlib.md5(payload_bytes).hexdigest() == EXPECTED_RELEASE_MD5
    assert hashlib.sha256(payload_bytes).hexdigest() == EXPECTED_RELEASE_SHA256

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload_bytes)
    print(f"wrote={args.output}")
    print(f"rows={len(output_rows)} clips={EXPECTED_CLIPS} grammar_valid={len(output_rows)}")
    print(f"md5={EXPECTED_RELEASE_MD5}")
    print(f"sha256={EXPECTED_RELEASE_SHA256}")


if __name__ == "__main__":
    main()

