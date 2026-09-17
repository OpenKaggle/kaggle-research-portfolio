#!/usr/bin/env python3
"""Fail-closed consistency checks for the preregistered ARC failure log."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


REQUIRED_COLUMNS = {
    "experiment_id",
    "task_id",
    "output_index",
    "anchor_pass2",
    "portfolio_oracle_pass2",
    "selected_pass2",
    "primary_failure_code",
    "secondary_tags",
    "correct_candidate_id",
    "selected_attempt1_id",
    "selected_attempt2_id",
    "gate_action",
    "evidence_snapshot_hash",
    "reviewer",
    "review_date",
    "notes",
}
FAILURE_CODES = {f"F{value:02d}" for value in range(13)} | {"F14"}
ORACLE_FAILURE_CODES = {"F03", "F04", "F05", "F06", "F07"}
SELECTOR_FAILURE_CODES = {"F08", "F09", "F10", "F11", "F12"}
GATE_ACTIONS = {"accept", "reject", "not_applicable"}
SECONDARY_TAGS = {
    "size_same", "size_crop", "size_expand", "multi_test",
    "color_role", "literal_color", "palette_mapping",
    "component", "hole", "line_ray", "symmetry_d4", "count", "panel",
    "gravity", "occlusion", "boundary_clip", "recursive_relation",
    "neural_only", "trm_only", "program_only", "cross_family_agreement",
    "loo_fail", "contract_fail", "ood_evidence", "low_confidence",
    "train_eval_coverage_collapse", "retrospective_rule", "support_abstention",
    "beneficial_override", "harmful_override", "neutral_override",
    "anchor_retained", "gate_accept", "gate_reject", "gate_not_applicable",
}


def bit(value: str, context: str) -> int:
    if value not in {"0", "1"}:
        raise ValueError(f"{context}: expected 0 or 1")
    return int(value)


def valid_task_id(value: str) -> bool:
    return len(value) == 8 and all(character in "0123456789abcdef" for character in value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("failure_csv", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    with args.failure_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_COLUMNS:
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
            extra = set(reader.fieldnames or []) - REQUIRED_COLUMNS
            raise ValueError(f"failure-log columns differ: missing={sorted(missing)} extra={sorted(extra)}")
        rows = []
        seen = set()
        for line_number, row in enumerate(reader, 2):
            context = f"line {line_number}"
            if not row["experiment_id"]:
                raise ValueError(f"{context}: experiment_id is required")
            if not valid_task_id(row["task_id"]):
                raise ValueError(f"{context}: task_id must be eight lowercase hex characters")
            try:
                output_index = int(row["output_index"])
            except ValueError as error:
                raise ValueError(f"{context}: output_index must be a nonnegative integer") from error
            if str(output_index) != row["output_index"] or output_index < 0:
                raise ValueError(f"{context}: output_index must be a nonnegative integer")
            key = (row["experiment_id"], row["task_id"], output_index)
            if key in seen:
                raise ValueError(f"{context}: duplicate experiment/task/output")
            seen.add(key)

            code = row["primary_failure_code"]
            if code not in FAILURE_CODES:
                raise ValueError(f"{context}: unknown primary failure code {code!r}")
            anchor = bit(row["anchor_pass2"], context)
            oracle = bit(row["portfolio_oracle_pass2"], context)
            selected = bit(row["selected_pass2"], context)
            if selected and not oracle:
                raise ValueError(f"{context}: selected success cannot exceed portfolio oracle")
            if code in ORACLE_FAILURE_CODES and oracle != 0:
                raise ValueError(f"{context}: {code} requires portfolio_oracle_pass2=0")
            if code in SELECTOR_FAILURE_CODES and (oracle != 1 or selected != 0):
                raise ValueError(f"{context}: {code} requires oracle=1 and selected=0")
            if code == "F08" and anchor != 1:
                raise ValueError(f"{context}: gate false accept requires anchor_pass2=1")
            if code == "F09" and anchor != 0:
                raise ValueError(f"{context}: gate false reject requires anchor_pass2=0")

            gate_action = row["gate_action"]
            if gate_action not in GATE_ACTIONS:
                raise ValueError(f"{context}: unknown gate_action {gate_action!r}")
            if code == "F08" and gate_action != "accept":
                raise ValueError(f"{context}: F08 requires gate_action=accept")
            if code == "F09" and gate_action != "reject":
                raise ValueError(f"{context}: F09 requires gate_action=reject")
            if oracle and not selected and not row["correct_candidate_id"]:
                raise ValueError(f"{context}: selector failure requires correct_candidate_id")
            if not row["selected_attempt1_id"] or not row["selected_attempt2_id"]:
                raise ValueError(f"{context}: both selected attempt IDs are required")

            tags = {tag for tag in row["secondary_tags"].split(";") if tag}
            unknown_tags = tags - SECONDARY_TAGS
            if unknown_tags:
                raise ValueError(f"{context}: unknown secondary tags {sorted(unknown_tags)}")
            evidence_hash = row["evidence_snapshot_hash"]
            if len(evidence_hash) != 64 or any(character not in "0123456789abcdef" for character in evidence_hash):
                raise ValueError(f"{context}: evidence_snapshot_hash must be lowercase SHA-256")
            if not row["reviewer"] or not row["review_date"]:
                raise ValueError(f"{context}: reviewer and review_date are required")
            rows.append(row)

    summary = {
        "rows": len(rows),
        "experiments": len({row["experiment_id"] for row in rows}),
        "primary_counts": {
            code: sum(row["primary_failure_code"] == code for row in rows)
            for code in sorted({row["primary_failure_code"] for row in rows})
        },
        "source_sha256": hashlib.sha256(args.failure_csv.read_bytes()).hexdigest(),
    }
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
