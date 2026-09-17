#!/usr/bin/env python3
"""Validate lifecycle registration without mutating the live campaign state."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TEST_MODULES = [
    "traffic.tests.test_evidence_registry",
    "traffic.tests.test_campaign_readiness_audit",
    "traffic.tests.test_final_submission_selector",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peak_memory_mb() -> float:
    peaks = [
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    ]
    raw = max(peaks)
    return float(raw / (1024 * 1024) if platform.system() == "Darwin" else raw / 1024)


def run(traffic_root: Path, output_root: Path) -> dict[str, object]:
    started = time.perf_counter()
    workspace = traffic_root.parent
    tracked = {
        "campaign_status.json": traffic_root / "artifacts" / "campaign_status.json",
        "experiment_ledger.csv": traffic_root / "artifacts" / "experiment_ledger.csv",
        "submission_ledger.csv": traffic_root / "artifacts" / "submission_ledger.csv",
    }
    before = {name: _sha256(path) for name, path in tracked.items()}
    command = [sys.executable, "-m", "unittest", *TEST_MODULES, "-v"]
    completed = subprocess.run(command, cwd=workspace, text=True, capture_output=True)
    after = {name: _sha256(path) for name, path in tracked.items()}
    test_text = completed.stdout + completed.stderr
    expected_tests = 14
    passed = completed.returncode == 0 and f"Ran {expected_tests} tests" in test_text and before == after
    if not passed:
        raise RuntimeError(
            f"registry validation failed: exit={completed.returncode}; "
            f"test_count_seen={f'Ran {expected_tests} tests' in test_text}; live_state_unchanged={before == after}"
        )

    source_paths = [
        traffic_root / "src" / "evidence_registry.py",
        traffic_root / "src" / "campaign_readiness_audit.py",
        traffic_root / "src" / "final_submission_selector.py",
        traffic_root / "run.py",
        traffic_root / "tests" / "test_evidence_registry.py",
        traffic_root / "tests" / "test_campaign_readiness_audit.py",
        traffic_root / "tests" / "test_final_submission_selector.py",
    ]
    receipt: dict[str, object] = {
        "status": "VALID",
        "experiment": "lifecycle_evidence_registry_v1",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "internal readiness and final-selection evidence registration only",
        "checks": {
            "isolated_readiness_registration": True,
            "isolated_final_selection_registration": True,
            "idempotent_repeated_registration": True,
            "atomic_single_file_replacement": True,
            "registered_receipt_live_gate_validation": True,
            "immutable_existing_receipt_paths": True,
            "live_campaign_state_unchanged": before == after,
            "unit_tests_passed": expected_tests,
        },
        "live_campaign_hashes_before": before,
        "live_campaign_hashes_after": after,
        "source_sha256": {
            str(path.relative_to(workspace)): _sha256(path) for path in source_paths
        },
        "information_boundary": {
            "predictions_changed": False,
            "kaggle_action_performed": False,
            "hidden_labels_read_or_reconstructed": False,
            "organizer_only_metrics_inferred": False,
        },
        "runtime_seconds": time.perf_counter() - started,
        "peak_memory_mb": _peak_memory_mb(),
        "decision": "USE_ACTIVATED_IDEMPOTENT_LIFECYCLE_REGISTRATION",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    receipt_path = output_root / "lifecycle_evidence_registry_receipt.json"
    if receipt_path.exists():
        raise ValueError("output root already contains a registry validation receipt")
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traffic-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    run(args.traffic_root.resolve(), args.output_root.resolve())


if __name__ == "__main__":
    main()
