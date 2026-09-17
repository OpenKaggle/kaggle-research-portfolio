#!/usr/bin/env python3
"""Behavioral and artifact regression for the final TRM logging-compat smoke V2."""

from __future__ import annotations

import ast
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import pathlib
import tempfile


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_runtime(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location("arc2_owned_trm_runtime", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def main() -> None:
    arc_root = pathlib.Path(__file__).resolve().parents[2]
    runtime_path = arc_root / "public_assets/trm_source/trm_runtime.py"
    upstream = arc_root / "public_assets/trm_source/third_party/TinyRecursiveModels"
    candidate_dir = arc_root / "candidate_notebooks/trm_wandb_log_compat_smoke_v2"
    notebook_path = candidate_dir / "arc2-trm-wandb-log-compat-smoke-v2.ipynb"
    metadata_path = candidate_dir / "kernel-metadata.json"
    builder_path = arc_root / "build_trm_compat_smoke_notebook.py"
    receipt_path = arc_root / "paper/results/trm_wandb_log_compat_smoke_v2_local_ready_2026-09-09.json"
    run_manifest_path = arc_root / "kaggle_runs/trm_wandb_log_compat_smoke_v2/run_manifest.json"
    boundary_receipt_path = (
        arc_root / "kaggle_runs/trm_wandb_log_compat_smoke_v2/local_preflight_receipt.json"
    )

    runtime = load_runtime(runtime_path)
    with tempfile.TemporaryDirectory(prefix="arc2-trm-v2-patch-") as raw:
        patched_entry = runtime.patch_trm_source(upstream, pathlib.Path(raw) / "runtime")
        patched_text = patched_entry.read_text(encoding="utf-8")
        tree = ast.parse(patched_text, filename=str(patched_entry))
        compile(tree, str(patched_entry), "exec")

        assert "import wandb" not in patched_text
        assert "wandb.log(" not in patched_text
        assert "print(" not in "\n".join(
            line for line in patched_text.splitlines() if "step=" in line
        )
        assert patched_text.count("lr=config.lr,") == 2
        assert "lr=0, # Needs to be set by scheduler" not in patched_text
        assert "lr_this_step = compute_lr(base_lr, config, train_state)" in patched_text
        assert "param_group['lr'] = lr_this_step" in patched_text

        logger_nodes = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_offline_wandb_log"
        ]
        assert len(logger_nodes) == 1
        logger_module = ast.Module(body=logger_nodes, type_ignores=[])
        ast.fix_missing_locations(logger_module)
        namespace: dict = {}
        exec(compile(logger_module, "<offline_logger>", "exec"), namespace)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            namespace["_offline_wandb_log"]({"loss": 1.0}, step=0)
        rendered = output.getvalue()
        assert "offline_step" in rendered and "0" in rendered and "loss" in rendered

    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    boundary_receipt = json.loads(boundary_receipt_path.read_text(encoding="utf-8"))
    assert metadata["is_private"] is True
    assert metadata["enable_internet"] is False
    assert metadata["id"] == "jahyee/arc2-trm-wandb-log-compat-smoke-v2"
    assert metadata["competition_sources"] == ["arc-prize-2026-arc-agi-2"]
    assert metadata["model_sources"] == []

    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    assert len(code_cells) == 1
    assert code_cells[0].get("execution_count") is None
    assert code_cells[0].get("outputs") == []
    code = cell_source(code_cells[0])
    assert "task_id = 'bc1d5164'" in code
    assert "arc-agi_training_challenges.json" in code
    assert "training_solutions" not in code
    assert '"TRM_EPOCHS": "1"' in code
    assert '"TRM_EVAL_INTERVAL": "1"' in code
    assert '"TRM_WORLD_SIZE": "1"' in code
    assert '"TRM_LR": "0.0000875"' in code
    assert '"TRM_NUM_AUG": "128"' in code
    assert '"all_guards_passed": all(guards.values())' in code
    assert 'if not receipt["all_guards_passed"]:' in code
    for guard in (
        "runtime_returncode_zero",
        "checkpoint_loaded",
        "optimizer_constructed",
        "scheduler_path_preserved",
        "first_step_checkpoint_saved",
        "submission_exists",
        "submission_schema_valid",
    ):
        assert f'"{guard}"' in code

    artifacts = receipt["artifacts"]
    assert sha256(notebook_path) == artifacts["candidate_notebook"]["sha256"]
    assert sha256(metadata_path) == artifacts["kernel_metadata"]["sha256"]
    assert sha256(runtime_path) == artifacts["runtime"]["sha256"]
    assert sha256(builder_path) == artifacts["builder"]["sha256"]
    assert notebook["metadata"]["arc2_smoke"]["runtime_sha256"] == artifacts["runtime"]["sha256"]
    assert (
        notebook["metadata"]["arc2_smoke"]["parent_runtime_sha256"]
        == artifacts["parent_runtime_sha256"]
    )
    assert receipt["external_push_authorized"] is False
    assert receipt["external_action_taken"] is False
    assert receipt["local_checks"]["no_training_solutions_reference"] is True
    assert receipt["stop_rule"].startswith("If any runtime smoke guard fails")

    # Preserve the later external-state boundary separately from the historical
    # pre-push receipt.  This test is local-only and must never infer a terminal
    # Kaggle state from the last RUNNING observation.
    assert sha256(run_manifest_path) == (
        "48f4447086b40541079bb4eb9625621330d421284007accda5233305992f5ae7"
    )
    assert sha256(boundary_receipt_path) == (
        "60d6c77bd1fd499630a88510635fec25dc867487ae2ea37d81400e049d91ae63"
    )
    assert run_manifest["kernel"] == metadata["id"]
    assert run_manifest["kernel_version"] == 1
    assert run_manifest["status"] == "RUNNING"
    assert run_manifest["further_external_actions_authorized"] is False
    assert boundary_receipt["artifact_status"] == (
        "PUSHED_RUNNING_AT_LATER_LOCAL_ONLY_SAFETY_BOUNDARY"
    )
    assert boundary_receipt["last_authoritative_status"] == "RUNNING"
    assert boundary_receipt["further_external_actions_authorized"] is False
    assert boundary_receipt["accuracy_use"] == "forbidden"
    assert datetime.datetime.fromisoformat(run_manifest["status_checked_at_cst"]) < (
        datetime.datetime.fromisoformat(run_manifest["safety_boundary_received_at_cst"])
    )

    print("TRM V2 local behavioral regression passed")


if __name__ == "__main__":
    main()
