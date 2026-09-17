#!/usr/bin/env python3
"""Fail closed when a candidate notebook has unbound or unverified Kaggle inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any


KIND_TO_METADATA = {
    "competition": "competition_sources",
    "dataset": "dataset_sources",
    "kernel": "kernel_sources",
    "model": "model_sources",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add(violations: list[dict[str, Any]], code: str, **details: Any) -> None:
    violations.append({"code": code, **details})


def resolve_binding(
    root: pathlib.Path,
    binding: Any,
    label: str,
    violations: list[dict[str, Any]],
) -> pathlib.Path | None:
    if not isinstance(binding, dict):
        add(violations, "artifact_binding_missing", artifact=label)
        return None
    raw = binding.get("path")
    expected = binding.get("sha256")
    if not isinstance(raw, str) or not raw:
        add(violations, "artifact_path_missing", artifact=label)
        return None
    if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
        add(violations, "artifact_hash_invalid", artifact=label)
        return None
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        add(violations, "artifact_path_unsafe", artifact=label, path=raw)
        return None
    candidate = (root / pathlib.Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        add(violations, "artifact_path_escapes_root", artifact=label, path=raw)
        return None
    if not candidate.is_file():
        add(violations, "artifact_file_missing", artifact=label, path=raw)
        return None
    actual = sha256(candidate)
    if actual != expected:
        add(
            violations,
            "artifact_hash_mismatch",
            artifact=label,
            expected=expected,
            actual=actual,
        )
    return candidate


def audit(manifest_path: pathlib.Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []

    if manifest.get("schema_version") != 1:
        add(violations, "unsupported_schema_version")
    status = manifest.get("status")
    if status not in {"READY", "BLOCKED_UNVERIFIED_DEPENDENCIES"}:
        add(violations, "invalid_status", value=status)

    raw_root = manifest.get("project_root")
    if not isinstance(raw_root, str) or not raw_root:
        add(violations, "project_root_missing")
        root = manifest_path.parent
    else:
        root = (manifest_path.parent / raw_root).resolve()

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        add(violations, "artifacts_missing")
        artifacts = {}
    notebook_path = resolve_binding(root, artifacts.get("notebook"), "notebook", violations)
    metadata_path = resolve_binding(
        root, artifacts.get("kernel_metadata"), "kernel_metadata", violations
    )
    resolve_binding(root, artifacts.get("preregistration"), "preregistration", violations)

    metadata: dict[str, Any] = {}
    if metadata_path is not None:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            add(violations, "kernel_metadata_invalid", detail=str(exc))

    if notebook_path is not None:
        try:
            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            add(violations, "notebook_invalid", detail=str(exc))
        else:
            for index, cell in enumerate(notebook.get("cells", [])):
                if cell.get("cell_type") != "code":
                    continue
                if cell.get("execution_count") is not None:
                    add(violations, "notebook_execution_count", cell=index)
                if cell.get("outputs"):
                    add(violations, "notebook_outputs_present", cell=index)

    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        add(violations, "dependencies_missing")
        dependencies = []

    declared: dict[str, set[str]] = {kind: set() for kind in KIND_TO_METADATA}
    unresolved: list[dict[str, str]] = []
    for index, dependency in enumerate(dependencies):
        if not isinstance(dependency, dict):
            add(violations, "dependency_invalid", index=index)
            continue
        kind = dependency.get("kind")
        ref = dependency.get("ref")
        if kind not in KIND_TO_METADATA:
            add(violations, "dependency_kind_invalid", index=index, value=kind)
            continue
        if not isinstance(ref, str) or not ref:
            add(violations, "dependency_ref_missing", index=index)
            continue
        if ref in declared[kind]:
            add(violations, "dependency_duplicate", kind=kind, ref=ref)
        declared[kind].add(ref)

        dependency_status = dependency.get("status")
        if dependency_status == "UNVERIFIED":
            unresolved.append({"kind": kind, "ref": ref})
            add(violations, "dependency_not_verified", kind=kind, ref=ref)
            local_evidence = dependency.get("local_evidence")
            if local_evidence is None:
                add(violations, "unverified_local_evidence_missing", kind=kind, ref=ref)
            else:
                resolve_binding(
                    root,
                    local_evidence,
                    f"local_evidence:{kind}:{ref}",
                    violations,
                )
            continue
        expected_status = (
            "JOINED_COMPETITION_SOURCE" if kind == "competition" else "VERIFIED_PUBLIC"
        )
        if dependency_status != expected_status:
            add(
                violations,
                "dependency_status_invalid",
                kind=kind,
                ref=ref,
                expected=expected_status,
                actual=dependency_status,
            )
        if kind != "competition" and dependency.get("public") is not True:
            add(violations, "dependency_not_public", kind=kind, ref=ref)
        license_value = dependency.get("license")
        if not isinstance(license_value, str) or not license_value.strip():
            add(violations, "dependency_license_missing", kind=kind, ref=ref)
        receipt = dependency.get("receipt")
        resolve_binding(root, receipt, f"dependency:{kind}:{ref}", violations)

    for kind, metadata_key in KIND_TO_METADATA.items():
        raw_sources = metadata.get(metadata_key, [])
        if not isinstance(raw_sources, list) or any(
            not isinstance(item, str) or not item for item in raw_sources
        ):
            add(violations, "metadata_dependency_list_invalid", kind=kind)
            raw_sources = []
        expected = set(raw_sources)
        actual = declared[kind]
        if expected != actual:
            add(
                violations,
                "metadata_dependency_mismatch",
                kind=kind,
                missing=sorted(expected - actual),
                extra=sorted(actual - expected),
            )

    if status == "READY" and unresolved:
        add(violations, "ready_status_with_unverified_dependencies")
    if status == "BLOCKED_UNVERIFIED_DEPENDENCIES" and not unresolved:
        add(violations, "blocked_status_without_unverified_dependencies")

    return {
        "schema_version": 1,
        "manifest": manifest_path.name,
        "status": status,
        "passes": not violations,
        "dependency_counts": {kind: len(refs) for kind, refs in declared.items()},
        "unresolved_dependencies": unresolved,
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = audit(args.manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"passes": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1) from exc
    stream = sys.stdout if result["passes"] else sys.stderr
    print(json.dumps(result, indent=2, sort_keys=True), file=stream)
    raise SystemExit(0 if result["passes"] else 1)


if __name__ == "__main__":
    main()
