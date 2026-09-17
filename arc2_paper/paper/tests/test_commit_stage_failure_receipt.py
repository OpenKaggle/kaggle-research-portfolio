#!/usr/bin/env python3
"""Atomic failed-stage receipt commit and byte-preserving rejection tests."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from paper.tests.test_stage_failure_receipt import failure_receipt  # noqa: E402
from paper.tests.test_three_stage_pipeline import (  # noqa: E402
    binding,
    build_complete_contract,
    normalized_receipt,
    sha256,
    write_json,
)
from paper.tools.audit_three_stage_pipeline import audit  # noqa: E402
from paper.tools.commit_stage_failure_receipt import (  # noqa: E402
    commit_stage_failure_receipt,
)


STAGES = ("private_development", "sealed_holdout", "competition_rerun")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def prepare(
    root: pathlib.Path, complete: dict, stage: str
) -> tuple[pathlib.Path, dict]:
    contract = copy.deepcopy(complete)
    contract["status"] = "ACTIVE_NOT_COMPLETE"
    index = STAGES.index(stage)
    for earlier in STAGES[:index]:
        contract["stages"][earlier]["state"] = "COMPLETE"
    target = contract["stages"][stage]
    target["state"] = "RUNNING"
    target["receipt"] = None
    for later in STAGES[index + 1 :]:
        contract["stages"][later]["state"] = "NOT_AUTHORIZED"
        contract["stages"][later]["authorization"] = None
        contract["stages"][later]["receipt"] = None
    contract_path = root / "contract.json"
    write_json(contract_path, contract)
    assert audit(contract_path)["passes"] is True
    return contract_path, contract


def write_failure(
    root: pathlib.Path, contract: dict, stage: str, name: str = "failure"
) -> pathlib.Path:
    notebook = root / contract["stages"][stage]["notebook"]["path"]
    receipt_path = root / f"{name}-{stage}.json"
    write_json(receipt_path, failure_receipt(sha256(notebook), stage=stage))
    return receipt_path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="arc2-stage-failure-commit-") as raw:
        root = pathlib.Path(raw)
        _, complete, _ = build_complete_contract(root)

        for stage in STAGES:
            contract_path, contract = prepare(root, complete, stage)
            receipt_path = write_failure(root, contract, stage)
            result = commit_stage_failure_receipt(contract_path, stage, receipt_path)
            committed = json.loads(contract_path.read_text(encoding="utf-8"))
            assert result["state"] == "FAILED"
            assert result["pipeline_complete"] is False
            assert result["external_action_performed"] is False
            assert (
                result["next_action"]
                == "STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT"
            )
            assert committed["status"] == "ACTIVE_NOT_COMPLETE"
            assert committed["stages"][stage]["state"] == "FAILED"
            assert committed["stages"][stage]["receipt"] == binding(
                receipt_path, root
            )
            assert audit(contract_path)["passes"] is True

        contract_path, contract = prepare(root, complete, "private_development")
        premature = write_failure(root, contract, "private_development", "premature")
        payload = json.loads(premature.read_text(encoding="utf-8"))
        payload["started_at"] = "2026-09-09T00:39:59+00:00"
        write_json(premature, payload)
        before = contract_path.read_bytes()
        try:
            commit_stage_failure_receipt(
                contract_path, "private_development", premature
            )
        except ValueError as error:
            assert "stage_started_before_authorization" in str(error)
        else:
            raise AssertionError("a run started before authorization was committed")
        assert contract_path.read_bytes() == before

        wrong_stage = write_failure(root, contract, "private_development", "wrong")
        wrong_payload = json.loads(wrong_stage.read_text(encoding="utf-8"))
        wrong_payload["stage"] = "sealed_holdout"
        write_json(wrong_stage, wrong_payload)
        try:
            commit_stage_failure_receipt(
                contract_path, "private_development", wrong_stage
            )
        except ValueError as error:
            assert "failure receipt failed normalized validation" in str(error)
        else:
            raise AssertionError("a wrong-stage failure receipt was committed")
        assert contract_path.read_bytes() == before

        complete_receipt = root / "complete-as-failure.json"
        notebook = root / contract["stages"]["private_development"]["notebook"]["path"]
        write_json(
            complete_receipt,
            normalized_receipt(
                "private_development",
                "2026-09-09T01:00:00+00:00",
                sha256(notebook),
            ),
        )
        try:
            commit_stage_failure_receipt(
                contract_path, "private_development", complete_receipt
            )
        except ValueError as error:
            assert "failure receipt failed normalized validation" in str(error)
        else:
            raise AssertionError("a complete-stage receipt was committed as failure")
        assert contract_path.read_bytes() == before

        inside = write_failure(root, contract, "private_development", "inside")
        outside = root.with_name(root.name + "-outside-failure.json")
        outside.write_bytes(inside.read_bytes())
        try:
            try:
                commit_stage_failure_receipt(
                    contract_path, "private_development", outside
                )
            except ValueError as error:
                assert "must be inside the contract project root" in str(error)
            else:
                raise AssertionError("an out-of-project failure receipt was committed")
        finally:
            outside.unlink(missing_ok=True)
        assert contract_path.read_bytes() == before

        receipt_path = write_failure(root, contract, "private_development", "valid")
        try:
            commit_stage_failure_receipt(
                contract_path, "sealed_holdout", receipt_path
            )
        except ValueError as error:
            assert "must be RUNNING with no bound receipt" in str(error)
        else:
            raise AssertionError("a non-running stage accepted a failure receipt")
        assert contract_path.read_bytes() == before

    active = ROOT / "paper/manifests/three_stage_pipeline_v1.json"
    try:
        commit_stage_failure_receipt(
            active,
            "private_development",
            ROOT / "does-not-exist.json",
        )
    except ValueError as error:
        assert "must be RUNNING with no bound receipt" in str(error)
    else:
        raise AssertionError("the inactive real stage accepted a failure receipt")

    print("stage failure receipt commit regression passed")


if __name__ == "__main__":
    main()
