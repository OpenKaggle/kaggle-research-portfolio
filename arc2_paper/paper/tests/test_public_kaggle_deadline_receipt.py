#!/usr/bin/env python3
"""Consistency checks for the public Kaggle deadline reconciliation receipt."""

from __future__ import annotations

import hashlib
import json
import pathlib


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[2]
    receipt_path = (
        root
        / "paper/results/public_kaggle_deadline_recheck_2026-09-09T184121+0800.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    paper = receipt["sources"]["paper_track"]
    arc = receipt["sources"]["arc_agi_2"]
    assert paper["url"].startswith(
        "https://www.kaggle.com/competitions/arc-prize-2026-paper-track/"
    )
    assert paper["observed_facts"]["final_submission_deadline_utc"] == (
        "2026-11-09T23:59:00Z"
    )
    assert arc["observed_facts"]["entry_deadline_utc"] == "2026-10-26T23:59:00Z"
    assert arc["observed_facts"]["team_merger_deadline_utc"] == (
        "2026-10-26T23:59:00Z"
    )
    assert arc["observed_facts"]["final_submission_deadline_utc"] == (
        "2026-11-02T23:59:00Z"
    )

    prior_public = receipt["prior_public_arc_prize_receipt"]
    prior_public_path = root / prior_public["path"]
    assert sha256(prior_public_path) == prior_public["sha256"]
    prior_public_payload = json.loads(prior_public_path.read_text(encoding="utf-8"))
    assert (
        prior_public_payload["sources"]["overview"]["observed_facts"][
            "papers_due_date"
        ]
        == prior_public["paper_due_date"]
    )

    prior_auth = receipt["prior_authenticated_kaggle_snapshot"]
    prior_auth_path = root / prior_auth["path"]
    assert sha256(prior_auth_path) == prior_auth["sha256"]
    prior_auth_payload = json.loads(prior_auth_path.read_text(encoding="utf-8"))
    assert (
        prior_auth_payload["competitions"]["arc-prize-2026-paper-track"][
            "deadline_utc"
        ]
        == prior_auth["paper_track_deadline_utc"]
        == paper["observed_facts"]["final_submission_deadline_utc"]
    )
    assert (
        prior_auth_payload["competitions"]["arc-prize-2026-arc-agi-2"][
            "deadline_utc"
        ]
        == prior_auth["arc_agi_2_deadline_utc"]
        == arc["observed_facts"]["final_submission_deadline_utc"]
    )

    reconciliation = receipt["reconciliation"]
    assert reconciliation["public_kaggle_matches_prior_authenticated_snapshot"] is True
    assert reconciliation["controlling_submission_surface_deadline_utc"] == (
        "2026-11-09T23:59:00Z"
    )
    assert reconciliation["conservative_internal_paper_cutoff_utc"] == (
        "2026-11-08T23:59:00Z"
    )

    boundary = receipt["authorization_boundary"]
    assert not any(boundary.values())
    assert "publicly indexed" in receipt["claim_boundary"]
    print("public Kaggle deadline receipt consistency regression passed")


if __name__ == "__main__":
    main()
