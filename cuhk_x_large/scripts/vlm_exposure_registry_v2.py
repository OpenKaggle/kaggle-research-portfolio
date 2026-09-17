#!/usr/bin/env python3
"""Append-only VLM exposure registry and fail-closed cohort conflict gate.

The registry records identifiers and provenance only.  It deliberately never
copies answers, labels, correctness flags, raw model output, or prediction
values from the source artifacts.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


SCHEMA_VERSION = "cuhk-vlm-exposure-v2"
DEFAULT_REGISTRY = Path("artifacts/manifests/vlm_exposure_registry_v2.jsonl")
SOURCE_SUFFIXES = {".json", ".jsonl", ".csv"}
STRUCTURAL_TOKENS = ("manifest", "protocol", "validation", "cohort", "frozen")
CLIP_MARKERS = ("HARn", "HAU", "LMT", "large_model_track_test")
MODALITY_PARTS = {
    "Depth",
    "Depth_Color",
    "IR",
    "RGB",
    "Thermal",
    "Skeleton",
    "IMU",
    "Radar",
    "mmWave",
}
QA_COLLECTION_RE = re.compile(r"(?:^|_)qa_ids$")
CLIP_COLLECTION_RE = re.compile(r"(?:^|_)clips$")


@dataclass(frozen=True)
class Exposure:
    qa_id: str | None
    clip_id: str | None
    source_locator: str
    evidence_kind: str
    has_prediction: bool
    record_sha256: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_qa_id(value: Any) -> str | None:
    if not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not text or len(text) > 256 or "/" in text or "\\" in text:
        return None
    return text


def normalize_clip_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().replace("\\", "/")
    if not text:
        return None
    parts = [part for part in text.split("/") if part not in ("", ".")]
    marker_index = next((i for i, part in enumerate(parts) if part in CLIP_MARKERS), None)
    if marker_index is None:
        return None
    parts = parts[marker_index:]
    modality_index = next((i for i, part in enumerate(parts) if part in MODALITY_PARTS), None)
    if modality_index is not None:
        parts = parts[:modality_index]
    elif parts and Path(parts[-1]).suffix.lower() in {".mp4", ".avi", ".npy", ".npz"}:
        parts = parts[:-1]
    if len(parts) < 2:
        return None
    return "/".join(parts).rstrip("/")


def json_pointer(parts: Iterable[Any]) -> str:
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped)


def prediction_present(obj: dict[str, Any]) -> bool:
    for key, value in obj.items():
        if key != "prediction" and not key.endswith("_prediction"):
            continue
        if value is not None and (not isinstance(value, str) or bool(value.strip())):
            return True
    return False


def _make_exposure(
    *,
    qa_id: Any,
    clip_id: Any,
    locator: str,
    evidence_kind: str,
    has_prediction: bool,
    identity: Any,
) -> Exposure | None:
    normalized_qa = normalize_qa_id(qa_id)
    normalized_clip = normalize_clip_id(clip_id)
    if normalized_qa is None and normalized_clip is None:
        return None
    return Exposure(
        qa_id=normalized_qa,
        clip_id=normalized_clip,
        source_locator=locator,
        evidence_kind=evidence_kind,
        has_prediction=has_prediction,
        record_sha256=sha256_bytes(canonical_json(identity)),
    )


def extract_json_value(value: Any, *, evidence_kind: str, path: tuple[Any, ...] = ()) -> Iterator[Exposure]:
    """Project only QA/clip identifiers out of a JSON value.

    Values in label-like fields are never referenced or serialized.
    """

    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from extract_json_value(item, evidence_kind=evidence_kind, path=path + (index,))
        return
    if not isinstance(value, dict):
        return

    locator = json_pointer(path)
    qa_value = value.get("qa_id")
    clip_value = value.get("clip_id", value.get("clip", value.get("path")))
    paired = _make_exposure(
        qa_id=qa_value,
        clip_id=clip_value,
        locator=locator,
        evidence_kind=evidence_kind,
        has_prediction=prediction_present(value),
        identity={"qa_id": normalize_qa_id(qa_value), "clip_id": normalize_clip_id(clip_value)},
    )
    if paired is not None:
        yield paired

    consumed: set[str] = set()
    for qa_key, qa_values in value.items():
        if not QA_COLLECTION_RE.search(qa_key) or not isinstance(qa_values, list):
            continue
        prefix = qa_key[: -len("qa_ids")]
        clip_key = prefix + "clips"
        clip_values = value.get(clip_key)
        if isinstance(clip_values, list) and len(clip_values) == len(qa_values):
            consumed.update({qa_key, clip_key})
            kind = "historical_reference" if "historical" in qa_key else evidence_kind
            for index, (qa_item, clip_item) in enumerate(zip(qa_values, clip_values, strict=True)):
                event = _make_exposure(
                    qa_id=qa_item,
                    clip_id=clip_item,
                    locator=json_pointer(path + (qa_key, index)),
                    evidence_kind=kind,
                    has_prediction=False,
                    identity={"qa_id": normalize_qa_id(qa_item), "clip_id": normalize_clip_id(clip_item)},
                )
                if event is not None:
                    yield event

    for key, item in value.items():
        if key in consumed or key in {"qa_id", "clip_id", "clip", "path"}:
            continue
        if QA_COLLECTION_RE.search(key) and isinstance(item, list):
            kind = "historical_reference" if "historical" in key else evidence_kind
            for index, qa_item in enumerate(item):
                event = _make_exposure(
                    qa_id=qa_item,
                    clip_id=None,
                    locator=json_pointer(path + (key, index)),
                    evidence_kind=kind,
                    has_prediction=False,
                    identity={"qa_id": normalize_qa_id(qa_item)},
                )
                if event is not None:
                    yield event
            continue
        if CLIP_COLLECTION_RE.search(key) and isinstance(item, list):
            kind = "historical_reference" if "historical" in key else evidence_kind
            for index, clip_item in enumerate(item):
                event = _make_exposure(
                    qa_id=None,
                    clip_id=clip_item,
                    locator=json_pointer(path + (key, index)),
                    evidence_kind=kind,
                    has_prediction=False,
                    identity={"clip_id": normalize_clip_id(clip_item)},
                )
                if event is not None:
                    yield event
            continue
        yield from extract_json_value(item, evidence_kind=evidence_kind, path=path + (key,))


def read_exposures(path: Path, *, evidence_kind: str) -> list[Exposure]:
    exposures: list[Exposure] = []
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                for event in extract_json_value(value, evidence_kind=evidence_kind, path=(line_number,)):
                    exposures.append(event)
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        exposures.extend(extract_json_value(value, evidence_kind=evidence_kind))
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                qa_value = row.get("qa_id")
                clip_value = row.get("clip_id", row.get("clip", row.get("path")))
                event = _make_exposure(
                    qa_id=qa_value,
                    clip_id=clip_value,
                    locator=f"csv:{row_number}",
                    evidence_kind=evidence_kind,
                    has_prediction=bool(row.get("prediction", "").strip()),
                    identity={"qa_id": normalize_qa_id(qa_value), "clip_id": normalize_clip_id(clip_value)},
                )
                if event is not None:
                    exposures.append(event)
    else:
        raise ValueError(f"Unsupported source type: {path}")
    return exposures


def discover_sources(root: Path, *, excluded: set[Path] | None = None) -> list[tuple[Path, str]]:
    excluded_resolved = {path.resolve() for path in (excluded or set())}
    found: dict[Path, str] = {}
    vlm_root = root / "artifacts/vlm"
    if vlm_root.exists():
        for path in vlm_root.rglob("*.jsonl"):
            found[path] = "inference"
    for base in (root / "artifacts/manifests", root / "reports"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            lower_name = path.name.lower()
            if "exposure_registry" in lower_name or "exposure_audit" in lower_name:
                continue
            if base.name == "reports" and not any(token in lower_name for token in STRUCTURAL_TOKENS):
                continue
            found.setdefault(path, "selection")
    return [
        (path, found[path])
        for path in sorted(found, key=lambda item: str(item.relative_to(root)))
        if path.resolve() not in excluded_resolved
    ]


def event_payload(root: Path, source: Path, source_sha256: str, event: Exposure) -> dict[str, Any]:
    relative_source = source.resolve().relative_to(root.resolve()).as_posix()
    identity = {
        "schema_version": SCHEMA_VERSION,
        "source_file": relative_source,
        "source_locator": event.source_locator,
        "record_sha256": event.record_sha256,
        "qa_id": event.qa_id,
        "clip_id": event.clip_id,
        "evidence_kind": event.evidence_kind,
        "has_prediction": event.has_prediction,
    }
    return {
        **identity,
        "event_id": sha256_bytes(canonical_json(identity)),
        "registered_at_utc": utc_now(),
        "source_file_sha256_at_registration": source_sha256,
        "fresh_evidence_eligible": False,
    }


def load_registry(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("schema_version") != SCHEMA_VERSION or not record.get("event_id"):
                raise ValueError(f"Invalid registry record at {path}:{line_number}")
            records.append(record)
    return records


def append_scan(root: Path, registry_path: Path, *, excluded: set[Path] | None = None) -> dict[str, Any]:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    sources = discover_sources(root, excluded=(excluded or set()) | {registry_path})
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    for source, kind in sources:
        try:
            source_sha = sha256_file(source)
            for event in read_exposures(source, evidence_kind=kind):
                candidates.append(event_payload(root, source, source_sha, event))
        except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{source.relative_to(root)}: {type(exc).__name__}: {exc}")
    if errors:
        raise RuntimeError("Exposure scan failed closed:\n" + "\n".join(errors))

    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    descriptor = os.open(registry_path, flags, 0o644)
    appended = 0
    try:
        with os.fdopen(descriptor, "r+", encoding="utf-8", newline="") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            existing: list[dict[str, Any]] = []
            event_ids: set[str] = set()
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("schema_version") != SCHEMA_VERSION or not record.get("event_id"):
                    raise ValueError(f"Invalid registry record at {registry_path}:{line_number}")
                existing.append(record)
                event_ids.add(record["event_id"])
            handle.seek(0, os.SEEK_END)
            for record in candidates:
                if record["event_id"] in event_ids:
                    continue
                line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                handle.write(line)
                event_ids.add(record["event_id"])
                existing.append(record)
                appended += 1
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except BaseException:
        # fdopen owns and closes descriptor on every exit path.
        raise
    return {
        "sources_scanned": len(sources),
        "candidate_events": len(candidates),
        "records_appended": appended,
        "registry_records": len(existing),
        "registry_sha256": sha256_file(registry_path),
    }


def registry_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    qa_sources: dict[str, set[str]] = defaultdict(set)
    clip_sources: dict[str, set[str]] = defaultdict(set)
    source_qas: dict[str, set[str]] = defaultdict(set)
    source_clips: dict[str, set[str]] = defaultdict(set)
    inference_qas: dict[str, set[str]] = defaultdict(set)
    inference_clips: dict[str, set[str]] = defaultdict(set)
    predicted_events = 0
    for record in records:
        source = record["source_file"]
        qa_id = record.get("qa_id")
        clip_id = record.get("clip_id")
        if qa_id:
            qa_sources[qa_id].add(source)
            source_qas[source].add(qa_id)
            if record["evidence_kind"] == "inference":
                inference_qas[qa_id].add(source)
        if clip_id:
            clip_sources[clip_id].add(source)
            source_clips[source].add(clip_id)
            if record["evidence_kind"] == "inference":
                inference_clips[clip_id].add(source)
        predicted_events += int(bool(record.get("has_prediction")))

    sources = sorted(set(source_qas) | set(source_clips))
    pairwise: list[dict[str, Any]] = []
    for left_index, left in enumerate(sources):
        for right in sources[left_index + 1 :]:
            qa_overlap = source_qas[left] & source_qas[right]
            clip_overlap = source_clips[left] & source_clips[right]
            if qa_overlap or clip_overlap:
                pairwise.append(
                    {
                        "left": left,
                        "right": right,
                        "qa_overlap": len(qa_overlap),
                        "clip_overlap": len(clip_overlap),
                    }
                )
    pairwise.sort(key=lambda row: (row["qa_overlap"] + row["clip_overlap"], row["qa_overlap"], row["clip_overlap"]), reverse=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_records": len(records),
        "source_files": len(sources),
        "unique_qa_ids": len(qa_sources),
        "unique_clip_ids": len(clip_sources),
        "events_with_prediction": predicted_events,
        "qa_ids_in_multiple_source_files": sum(len(value) > 1 for value in qa_sources.values()),
        "clip_ids_in_multiple_source_files": sum(len(value) > 1 for value in clip_sources.values()),
        "qa_ids_in_multiple_inference_logs": sum(len(value) > 1 for value in inference_qas.values()),
        "clip_ids_in_multiple_inference_logs": sum(len(value) > 1 for value in inference_clips.values()),
        "top_pairwise_overlaps": pairwise[:25],
    }


def conflict_report(records: list[dict[str, Any]], cohort_path: Path) -> dict[str, Any]:
    cohort_events = read_exposures(cohort_path, evidence_kind="candidate_cohort")
    if not cohort_events:
        raise ValueError(f"No QA or clip identifiers found in cohort: {cohort_path}")
    cohort_qas = {event.qa_id for event in cohort_events if event.qa_id}
    cohort_clips = {event.clip_id for event in cohort_events if event.clip_id}
    by_qa: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_clip: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("qa_id") in cohort_qas:
            by_qa[record["qa_id"]].append(record)
        if record.get("clip_id") in cohort_clips:
            by_clip[record["clip_id"]].append(record)

    def compact(items: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for identifier, hits in sorted(items.items()):
            sources = sorted({hit["source_file"] for hit in hits})
            output.append(
                {
                    "id": identifier,
                    "source_files": sources,
                    "has_prediction_in_registry": any(bool(hit.get("has_prediction")) for hit in hits),
                }
            )
        return output

    return {
        "schema_version": SCHEMA_VERSION,
        "decision": "REJECT_CONFLICT" if by_qa or by_clip else "PASS_FRESH",
        "cohort_file": str(cohort_path),
        "cohort_unique_qa_ids": len(cohort_qas),
        "cohort_unique_clip_ids": len(cohort_clips),
        "qa_conflict_count": len(by_qa),
        "clip_conflict_count": len(by_clip),
        "qa_conflicts": compact(by_qa),
        "clip_conflicts": compact(by_clip),
    }


def check_and_reserve(root: Path, registry_path: Path, cohort_path: Path) -> dict[str, Any]:
    """Atomically reject overlap or append a clean cohort reservation.

    The lock closes the cross-process gap between the last conflict read and
    reservation.  A second thread checking the same QA/clip union must observe
    the first reservation and fail.
    """

    cohort_events = read_exposures(cohort_path, evidence_kind="cohort_reservation")
    if not cohort_events:
        raise ValueError(f"No QA or clip identifiers found in cohort: {cohort_path}")
    source_sha = sha256_file(cohort_path)
    reservations = [event_payload(root, cohort_path, source_sha, event) for event in cohort_events]
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(registry_path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
    with os.fdopen(descriptor, "r+", encoding="utf-8", newline="") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        records: list[dict[str, Any]] = []
        event_ids: set[str] = set()
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("schema_version") != SCHEMA_VERSION or not record.get("event_id"):
                raise ValueError(f"Invalid registry record at {registry_path}:{line_number}")
            records.append(record)
            event_ids.add(record["event_id"])
        report = conflict_report(records, cohort_path)
        if report["decision"] != "PASS_FRESH":
            report["reservation_records_appended"] = 0
            report["registry_sha256_after_check"] = sha256_file(registry_path)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return report

        handle.seek(0, os.SEEK_END)
        appended = 0
        for record in reservations:
            if record["event_id"] in event_ids:
                continue
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
            event_ids.add(record["event_id"])
            appended += 1
        handle.flush()
        os.fsync(handle.fileno())
        report["decision"] = "PASS_FRESH_RESERVED"
        report["reservation_records_appended"] = appended
        report["registry_sha256_after_check"] = sha256_file(registry_path)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return report


def resolve_under_root(root: Path, path: Path) -> Path:
    resolved = path if path.is_absolute() else root / path
    return resolved.resolve()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan", help="Append newly discovered exposures and print an audit summary")
    scan_parser.add_argument("--report", type=Path)
    check_parser = subparsers.add_parser("check", help="Refresh the registry and reject any cohort overlap")
    check_parser.add_argument("--cohort", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    registry_path = resolve_under_root(root, args.registry)
    cohort_path = resolve_under_root(root, args.cohort) if args.command == "check" else None
    excluded = {cohort_path} if cohort_path is not None else set()
    scan = append_scan(root, registry_path, excluded=excluded)
    records = load_registry(registry_path)
    if args.command == "scan":
        output = {
            "generated_at_utc": utc_now(),
            "root": str(root),
            "registry": str(registry_path),
            "scan": scan,
            "summary": registry_summary(records),
            "governance": {
                "append_only": True,
                "freshness_rule": "A proposed cohort must share neither qa_id nor canonical clip_id with any registry event.",
                "label_fields_copied": False,
                "prediction_values_copied": False,
            },
        }
        if args.report:
            report_path = resolve_under_root(root, args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            if report_path.exists():
                raise FileExistsError(f"Refusing to overwrite existing report: {report_path}")
            report_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output["report"] = str(report_path)
            output["report_sha256"] = sha256_file(report_path)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    assert cohort_path is not None
    output = {"scan": scan, "conflict_check": check_and_reserve(root, registry_path, cohort_path)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["conflict_check"]["decision"] == "PASS_FRESH_RESERVED" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileExistsError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "STOP", "error": f"{type(exc).__name__}: {exc}"}, indent=2), file=sys.stderr)
        raise SystemExit(2)
