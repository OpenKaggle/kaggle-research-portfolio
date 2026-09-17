#!/usr/bin/env python3
"""Regression checks for atomic, fail-closed stage receipt commits."""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    build_complete_contract,
    write_json,
)
from paper.tools.audit_three_stage_pipeline import audit  # noqa: E402
from paper.tools.commit_stage_receipt import commit_stage_receipt  # noqa: E402


def set_running(contract: dict, stage: str) -> None:
    order = ("private_development", "sealed_holdout", "competition_rerun")
    index = order.index(stage)
    contract["status"] = "ACTIVE_NOT_COMPLETE"
    for earlier in order[:index]:
        contract["stages"][earlier]["state"] = "COMPLETE"
    contract["stages"][stage]["state"] = "RUNNING"
    contract["stages"][stage]["receipt"] = None
    for later in order[index + 1 :]:
        contract["stages"][later]["state"] = "NOT_AUTHORIZED"
        contract["stages"][later]["receipt"] = None
        contract["stages"][later]["authorization"] = None


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arc2-stage-commit-") as raw:
        root = pathlib.Path(raw)
        contract_path, complete_contract, receipts = build_complete_contract(root)

        running = copy.deepcopy(complete_contract)
        set_running(running, "private_development")
        write_json(contract_path, running)
        before = contract_path.read_bytes()
        result = commit_stage_receipt(
            contract_path,
            "private_development",
            receipts["private_development"],
        )
        committed = json.loads(contract_path.read_text(encoding="utf-8"))
        assert committed["stages"]["private_development"]["state"] == "COMPLETE"
        assert committed["stages"]["private_development"]["receipt"]["sha256"] == result[
            "receipt_sha256"
        ]
        assert committed["stages"]["sealed_holdout"]["state"] == "NOT_AUTHORIZED"
        assert result["pipeline_complete"] is False
        assert result["next_action"] == "SEALED_HOLDOUT"
        assert result["contract_sha256_before"] != result["contract_sha256_after"]
        assert audit(contract_path)["passes"] is True

        invalid_running = copy.deepcopy(running)
        write_json(contract_path, invalid_running)
        invalid_receipt = json.loads(
            receipts["private_development"].read_text(encoding="utf-8")
        )
        invalid_receipt["metrics"]["method_accuracy"] = 0.123
        invalid_receipt_path = root / "invalid-development-receipt.json"
        write_json(invalid_receipt_path, invalid_receipt)
        unchanged = contract_path.read_bytes()
        try:
            commit_stage_receipt(
                contract_path,
                "private_development",
                invalid_receipt_path,
            )
        except ValueError as error:
            assert "receipt failed normalized validation" in str(error)
        else:
            raise AssertionError("arithmetically invalid receipt was committed")
        assert contract_path.read_bytes() == unchanged

        try:
            commit_stage_receipt(
                contract_path,
                "private_development",
                receipts["sealed_holdout"],
            )
        except ValueError as error:
            assert "receipt failed normalized validation" in str(error)
        else:
            raise AssertionError("receipt for a different stage was committed")
        assert contract_path.read_bytes() == unchanged

        outside = pathlib.Path(raw).parent / "arc2-outside-receipt.json"
        outside.write_bytes(receipts["private_development"].read_bytes())
        try:
            commit_stage_receipt(contract_path, "private_development", outside)
        except ValueError as error:
            assert "inside the contract project root" in str(error)
        else:
            raise AssertionError("receipt outside the project root was committed")
        assert contract_path.read_bytes() == unchanged
        outside.unlink()

        all_but_competition = copy.deepcopy(complete_contract)
        set_running(all_but_competition, "competition_rerun")
        write_json(contract_path, all_but_competition)
        result = commit_stage_receipt(
            contract_path,
            "competition_rerun",
            receipts["competition_rerun"],
        )
        assert result["pipeline_complete"] is True
        assert result["next_action"] == "NONE_PIPELINE_COMPLETE"
        assert json.loads(contract_path.read_text(encoding="utf-8"))["status"] == "COMPLETE"

        assert before != contract_path.read_bytes()

    current_contract = ROOT / "paper/manifests/three_stage_pipeline_v1.json"
    current_before = current_contract.read_bytes()
    try:
        commit_stage_receipt(
            current_contract,
            "private_development",
            ROOT / "does-not-exist.json",
        )
    except ValueError as error:
        assert "must be RUNNING" in str(error)
    else:
        raise AssertionError("current unauthorized development stage was committed")
    assert current_contract.read_bytes() == current_before

    print("stage receipt commit regression passed")


if __name__ == "__main__":
    main()
