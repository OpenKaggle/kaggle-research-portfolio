#!/usr/bin/env python3
"""Fail-closed audit for the single public Qwen ARC-AGI-2 anchor."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "paper/manifests/public_anchor_control_plane_v1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_bound(root: Path, binding: dict[str, Any], label: str, violations: list[str]) -> Path | None:
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        violations.append(f"{label}_binding_fields_invalid")
        return None
    path = (root / binding["path"]).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        violations.append(f"{label}_outside_project")
        return None
    if not path.is_file():
        violations.append(f"{label}_missing")
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", str(binding["sha256"])):
        violations.append(f"{label}_sha256_invalid")
    elif sha256(path) != binding["sha256"]:
        violations.append(f"{label}_sha256_mismatch")
    return path


def cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def valid_grid(grid: Any) -> bool:
    if not isinstance(grid, list) or not 1 <= len(grid) <= 30:
        return False
    if not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30:
        return False
    width = len(grid[0])
    return all(
        isinstance(row, list)
        and len(row) == width
        and all(type(value) is int and 0 <= value <= 9 for value in row)
        for row in grid
    )


def validate_submission(challenges: Any, submission: Any, violations: list[str]) -> tuple[int, int]:
    if not isinstance(challenges, dict) or not isinstance(submission, dict):
        violations.append("public_output_not_objects")
        return 0, 0
    if set(submission) != set(challenges):
        violations.append("public_output_task_coverage_mismatch")
    output_count = 0
    for task_id, task in challenges.items():
        rows = submission.get(task_id)
        expected = len(task.get("test", [])) if isinstance(task, dict) else -1
        if not isinstance(rows, list) or len(rows) != expected:
            violations.append(f"public_output_row_count_invalid:{task_id}")
            continue
        output_count += len(rows)
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"attempt_1", "attempt_2"}:
                violations.append(f"public_output_attempt_keys_invalid:{task_id}")
                continue
            if not all(valid_grid(row[key]) for key in ("attempt_1", "attempt_2")):
                violations.append(f"public_output_grid_invalid:{task_id}")
    return len(submission), output_count


def audit_payload(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema_version") != 1:
        violations.append("schema_version_invalid")
    control_status = manifest.get("status")
    post_dry_run_statuses = {
        "DRY_RUN_PASSED_SUBMISSION_ELIGIBLE",
        "PUBLIC_ANCHOR_SUBMITTED_RUNNING",
    }
    if control_status not in {"FROZEN_PRE_DRY_RUN", *post_dry_run_statuses}:
        violations.append("status_invalid")
    if manifest.get("route") != "SINGLE_PUBLIC_QWEN_ANCHOR_NO_V2_NO_TRM":
        violations.append("route_invalid")
    if manifest.get("single_anchor_enforced") is not True:
        violations.append("single_anchor_not_enforced")

    survey_path = resolve_bound(root, manifest.get("survey_receipt"), "survey", violations)
    source = manifest.get("public_source", {})
    candidate = manifest.get("candidate", {})
    dependencies = manifest.get("dependencies", {})
    source_nb_path = resolve_bound(root, source.get("notebook"), "source_notebook", violations)
    source_meta_path = resolve_bound(root, source.get("metadata"), "source_metadata", violations)
    candidate_nb_path = resolve_bound(root, candidate.get("notebook"), "candidate_notebook", violations)
    candidate_meta_path = resolve_bound(root, candidate.get("metadata"), "candidate_metadata", violations)
    dry_run_receipt_path = None
    if control_status in post_dry_run_statuses:
        dry_run_receipt_path = resolve_bound(
            root,
            manifest.get("kaggle_dry_run_receipt"),
            "kaggle_dry_run_receipt",
            violations,
        )

    dependency_bindings = {
        "bootstrap_notebook": dependencies.get("bootstrap_notebook"),
        "bootstrap_metadata": dependencies.get("bootstrap_metadata"),
        "model_access_license_receipt": dependencies.get("model_access_license_receipt"),
        "local_asset_verification": dependencies.get("local_asset_verification"),
        "competition_manifest": dependencies.get("competition_manifest"),
    }
    resolved_dependencies = {
        name: resolve_bound(root, binding, name, violations)
        for name, binding in dependency_bindings.items()
    }

    expected_source_ref = "qiuqiuh/arc-highscore-lb3389-replica"
    if source.get("ref") != expected_source_ref or source.get("displayed_score") != 0.3181:
        violations.append("single_public_source_identity_invalid")
    if source.get("score_status") != "SOURCE_PAGE_CLAIM_NOT_INDEPENDENTLY_REPRODUCED":
        violations.append("public_score_claim_boundary_missing")
    if candidate.get("algorithm_change_from_public_source") != "NONE_BYTE_IDENTICAL_NOTEBOOK":
        violations.append("candidate_algorithm_change_invalid")
    if source.get("notebook", {}).get("sha256") != candidate.get("notebook", {}).get("sha256"):
        violations.append("candidate_not_byte_identical_to_source")

    survey = load_json(survey_path) if survey_path else {}
    rules = survey.get("official_rules_observed", {}) if isinstance(survey, dict) else {}
    required_rules = {
        "submission_limit_per_day": 1,
        "maximum_final_submissions": 2,
        "cpu_runtime_limit_hours": 12,
        "gpu_runtime_limit_hours": 12,
        "internet_must_be_disabled": True,
        "public_freely_available_external_data_and_models_allowed": True,
        "submission_filename": "submission.json",
        "competition_data_license": "Apache-2.0",
        "winner_license": "CC BY 4.0",
    }
    if any(rules.get(key) != value for key, value in required_rules.items()):
        violations.append("official_rule_snapshot_invalid")
    selected = survey.get("selected_anchor", {}) if isinstance(survey, dict) else {}
    if selected.get("ref") != expected_source_ref or selected.get("displayed_score") != 0.3181:
        violations.append("survey_selected_anchor_invalid")
    if survey.get("claim_boundary") is None:
        violations.append("survey_claim_boundary_missing")

    source_meta = load_json(source_meta_path) if source_meta_path else {}
    candidate_meta = load_json(candidate_meta_path) if candidate_meta_path else {}
    expected_inputs = {
        "kernel_sources": ["sorokin/pip-install-unsloth-flash-patch"],
        "competition_sources": ["arc-prize-2026-arc-agi-2"],
        "model_sources": ["sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1"],
    }
    if source_meta.get("id") != expected_source_ref or source_meta.get("is_private") is not False:
        violations.append("source_metadata_identity_invalid")
    for key, value in expected_inputs.items():
        if source_meta.get(key) != value or candidate_meta.get(key) != value:
            violations.append(f"metadata_{key}_invalid")
    expected_candidate_meta = {
        "id": "jahyee/arc2-public-qwen-lb3181-anchor-v1",
        "code_file": "arc2-public-qwen-lb3181-anchor-v1.ipynb",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": False,
        "machine_shape": "NvidiaL4",
    }
    if any(candidate_meta.get(key) != value for key, value in expected_candidate_meta.items()):
        violations.append("candidate_metadata_runtime_policy_invalid")
    if candidate.get("kernel_ref") != expected_candidate_meta["id"]:
        violations.append("candidate_kernel_ref_invalid")
    if control_status in post_dry_run_statuses:
        expected_resolved_identity = {
            "resolved_kaggle_ref": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
            "kaggle_kernel_id": 134648497,
            "kaggle_run_id": 350403559,
            "kaggle_version": 1,
        }
        if any(candidate.get(key) != value for key, value in expected_resolved_identity.items()):
            violations.append("resolved_kaggle_identity_invalid")

    notebook = load_json(candidate_nb_path) if candidate_nb_path else {}
    cells = notebook.get("cells", []) if isinstance(notebook, dict) else []
    if len(cells) != 9:
        violations.append("candidate_notebook_cell_count_invalid")
    if any(cell.get("outputs") for cell in cells if isinstance(cell, dict)):
        violations.append("candidate_notebook_contains_outputs")
    notebook_text = "\n".join(cell_source(cell) for cell in cells if isinstance(cell, dict))
    forbidden = ["conservative_agreement_stable_v2", "TinyRecursiveModels", "trm_runtime", "TRM hybrid"]
    if any(token in notebook_text for token in forbidden):
        violations.append("old_v2_or_trm_lineage_detected")
    required_fragments = [
        "global_end_time = time.time() + 12 * 3600 - 600",
        "KAGGLE_IS_COMPETITION_RERUN",
        "arc-agi_test_challenges.json",
        "arc-agi_evaluation_challenges.json",
        "arc-agi_evaluation_solutions.json",
        "spend_time > 1200",
        "nprocs=4",
        'with open("submission.json", "w")',
    ]
    for fragment in required_fragments:
        if fragment not in notebook_text:
            violations.append(f"candidate_required_fragment_missing:{fragment}")
    if "arc-agi_test_solutions" in notebook_text:
        violations.append("test_solution_reference_detected")
    expected_smoke_filter = 'if key not in ["0934a4d8", "36a08778", "981571dc", "aa4ec2a5"]:'
    if expected_smoke_filter not in notebook_text:
        violations.append("public_dry_run_four_task_filter_missing")

    writefiles: dict[str, str] = {}
    for cell in cells:
        source_text = cell_source(cell)
        if source_text.startswith("%%writefile ") and "\n" in source_text:
            first, body = source_text.split("\n", 1)
            writefiles[first.split(maxsplit=1)[1]] = body

    dry_run = manifest.get("downloaded_public_dry_run", {})
    dry_files = dry_run.get("files", {}) if isinstance(dry_run, dict) else {}
    resolved_dry_files = {
        name: resolve_bound(root, binding, f"public_output_{name.replace('.', '_')}", violations)
        for name, binding in dry_files.items()
    }
    for name in ("arc_loader.py", "arc_decoder.py", "arc_solver.py", "starter.py"):
        path = resolved_dry_files.get(name)
        if name not in writefiles or path is None:
            violations.append(f"writefile_binding_missing:{name}")
        elif path.read_text(encoding="utf-8").rstrip("\n") != writefiles[name].rstrip("\n"):
            violations.append(f"downloaded_writefile_drift:{name}")

    challenges_path = root / "official/competition_files/arc-agi_evaluation_challenges.json"
    solutions_path = root / "official/competition_files/arc-agi_evaluation_solutions.json"
    submission_path = resolved_dry_files.get("submission.json")
    task_count = output_count = exact = 0
    if submission_path and challenges_path.is_file() and solutions_path.is_file():
        challenges = load_json(challenges_path)
        solutions = load_json(solutions_path)
        submission = load_json(submission_path)
        task_count, output_count = validate_submission(challenges, submission, violations)
        if set(solutions) != set(challenges):
            violations.append("public_evaluation_solution_alignment_invalid")
        else:
            exact = sum(
                any(row[attempt] == solutions[task_id][index] for attempt in ("attempt_1", "attempt_2"))
                for task_id, rows in submission.items()
                for index, row in enumerate(rows)
            )
    else:
        violations.append("public_evaluation_validation_inputs_missing")
    expected_counts = {
        "task_count": 120,
        "output_count": 172,
        "computed_task_count": 4,
        "exact_pass2_outputs": 3,
        "exact_pass2_denominator": 172,
        "accuracy_claim_allowed": False,
    }
    if any(dry_run.get(key) != value for key, value in expected_counts.items()):
        violations.append("downloaded_public_dry_run_boundary_invalid")
    if task_count != 120 or output_count != 172 or exact != 3:
        violations.append("downloaded_public_output_measurement_mismatch")

    terminal_dry_run: dict[str, Any] = {}
    terminal_submission_counts = {"tasks": 0, "outputs": 0, "exact_pass2": 0}
    if control_status in post_dry_run_statuses and dry_run_receipt_path:
        terminal_dry_run = load_json(dry_run_receipt_path)
        attempt = terminal_dry_run.get("attempt", {})
        kernel = terminal_dry_run.get("kaggle_kernel", {})
        if terminal_dry_run.get("receipt_type") != "arc2_public_qwen_anchor_private_kaggle_dry_run":
            violations.append("kaggle_dry_run_receipt_type_invalid")
        expected_attempt = {
            "ordinal": 1,
            "maximum_attempts": 2,
            "dependency_repairs_used": 0,
            "maximum_dependency_repairs": 1,
            "official_status": "COMPLETE",
            "outcome": "PASSED",
        }
        if any(attempt.get(key) != value for key, value in expected_attempt.items()):
            violations.append("kaggle_dry_run_attempt_receipt_invalid")
        expected_kernel = {
            "requested_ref": "jahyee/arc2-public-qwen-lb3181-anchor-v1",
            "resolved_ref": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
            "kernel_id": 134648497,
            "run_id": 350403559,
            "version": 1,
            "visibility": "private",
            "internet_enabled": False,
            "accelerator": "NVIDIA L4 x4",
            "runtime_seconds": 1697.0,
            "completion_banner": "1697.0 second run - successful",
        }
        if any(kernel.get(key) != value for key, value in expected_kernel.items()):
            violations.append("kaggle_dry_run_kernel_receipt_invalid")
        if not isinstance(kernel.get("runtime_seconds"), (int, float)) or kernel.get("runtime_seconds", 0) >= 12 * 3600:
            violations.append("kaggle_dry_run_runtime_limit_invalid")

        source_bindings = terminal_dry_run.get("source_bindings", {})
        resolved_terminal_sources = {
            name: resolve_bound(root, binding, f"dry_run_{name}", violations)
            for name, binding in source_bindings.items()
        }
        required_source_names = {
            "pre_push_notebook",
            "pre_push_metadata",
            "pulled_version_notebook",
            "pulled_version_metadata",
        }
        if set(resolved_terminal_sources) != required_source_names:
            violations.append("kaggle_dry_run_source_binding_set_invalid")
        pulled_nb = resolved_terminal_sources.get("pulled_version_notebook")
        pulled_meta = resolved_terminal_sources.get("pulled_version_metadata")
        if pulled_nb and candidate_nb_path and sha256(pulled_nb) != sha256(candidate_nb_path):
            violations.append("kaggle_pulled_notebook_drift")
        pulled_metadata = load_json(pulled_meta) if pulled_meta else {}
        expected_pulled_meta = {
            "id": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
            "id_no": 134648497,
            "code_file": "arc2-public-qwen-lb31-81-anchor-v1.ipynb",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": False,
            "machine_shape": "NvidiaL4",
        }
        if any(pulled_metadata.get(key) != value for key, value in expected_pulled_meta.items()):
            violations.append("kaggle_pulled_metadata_invalid")
        for key, value in expected_inputs.items():
            if pulled_metadata.get(key) != value:
                violations.append(f"kaggle_pulled_metadata_{key}_invalid")

        output_bindings = terminal_dry_run.get("output_bindings", {})
        required_output_names = {
            "log",
            "submission.json",
            "arc_loader.py",
            "arc_decoder.py",
            "arc_solver.py",
            "starter.py",
        }
        if set(output_bindings) != required_output_names:
            violations.append("kaggle_dry_run_output_binding_set_invalid")
        resolved_terminal_outputs: dict[str, Path | None] = {}
        for name, binding in output_bindings.items():
            minimal_binding = (
                {"path": binding.get("path"), "sha256": binding.get("sha256")}
                if isinstance(binding, dict)
                else binding
            )
            resolved_terminal_outputs[name] = resolve_bound(
                root,
                minimal_binding,
                f"dry_run_output_{name.replace('.', '_')}",
                violations,
            )
        log_path = resolved_terminal_outputs.get("log")
        log_text = log_path.read_text(encoding="utf-8") if log_path else ""
        if output_bindings.get("log", {}).get("bytes") != 21795:
            violations.append("kaggle_dry_run_log_size_receipt_invalid")
        if log_path and log_path.stat().st_size != output_bindings.get("log", {}).get("bytes"):
            violations.append("kaggle_dry_run_log_size_mismatch")
        if re.search(r"traceback|exception|\berror\b|failed|failure", log_text, flags=re.IGNORECASE):
            violations.append("kaggle_dry_run_log_failure_detected")
        if len(re.findall(r"\[Rank \d\] start!", log_text)) != 4:
            violations.append("kaggle_dry_run_rank_start_count_invalid")
        if len(re.findall(r"\[Rank \d\] done!", log_text)) != 4:
            violations.append("kaggle_dry_run_rank_done_count_invalid")
        expected_finished_tasks = {"0934a4d8", "36a08778", "981571dc", "aa4ec2a5"}
        finished_tasks = set(re.findall(r"finished ([0-9a-f]{8}) in [0-9.]+s", log_text))
        if finished_tasks != expected_finished_tasks:
            violations.append("kaggle_dry_run_terminal_task_set_invalid")
        required_log_fragments = [
            "*** Generating submission for 5 outputs...",
            "acc:   2.5/  4 ('score_full_probmul_3')",
            "acc:   2.5/  4 ('score_kgmon')",
            "*** Reload score: 2.5",
        ]
        if any(fragment not in log_text for fragment in required_log_fragments):
            violations.append("kaggle_dry_run_log_evidence_incomplete")

        terminal_submission_path = resolved_terminal_outputs.get("submission.json")
        if terminal_submission_path and challenges_path.is_file() and solutions_path.is_file():
            terminal_submission = load_json(terminal_submission_path)
            terminal_task_count, terminal_output_count = validate_submission(
                load_json(challenges_path), terminal_submission, violations
            )
            terminal_solutions = load_json(solutions_path)
            terminal_exact = sum(
                any(
                    row[attempt_key] == terminal_solutions[task_id][index]
                    for attempt_key in ("attempt_1", "attempt_2")
                )
                for task_id, rows in terminal_submission.items()
                for index, row in enumerate(rows)
            )
            non_placeholder_tasks = {
                task_id
                for task_id, rows in terminal_submission.items()
                if any(row["attempt_1"] != [[0]] or row["attempt_2"] != [[0]] for row in rows)
            }
            if non_placeholder_tasks != expected_finished_tasks:
                violations.append("kaggle_dry_run_non_placeholder_task_set_invalid")
            terminal_submission_counts = {
                "tasks": terminal_task_count,
                "outputs": terminal_output_count,
                "exact_pass2": terminal_exact,
            }
            if terminal_submission_counts != {"tasks": 120, "outputs": 172, "exact_pass2": 3}:
                violations.append("kaggle_dry_run_submission_measurement_mismatch")
        else:
            violations.append("kaggle_dry_run_submission_validation_inputs_missing")

        for name in ("arc_loader.py", "arc_decoder.py", "arc_solver.py", "starter.py"):
            output_path = resolved_terminal_outputs.get(name)
            if output_path is None or name not in writefiles:
                violations.append(f"kaggle_dry_run_writefile_binding_missing:{name}")
            elif output_path.read_text(encoding="utf-8").rstrip("\n") != writefiles[name].rstrip("\n"):
                violations.append(f"kaggle_dry_run_writefile_drift:{name}")

        schema_evidence = terminal_dry_run.get("schema_evidence", {})
        if (
            schema_evidence.get("task_count") != 120
            or schema_evidence.get("output_count") != 172
            or schema_evidence.get("task_keys_equal_official_evaluation_challenges") is not True
            or schema_evidence.get("attempt_keys_exact") != ["attempt_1", "attempt_2"]
            or schema_evidence.get("all_grids_valid") is not True
            or schema_evidence.get("non_placeholder_tasks_equal_computed_tasks") is not True
        ):
            violations.append("kaggle_dry_run_schema_receipt_invalid")
        receipt_gates = terminal_dry_run.get("gates", {})
        required_gate_names = {
            "official_status_COMPLETE",
            "return_or_notebook_exception_absent",
            "submission_json_present",
            "submission_schema_120_tasks_172_outputs",
            "all_four_public_smoke_tasks_reach_terminal_processing",
            "runtime_below_12_hours",
            "source_and_dependency_hashes_match",
            "all_pass",
        }
        if set(receipt_gates) != required_gate_names or not all(receipt_gates.values()):
            violations.append("kaggle_dry_run_gate_receipt_invalid")
        competition_submission = terminal_dry_run.get("competition_submission", {})
        if competition_submission != {"made": False, "submission_quota_consumed": False}:
            violations.append("kaggle_dry_run_submission_boundary_invalid")

    submission_launch: dict[str, Any] = {}
    if control_status == "PUBLIC_ANCHOR_SUBMITTED_RUNNING":
        launch_path = resolve_bound(
            root,
            manifest.get("submission_launch_receipt"),
            "submission_launch_receipt",
            violations,
        )
        submission_launch = load_json(launch_path) if launch_path else {}
        if submission_launch.get("receipt_type") != "arc2_public_qwen_anchor_competition_submission_launch":
            violations.append("submission_launch_receipt_type_invalid")
        pre_gate = submission_launch.get("pre_submission_gate", {})
        expected_pre_gate = {
            "local_control_plane_audit_passed": True,
            "private_kaggle_dry_run_passed": True,
            "submissions_before_launch": 0,
            "daily_submissions_remaining_before_launch": 1,
            "dependency_repairs_used": 0,
        }
        if pre_gate != expected_pre_gate:
            violations.append("submission_launch_pre_gate_invalid")
        submitted_artifact = submission_launch.get("submitted_artifact", {})
        expected_submitted_artifact = {
            "kernel_ref": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
            "kernel_id": 134648497,
            "run_id": 350403559,
            "version": 1,
            "notebook_sha256": "95c9274c8c17d69e2e91867bfc6ef93d9ce1f046eec2a85a3cc6148bf961bcbe",
            "output_file": "submission.json",
        }
        if submitted_artifact != expected_submitted_artifact:
            violations.append("submission_launch_artifact_invalid")
        launched_submission = submission_launch.get("submission", {})
        expected_launched_submission = {
            "id": 56287444,
            "submitted_at_utc": "2026-09-16T21:08:35.533000Z",
            "submitted_at_cst": "2026-09-17T05:08:35.533000+08:00",
            "cli_status": "SubmissionStatus.PENDING",
            "ui_status": "Notebook Running",
            "public_score": None,
            "private_score": None,
            "submissions_remaining_today_after_launch": 0,
        }
        if launched_submission != expected_launched_submission:
            violations.append("submission_launch_state_invalid")
        monitor = submission_launch.get("monitor", {})
        if (
            monitor.get("kind") != "heartbeat"
            or monitor.get("automation_id") != "arc2-public-anchor-submission-monitor"
            or monitor.get("cadence_minutes") != 15
            or monitor.get("quiet_while_unchanged") is not True
            or monitor.get("below_public_score_action")
            != {"threshold": 0.29, "action": "ARCHIVE_WITH_TERMINAL_SCORE_RECEIPT"}
        ):
            violations.append("submission_launch_monitor_invalid")
        prohibitions = submission_launch.get("prohibitions", {})
        if not prohibitions or not all(value is True for value in prohibitions.values()):
            violations.append("submission_launch_prohibitions_invalid")

    asset_path = resolved_dependencies.get("local_asset_verification")
    asset_receipt = load_json(asset_path) if asset_path else {}
    if asset_receipt.get("complete") is not True or asset_receipt.get("qwen", {}).get("complete") is not True:
        violations.append("local_qwen_asset_not_verified")
    license_path = resolved_dependencies.get("model_access_license_receipt")
    license_receipt = load_json(license_path) if license_path else {}
    qwen = license_receipt.get("assets", {}).get("qwen_finetune", {})
    if (
        qwen.get("kaggle_ref") != "sorokin/qwen3_4b_grids15_sft139"
        or qwen.get("instance") != "Transformers/bfloat16/1"
        or qwen.get("is_private") is not False
        or qwen.get("license_name") != "Apache 2.0"
    ):
        violations.append("qwen_public_access_license_binding_invalid")

    gates = manifest.get("gates", {})
    kaggle_gate = gates.get("kaggle_dry_run", {}) if isinstance(gates, dict) else {}
    score_gate = gates.get("public_score", {}) if isinstance(gates, dict) else {}
    if kaggle_gate.get("maximum_attempts") != 2 or kaggle_gate.get("maximum_dependency_repairs") != 1:
        violations.append("dry_run_failure_budget_invalid")
    if score_gate.get("minimum") != 0.29:
        violations.append("public_score_floor_invalid")
    if control_status in {"FROZEN_PRE_DRY_RUN", "DRY_RUN_PASSED_SUBMISSION_ELIGIBLE"}:
        if score_gate.get("status") != "NOT_SUBMITTED":
            violations.append("public_score_gate_invalid")
    elif control_status == "PUBLIC_ANCHOR_SUBMITTED_RUNNING":
        expected_pending_score_gate = {
            "status": "PENDING",
            "submission_id": 56287444,
            "submitted_kernel_ref": "jahyee/arc2-public-qwen-lb31-81-anchor-v1",
            "submitted_version": 1,
            "public_score": None,
        }
        if any(score_gate.get(key) != value for key, value in expected_pending_score_gate.items()):
            violations.append("pending_public_score_gate_invalid")
    authorization = manifest.get("authorization", {})
    if control_status == "FROZEN_PRE_DRY_RUN":
        if kaggle_gate.get("attempts_used") != 0 or kaggle_gate.get("dependency_repairs_used") != 0:
            violations.append("pre_run_counters_not_zero")
        if kaggle_gate.get("status") != "NOT_STARTED":
            violations.append("pre_run_status_invalid")
        if authorization.get("submission_allowed_now") is not False:
            violations.append("submission_prematurely_allowed")
    elif control_status == "DRY_RUN_PASSED_SUBMISSION_ELIGIBLE":
        if kaggle_gate.get("attempts_used") != 1 or kaggle_gate.get("dependency_repairs_used") != 0:
            violations.append("passed_run_counters_invalid")
        if kaggle_gate.get("status") != "PASSED":
            violations.append("passed_run_status_invalid")
        if authorization.get("submission_allowed_now") is not True:
            violations.append("submission_eligibility_missing")
    elif control_status == "PUBLIC_ANCHOR_SUBMITTED_RUNNING":
        if kaggle_gate.get("attempts_used") != 1 or kaggle_gate.get("dependency_repairs_used") != 0:
            violations.append("submitted_run_counters_invalid")
        if kaggle_gate.get("status") != "PASSED":
            violations.append("submitted_run_dry_run_status_invalid")
        if authorization.get("submission_allowed_now") is not False:
            violations.append("additional_submission_not_blocked")
    if authorization.get("old_v2_trm_actions_allowed") is not False:
        violations.append("old_v2_trm_actions_not_blocked")
    if authorization.get("additional_public_anchor_allowed") is not False:
        violations.append("additional_public_anchor_not_blocked")

    warnings.extend(
        [
            "public_source_score_not_independently_reproduced",
            "downloaded_public_output_computes_only_four_evaluation_tasks",
            "python_hash_seed_is_not_fixed_in_public_source",
            "third_party_notebook_release_license_not_cleared",
        ]
    )
    return {
        "schema_version": 1,
        "audit": "single_public_qwen_anchor_local_gate",
        "passes": not violations,
        "route": manifest.get("route"),
        "selected_public_anchor": source.get("ref"),
        "displayed_public_score": source.get("displayed_score"),
        "candidate_kernel_ref": candidate.get("kernel_ref"),
        "candidate_notebook_sha256": candidate.get("notebook", {}).get("sha256"),
        "control_status": control_status,
        "local_public_output": {
            "tasks": task_count,
            "outputs": output_count,
            "exact_pass2": exact,
            "computed_source_tasks": dry_run.get("computed_task_count"),
            "accuracy_claim_allowed": False,
        },
        "kaggle_dry_run": {
            "status": kaggle_gate.get("status"),
            "attempts_used": kaggle_gate.get("attempts_used"),
            "dependency_repairs_used": kaggle_gate.get("dependency_repairs_used"),
            "resolved_kernel_ref": candidate.get("resolved_kaggle_ref"),
            "runtime_seconds": terminal_dry_run.get("kaggle_kernel", {}).get("runtime_seconds"),
            "submission": terminal_submission_counts,
        },
        "competition_submission": {
            "status": score_gate.get("status"),
            "submission_id": score_gate.get("submission_id"),
            "submitted_kernel_ref": score_gate.get("submitted_kernel_ref"),
            "submitted_version": score_gate.get("submitted_version"),
            "public_score": score_gate.get("public_score"),
            "monitor_automation_id": submission_launch.get("monitor", {}).get("automation_id"),
        },
        "failure_budget": {
            "maximum_kaggle_dry_runs": kaggle_gate.get("maximum_attempts"),
            "maximum_dependency_repairs": kaggle_gate.get("maximum_dependency_repairs"),
            "public_score_floor": score_gate.get("minimum"),
        },
        "violations": violations,
        "warnings": warnings,
        "next_action": (
            (
                "PUSH_ONE_PRIVATE_KAGGLE_DRY_RUN_NO_SUBMISSION"
                if control_status == "FROZEN_PRE_DRY_RUN"
                else (
                    "CHECK_DAILY_QUOTA_THEN_SUBMIT_ONE_COMPETITION_ANCHOR"
                    if control_status == "DRY_RUN_PASSED_SUBMISSION_ELIGIBLE"
                    else "WAIT_FOR_SUBMISSION_56287444_TERMINAL_STATE"
                )
            )
            if not violations
            else "STOP_FIX_LOCAL_CONTROL_PLANE"
        ),
        "claim_boundary": (
            "The sole authorized competition submission is now in flight and all further submissions, kernel pushes, repairs, alternate anchors, and old V2/TRM actions are blocked. Until Kaggle publishes its Public Score, this is not an independent 31.81 reproduction, hidden-set result, generalization result, or public-release clearance."
        ),
    }


def audit_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    root = (path.parent / manifest.get("project_root", "../..")).resolve()
    return audit_payload(root, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, nargs="?", default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_manifest(args.manifest.resolve())
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
