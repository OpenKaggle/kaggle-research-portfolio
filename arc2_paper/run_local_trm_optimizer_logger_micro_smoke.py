#!/usr/bin/env python3
"""CPU micro-smoke for the two TRM runtime compatibility repairs.

This does not load the TRM model, checkpoint, ARC tasks, or solutions.  It
executes the exact AdamAtan2 0.2.4 constructor/scheduler/step sequence with a
single scalar parameter and executes the logger function extracted from the
actually patched upstream pretrain source.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "public_assets/trm_source"
WHEEL = SOURCE / "wheels/adam_atan2_pytorch-0.2.4-py3-none-any.whl"
sys.path.insert(0, str(WHEEL))
sys.path.insert(0, str(SOURCE))

from adam_atan2_pytorch import AdamAtan2  # noqa: E402
from trm_runtime import patch_trm_source  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_function(source: str, name: str):
    tree = ast.parse(source)
    matches = [
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} definition, found {len(matches)}")
    module = ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[]))
    namespace: dict[str, object] = {}
    exec(compile(module, "<patched-pretrain-logger>", "exec"), namespace)
    return namespace[name]


def main() -> None:
    base_lr = 0.0000875
    scheduled_lr = base_lr / 4
    guards: dict[str, bool] = {}

    negative_control_exception = None
    try:
        parameter = torch.nn.Parameter(torch.tensor([1.0], dtype=torch.float32))
        AdamAtan2([parameter], lr=0, weight_decay=0.1, betas=(0.9, 0.95))
    except Exception as error:  # The exact third-party failure is part of the receipt.
        negative_control_exception = f"{type(error).__name__}: {error}"
    guards["zero_lr_negative_control_rejected"] = negative_control_exception is not None

    with tempfile.TemporaryDirectory(prefix="arc2-trm-micro-") as raw:
        runtime = Path(raw) / "runtime"
        patched_entry = patch_trm_source(
            SOURCE / "third_party/TinyRecursiveModels", runtime
        )
        patched_text = patched_entry.read_text(encoding="utf-8")
        patched_sha256 = sha256(patched_entry)

        guards["two_positive_lr_constructor_replacements"] = (
            patched_text.count("AdamAtan2(\n                model.parameters(),\n                lr=config.lr,")
            == 2
        )
        schedule_assignment = "param_group['lr'] = lr_this_step"
        optimizer_step = "optim.step()"
        guards["scheduler_assignment_precedes_optimizer_step"] = (
            schedule_assignment in patched_text
            and optimizer_step in patched_text
            and patched_text.index(schedule_assignment) < patched_text.index(optimizer_step)
        )
        guards["all_wandb_log_calls_redirected"] = (
            "wandb.log(" not in patched_text and "_offline_wandb_log(" in patched_text
        )

        offline_log = extract_function(patched_text, "_offline_wandb_log")
        logger_stdout = io.StringIO()
        with contextlib.redirect_stdout(logger_stdout):
            offline_log({"train/lr": scheduled_lr}, step=0)
        logger_text = logger_stdout.getvalue().strip()
        guards["logger_accepts_step_keyword"] = (
            "'offline_step': 0" in logger_text and "'train/lr'" in logger_text
        )

    parameter = torch.nn.Parameter(torch.tensor([1.0], dtype=torch.float32))
    optimizer = AdamAtan2(
        [parameter],
        lr=base_lr,
        weight_decay=0.1,
        betas=(0.9, 0.95),
    )
    guards["positive_lr_constructor_succeeds"] = optimizer.param_groups[0]["lr"] == base_lr
    loss = parameter.square().sum()
    loss.backward()
    optimizer.param_groups[0]["lr"] = scheduled_lr
    before = float(parameter.detach().item())
    optimizer.step()
    optimizer.zero_grad()
    after = float(parameter.detach().item())
    state = optimizer.state[parameter]
    guards["scheduled_lr_overrides_bootstrap"] = optimizer.param_groups[0]["lr"] == scheduled_lr
    guards["optimizer_step_updates_parameter"] = after != before
    guards["optimizer_state_initialized"] = {
        "steps",
        "exp_avg",
        "exp_avg_sq",
    } <= set(state)
    guards["gradient_cleared_after_step"] = parameter.grad is None

    receipt = {
        "purpose": "local CPU API/path micro-smoke; accuracy use forbidden",
        "external_actions_performed": False,
        "arc_tasks_or_solutions_read": False,
        "model_or_checkpoint_loaded": False,
        "torch_version": torch.__version__,
        "device": "cpu",
        "adam_package": "adam_atan2_pytorch==0.2.4",
        "base_lr": base_lr,
        "scheduled_lr": scheduled_lr,
        "parameter_before": before,
        "parameter_after": after,
        "negative_control_exception": negative_control_exception,
        "logger_stdout": logger_text,
        "guards": guards,
        "all_guards_passed": all(guards.values()),
        "hashes": {
            "runtime_adapter_sha256": sha256(SOURCE / "trm_runtime.py"),
            "upstream_pretrain_sha256": sha256(
                SOURCE / "third_party/TinyRecursiveModels/pretrain.py"
            ),
            "patched_pretrain_sha256": patched_sha256,
            "adam_wheel_sha256": sha256(WHEEL),
            "micro_smoke_script_sha256": sha256(Path(__file__)),
        },
        "limitations": [
            "does not instantiate the TRM architecture",
            "does not load the 2.16 GB checkpoint",
            "does not execute CUDA, distributed training, dataset building, evaluation, or submission export",
            "cannot replace the authoritative Kaggle one-task/one-step smoke",
        ],
        "decision": "local API path passes; await authorized authoritative smoke status",
    }
    output_dir = ROOT / "artifacts/trm_optimizer_logger_micro_smoke"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "local_micro_smoke_receipt.json"
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(output_path), "receipt_sha256": sha256(output_path), **receipt}, indent=2, sort_keys=True))
    if not receipt["all_guards_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
