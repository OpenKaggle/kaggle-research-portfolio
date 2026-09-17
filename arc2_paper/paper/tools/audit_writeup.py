#!/usr/bin/env python3
"""Audit ARC Paper Track Writeup structure, evidence coverage, and final binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any


DIMENSIONS = {"Accuracy", "Universality", "Progress", "Theory", "Completeness", "Novelty"}
FINAL_BINDINGS = {
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

# The current official Paper Prize guidance says not to report train-set
# performance. Dataset sizes and protocol descriptions remain allowed; these
# expressions target only ratio/percentage-shaped results near train/development
# language in either word order.
TRAIN_PERFORMANCE_PATTERNS = (
    re.compile(
        r"(?:\btrain(?:ing)?(?:[- ](?:set|split))?|\bpublic[- ]training|\bdevelopment)"
        r"[^.\n]{0,120}(?:\b\d[\d,]*\s*/\s*\d[\d,]*\b|\b\d+(?:\.\d+)?\s*%)",
        flags=re.I,
    ),
    re.compile(
        r"(?:\b\d[\d,]*\s*/\s*\d[\d,]*\b|\b\d+(?:\.\d+)?\s*%)"
        r"[^.\n]{0,120}(?:\btrain(?:ing)?(?:[- ](?:set|split))?|\bpublic[- ]training|\bdevelopment)",
        flags=re.I,
    ),
)


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add(items: list[dict[str, Any]], code: str, **details: Any) -> None:
    items.append({"code": code, **details})


def normalize_heading(value: str) -> str:
    value = re.sub(r"[`*_]", "", value).strip().lower()
    value = re.sub(r"\s+[—-]\s+.*$", "", value)
    return re.sub(r"\s+", " ", value)


def audit(contract_path: pathlib.Path) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if contract.get("schema_version") != 1:
        add(violations, "unsupported_schema_version")
    status = contract.get("status")
    if status not in {"DRAFT", "FINAL_SUBMISSION_READY"}:
        add(violations, "invalid_status", value=status)

    root_raw = contract.get("project_root")
    if not isinstance(root_raw, str) or not root_raw:
        add(violations, "missing_project_root")
        root = contract_path.parent.resolve()
    else:
        root = (contract_path.parent / root_raw).resolve()

    writeup_raw = contract.get("writeup_path")
    writeup: pathlib.Path | None = None
    text = ""
    if not isinstance(writeup_raw, str) or not writeup_raw:
        add(violations, "missing_writeup_path")
    else:
        relative = pathlib.PurePosixPath(writeup_raw)
        if relative.is_absolute() or ".." in relative.parts:
            add(violations, "unsafe_writeup_path", path=writeup_raw)
        else:
            writeup = (root / pathlib.Path(*relative.parts)).resolve()
            try:
                writeup.relative_to(root)
            except ValueError:
                add(violations, "writeup_escapes_project_root", path=writeup_raw)
                writeup = None
            if writeup is not None and not writeup.is_file():
                add(violations, "writeup_missing", path=writeup_raw)
                writeup = None
    if writeup is not None:
        text = writeup.read_text(encoding="utf-8")
        if contract.get("writeup_bytes") != writeup.stat().st_size:
            add(
                violations,
                "writeup_byte_count_mismatch",
                expected=contract.get("writeup_bytes"),
                actual=writeup.stat().st_size,
            )
        actual_hash = sha256(writeup)
        if contract.get("writeup_sha256") != actual_hash:
            add(
                violations,
                "writeup_sha256_mismatch",
                expected=contract.get("writeup_sha256"),
                actual=actual_hash,
            )

    word_count = len(text.split())
    maximum = contract.get("maximum_words")
    safety_target = contract.get("local_safety_target_words")
    if not isinstance(maximum, int) or maximum <= 0:
        add(violations, "invalid_maximum_words")
    elif word_count > maximum:
        add(violations, "absolute_word_limit_exceeded", words=word_count, maximum=maximum)
    if not isinstance(safety_target, int) or safety_target <= 0 or (
        isinstance(maximum, int) and safety_target > maximum
    ):
        add(violations, "invalid_safety_target")
    elif word_count > safety_target:
        add(violations, "local_safety_target_exceeded", words=word_count, target=safety_target)

    headings = [
        normalize_heading(match.group(1))
        for match in re.finditer(r"^#{2,6}\s+(.+?)\s*$", text, flags=re.M)
    ]
    required_sections = contract.get("required_sections")
    if not isinstance(required_sections, list) or not required_sections:
        add(violations, "missing_required_sections")
        required_sections = []
    for section in required_sections:
        if not isinstance(section, dict) or not isinstance(section.get("name"), str):
            add(violations, "invalid_required_section")
            continue
        patterns = section.get("heading_patterns")
        if not isinstance(patterns, list) or not patterns:
            add(violations, "invalid_section_patterns", section=section.get("name"))
            continue
        if not any(
            re.search(pattern, heading, flags=re.I)
            for pattern in patterns
            if isinstance(pattern, str)
            for heading in headings
        ):
            add(violations, "missing_section", section=section["name"])

    registry_raw = contract.get("evidence_registry_path")
    evidence_ids: set[str] = set()
    if not isinstance(registry_raw, str) or not registry_raw:
        add(violations, "missing_evidence_registry_path")
    else:
        registry = (root / registry_raw).resolve()
        try:
            registry.relative_to(root)
        except ValueError:
            add(violations, "evidence_registry_escapes_project_root")
        else:
            if not registry.is_file():
                add(violations, "evidence_registry_missing")
            else:
                registry_text = registry.read_text(encoding="utf-8")
                evidence_ids = set(re.findall(r"^\|\s*([A-Z][0-9]+)\s*\|", registry_text, flags=re.M))

    rubric = contract.get("rubric_dimensions")
    if not isinstance(rubric, dict):
        add(violations, "missing_rubric_dimensions")
        rubric = {}
    missing_dimensions = sorted(DIMENSIONS - set(rubric))
    extra_dimensions = sorted(set(rubric) - DIMENSIONS)
    if missing_dimensions:
        add(violations, "missing_rubric_dimension", dimensions=missing_dimensions)
    if extra_dimensions:
        add(violations, "unknown_rubric_dimension", dimensions=extra_dimensions)

    unsupported_dimensions: list[str] = []
    for dimension in sorted(DIMENSIONS.intersection(rubric)):
        item = rubric[dimension]
        if not isinstance(item, dict):
            add(violations, "invalid_rubric_entry", dimension=dimension)
            continue
        evidence_status = item.get("status")
        if evidence_status not in {"missing", "partial", "supported"}:
            add(violations, "invalid_dimension_status", dimension=dimension)
        if evidence_status != "supported":
            unsupported_dimensions.append(dimension)
        ids = item.get("evidence_ids")
        if not isinstance(ids, list) or not ids:
            add(violations, "dimension_without_evidence", dimension=dimension)
            continue
        unknown = sorted(value for value in ids if value not in evidence_ids)
        if unknown:
            add(
                violations,
                "unknown_dimension_evidence",
                dimension=dimension,
                evidence_ids=unknown,
            )

    claims = contract.get("required_claim_bindings", [])
    if not isinstance(claims, list):
        add(violations, "invalid_claim_bindings")
        claims = []
    seen_claims: set[str] = set()
    normalized_text = re.sub(r"\s+", " ", text)
    for claim in claims:
        if not isinstance(claim, dict):
            add(violations, "invalid_claim_binding")
            continue
        claim_id = claim.get("claim_id")
        needle = claim.get("text_contains")
        ids = claim.get("evidence_ids")
        if not isinstance(claim_id, str) or not claim_id or claim_id in seen_claims:
            add(violations, "invalid_or_duplicate_claim_id", claim_id=claim_id)
        else:
            seen_claims.add(claim_id)
        normalized_needle = re.sub(r"\s+", " ", needle).strip() if isinstance(needle, str) else ""
        if not normalized_needle or normalized_needle not in normalized_text:
            add(violations, "claim_text_missing", claim_id=claim_id)
        if not isinstance(ids, list) or not ids:
            add(violations, "claim_without_evidence", claim_id=claim_id)
        else:
            unknown = sorted(value for value in ids if value not in evidence_ids)
            if unknown:
                add(
                    violations,
                    "unknown_claim_evidence",
                    claim_id=claim_id,
                    evidence_ids=unknown,
                )

    training_performance_matches = {
        match.group(0).strip()
        for pattern in TRAIN_PERFORMANCE_PATTERNS
        for match in pattern.finditer(text)
    }
    if training_performance_matches:
        add(
            violations,
            "train_performance_reported",
            count=len(training_performance_matches),
        )

    placeholder_matches = list(re.finditer(r"\[(?:PENDING|TBD)[^\]]*\]", text, flags=re.I))
    if status == "DRAFT":
        if unsupported_dimensions:
            add(
                warnings,
                "dimensions_not_final",
                dimensions=unsupported_dimensions,
            )
        if placeholder_matches:
            add(warnings, "draft_placeholders_present", count=len(placeholder_matches))
    elif status == "FINAL_SUBMISSION_READY":
        if placeholder_matches:
            add(violations, "final_placeholders_present", count=len(placeholder_matches))
        if unsupported_dimensions:
            add(
                violations,
                "unsupported_final_dimensions",
                dimensions=unsupported_dimensions,
            )
        platform_word_count = contract.get("platform_word_count")
        if not isinstance(platform_word_count, int) or platform_word_count < 1:
            add(violations, "missing_platform_word_count")
        elif isinstance(maximum, int) and platform_word_count > maximum:
            add(
                violations,
                "platform_word_limit_exceeded",
                words=platform_word_count,
                maximum=maximum,
            )
        bindings = contract.get("final_bindings")
        if not isinstance(bindings, dict):
            add(violations, "missing_final_bindings")
        else:
            missing = sorted(
                key
                for key in FINAL_BINDINGS
                if not isinstance(bindings.get(key), str) or not bindings.get(key).strip()
            )
            if missing:
                add(violations, "incomplete_final_bindings", fields=missing)
            for key in ("cover_sha256", "platform_count_receipt_sha256", "submission_sha256"):
                value = bindings.get(key)
                if isinstance(value, str) and value and not re.fullmatch(r"[0-9a-f]{64}", value):
                    add(violations, "invalid_final_binding_hash", field=key)
            for key in ("project_url", "public_notebook_url", "source_repository_url", "writeup_url"):
                value = bindings.get(key)
                if isinstance(value, str) and value and not value.startswith("https://"):
                    add(violations, "invalid_final_binding_url", field=key)

    markdown_links = len(re.findall(r"\[[^\]]+\]\(https://[^)]+\)", text))
    if markdown_links == 0:
        add(violations, "no_public_reference_links")

    passes = not violations
    final_ready = passes and status == "FINAL_SUBMISSION_READY"
    return {
        "schema_version": 1,
        "contract": contract_path.name,
        "status": status,
        "passes": passes,
        "final_ready": final_ready,
        "word_count_method": "Unicode whitespace-delimited tokens on Markdown source",
        "word_count": word_count,
        "maximum_words": maximum,
        "local_safety_target_words": safety_target,
        "headings": headings,
        "rubric_status": {
            dimension: rubric.get(dimension, {}).get("status")
            if isinstance(rubric.get(dimension), dict)
            else None
            for dimension in sorted(DIMENSIONS)
        },
        "claim_bindings": len(claims),
        "training_performance_mentions": len(training_performance_matches),
        "placeholders": len(placeholder_matches),
        "public_reference_links": markdown_links,
        "warnings": warnings,
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("contract", type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = audit(args.contract.resolve())
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"passes": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
    stream = sys.stdout if result["passes"] else sys.stderr
    print(json.dumps(result, indent=2, sort_keys=True), file=stream)
    raise SystemExit(0 if result["passes"] else 1)


if __name__ == "__main__":
    main()
