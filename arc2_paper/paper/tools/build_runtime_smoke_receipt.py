#!/usr/bin/env python3
"""Build a terminal receipt for the already-pushed runtime smoke.

This tool is deliberately local-only.  It never invokes Kaggle.  It consumes a
previously captured read-only terminal-status manifest and, when available,
the downloaded kernel outputs.  The active three-stage contract supplies the
frozen identity and artifact hashes; no caller-provided hypothesis or success
claim is accepted.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

try:
    from paper.tools.audit_three_stage_pipeline import audit
    from paper.tools.build_stage_receipt import contract_root
except ModuleNotFoundError:  # Direct execution from paper/tools.
    from audit_three_stage_pipeline import audit  # type: ignore
    from build_stage_receipt import contract_root  # type: ignore


KERNEL = "jahyee/arc2-trm-wandb-log-compat-smoke-v2"
KERNEL_VERSION = 1
TASK_ID = "bc1d5164"
RUNTIME_SHA256 = "8ac51e00df2f220ff8742bddceae9a84a407e426734975db2f55234460a48776"
PARENT_RUNTIME_SHA256 = "17d8757c874f14d20aee0368054137874e8df16f2dd8f0fe9e521d5aff2c9e82"
TERMINAL_STATUSES = {"COMPLETE", "ERROR", "CANCELLED"}
SHA256 = re.compile(r"[0-9a-f]{64}")
OBSERVATION_FIELDS = {
    "schema_version",
    "kernel",
    "kernel_version",
    "authoritative_kernel_status",
    "status_verified_at_cst",
    "observation_mode",
    "raw_status",
    "artifacts_downloaded",
}
SOURCE_RECEIPT_FIELDS = {
    "purpose",
    "repair_id",
    "single_change",
    "task_id",
    "task_count",
    "epochs",
    "expected_optimizer_steps",
    "runtime_sha256",
    "parent_runtime_sha256",
    "challenge_sha256",
    "submission_sha256",
    "elapsed_seconds",
    "returncode",
    "guards",
    "all_guards_passed",
}
GUARD_FIELDS = {
    "runtime_returncode_zero",
    "checkpoint_loaded",
    "optimizer_constructed",
    "scheduler_path_preserved",
    "first_step_checkpoint_saved",
    "submission_exists",
    "submission_schema_valid",
}
TERMINAL_GUARD_FIELDS = GUARD_FIELDS | {"all_guards_passed"}
SOURCE_ARTIFACT_FIELDS = {
    "run_manifest.json",
    "trm-smoke-receipt.json",
    "trm-smoke.log",
    "trm_submission.json",
    "notebook_sha256",
    "kernel_metadata_sha256",
}
TERMINAL_RECEIPT_FIELDS = {
    "schema_version",
    "artifact_status",
    "kernel",
    "kernel_version",
    "authoritative_kernel_status",
    "status_verified_at_cst",
    "is_private",
    "internet_enabled",
    "data_boundary",
    "purpose",
    "task_id",
    "task_count",
    "epochs",
    "expected_optimizer_steps",
    "runtime_sha256",
    "parent_runtime_sha256",
    "elapsed_seconds",
    "returncode",
    "guards",
    "source_artifacts",
    "source_paths",
    "claim_boundary",
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing or extra:
        raise ValueError(f"{label} fields differ: missing={missing}, extra={extra}")
    return value


def parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def relative_project_file(
    root: pathlib.Path,
    raw: pathlib.Path | str,
    label: str,
) -> tuple[pathlib.Path, str]:
    path = pathlib.Path(raw).resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} must be inside the contract project root") from error
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return path, relative.as_posix()


def receipt_project_file(
    root: pathlib.Path,
    raw: Any,
    label: str,
) -> pathlib.Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a repository-relative file path")
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} is unsafe")
    path = (root / pathlib.Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} escapes the project root") from error
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {raw}")
    return path


def bound_json(root: pathlib.Path, binding: Any, label: str) -> dict[str, Any]:
    binding = exact_keys(binding, {"path", "sha256"}, f"{label} binding")
    path = receipt_project_file(root, binding["path"], label)
    if not isinstance(binding["sha256"], str) or digest(path) != binding["sha256"]:
        raise ValueError(f"{label} hash mismatch")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_manifest_artifact_path(root: pathlib.Path, raw: Any, label: str) -> pathlib.Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} path missing from the frozen run manifest")
    relative = pathlib.PurePosixPath(raw)
    parts = relative.parts
    if parts and parts[0] == root.name:
        parts = parts[1:]
    if not parts or ".." in parts:
        raise ValueError(f"{label} path is unsafe")
    return receipt_project_file(root, pathlib.PurePosixPath(*parts).as_posix(), label)


def frozen_identity(
    contract_path: pathlib.Path,
    contract: dict[str, Any],
) -> tuple[pathlib.Path, dict[str, Any], str, str, str, str]:
    root = contract_root(contract_path, contract)
    prerequisite = contract.get("runtime_smoke_prerequisite")
    if not isinstance(prerequisite, dict):
        raise ValueError("runtime-smoke prerequisite is missing")
    if prerequisite.get("status") != "UNKNOWN" or prerequisite.get("terminal_receipt") is not None:
        raise ValueError("runtime-smoke prerequisite must still be UNKNOWN and unbound")
    if prerequisite.get("kernel") != KERNEL or prerequisite.get("kernel_version") != KERNEL_VERSION:
        raise ValueError("runtime-smoke identity differs from the frozen target")
    frozen_run = bound_json(
        root,
        prerequisite.get("last_authorized_run_manifest"),
        "last_authorized_run_manifest",
    )
    if frozen_run.get("status") != "RUNNING":
        raise ValueError("last authorized run manifest is not the frozen RUNNING observation")
    if frozen_run.get("runtime_sha256") != RUNTIME_SHA256:
        raise ValueError("frozen runtime hash differs from the V2 repair")
    if frozen_run.get("parent_runtime_sha256") != PARENT_RUNTIME_SHA256:
        raise ValueError("frozen parent runtime hash differs from the V1 repair")
    notebook_hash = frozen_run.get("notebook_sha256")
    metadata_hash = frozen_run.get("kernel_metadata_sha256")
    if not isinstance(notebook_hash, str) or not SHA256.fullmatch(notebook_hash):
        raise ValueError("frozen notebook hash is invalid")
    if not isinstance(metadata_hash, str) or not SHA256.fullmatch(metadata_hash):
        raise ValueError("frozen kernel-metadata hash is invalid")
    artifacts = frozen_run.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("frozen run manifest artifact paths are missing")
    notebook_record = exact_keys(artifacts.get("notebook"), {"path", "sha256"}, "notebook")
    metadata_record = exact_keys(
        artifacts.get("kernel_metadata"), {"path", "sha256"}, "kernel_metadata"
    )
    if notebook_record["sha256"] != notebook_hash or metadata_record["sha256"] != metadata_hash:
        raise ValueError("frozen direct and nested notebook hashes disagree")
    notebook_path = normalize_manifest_artifact_path(root, notebook_record["path"], "notebook")
    metadata_path = normalize_manifest_artifact_path(root, metadata_record["path"], "kernel_metadata")
    if digest(notebook_path) != notebook_hash or digest(metadata_path) != metadata_hash:
        raise ValueError("current notebook or metadata differs from the pushed V2 artifact")
    boundary = prerequisite.get("authorization_boundary_cst")
    parse_timestamp(boundary, "authorization boundary")
    return root, prerequisite, notebook_hash, metadata_hash, notebook_path.as_posix(), metadata_path.as_posix()


def validate_observation(observation: Any, boundary_raw: Any) -> dict[str, Any]:
    observation = exact_keys(observation, OBSERVATION_FIELDS, "terminal observation")
    if observation.get("schema_version") != 1:
        raise ValueError("terminal observation schema_version must be 1")
    if observation.get("kernel") != KERNEL or observation.get("kernel_version") != KERNEL_VERSION:
        raise ValueError("terminal observation identity differs from the frozen kernel version")
    status = observation.get("authoritative_kernel_status")
    if status not in TERMINAL_STATUSES:
        raise ValueError("terminal observation is not terminal")
    if observation.get("observation_mode") != "READ_ONLY_KAGGLE_STATUS":
        raise ValueError("terminal observation mode must be READ_ONLY_KAGGLE_STATUS")
    if type(observation.get("artifacts_downloaded")) is not bool:
        raise ValueError("terminal observation artifacts_downloaded must be boolean")
    raw_status = observation.get("raw_status")
    if not isinstance(raw_status, str) or status.lower() not in raw_status.lower():
        raise ValueError("raw status does not contain the normalized terminal status")
    verified = parse_timestamp(observation.get("status_verified_at_cst"), "status_verified_at_cst")
    boundary = parse_timestamp(boundary_raw, "authorization_boundary_cst")
    if verified <= boundary:
        raise ValueError("terminal observation does not postdate the local-only boundary")
    return observation


def validate_source_receipt(
    payload: Any,
    submission_path: pathlib.Path | None,
) -> tuple[dict[str, bool], float, int]:
    payload = exact_keys(payload, SOURCE_RECEIPT_FIELDS, "trm-smoke-receipt")
    guards = exact_keys(payload.get("guards"), GUARD_FIELDS, "source smoke guards")
    if any(type(value) is not bool for value in guards.values()):
        raise ValueError("every source smoke guard must be boolean")
    if type(payload.get("all_guards_passed")) is not bool:
        raise ValueError("source all_guards_passed must be boolean")
    if payload["all_guards_passed"] != all(guards.values()):
        raise ValueError("source all_guards_passed disagrees with individual guards")
    expected = {
        "purpose": "runtime compatibility smoke; not an accuracy experiment",
        "repair_id": "offline_wandb_stdout_helper_v2",
        "task_id": TASK_ID,
        "task_count": 1,
        "epochs": 1,
        "expected_optimizer_steps": 1,
        "runtime_sha256": RUNTIME_SHA256,
        "parent_runtime_sha256": PARENT_RUNTIME_SHA256,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("source smoke receipt differs from the frozen V2 configuration")
    challenge_hash = payload.get("challenge_sha256")
    if not isinstance(challenge_hash, str) or not SHA256.fullmatch(challenge_hash):
        raise ValueError("source challenge hash is invalid")
    elapsed = payload.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed < 0:
        raise ValueError("source elapsed_seconds is invalid")
    returncode = payload.get("returncode")
    if type(returncode) is not int:
        raise ValueError("source returncode is invalid")
    if guards["runtime_returncode_zero"] != (returncode == 0):
        raise ValueError("source returncode and runtime guard disagree")
    submission_hash = payload.get("submission_sha256")
    if submission_path is None:
        if submission_hash is not None or guards["submission_exists"]:
            raise ValueError("source receipt claims a missing submission")
    else:
        if submission_hash != digest(submission_path) or not guards["submission_exists"]:
            raise ValueError("source submission hash or existence guard is inconsistent")
    if guards["submission_schema_valid"] and submission_path is None:
        raise ValueError("source receipt validates a missing submission")
    return dict(guards), float(elapsed), returncode


def validate_terminal_receipt(
    contract_path: pathlib.Path,
    receipt: Any,
) -> str:
    contract_path = contract_path.resolve()
    current = audit(contract_path)
    if not current["passes"]:
        raise ValueError("pipeline contract does not pass before runtime-smoke validation")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    root, prerequisite, notebook_hash, metadata_hash, _, _ = frozen_identity(
        contract_path, contract
    )
    receipt = exact_keys(receipt, TERMINAL_RECEIPT_FIELDS, "terminal smoke receipt")
    if receipt.get("schema_version") != 1 or receipt.get("artifact_status") != "terminal_runtime_smoke":
        raise ValueError("terminal smoke receipt schema or artifact status is invalid")
    fixed = {
        "kernel": KERNEL,
        "kernel_version": KERNEL_VERSION,
        "is_private": True,
        "internet_enabled": False,
        "task_id": TASK_ID,
        "task_count": 1,
        "epochs": 1,
        "expected_optimizer_steps": 1,
        "runtime_sha256": RUNTIME_SHA256,
        "parent_runtime_sha256": PARENT_RUNTIME_SHA256,
    }
    if any(receipt.get(key) != value for key, value in fixed.items()):
        raise ValueError("terminal smoke receipt differs from the frozen V2 identity")
    status = receipt.get("authoritative_kernel_status")
    if status not in TERMINAL_STATUSES:
        raise ValueError("terminal smoke receipt status is not terminal")
    verified = parse_timestamp(receipt.get("status_verified_at_cst"), "status_verified_at_cst")
    boundary = parse_timestamp(prerequisite.get("authorization_boundary_cst"), "authorization_boundary_cst")
    if verified <= boundary:
        raise ValueError("terminal smoke receipt does not postdate the authorization boundary")
    for field in ("data_boundary", "purpose", "claim_boundary"):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip():
            raise ValueError(f"terminal smoke receipt {field} is missing")

    guards = exact_keys(receipt.get("guards"), TERMINAL_GUARD_FIELDS, "terminal guards")
    if any(type(value) is not bool for value in guards.values()):
        raise ValueError("every terminal guard must be boolean")
    if guards["all_guards_passed"] != all(guards[name] for name in GUARD_FIELDS):
        raise ValueError("terminal all_guards_passed disagrees with individual guards")

    hashes = exact_keys(receipt.get("source_artifacts"), SOURCE_ARTIFACT_FIELDS, "source_artifacts")
    paths = exact_keys(receipt.get("source_paths"), SOURCE_ARTIFACT_FIELDS, "source_paths")
    for name in SOURCE_ARTIFACT_FIELDS:
        expected_hash = hashes[name]
        raw_path = paths[name]
        if expected_hash is None or raw_path is None:
            if expected_hash is not None or raw_path is not None:
                raise ValueError(f"source artifact {name} has only one of path/hash")
            continue
        if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash):
            raise ValueError(f"source artifact {name} hash is invalid")
        path = receipt_project_file(root, raw_path, f"source_paths.{name}")
        if digest(path) != expected_hash:
            raise ValueError(f"source artifact {name} changed after receipt construction")
    for name in ("run_manifest.json", "notebook_sha256", "kernel_metadata_sha256"):
        if hashes[name] is None:
            raise ValueError(f"required source artifact {name} is missing")
    if hashes["notebook_sha256"] != notebook_hash or hashes["kernel_metadata_sha256"] != metadata_hash:
        raise ValueError("terminal receipt notebook or metadata hash differs from the pushed V2 artifact")

    observation_path = receipt_project_file(root, paths["run_manifest.json"], "run_manifest.json")
    observation = validate_observation(
        json.loads(observation_path.read_text(encoding="utf-8")),
        prerequisite.get("authorization_boundary_cst"),
    )
    if status != observation["authoritative_kernel_status"] or receipt["status_verified_at_cst"] != observation["status_verified_at_cst"]:
        raise ValueError("terminal receipt and read-only observation disagree")

    source_receipt_path = None
    if paths["trm-smoke-receipt.json"] is not None:
        source_receipt_path = receipt_project_file(
            root, paths["trm-smoke-receipt.json"], "trm-smoke-receipt.json"
        )
    log_path = None
    if paths["trm-smoke.log"] is not None:
        log_path = receipt_project_file(root, paths["trm-smoke.log"], "trm-smoke.log")
    submission_path = None
    if paths["trm_submission.json"] is not None:
        submission_path = receipt_project_file(
            root, paths["trm_submission.json"], "trm_submission.json"
        )
    if source_receipt_path is None:
        if any(guards[name] for name in GUARD_FIELDS):
            raise ValueError("terminal receipt claims guards without a source smoke receipt")
        if receipt.get("elapsed_seconds") is not None or receipt.get("returncode") is not None:
            raise ValueError("terminal receipt claims runtime fields without a source smoke receipt")
    else:
        if log_path is None:
            raise ValueError("source smoke receipt exists without its log")
        source_guards, elapsed, returncode = validate_source_receipt(
            json.loads(source_receipt_path.read_text(encoding="utf-8")), submission_path
        )
        if any(guards[name] != source_guards[name] for name in GUARD_FIELDS):
            raise ValueError("terminal and source smoke guards disagree")
        if receipt.get("elapsed_seconds") != elapsed or receipt.get("returncode") != returncode:
            raise ValueError("terminal and source smoke runtime fields disagree")

    derived = "PASSED" if status == "COMPLETE" and guards["all_guards_passed"] else "FAILED"
    if derived == "PASSED":
        if not observation["artifacts_downloaded"]:
            raise ValueError("passing smoke lacks downloaded terminal artifacts")
        for name in ("trm-smoke-receipt.json", "trm-smoke.log", "trm_submission.json"):
            if hashes[name] is None:
                raise ValueError(f"passing smoke lacks {name}")
    return derived


def build_runtime_smoke_receipt(
    contract_path: pathlib.Path,
    observation_path: pathlib.Path,
    artifact_dir: pathlib.Path | None,
) -> dict[str, Any]:
    contract_path = contract_path.resolve()
    current = audit(contract_path)
    if not current["passes"]:
        raise ValueError("pipeline contract does not pass before runtime-smoke construction")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    root, prerequisite, notebook_hash, metadata_hash, notebook_raw, metadata_raw = frozen_identity(
        contract_path, contract
    )
    observation_path, observation_relative = relative_project_file(
        root, observation_path, "terminal observation"
    )
    observation = validate_observation(
        json.loads(observation_path.read_text(encoding="utf-8")),
        prerequisite.get("authorization_boundary_cst"),
    )

    artifact_paths: dict[str, pathlib.Path | None] = {
        "trm-smoke-receipt.json": None,
        "trm-smoke.log": None,
        "trm_submission.json": None,
    }
    if artifact_dir is not None:
        directory = artifact_dir.resolve()
        try:
            directory.relative_to(root)
        except ValueError as error:
            raise ValueError("artifact directory must be inside the contract project root") from error
        if not directory.is_dir():
            raise ValueError("artifact directory does not exist")
        for name in artifact_paths:
            candidate = directory / name
            if candidate.is_file():
                artifact_paths[name] = candidate

    source_receipt_path = artifact_paths["trm-smoke-receipt.json"]
    log_path = artifact_paths["trm-smoke.log"]
    submission_path = artifact_paths["trm_submission.json"]
    if observation["authoritative_kernel_status"] == "COMPLETE" and source_receipt_path is None:
        raise ValueError("COMPLETE terminal status requires downloaded smoke artifacts")
    if observation["artifacts_downloaded"] != (artifact_dir is not None):
        raise ValueError("observation artifacts_downloaded disagrees with the provided directory")

    if source_receipt_path is None:
        guards = {name: False for name in GUARD_FIELDS}
        elapsed_seconds: float | None = None
        returncode: int | None = None
    else:
        if log_path is None:
            raise ValueError("downloaded source smoke receipt is missing trm-smoke.log")
        guards, elapsed_seconds, returncode = validate_source_receipt(
            json.loads(source_receipt_path.read_text(encoding="utf-8")), submission_path
        )
    terminal_guards = {**guards, "all_guards_passed": all(guards.values())}

    notebook_path = pathlib.Path(notebook_raw)
    metadata_path = pathlib.Path(metadata_raw)
    source_files: dict[str, pathlib.Path | None] = {
        "run_manifest.json": observation_path,
        **artifact_paths,
        "notebook_sha256": notebook_path,
        "kernel_metadata_sha256": metadata_path,
    }
    source_hashes: dict[str, str | None] = {}
    source_paths: dict[str, str | None] = {}
    for name, path in source_files.items():
        if path is None:
            source_hashes[name] = None
            source_paths[name] = None
        else:
            path, relative = relative_project_file(root, path, name)
            source_hashes[name] = digest(path)
            source_paths[name] = relative
    if source_hashes["notebook_sha256"] != notebook_hash:
        raise ValueError("notebook changed after the V2 push")
    if source_hashes["kernel_metadata_sha256"] != metadata_hash:
        raise ValueError("kernel metadata changed after the V2 push")

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "artifact_status": "terminal_runtime_smoke",
        "kernel": KERNEL,
        "kernel_version": KERNEL_VERSION,
        "authoritative_kernel_status": observation["authoritative_kernel_status"],
        "status_verified_at_cst": observation["status_verified_at_cst"],
        "is_private": True,
        "internet_enabled": False,
        "data_boundary": "one frozen public-training challenge; solutions never read",
        "purpose": "runtime compatibility smoke; not an accuracy experiment",
        "task_id": TASK_ID,
        "task_count": 1,
        "epochs": 1,
        "expected_optimizer_steps": 1,
        "runtime_sha256": RUNTIME_SHA256,
        "parent_runtime_sha256": PARENT_RUNTIME_SHA256,
        "elapsed_seconds": elapsed_seconds,
        "returncode": returncode,
        "guards": terminal_guards,
        "source_artifacts": source_hashes,
        "source_paths": source_paths,
        "claim_boundary": (
            "Authoritative terminal runtime evidence only; this is not accuracy, "
            "development, sealed-holdout, public-evaluation, submission, or score evidence."
        ),
    }
    validate_terminal_receipt_payload_only(receipt, observation_relative)
    return receipt


def validate_terminal_receipt_payload_only(receipt: dict[str, Any], observation_relative: str) -> None:
    exact_keys(receipt, TERMINAL_RECEIPT_FIELDS, "terminal smoke receipt")
    if receipt["source_paths"]["run_manifest.json"] != observation_relative:
        raise ValueError("terminal observation path changed during receipt construction")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=pathlib.Path, required=True)
    parser.add_argument("--observation", type=pathlib.Path, required=True)
    parser.add_argument("--artifact-dir", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
        root = contract_root(args.contract.resolve(), contract)
        output = args.output.resolve()
        try:
            output.relative_to(root)
        except ValueError as error:
            raise ValueError("output must be inside the contract project root") from error
        if output.exists():
            raise ValueError("output already exists; refusing to overwrite a terminal receipt")
        receipt = build_runtime_smoke_receipt(
            args.contract, args.observation, args.artifact_dir
        )
        derived = validate_terminal_receipt(args.contract, receipt)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(output.relative_to(root)),
                    "receipt_sha256": digest(output),
                    "runtime_smoke_status": derived,
                },
                sort_keys=True,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"passes": False, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
