from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_harn_stage2_native_v1.py"
SPEC = importlib.util.spec_from_file_location("harn_stage2_native", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_clip_key_is_modality_invariant() -> None:
    expected = "HARn/12_Sweep_the_floor/user17/3-1-2"
    assert MODULE.clip_key(expected + "/Depth/Depth.mp4") == expected
    assert MODULE.clip_key(expected + "/IR/IR.mp4") == expected
    assert MODULE.clip_key(expected) == expected


def test_parser_fails_closed() -> None:
    assert MODULE.parse_vlm("B") == "B"
    assert MODULE.parse_vlm("Answer: C") == "C"
    assert MODULE.parse_vlm("A or D") == ""
    assert MODULE.parse_vlm("") == ""


def test_network_static_audit_does_not_self_match() -> None:
    assert MODULE.network_static_audit(SCRIPT.read_text()) == []
    assert MODULE.network_static_audit("import requests\n") == ["import:requests"]
    assert MODULE.network_static_audit("TARGET = 'https://example.invalid'\n") == ["literal_url"]


def test_route_is_preregistered_and_conservative() -> None:
    assert MODULE.routed_prediction("single", "A", "B", 0.9, True, "A") == "A"
    assert MODULE.routed_prediction("single", "A", "B", 0.9, True, "B") == "B"
    assert MODULE.routed_prediction("single", "A", "B", 0.14, True, "C") == "A"
    assert MODULE.routed_prediction("single", "A", "B", 0.15, True, "C") == "B"
    assert MODULE.routed_prediction("object_interaction", "A", "B", 0.9, True, "C") == "A"
    assert MODULE.routed_prediction("object_interaction", "A", "B", 0.05, True, "B") == "B"
    assert MODULE.routed_prediction("single", "A", "B", 0.9, False, "B") == "A"


def test_frozen_cohort_subject_disjoint_and_fresh() -> None:
    selection = pd.read_csv(ROOT / "artifacts/manifests/harn_stage2_native48.csv", dtype=str)
    protocol = MODULE.json.loads((ROOT / "reports/harn_stage2_native48_protocol.json").read_text())
    assert len(selection) == selection["qa_id"].nunique() == selection["path"].nunique() == 48
    assert set(selection["qa_id"]) == set(protocol["selected_qa_ids"])
    assert set(selection["path"]) == set(protocol["selected_clips"])
    assert selection.groupby("subject_half").size().to_dict() == {
        "A_user1_9": 24,
        "B_user16_24": 24,
    }
    assert selection.groupby("category").size().to_dict() == {
        "object_interaction": 12,
        "single": 36,
    }
    for half, users in {
        "A_user1_9": set(range(1, 10)),
        "B_user16_24": set(range(16, 25)),
    }.items():
        observed = {
            int(value.removeprefix("user"))
            for value in selection.loc[selection["subject_half"] == half, "subject"]
        }
        assert observed <= users


def test_input_and_runner_locks() -> None:
    protocol_path = ROOT / "reports/harn_stage2_native48_protocol.json"
    protocol = MODULE.json.loads(protocol_path.read_text())
    lock = (ROOT / "reports/harn_stage2_native48_protocol.sha256").read_text().split()[0]
    assert MODULE.sha256(protocol_path) == lock
    assert MODULE.sha256(SCRIPT) == protocol["inputs"]["runner_sha256"]
    assert MODULE.sha256(ROOT / "artifacts/manifests/harn_stage2_native48.csv") == protocol["selection_sha256"]
