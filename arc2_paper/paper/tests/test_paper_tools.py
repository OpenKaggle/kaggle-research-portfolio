#!/usr/bin/env python3
"""Regression checks for paper-side manifests, receipts, and statistics."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def run_fails(*args: str) -> None:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    assert result.returncode != 0


def main() -> None:
    paper = pathlib.Path(__file__).resolve().parents[1]
    manifest = json.loads((paper / "manifests/grouped_folds_v1.json").read_text(encoding="utf-8"))
    assert manifest["fold_count"] == 5
    assert manifest["dataset"]["tasks"] == 1000
    assigned = [task_id for fold in manifest["folds"] for task_id in fold["task_ids"]]
    assert len(assigned) == len(set(assigned)) == 1000
    task_to_fold = {
        task_id: fold["fold"] for fold in manifest["folds"] for task_id in fold["task_ids"]
    }
    for group in manifest["groups"]:
        assert len({task_to_fold[task_id] for task_id in group["task_ids"]}) == 1

    receipt_output = run(
        sys.executable,
        str(paper / "tools/validate_candidate_receipts.py"),
        str(paper / "tests/fixtures/candidate_receipts_valid.jsonl"),
    )
    receipt_summary = json.loads(receipt_output)
    assert receipt_summary["receipts"] == 1
    assert receipt_summary["unique_grids"] == 1

    failure_output = run(
        sys.executable,
        str(paper / "tools/validate_failure_log.py"),
        str(paper / "tests/fixtures/failure_log_valid.csv"),
    )
    failure_summary = json.loads(failure_output)
    assert failure_summary["rows"] == 1
    assert failure_summary["primary_counts"] == {"F09": 1}

    with tempfile.TemporaryDirectory(prefix="arc2-paper-test-") as raw:
        temporary = pathlib.Path(raw)
        valid_receipt = json.loads(
            (paper / "tests/fixtures/candidate_receipts_valid.jsonl").read_text(encoding="utf-8")
        )
        invalid_nested = dict(valid_receipt)
        invalid_nested["generation"] = {**valid_receipt["generation"], "unexpected": 1}
        invalid_nested_path = temporary / "invalid-nested.jsonl"
        invalid_nested_path.write_text(json.dumps(invalid_nested) + "\n", encoding="utf-8")
        run_fails(
            sys.executable,
            str(paper / "tools/validate_candidate_receipts.py"),
            str(invalid_nested_path),
        )

        invalid_evidence = dict(valid_receipt)
        invalid_evidence["evidence"] = {"heldout_output_probability": 0.9}
        invalid_evidence_path = temporary / "invalid-evidence.jsonl"
        invalid_evidence_path.write_text(json.dumps(invalid_evidence) + "\n", encoding="utf-8")
        run_fails(
            sys.executable,
            str(paper / "tools/validate_candidate_receipts.py"),
            str(invalid_evidence_path),
        )

        invalid_failure_path = temporary / "invalid-failure.csv"
        invalid_failure_path.write_text(
            (paper / "tests/fixtures/failure_log_valid.csv")
            .read_text(encoding="utf-8")
            .replace(",0,1,0,F09,", ",1,1,0,F09,"),
            encoding="utf-8",
        )
        run_fails(
            sys.executable,
            str(paper / "tools/validate_failure_log.py"),
            str(invalid_failure_path),
        )

        output = pathlib.Path(raw) / "paired.json"
        paired_output = run(
            sys.executable,
            str(paper / "tools/analyze_paired_results.py"),
            str(paper / "tests/fixtures/paired_results_small.csv"),
            "--bootstrap-replicates",
            "1000",
            "--output",
            str(output),
        )
        paired = json.loads(paired_output)
        assert paired["tasks"] == 4
        assert paired["beneficial_outputs"] == 1
        assert paired["harmful_outputs"] == 1
        assert paired["delta_pass2"] == 0.0
        assert paired["anchor_attempt2_incremental_rate"] == 0.25
        assert paired["method_attempt2_incremental_rate"] == 0.25
        assert paired["oracle_pool_rate"] == 0.75
        assert paired["oracle_gain_over_anchor"] == 0.25
        assert paired["selector_regret_to_oracle"] == 0.25
        assert paired["oracle_gap_recovery"] == 0.0
        assert output.is_file()

        invalid_oracle_path = temporary / "paired-invalid-oracle.csv"
        invalid_oracle_path.write_text(
            (paper / "tests/fixtures/paired_results_small.csv")
            .read_text(encoding="utf-8")
            .replace("0a1b2c3d,0,1,0,1,0,1", "0a1b2c3d,0,1,0,1,0,0", 1),
            encoding="utf-8",
        )
        run_fails(
            sys.executable,
            str(paper / "tools/analyze_paired_results.py"),
            str(invalid_oracle_path),
            "--bootstrap-replicates",
            "1000",
        )

        family_output = run(
            sys.executable,
            str(paper / "tools/analyze_family_coverage.py"),
            str(paper / "tests/fixtures/family_results_small.csv"),
        )
        family = json.loads(family_output)
        assert family["tasks"] == 4
        assert family["task_outputs"] == 4
        assert family["oracle_union_outputs"] == 3
        assert family["oracle_union_rate"] == 0.75
        by_family = {row["family"]: row for row in family["families"]}
        assert by_family["neural"]["exclusive_exact_outputs"] == 1
        assert by_family["program"]["exclusive_exact_outputs"] == 1
        assert by_family["trm"]["exclusive_exact_outputs"] == 0
        program_trm = next(
            row
            for row in family["pairwise_overlap"]
            if row["family_a"] == "program" and row["family_b"] == "trm"
        )
        assert program_trm["both_exact"] == 1
        assert program_trm["jaccard_exact"] == 0.5

        incomplete_family_path = temporary / "family-incomplete.csv"
        incomplete_family_path.write_text(
            (paper / "tests/fixtures/family_results_small.csv")
            .read_text(encoding="utf-8")
            .replace("3a4b5c6d,0,trm,0\n", ""),
            encoding="utf-8",
        )
        run_fails(
            sys.executable,
            str(paper / "tools/analyze_family_coverage.py"),
            str(incomplete_family_path),
        )

        arc_root = paper.parent
        audit_json = temporary / "revision-audit.json"
        audit_csv = temporary / "revision-tasks.csv"
        audit_eval = temporary / "evaluator-only"
        audit_result = subprocess.run(
            [
                sys.executable,
                "paper/tools/audit_dataset_revision.py",
                "--competition-dir",
                "official/competition_files",
                "--github-data-dir",
                "official/ARC-AGI-2/data",
                "--output-json",
                str(audit_json),
                "--output-csv",
                str(audit_csv),
                "--materialize-evaluation",
                str(audit_eval),
            ],
            cwd=arc_root,
            check=True,
            capture_output=True,
            text=True,
        )
        audit = json.loads(audit_result.stdout)
        assert audit["splits"]["training"]["status_counts"] == {"exact": 1000}
        assert audit["splits"]["evaluation"]["kaggle_outputs"] == 172
        assert audit["materialized_evaluation"]["tasks"] == 120
        assert audit_json.is_file() and audit_csv.is_file()
    print("paper tool regression passed")


if __name__ == "__main__":
    main()
