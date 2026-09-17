#!/usr/bin/env python3
"""Atomic one-stage authorization and fail-closed transition regressions."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    AUTH_ACTIONS,
    binding,
    build_complete_contract,
    write_json,
)
from paper.tools.audit_three_stage_pipeline import audit  # noqa: E402
from paper.tools.authorize_stage import authorize_stage  # noqa: E402


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def prepare(
    root: pathlib.Path,
    complete: dict,
    stage: str,
    competition_notebook: pathlib.Path | None = None,
) -> tuple[pathlib.Path, dict]:
    contract = copy.deepcopy(complete)
    contract["status"] = "ACTIVE_NOT_COMPLETE"
    order = ("private_development", "sealed_holdout", "competition_rerun")
    index = order.index(stage)
    for earlier in order[:index]:
        contract["stages"][earlier]["state"] = "COMPLETE"
    target = contract["stages"][stage]
    target["state"] = (
        "PENDING_PREREQUISITE" if stage == "private_development" else "NOT_AUTHORIZED"
    )
    target["receipt"] = None
    target["authorization"] = None
    if stage == "competition_rerun":
        target["notebook"] = None
        assert competition_notebook is not None
    for later in order[index + 1 :]:
        contract["stages"][later]["state"] = "NOT_AUTHORIZED"
        contract["stages"][later]["receipt"] = None
        contract["stages"][later]["authorization"] = None
    contract_path = root / "contract.json"
    write_json(contract_path, contract)
    assert audit(contract_path)["passes"] is True
    return contract_path, contract


def authorization_receipt(
    root: pathlib.Path,
    contract_path: pathlib.Path,
    contract: dict,
    stage: str,
    notebook: pathlib.Path,
    authorized_at: str,
) -> pathlib.Path:
    path = root / f"authorize-{stage}.json"
    write_json(
        path,
        {
            "schema_version": 1,
            "candidate_id": contract["candidate_id"],
            "stage": stage,
            "decision": "AUTHORIZE_ONE_STAGE_RUN",
            "authorized": True,
            "authorized_by_user": True,
            "authorized_at": authorized_at,
            "contract_sha256_before": sha256_bytes(contract_path.read_bytes()),
            "notebook": binding(notebook, root),
            "allowed_external_action": AUTH_ACTIONS[stage],
            "one_run_only": True,
            "read_terminal_evidence_after_run": True,
            "public_leaderboard_used_for_selection": False,
            "future_stages_authorized": False,
            "claim_boundary": "One stage only; no future stage is authorized.",
        },
    )
    return path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arc2-stage-authorization-") as raw:
        root = pathlib.Path(raw)
        _, complete, _ = build_complete_contract(root)

        cases = (
            ("private_development", "2026-09-09T00:40:00+00:00"),
            ("sealed_holdout", "2026-09-09T01:30:00+00:00"),
            ("competition_rerun", "2026-09-09T02:30:00+00:00"),
        )
        for stage, authorized_at in cases:
            competition_notebook = None
            if stage == "competition_rerun":
                competition_notebook = root / "frozen-final-competition.ipynb"
                competition_notebook.write_text("{}\n", encoding="utf-8")
            contract_path, contract = prepare(
                root, complete, stage, competition_notebook
            )
            notebook = (
                competition_notebook
                if competition_notebook is not None
                else root / contract["stages"][stage]["notebook"]["path"]
            )
            receipt_path = authorization_receipt(
                root,
                contract_path,
                contract,
                stage,
                notebook,
                authorized_at,
            )
            result = authorize_stage(contract_path, stage, receipt_path)
            committed = json.loads(contract_path.read_text(encoding="utf-8"))
            assert result["state"] == "RUNNING"
            assert result["external_action_performed"] is False
            assert result["allowed_external_action"] == AUTH_ACTIONS[stage]
            assert committed["stages"][stage]["state"] == "RUNNING"
            assert committed["stages"][stage]["authorization"]["sha256"] == sha256_bytes(
                receipt_path.read_bytes()
            )
            assert committed["stages"][stage]["notebook"] == binding(notebook, root)
            assert audit(contract_path)["passes"] is True

        contract_path, contract = prepare(root, complete, "private_development")
        notebook = root / contract["stages"]["private_development"]["notebook"]["path"]
        wrong = authorization_receipt(
            root,
            contract_path,
            contract,
            "private_development",
            notebook,
            "2026-09-09T00:40:00+00:00",
        )
        payload = json.loads(wrong.read_text(encoding="utf-8"))
        payload["allowed_external_action"] = AUTH_ACTIONS["sealed_holdout"]
        write_json(wrong, payload)
        before = contract_path.read_bytes()
        try:
            authorize_stage(contract_path, "private_development", wrong)
        except ValueError as error:
            assert "differs from the eligible transition" in str(error)
        else:
            raise AssertionError("wrong external-action scope was accepted")
        assert contract_path.read_bytes() == before

        stale = authorization_receipt(
            root,
            contract_path,
            contract,
            "private_development",
            notebook,
            "2026-09-09T00:40:00+00:00",
        )
        stale_payload = json.loads(stale.read_text(encoding="utf-8"))
        stale_payload["contract_sha256_before"] = "0" * 64
        write_json(stale, stale_payload)
        try:
            authorize_stage(contract_path, "private_development", stale)
        except ValueError as error:
            assert "contract_sha256_before" in str(error)
        else:
            raise AssertionError("stale contract authorization was accepted")
        assert contract_path.read_bytes() == before

        premature = authorization_receipt(
            root,
            contract_path,
            contract,
            "private_development",
            notebook,
            "2026-09-09T00:10:00+00:00",
        )
        try:
            authorize_stage(contract_path, "private_development", premature)
        except ValueError as error:
            assert "does not postdate its prerequisite" in str(error)
        else:
            raise AssertionError("pre-prerequisite authorization was accepted")
        assert contract_path.read_bytes() == before

        selected = authorization_receipt(
            root,
            contract_path,
            contract,
            "private_development",
            notebook,
            "2026-09-09T00:40:00+00:00",
        )
        selected_payload = json.loads(selected.read_text(encoding="utf-8"))
        selected_payload["public_leaderboard_used_for_selection"] = True
        write_json(selected, selected_payload)
        try:
            authorize_stage(contract_path, "private_development", selected)
        except ValueError as error:
            assert "differs from the eligible transition" in str(error)
        else:
            raise AssertionError("leaderboard-selected authorization was accepted")
        assert contract_path.read_bytes() == before

        substituted_notebook = root / "substituted.ipynb"
        substituted_notebook.write_text("{}\n", encoding="utf-8")
        substituted = authorization_receipt(
            root,
            contract_path,
            contract,
            "private_development",
            substituted_notebook,
            "2026-09-09T00:40:00+00:00",
        )
        try:
            authorize_stage(contract_path, "private_development", substituted)
        except ValueError as error:
            assert "differs from the frozen stage notebook" in str(error)
        else:
            raise AssertionError("substituted notebook authorization was accepted")
        assert contract_path.read_bytes() == before

        inside = authorization_receipt(
            root,
            contract_path,
            contract,
            "private_development",
            notebook,
            "2026-09-09T00:40:00+00:00",
        )
        outside = root.with_name(root.name + "-authorization.json")
        outside.write_bytes(inside.read_bytes())
        try:
            try:
                authorize_stage(contract_path, "private_development", outside)
            except ValueError as error:
                assert "must be inside the project root" in str(error)
            else:
                raise AssertionError("out-of-project authorization was accepted")
        finally:
            outside.unlink(missing_ok=True)
        assert contract_path.read_bytes() == before

    active = ROOT / "paper/manifests/three_stage_pipeline_v1.json"
    try:
        authorize_stage(active, "private_development", ROOT / "does-not-exist.json")
    except ValueError as error:
        assert "not the next eligible stage" in str(error)
    else:
        raise AssertionError("development was authorized while runtime smoke is unknown")

    print("stage authorization regression passed")


if __name__ == "__main__":
    main()
