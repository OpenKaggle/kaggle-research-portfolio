#!/usr/bin/env python3
"""Retry the local Icecuber smoke with one explicit libc++ header repair."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from run_local_icecuber_smoke import sha256, valid_submission


ROOT = Path(__file__).resolve().parent
TASK_ID = "bc1d5164"
OUT_DIR = ROOT / "artifacts" / "icecuber_local_smoke_bc1d5164_v2_map_include"


def main() -> None:
    source_root = ROOT / "public_assets" / "trm_source"
    challenges_path = ROOT / "official" / "competition_files" / "arc-agi_training_challenges.json"
    challenges = json.loads(challenges_path.read_text(encoding="utf-8"))
    task = challenges[TASK_ID]
    if len(task["test"]) != 1:
        raise ValueError("the frozen smoke task must have exactly one test output")

    input_dir = OUT_DIR / "input"
    working_dir = OUT_DIR / "working"
    runtime_root = working_dir / "proof_search_runtime"
    input_dir.mkdir(parents=True, exist_ok=True)
    working_dir.mkdir(parents=True, exist_ok=True)
    challenge_path = input_dir / "arc-agi_test_challenges.json"
    challenge_path.write_text(
        json.dumps({TASK_ID: task}, separators=(",", ":")),
        encoding="utf-8",
    )

    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    shutil.copytree(
        source_root,
        runtime_root,
        ignore=shutil.ignore_patterns(
            ".git", "ARC-AGI-2", "training-sample-*", "*.zip", "__pycache__",
            "store", "obj", "run", "output", "*.out", "*.err",
        ),
    )
    ice_root = runtime_root / "third_party" / "icecuber"
    header = ice_root / "headers" / "precompiled_stl.hpp"
    header_before_sha256 = sha256(header)
    header_text = header.read_text(encoding="utf-8")
    if "#include <map>" in header_text:
        raise RuntimeError("compatibility anchor unexpectedly already present")
    header.write_text(
        header_text.replace("#include <vector>\n", "#include <vector>\n#include <map>\n", 1),
        encoding="utf-8",
    )
    header_after_sha256 = sha256(header)

    sample_name = "local_smoke_v2"
    sample_dir = ice_root / "dataset" / sample_name
    sample_dir.mkdir(parents=True)
    (sample_dir / f"{TASK_ID}.json").write_text(
        json.dumps(task, separators=(",", ":")),
        encoding="utf-8",
    )
    (ice_root / "output").mkdir()

    started = time.time()
    log_parts = [
        "single_change=insert explicit #include <map> into runtime-copy precompiled_stl.hpp"
    ]
    compile_result = subprocess.run(
        ["make", "-j", str(max(1, os.cpu_count() or 1))],
        cwd=ice_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    log_parts.append(compile_result.stdout)

    run_result = None
    if compile_result.returncode == 0:
        environment = os.environ.copy()
        environment["ARC_SAMPLE_DIR"] = sample_name
        environment["ARC_EVAL_MODE"] = "1"
        try:
            run_result = subprocess.run(
                [str(ice_root / "run"), "0", "2"],
                cwd=ice_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
                check=False,
            )
            log_parts.append(run_result.stdout)
        except subprocess.TimeoutExpired as error:
            log_parts.append(str(error))

    submission_path = working_dir / "submission.json"
    generation_error = None
    if run_result is not None and run_result.returncode == 0:
        sys.path.insert(0, str(runtime_root))
        try:
            from icecuber_adapter import make_ensemble_submission

            make_ensemble_submission(challenge_path, ice_root / "output", submission_path)
        except Exception as error:
            generation_error = repr(error)
            log_parts.append(generation_error)

    elapsed = time.time() - started
    log_path = OUT_DIR / "smoke.log"
    log_path.write_text("\n".join(log_parts), encoding="utf-8")
    guards = {
        "map_include_was_single_source_change": header_before_sha256 != header_after_sha256,
        "compiled": compile_result.returncode == 0 and (ice_root / "run").is_file(),
        "solver_returncode_zero": run_result is not None and run_result.returncode == 0,
        "submission_exists": submission_path.is_file(),
        "submission_schema_valid": (
            submission_path.is_file() and valid_submission(challenge_path, submission_path)
        ),
        "no_generation_exception": generation_error is None,
    }
    receipt = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "local runtime compatibility smoke; not accuracy evidence",
        "solver_family": "unchanged Icecuber depth 2 plus symbolic fallback",
        "data_boundary": "one official public-training challenge; solutions never loaded",
        "single_change_from_v1": "insert explicit #include <map> in the temporary runtime copy for macOS libc++",
        "task_id": TASK_ID,
        "task_count": 1,
        "depth": 2,
        "elapsed_seconds": elapsed,
        "compile_returncode": compile_result.returncode,
        "solver_returncode": run_result.returncode if run_result is not None else None,
        "guards": guards,
        "all_guards_passed": all(guards.values()),
        "input_sha256": sha256(challenge_path),
        "source_root_entry_sha256": sha256(source_root / "run_entry.py"),
        "header_before_sha256": header_before_sha256,
        "header_after_sha256": header_after_sha256,
        "submission_sha256": sha256(submission_path) if submission_path.is_file() else None,
        "log_sha256": sha256(log_path),
        "external_actions": False,
        "solutions_loaded": False,
    }
    receipt_path = OUT_DIR / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if not receipt["all_guards_passed"]:
        print("\n".join(log_parts[-2:])[-12000:], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
