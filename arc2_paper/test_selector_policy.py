#!/usr/bin/env python3
"""Regression test for the conservative checkpoint-agreement selector."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile


def write(path: pathlib.Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def fill_distinct_trm_rank2(
    selected: dict, nvarc: dict, final: dict
) -> int:
    fills = 0
    for task_id, rows in selected.items():
        for output_index, row in enumerate(rows):
            nrow = nvarc[task_id][output_index]
            trow = final[task_id][output_index]
            anchor = nrow["attempt_1"]
            if (
                nrow["attempt_2"] == anchor
                and trow["attempt_1"] == anchor
                and trow["attempt_2"] != anchor
            ):
                row["attempt_2"] = trow["attempt_2"]
                fills += 1
    return fills


def main() -> None:
    root = pathlib.Path(__file__).resolve().parent
    merger = root / "public_assets/trm_source/merge_agreement.py"
    challenge = {
        "agree": {"train": [], "test": [{"input": [[0]]}]},
        "disagree": {"train": [], "test": [{"input": [[0]]}]},
        "duplicate": {"train": [], "test": [{"input": [[0]]}]},
    }
    nvarc = {
        "agree": [{"attempt_1": [[1]], "attempt_2": [[2]]}],
        "disagree": [{"attempt_1": [[1]], "attempt_2": [[2]]}],
        "duplicate": [{"attempt_1": [[1]], "attempt_2": [[1]]}],
    }
    early = {
        "agree": [{"attempt_1": [[3]], "attempt_2": [[4]]}],
        "disagree": [{"attempt_1": [[3]], "attempt_2": [[4]]}],
        "duplicate": [{"attempt_1": [[1]], "attempt_2": [[4]]}],
    }
    final = {
        "agree": [{"attempt_1": [[3]], "attempt_2": [[4]]}],
        "disagree": [{"attempt_1": [[4]], "attempt_2": [[3]]}],
        "duplicate": [{"attempt_1": [[1]], "attempt_2": [[4]]}],
    }

    with tempfile.TemporaryDirectory(prefix="arc2-selector-test-") as raw:
        temp = pathlib.Path(raw)
        paths = {name: temp / f"{name}.json" for name in ("challenge", "nvarc", "early", "final")}
        for name, value in (
            ("challenge", challenge),
            ("nvarc", nvarc),
            ("early", early),
            ("final", final),
        ):
            write(paths[name], value)
        output = temp / "submission.json"
        receipt = temp / "receipt.json"
        subprocess.run(
            [
                sys.executable,
                str(merger),
                "--challenge",
                str(paths["challenge"]),
                "--proof",
                str(paths["nvarc"]),
                "--trm-early",
                str(paths["early"]),
                "--trm-final",
                str(paths["final"]),
                "--output",
                str(output),
                "--receipt",
                str(receipt),
                "--policy",
                "agreement",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        selected = json.loads(output.read_text(encoding="utf-8"))
        audit = json.loads(receipt.read_text(encoding="utf-8"))

    assert selected["agree"][0] == {"attempt_1": [[1]], "attempt_2": [[3]]}
    assert selected["disagree"][0] == {"attempt_1": [[1]], "attempt_2": [[2]]}
    assert selected["duplicate"][0] == {"attempt_1": [[1]], "attempt_2": [[0]]}
    assert audit["agreement_selected"] == 1
    assert audit["nvarc_second_retained"] == 1
    assert audit["duplicate_slot_filled_by_trm"] == 0
    assert audit["fallback_used"] == 1
    fills = fill_distinct_trm_rank2(selected, nvarc, final)
    assert fills == 1
    assert selected["duplicate"][0] == {"attempt_1": [[1]], "attempt_2": [[4]]}
    print("selector regression passed")


if __name__ == "__main__":
    main()
