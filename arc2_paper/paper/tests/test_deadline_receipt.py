#!/usr/bin/env python3
"""Consistency checks for the frozen public-official deadline receipt."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import date, datetime


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[2]
    receipt_path = root / "paper/results/official_arc_prize_deadline_recheck_2026-09-09.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    sources = receipt["sources"]
    assert sources["overview"]["url"] == "https://arcprize.org/competitions/2026"
    assert sources["arc_agi_2"]["url"] == "https://arcprize.org/competitions/2026/arc-agi-2"
    assert sources["paper"]["url"] == "https://arcprize.org/competitions/2026/paper"

    prior = receipt["prior_authenticated_kaggle_snapshot"]
    prior_path = root / prior["path"]
    assert prior_path.is_file()
    assert sha256(prior_path) == prior["sha256"]
    prior_payload = json.loads(prior_path.read_text(encoding="utf-8"))
    assert (
        prior_payload["competitions"]["arc-prize-2026-arc-agi-2"]["deadline_utc"]
        == prior["arc_agi_2_deadline_utc"]
    )
    assert (
        prior_payload["competitions"]["arc-prize-2026-paper-track"]["deadline_utc"]
        == prior["paper_track_deadline_utc"]
    )

    schedule = receipt["operational_schedule"]
    check_date = datetime.fromisoformat(receipt["checked_at_cst"]).date()
    competition_due = date.fromisoformat(
        sources["overview"]["observed_facts"]["competition_submissions_due_date"]
    )
    paper_due = date.fromisoformat(
        sources["overview"]["observed_facts"]["papers_due_date"]
    )
    assert date.fromisoformat(schedule["competition_submission_cutoff_date"]) == competition_due
    assert date.fromisoformat(schedule["paper_internal_cutoff_date"]) == paper_due
    assert schedule["days_remaining_at_check_date"] == (competition_due - check_date).days
    assert (competition_due - date.fromisoformat(schedule["d_minus_21_architecture_freeze"])).days == 21
    assert (
        competition_due
        - date.fromisoformat(schedule["d_minus_7_notebook_dependency_freeze"])
    ).days == 7
    assert (
        competition_due
        - date.fromisoformat(schedule["d_minus_3_validation_and_final_selection_only"])
    ).days == 3

    assert receipt["reconciliation"]["current_kaggle_status_or_deadline_rechecked"] is False
    assert "time or timezone" in receipt["claim_boundary"]
    print("deadline receipt consistency regression passed")


if __name__ == "__main__":
    main()
