#!/usr/bin/env python3
"""Fail-closed audit for an exact ARC paper/public-notebook release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any


TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".csv",
    ".h",
    ".hpp",
    ".ipynb",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

FORBIDDEN_COMPONENTS = {
    ".agents",
    ".codex",
    ".env",
    ".git",
    ".kaggle",
    ".ssh",
    "__pycache__",
    "artifacts",
    "evaluator_only",
    "kaggle_runs",
    "node_modules",
    "qwen3_4b_grids15_sft139",
    "trm_checkpoint",
    "unsloth_compiled_cache",
}

CONTENT_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|"
            r"kaggle[_-]?key|secret[_-]?key)\b\s*[:=]\s*[\"'][^\"'\r\n]{8,}"
        ),
    ),
    ("bearer_token", re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("absolute_user_path", re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[A-Za-z0-9._-]+(?:/|\b)")),
    ("file_uri", re.compile(r"file://")),
    ("evaluation_solutions", re.compile(r"arc-agi[_-]evaluation[_-]solutions\.json", re.I)),
    ("hidden_test_solutions", re.compile(r"arc-agi[_-]test[_-]solutions\.json", re.I)),
    ("benchmark_solutions", re.compile(r"benchmark[_-]solutions\.json", re.I)),
    ("evaluator_only_reference", re.compile(r"(?:^|[\"'/])evaluator_only/", re.I | re.M)),
)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_violation(violations: list[dict[str, Any]], code: str, **details: Any) -> None:
    violations.append({"code": code, **details})


def audit_notebook(path: str, text: str, violations: list[dict[str, Any]]) -> None:
    try:
        notebook = json.loads(text)
    except json.JSONDecodeError as exc:
        add_violation(violations, "invalid_notebook_json", path=path, detail=str(exc))
        return

    if "widgets" in notebook.get("metadata", {}):
        add_violation(violations, "notebook_widget_state", path=path)

    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        if cell.get("execution_count") is not None:
            add_violation(
                violations,
                "notebook_execution_count",
                path=path,
                cell=index,
            )
        if cell.get("outputs"):
            add_violation(violations, "notebook_outputs_present", path=path, cell=index)


def audit_manifest(manifest_path: pathlib.Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []

    if manifest.get("schema_version") != 1:
        add_violation(violations, "unsupported_schema_version")
    status = manifest.get("status")
    if status not in {"PRELIMINARY_NOT_FINAL", "FINAL_RELEASE_CANDIDATE"}:
        add_violation(violations, "invalid_status", value=status)

    root_value = manifest.get("project_root")
    if not isinstance(root_value, str) or not root_value:
        add_violation(violations, "missing_project_root")
        root = manifest_path.parent.resolve()
    else:
        root = (manifest_path.parent / root_value).resolve()

    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        add_violation(violations, "empty_file_allowlist")
        entries = []

    seen: set[str] = set()
    scanned_text = 0
    binary_files = 0
    total_bytes = 0
    categories: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            add_violation(violations, "invalid_file_entry")
            continue
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            add_violation(violations, "missing_file_path")
            continue
        if raw_path in seen:
            add_violation(violations, "duplicate_file_path", path=raw_path)
            continue
        seen.add(raw_path)

        relative = pathlib.PurePosixPath(raw_path)
        if relative.is_absolute() or ".." in relative.parts:
            add_violation(violations, "unsafe_file_path", path=raw_path)
            continue
        forbidden = sorted(FORBIDDEN_COMPONENTS.intersection(part.lower() for part in relative.parts))
        if forbidden:
            add_violation(
                violations,
                "forbidden_path_component",
                path=raw_path,
                components=forbidden,
            )

        unresolved = root / pathlib.Path(*relative.parts)
        candidate = unresolved.resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            add_violation(violations, "path_escapes_project_root", path=raw_path)
            continue
        if not candidate.is_file():
            add_violation(violations, "file_missing", path=raw_path)
            continue
        relative_cursor = root
        symlink_component = None
        for component in relative.parts:
            relative_cursor = relative_cursor / component
            if relative_cursor.is_symlink():
                symlink_component = component
                break
        if symlink_component is not None:
            add_violation(
                violations,
                "symlink_not_allowed",
                path=raw_path,
                component=symlink_component,
            )
            continue

        actual_bytes = candidate.stat().st_size
        actual_hash = sha256(candidate)
        total_bytes += actual_bytes
        if entry.get("bytes") != actual_bytes:
            add_violation(
                violations,
                "byte_count_mismatch",
                path=raw_path,
                expected=entry.get("bytes"),
                actual=actual_bytes,
            )
        if entry.get("sha256") != actual_hash:
            add_violation(
                violations,
                "sha256_mismatch",
                path=raw_path,
                expected=entry.get("sha256"),
                actual=actual_hash,
            )
        category = entry.get("category")
        if not isinstance(category, str) or not category:
            add_violation(violations, "missing_category", path=raw_path)
        else:
            categories.add(category)
        license_decision = entry.get("license")
        if not isinstance(license_decision, str) or not license_decision:
            add_violation(violations, "missing_license_decision", path=raw_path)
        elif status == "FINAL_RELEASE_CANDIDATE" and re.search(
            r"(?i)\b(?:pending|internal|unknown|unreviewed|not[- ]cleared)\b",
            license_decision,
        ):
            add_violation(
                violations,
                "unresolved_final_license",
                path=raw_path,
                value=license_decision,
            )

        text_categories = {"config", "license", "notice", "notebook", "paper", "receipt", "source"}
        if candidate.suffix.lower() not in TEXT_SUFFIXES and category not in text_categories:
            binary_files += 1
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            add_violation(violations, "non_utf8_text_file", path=raw_path)
            continue
        scanned_text += 1
        for name, pattern in CONTENT_PATTERNS:
            match = pattern.search(text)
            if match:
                add_violation(
                    violations,
                    "forbidden_content",
                    path=raw_path,
                    pattern=name,
                    line=text.count("\n", 0, match.start()) + 1,
                )
        if candidate.suffix.lower() == ".ipynb":
            audit_notebook(raw_path, text, violations)

    external_assets = manifest.get("external_assets", [])
    if not isinstance(external_assets, list):
        add_violation(violations, "invalid_external_assets")
        external_assets = []
    for index, asset in enumerate(external_assets):
        if not isinstance(asset, dict):
            add_violation(violations, "invalid_external_asset", index=index)
            continue
        for key in ("kind", "ref", "version", "license", "receipt_sha256"):
            if not isinstance(asset.get(key), str) or not asset.get(key):
                add_violation(
                    violations,
                    "incomplete_external_asset",
                    index=index,
                    field=key,
                )
        if asset.get("public") is not True:
            add_violation(violations, "external_asset_not_public", index=index)
        receipt_hash = asset.get("receipt_sha256")
        if isinstance(receipt_hash, str) and not re.fullmatch(r"[0-9a-f]{64}", receipt_hash):
            add_violation(violations, "invalid_external_receipt_hash", index=index)

    if status == "FINAL_RELEASE_CANDIDATE":
        required = {"cover", "license", "notebook", "notice", "paper", "receipt", "source"}
        missing_categories = sorted(required - categories)
        if missing_categories:
            add_violation(
                violations,
                "missing_final_category",
                categories=missing_categories,
            )
        if not external_assets:
            add_violation(violations, "missing_final_external_assets")
        bindings = manifest.get("final_bindings")
        required_bindings = {
            "arc_submission_id",
            "cover_sha256",
            "project_url",
            "public_notebook_url",
            "public_notebook_version",
            "source_commit",
            "source_repository_url",
            "submission_sha256",
            "writeup_url",
        }
        if not isinstance(bindings, dict):
            add_violation(violations, "missing_final_bindings")
        else:
            missing_bindings = sorted(
                key
                for key in required_bindings
                if not isinstance(bindings.get(key), str) or not bindings.get(key).strip()
            )
            if missing_bindings:
                add_violation(
                    violations,
                    "incomplete_final_bindings",
                    fields=missing_bindings,
                )
            for key in ("cover_sha256", "submission_sha256"):
                value = bindings.get(key)
                if isinstance(value, str) and value and not re.fullmatch(r"[0-9a-f]{64}", value):
                    add_violation(
                        violations,
                        "invalid_final_binding_hash",
                        field=key,
                    )
            for key in ("project_url", "public_notebook_url", "source_repository_url", "writeup_url"):
                value = bindings.get(key)
                if isinstance(value, str) and value and not value.startswith("https://"):
                    add_violation(
                        violations,
                        "invalid_final_binding_url",
                        field=key,
                    )

    return {
        "schema_version": 1,
        "manifest": manifest_path.name,
        "status": status,
        "passes": not violations,
        "files": len(entries),
        "text_files_scanned": scanned_text,
        "binary_files_hashed": binary_files,
        "total_bytes": total_bytes,
        "external_assets": len(external_assets),
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = audit_manifest(args.manifest.resolve())
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"passes": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
    stream = sys.stdout if result["passes"] else sys.stderr
    print(json.dumps(result, indent=2, sort_keys=True), file=stream)
    raise SystemExit(0 if result["passes"] else 1)


if __name__ == "__main__":
    main()
