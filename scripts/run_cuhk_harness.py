#!/usr/bin/env python3
"""Read-only CUHK-X campaign harness.

Runs both track test suites, the Large pytest-style zero-argument tests without
requiring pytest, candidate grammar checks, manifest integrity checks, exposure
registry invariants, and finalist-package readiness checks.

The default research mode succeeds when research artifacts are internally
consistent while reporting known release blockers.  ``--release`` fails closed
until every finalist-package boundary is complete.  ``--deep`` additionally
rehashes every artifact in the current Large reproducibility manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LARGE = ROOT / "cuhk_x_large"
SMALL = ROOT / "cuhkx_small"
PACKAGE_AUDIT = LARGE / "reports/stage2_owned_package_control_audit_v1.json"
REGISTRY = LARGE / "artifacts/manifests/vlm_exposure_registry_v2.jsonl"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command,
        "output_tail": completed.stdout.splitlines()[-30:],
    }


def run_plain_function_tests() -> dict[str, Any]:
    executed: list[str] = []
    failures: list[str] = []
    skipped_with_fixtures: list[str] = []
    for path in sorted((LARGE / "tests").glob("test_*.py")):
        name = f"cuhk_harness_{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            failures.append(f"{path.name}: could not create import spec")
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # fail closed and preserve the exact import error
            failures.append(f"{path.name}: import {type(exc).__name__}: {exc}")
            continue
        for test_name, function in inspect.getmembers(module, inspect.isfunction):
            if not test_name.startswith("test_") or function.__module__ != name:
                continue
            parameters = inspect.signature(function).parameters
            qualified = f"{path.name}::{test_name}"
            if parameters:
                skipped_with_fixtures.append(qualified)
                continue
            try:
                function()
                executed.append(qualified)
            except Exception as exc:  # assertions are reported without hiding type
                failures.append(f"{qualified}: {type(exc).__name__}: {exc}")
    return {
        "passed": not failures and not skipped_with_fixtures,
        "executed": executed,
        "executed_count": len(executed),
        "unsupported_fixture_tests": skipped_with_fixtures,
        "failures": failures,
    }


def latest_manifest_pair() -> tuple[Path, Path, int]:
    candidates: list[tuple[int, Path]] = []
    prefix = "final_reproducibility_manifest_2026-09-11_v"
    for path in (LARGE / "reports").glob(f"{prefix}*.json"):
        suffix = path.stem.removeprefix(prefix)
        if suffix.isdigit():
            candidates.append((int(suffix), path))
    if not candidates:
        raise FileNotFoundError("No versioned Large reproducibility manifest found")
    version, manifest_path = max(candidates)
    verification_path = manifest_path.with_name(
        manifest_path.name.replace("manifest", "verification", 1)
    )
    if not verification_path.is_file():
        raise FileNotFoundError(
            f"Latest manifest v{version} has no matching verification report"
        )
    return manifest_path, verification_path, version


def check_manifest(deep: bool) -> dict[str, Any]:
    manifest_path, verification_path, version = latest_manifest_pair()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    missing: list[str] = []
    size_mismatches: list[str] = []
    hash_mismatches: list[str] = []
    for item in manifest["artifact_inventory"]:
        path = LARGE / item["path"]
        if not path.is_file():
            missing.append(item["path"])
            continue
        if path.stat().st_size != item["bytes"]:
            size_mismatches.append(item["path"])
        if deep and sha256(path) != item["sha256"]:
            hash_mismatches.append(item["path"])
    manifest_hash = sha256(manifest_path)
    checks = {
        "snapshot_version_matches_latest_filename": manifest.get("snapshot_version") == version,
        "registration_complete": bool(
            manifest.get("competition", {}).get("external_registration_complete")
        ),
        "verification_pass": verification.get("status") == "PASS",
        "verification_binds_manifest": verification.get("manifest_sha256") == manifest_hash,
        "all_inventory_files_present": not missing,
        "all_inventory_sizes_match": not size_mismatches,
        "all_inventory_hashes_match": not deep or not hash_mismatches,
    }
    return {
        "passed": all(checks.values()),
        "mode": "deep_hash" if deep else "quick_size_and_binding",
        "checks": checks,
        "inventory_count": len(manifest["artifact_inventory"]),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "verification": str(verification_path.relative_to(ROOT)),
        "missing": missing,
        "size_mismatches": size_mismatches,
        "hash_mismatches": hash_mismatches,
        "manifest_sha256": manifest_hash,
    }


def check_registry() -> dict[str, Any]:
    forbidden = {"answer", "label", "correct", "raw_output", "prediction"}
    event_ids: set[str] = set()
    duplicate_ids: list[str] = []
    forbidden_keys: list[str] = []
    rows = 0
    with REGISTRY.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            rows += 1
            event_id = row.get("event_id")
            if not event_id or event_id in event_ids:
                duplicate_ids.append(f"line {line_number}: {event_id}")
            event_ids.add(event_id)
            bad = forbidden.intersection(row)
            if bad:
                forbidden_keys.append(f"line {line_number}: {sorted(bad)}")
    return {
        "passed": not duplicate_ids and not forbidden_keys and rows > 0,
        "events": rows,
        "duplicate_event_ids": duplicate_ids,
        "forbidden_sensitive_keys": forbidden_keys,
        "registry_sha256": sha256(REGISTRY),
    }


def check_package_boundary() -> dict[str, Any]:
    audit = json.loads(PACKAGE_AUDIT.read_text(encoding="utf-8"))
    checks = audit["checks"]
    research_pass = all(
        checks[name]
        for name in (
            "subject_disjoint_core_gate_pass",
            "official_682_row_grammar_pass",
            "two_network_free_runs_byte_identical",
            "arbitrary_qa_id_and_clip_key_smoke_pass",
            "qwen_rejection_enforced",
        )
    ) and checks["fixed_third_party_682_vector_dependency"] is False
    blockers = [
        name
        for name in (
            "owned_builder_called_by_inference_sh",
            "raw_organizer_sensor_to_feature_cache_packaged",
            "post_competition_deadline_conflict_resolved",
            "small_llm_rule_scope_resolved",
            "finalist_license_layers_resolved",
            "finalist_package_ready",
        )
        if not checks[name]
    ]
    return {
        "passed_research_boundary": research_pass,
        "passed_release_boundary": research_pass and not blockers,
        "release_blockers": blockers,
        "decision": audit["decision"],
        "candidate_sha256": audit["candidate_sha256"],
        "technical_raw_package_ready": checks.get("technical_raw_package_ready", False),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deep", action="store_true", help="rehash every manifest artifact")
    parser.add_argument(
        "--release", action="store_true", help="fail until raw-input finalist package is ready"
    )
    args = parser.parse_args()

    large_unittest = run(
        [sys.executable, "-m", "unittest", "discover", "-s", "cuhk_x_large/tests", "-p", "test_*.py", "-v"]
    )
    large_plain = run_plain_function_tests()
    small_unittest = run(
        [sys.executable, "-m", "unittest", "discover", "-s", "cuhkx_small/src", "-p", "test_*.py", "-v"]
    )
    small_boundary = run(
        [
            sys.executable,
            "cuhkx_small/src/small_boundary_harness.py",
            "--config",
            "cuhkx_small/config/top5_preregistered_ladder.json",
            "--submission-log",
            "cuhkx_small/SUBMISSION_LOG.csv",
        ]
    )
    candidates = {}
    for relative in (
        "candidates/emotion_extratrees_rf_union_v1.csv",
        "candidates/nonvisual_sensor_union_v1.csv",
        "candidates/stage2_native_owned_v1.csv",
    ):
        candidates[relative] = run(
            [sys.executable, "cuhk_x_large/scripts/validate_submission.py", f"cuhk_x_large/{relative}"]
        )

    manifest = check_manifest(args.deep)
    registry = check_registry()
    package = check_package_boundary()
    scientific_pass = (
        large_unittest["passed"]
        and large_plain["passed"]
        and small_unittest["passed"]
        and small_boundary["passed"]
        and all(item["passed"] for item in candidates.values())
        and manifest["passed"]
        and registry["passed"]
        and package["passed_research_boundary"]
    )
    release_pass = scientific_pass and package["passed_release_boundary"]
    result = {
        "harness": "cuhk-x-campaign-v1",
        "interpreter": sys.executable,
        "mode": "release" if args.release else "research",
        "deep_manifest_hashing": args.deep,
        "scientific_harness_pass": scientific_pass,
        "release_harness_pass": release_pass,
        "large_unittest": large_unittest,
        "large_plain_function_tests": large_plain,
        "small_unittest": small_unittest,
        "small_boundary_harness": small_boundary,
        "candidate_validation": candidates,
        "manifest": manifest,
        "exposure_registry": registry,
        "owned_stage2_package": package,
        "status": (
            "PASS_RELEASE_READY"
            if release_pass
            else "PASS_RESEARCH_BLOCK_RELEASE"
            if scientific_pass
            else "FAIL_SCIENTIFIC_HARNESS"
        ),
    }
    print(json.dumps(result, indent=2))
    if not scientific_pass:
        return 2
    if args.release and not release_pass:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
