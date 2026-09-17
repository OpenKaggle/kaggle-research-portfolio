#!/usr/bin/env python3
"""Build a private one-task/one-step Kaggle smoke for the TRM LR repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "candidate_notebooks" / "trm_wandb_log_compat_smoke_v2"
SLUG = "arc2-trm-wandb-log-compat-smoke-v2"
FILE_STEM = "arc2-trm-wandb-log-compat-smoke-v2"
TASK_ID = "bc1d5164"
PARENT_RUNTIME_SHA256 = "17d8757c874f14d20aee0368054137874e8df16f2dd8f0fe9e521d5aff2c9e82"


def code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


def main() -> None:
    runtime_path = ROOT / "public_assets" / "trm_source" / "trm_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    runtime_sha = hashlib.sha256(runtime_text.encode("utf-8")).hexdigest()
    required_runtime_fragments = (
        "lr=config.lr",
        "def _offline_wandb_log(payload, step=None):",
        "_offline_wandb_log(",
    )
    if not all(fragment in runtime_text for fragment in required_runtime_fragments):
        raise RuntimeError("TRM V2 compatibility patches are missing from the owned runtime")

    setup = f'''import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

task_id = {TASK_ID!r}
repair_id = "offline_wandb_stdout_helper_v2"
parent_runtime_sha256 = {PARENT_RUNTIME_SHA256!r}
expected_runtime_sha256 = {runtime_sha!r}
started_at = time.time()

competition_root = Path("/kaggle/input/competitions/arc-prize-2026-arc-agi-2")
training_path = competition_root / "arc-agi_training_challenges.json"
all_tasks = json.loads(training_path.read_text(encoding="utf-8"))
if task_id not in all_tasks:
    raise KeyError(f"frozen smoke task {{task_id}} missing from official training data")
challenge_path = Path("/kaggle/working/trm_smoke_challenge.json")
challenge_path.write_text(json.dumps({{task_id: all_tasks[task_id]}}), encoding="utf-8")

matches = sorted(Path("/kaggle/input").rglob("trm_runtime.py"))
if not matches:
    raise FileNotFoundError("attached ARC proof-search/TRM source is missing")
attached_source = matches[0].parent
trm_source = Path("/kaggle/working/hybrid_trm_source")
if trm_source.exists():
    shutil.rmtree(trm_source)
shutil.copytree(attached_source, trm_source)
sys.path.insert(0, str(trm_source))
from bootstrap_runtime import restore_archived_directories
restore_archived_directories(trm_source)

patched_runtime = {runtime_text!r}
runtime_destination = trm_source / "trm_runtime.py"
runtime_destination.write_text(patched_runtime, encoding="utf-8")
actual_runtime_sha256 = hashlib.sha256(runtime_destination.read_bytes()).hexdigest()
assert actual_runtime_sha256 == expected_runtime_sha256

packages = [
    "hydra-core==1.3.2", "omegaconf==2.3.0",
    "adam_atan2_pytorch==0.2.4", "argdantic==1.3.3", "coolname==2.2.0",
]
subprocess.run([
    sys.executable, "-m", "pip", "install", "--no-index",
    f"--find-links={{trm_source / 'wheels'}}", *packages,
], check=True)

env = os.environ.copy()
env.update({{
    "ARC_CHALLENGE_FILE": str(challenge_path),
    "ARC_WORKING_ROOT": "/kaggle/working",
    "CUDA_VISIBLE_DEVICES": "0",
    "TRM_WORLD_SIZE": "1",
    "TRM_EPOCHS": "1",
    "TRM_EVAL_INTERVAL": "1",
    "TRM_GLOBAL_BATCH_SIZE": "112",
    "TRM_LR": "0.0000875",
    "TRM_WARMUP_STEPS": "229",
    "TRM_NUM_AUG": "128",
    "OMP_NUM_THREADS": "4",
    "PYTHONNOUSERSITE": "1",
}})
polluted_root = "/kaggle/usr/lib/notebooks/sorokin/pip_install_unsloth_flash_patch"
env["PYTHONPATH"] = os.pathsep.join(
    value for value in env.get("PYTHONPATH", "").split(os.pathsep)
    if value and polluted_root not in value
)

log_path = Path("/kaggle/working/trm-smoke.log")
with log_path.open("w", encoding="utf-8", buffering=1) as log_handle:
    result = subprocess.run(
        [sys.executable, str(runtime_destination)],
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )

submission_path = Path("/kaggle/working/trm_submission.json")
submission_valid = False
submission_sha256 = None
if result.returncode == 0 and submission_path.is_file():
    from trm_runtime import validate_submission
    validate_submission(submission_path, challenge_path)
    submission_valid = True
    submission_sha256 = hashlib.sha256(submission_path.read_bytes()).hexdigest()

log_text = log_path.read_text(encoding="utf-8", errors="replace")
step_one_checkpoint = Path("/kaggle/working/trm_output/step_1")
patched_pretrain_text = Path("/kaggle/working/trm_runtime/pretrain.py").read_text(
    encoding="utf-8", errors="replace"
)
guards = {{
    "runtime_returncode_zero": result.returncode == 0,
    "checkpoint_loaded": "Loading checkpoint" in log_text,
    "optimizer_constructed": "AssertionError" not in log_text,
    "scheduler_path_preserved": (
        "lr_this_step = compute_lr(base_lr, config, train_state)" in patched_pretrain_text
        and "param_group['lr'] = lr_this_step" in patched_pretrain_text
    ),
    "first_step_checkpoint_saved": step_one_checkpoint.is_file(),
    "submission_exists": submission_path.is_file(),
    "submission_schema_valid": submission_valid,
}}
receipt = {{
    "purpose": "runtime compatibility smoke; not an accuracy experiment",
    "repair_id": repair_id,
    "single_change": "offline wandb.log adapter -> stdout-only helper accepting step=None; model, optimizer, scheduler, data, and RNG unchanged",
    "task_id": task_id,
    "task_count": 1,
    "epochs": 1,
    "expected_optimizer_steps": 1,
    "runtime_sha256": actual_runtime_sha256,
    "parent_runtime_sha256": parent_runtime_sha256,
    "challenge_sha256": hashlib.sha256(challenge_path.read_bytes()).hexdigest(),
    "submission_sha256": submission_sha256,
    "elapsed_seconds": time.time() - started_at,
    "returncode": result.returncode,
    "guards": guards,
    "all_guards_passed": all(guards.values()),
}}
receipt_path = Path("/kaggle/working/trm-smoke-receipt.json")
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\\n", encoding="utf-8")
print(json.dumps(receipt, indent=2, sort_keys=True))
if not receipt["all_guards_passed"]:
    print("*** TRM SMOKE LOG TAIL ***")
    print("\\n".join(log_text.splitlines()[-100:]))
    raise SystemExit(1)
'''

    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": (
                    "# ARC2 TRM offline logging compatibility smoke V2\n\n"
                    "Private, frozen one-task/one-step runtime diagnostic. It does not "
                    "measure accuracy and cannot authorize sealed-holdout access. The "
                    "V1's positive AdamAtan2 bootstrap is retained. The only V2 change "
                    "is a network-free stdout logger accepting `step=`; model, optimizer, "
                    "scheduler, data, and RNG behavior are unchanged."
                ),
            },
            code_cell(setup),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
            "arc2_smoke": {
                "repair_id": "offline_wandb_stdout_helper_v2",
                "parent_runtime_sha256": PARENT_RUNTIME_SHA256,
                "task_id": TASK_ID,
                "epochs": 1,
                "expected_optimizer_steps": 1,
                "runtime_sha256": runtime_sha,
                "score_use": "forbidden",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    metadata = {
        "id": f"jahyee/{SLUG}",
        "title": "ARC2 TRM Wandb Log Compat Smoke V2",
        "code_file": f"{FILE_STEM}.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "enable_tpu": False,
        "machine_shape": "NvidiaL4",
        "competition_sources": ["arc-prize-2026-arc-agi-2"],
        "dataset_sources": [
            "christopherdaleman/arc-proof-search-trm-2026-source",
            "cpmpml/arc-prize-trm-031",
        ],
        "kernel_sources": [],
        "model_sources": [],
        "keywords": ["gpu"],
        "docker_image": (
            "gcr.io/kaggle-private-byod/python@sha256:"
            "37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461"
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    notebook_path = OUT_DIR / metadata["code_file"]
    notebook_path.write_text(
        json.dumps(notebook, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (OUT_DIR / "kernel-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(notebook_path)
    print(f"runtime_sha256={runtime_sha}")


if __name__ == "__main__":
    main()
