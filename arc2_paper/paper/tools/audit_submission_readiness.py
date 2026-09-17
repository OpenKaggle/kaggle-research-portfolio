#!/usr/bin/env python3
"""Aggregate every local ARC Paper submission gate without external actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from paper.tools.audit_notebook_dependencies import audit as audit_dependencies
from paper.tools.audit_release_manifest import audit_manifest as audit_release
from paper.tools.audit_three_stage_pipeline import audit as audit_pipeline
from paper.tools.audit_writeup import audit as audit_writeup


SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_ARTIFACTS = {
    "authorship_manifest",
    "corpus_eligibility_receipt",
    "cover",
    "cover_manifest",
    "deadline_receipt",
    "dependency_manifest",
    "license_audit",
    "pipeline_contract",
    "publication_checklist",
    "release_manifest",
    "writeup_contract",
}
REQUIRED_PLATFORM_RECEIPTS = {
    "cover_attachment_receipt_sha256",
    "paper_submission_receipt_sha256",
}
REQUIRED_APPROVALS = {
    "author_order_frozen",
    "author_ip_approved",
    "employer_not_required_or_approved",
    "final_claim_reviewed",
}
REQUIRED_FINAL_BINDINGS = {
    "arc_submission_id",
    "cover_sha256",
    "platform_count_receipt_sha256",
    "project_url",
    "public_notebook_url",
    "public_notebook_version",
    "source_commit",
    "source_repository_url",
    "submission_sha256",
    "writeup_url",
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add(items: list[dict[str, Any]], code: str, **details: Any) -> None:
    items.append({"code": code, **details})


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
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        add(violations, "artifact_hash_invalid", artifact=label)
        return None
    relative = pathlib.PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        add(violations, "artifact_path_unsafe", artifact=label, path=raw)
        return None
    path = (root / pathlib.Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        add(violations, "artifact_path_escapes_root", artifact=label, path=raw)
        return None
    if not path.is_file():
        add(violations, "artifact_file_missing", artifact=label, path=raw)
        return None
    actual = digest(path)
    if actual != expected:
        add(
            violations,
            "artifact_hash_mismatch",
            artifact=label,
            expected=expected,
            actual=actual,
        )
    return path


def png_dimensions(path: pathlib.Path) -> tuple[int, int] | None:
    raw = path.read_bytes()[:24]
    if len(raw) != 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", raw[16:24])


def readiness_blockers(
    writeup: dict[str, Any],
    pipeline: dict[str, Any],
    corpus_eligibility: dict[str, Any],
    release: dict[str, Any],
    dependencies: dict[str, Any],
    final_bindings: Any,
    platform_receipts: Any,
    approvals: Any,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if writeup.get("final_ready") is not True:
        add(
            blockers,
            "writeup_not_final",
            placeholders=writeup.get("placeholders"),
            word_count=writeup.get("word_count"),
        )
    unsupported = sorted(
        name
        for name, status in writeup.get("rubric_status", {}).items()
        if status != "supported"
    )
    if unsupported:
        add(blockers, "rubric_dimensions_not_supported", dimensions=unsupported)

    if pipeline.get("pipeline_complete") is not True:
        add(
            blockers,
            "pipeline_incomplete",
            runtime_smoke_status=pipeline.get("runtime_smoke_status"),
            stage_states=pipeline.get("stage_states"),
        )
    if pipeline.get("holdout_promotion_blocked") is True:
        add(
            blockers,
            "holdout_contaminated_for_method_generalization",
            status=pipeline.get("holdout_integrity_status"),
            next_action=pipeline.get("next_action"),
        )
    corpus_status = corpus_eligibility.get("status") or corpus_eligibility.get(
        "audit_status"
    )
    corpus_decision = corpus_eligibility.get("decision") or corpus_eligibility.get(
        "current_decision"
    )
    if corpus_status in {
        "SYSTEMS_NEGATIVE_NO_VERIFIED_UNTOUCHED_CORPUS",
        "NO_VERIFIED_ELIGIBLE_ARC_AGI_2_GENERALIZATION_CORPUS",
    }:
        add(
            blockers,
            "no_verified_eligible_generalization_corpus",
            status=corpus_status,
            decision=corpus_decision,
            permitted_alternative="SYSTEMS_NEGATIVE",
        )

    if release.get("passes") is not True or release.get("status") != "FINAL_RELEASE_CANDIDATE":
        add(
            blockers,
            "release_not_final",
            passes=release.get("passes"),
            status=release.get("status"),
        )

    if dependencies.get("passes") is not True:
        add(
            blockers,
            "dependencies_unresolved",
            dependencies=dependencies.get("unresolved_dependencies", []),
        )

    if not isinstance(final_bindings, dict):
        missing_bindings = sorted(REQUIRED_FINAL_BINDINGS)
    else:
        missing_bindings = sorted(
            key
            for key in REQUIRED_FINAL_BINDINGS
            if not isinstance(final_bindings.get(key), str) or not final_bindings[key].strip()
        )
    if missing_bindings:
        add(blockers, "final_bindings_incomplete", fields=missing_bindings)

    if not isinstance(platform_receipts, dict):
        missing_receipts = sorted(REQUIRED_PLATFORM_RECEIPTS)
    else:
        missing_receipts = sorted(
            key
            for key in REQUIRED_PLATFORM_RECEIPTS
            if not isinstance(platform_receipts.get(key), str)
            or not SHA256.fullmatch(platform_receipts[key])
        )
    if missing_receipts:
        add(blockers, "platform_receipts_incomplete", fields=missing_receipts)

    if not isinstance(approvals, dict):
        missing_approvals = sorted(REQUIRED_APPROVALS)
    else:
        missing_approvals = sorted(
            key for key in REQUIRED_APPROVALS if approvals.get(key) is not True
        )
    if missing_approvals:
        add(blockers, "authorship_approvals_incomplete", fields=missing_approvals)
    return blockers


def audit(manifest_path: pathlib.Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []
    if manifest.get("schema_version") != 1:
        add(violations, "unsupported_schema_version")
    status = manifest.get("status")
    if status not in {"ACTIVE_NOT_READY", "FINAL_SUBMISSION_READY"}:
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
    missing_artifacts = sorted(REQUIRED_ARTIFACTS - set(artifacts))
    extra_artifacts = sorted(set(artifacts) - REQUIRED_ARTIFACTS)
    if missing_artifacts or extra_artifacts:
        add(
            violations,
            "artifact_set_invalid",
            missing=missing_artifacts,
            extra=extra_artifacts,
        )
    paths = {
        label: resolve_binding(root, artifacts.get(label), label, violations)
        for label in REQUIRED_ARTIFACTS
    }

    cover_dimensions = None
    cover_path = paths.get("cover")
    if cover_path is not None:
        cover_dimensions = png_dimensions(cover_path)
        if cover_dimensions is None:
            add(violations, "cover_not_png")
        elif min(cover_dimensions) < 512:
            add(violations, "cover_dimensions_too_small", dimensions=cover_dimensions)

    writeup: dict[str, Any] = {}
    pipeline: dict[str, Any] = {}
    release: dict[str, Any] = {}
    dependencies: dict[str, Any] = {}
    corpus_eligibility: dict[str, Any] = {}
    if paths.get("writeup_contract") is not None:
        writeup = audit_writeup(paths["writeup_contract"])
    if paths.get("pipeline_contract") is not None:
        pipeline = audit_pipeline(paths["pipeline_contract"])
    if paths.get("release_manifest") is not None:
        release = audit_release(paths["release_manifest"])
    if paths.get("dependency_manifest") is not None:
        dependencies = audit_dependencies(paths["dependency_manifest"])
    if paths.get("corpus_eligibility_receipt") is not None:
        try:
            corpus_eligibility = json.loads(
                paths["corpus_eligibility_receipt"].read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            add(violations, "corpus_eligibility_receipt_json_invalid")
        if corpus_eligibility.get("schema_version") != 1:
            add(violations, "corpus_eligibility_schema_version_invalid")
        corpus_status = corpus_eligibility.get("status") or corpus_eligibility.get(
            "audit_status"
        )
        if corpus_status not in {
            "SYSTEMS_NEGATIVE_NO_VERIFIED_UNTOUCHED_CORPUS",
            "NO_VERIFIED_ELIGIBLE_ARC_AGI_2_GENERALIZATION_CORPUS",
            "VERIFIED_ELIGIBLE_ARC_AGI_2_GENERALIZATION_CORPUS",
        }:
            add(violations, "corpus_eligibility_status_invalid")

    final_bindings = {}
    if paths.get("writeup_contract") is not None:
        final_bindings = json.loads(
            paths["writeup_contract"].read_text(encoding="utf-8")
        ).get("final_bindings")
    blockers = readiness_blockers(
        writeup,
        pipeline,
        corpus_eligibility,
        release,
        dependencies,
        final_bindings,
        manifest.get("platform_receipts"),
        manifest.get("approvals"),
    )

    if status == "ACTIVE_NOT_READY" and not blockers:
        add(violations, "active_status_without_blockers")
    if status == "FINAL_SUBMISSION_READY" and blockers:
        add(violations, "final_status_with_blockers", blocker_codes=[b["code"] for b in blockers])

    passes = not violations
    final_ready = passes and status == "FINAL_SUBMISSION_READY" and not blockers
    return {
        "schema_version": 1,
        "manifest": manifest_path.name,
        "status": status,
        "passes": passes,
        "final_ready": final_ready,
        "cover_dimensions": cover_dimensions,
        "subsystems": {
            "writeup": {
                "passes": writeup.get("passes"),
                "final_ready": writeup.get("final_ready"),
                "word_count": writeup.get("word_count"),
            },
            "pipeline": {
                "passes": pipeline.get("passes"),
                "pipeline_complete": pipeline.get("pipeline_complete"),
                "runtime_smoke_status": pipeline.get("runtime_smoke_status"),
                "holdout_integrity_status": pipeline.get(
                    "holdout_integrity_status"
                ),
                "holdout_promotion_blocked": pipeline.get(
                    "holdout_promotion_blocked"
                ),
                "generalization_route": pipeline.get("generalization_route"),
                "next_action": pipeline.get("next_action"),
            },
            "corpus_eligibility": {
                "status": corpus_eligibility.get("status")
                or corpus_eligibility.get("audit_status"),
                "decision": corpus_eligibility.get("decision")
                or corpus_eligibility.get("current_decision"),
            },
            "release": {
                "passes": release.get("passes"),
                "status": release.get("status"),
            },
            "dependencies": {
                "passes": dependencies.get("passes"),
                "unresolved": dependencies.get("unresolved_dependencies", []),
            },
        },
        "blockers": blockers,
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
