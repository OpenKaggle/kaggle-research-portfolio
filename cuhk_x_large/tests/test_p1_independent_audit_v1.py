from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_p1_and_preflight_p2_v1.py"
SPEC = importlib.util.spec_from_file_location("p1_audit", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_parse_answer_fails_closed() -> None:
    assert MODULE.parse_answer("answer=c") == "C"
    assert MODULE.parse_answer("A") == "A"
    assert MODULE.parse_answer("evidence only") == ""
    assert MODULE.parse_answer("answer=A or answer=B") == "A"


def test_route_is_symmetric_for_prompt_variants() -> None:
    assert MODULE.route("single", "A", "B", "B", 0.15, True) == "B"
    assert MODULE.route("single", "A", "B", "C", 0.99, True) == "A"
    assert MODULE.route("object_interaction", "A", "B", "A", 0.05, True) == "A"
    assert MODULE.route("object_interaction", "A", "B", "C", 0.99, True) == "B"
    assert MODULE.route("single", "", "B", "B", 0.99, True) == ""


def test_temporal_field_and_frame_formula() -> None:
    raw = "verb=hold; object=cup; temporal=middle; answer=D"
    assert MODULE.field(raw, "temporal") == "middle"
    assert MODULE.sampled_frames_at_fps(5, 30.0, 1.0) == 4
    assert MODULE.sampled_frames_at_fps(300, 30.0, 1.0) == 10


def test_runner_static_network_audit() -> None:
    audit = MODULE.static_network_audit(ROOT / "scripts/run_p1_decomposed_sensor_screen_v1.py")
    assert audit["forbidden_network_imports"] == []
    assert audit["literal_urls"] == []
    assert audit["offline_environment_set"]
    assert audit["socket_connect_blocked"]
    assert audit["block_installed_before_model_import"]
