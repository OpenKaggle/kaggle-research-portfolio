#!/usr/bin/env python3
"""Atomically reserve a label-blind, readable VLM cohort before protocol freeze."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


FORBIDDEN_COLUMNS = {"answer", "correct", "label", "prediction", "target"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def frame_count(path: Path) -> int:
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=nb_read_frames",
        "-of", "default=nokey=1:noprint_wrappers=1", str(path),
    ]
    value = subprocess.check_output(command, text=True, timeout=60).strip()
    if not value.isdigit() or int(value) <= 0:
        raise ValueError(f"Unreadable or empty video: {path}")
    return int(value)


def registry_exposures(path: Path) -> tuple[set[str], set[str]]:
    qa_ids: set[str] = set()
    clips: set[str] = set()
    if not path.exists():
        return qa_ids, clips
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        for key in ("excluded", "reserved"):
            for item in event.get(key, []):
                qa_id = str(item.get("qa_id", ""))
                clip = str(item.get("clip", item.get("path", "")))
                if qa_id:
                    qa_ids.add(qa_id)
                if clip:
                    clips.add(clip)
    return qa_ids, clips


def all_exposures(root: Path, cohort_path: Path, canonical: Path) -> tuple[set[str], set[str], list[str]]:
    qa_ids, clips = registry_exposures(canonical)
    sources = [str(canonical.relative_to(root))]
    row_registry = root / "reports/vlm_exposure_registry.jsonl"
    if row_registry.exists():
        for line in row_registry.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                qa_ids.add(str(item["qa_id"]))
                clips.add(str(item["path"]))
        sources.append(str(row_registry.relative_to(root)))
    for path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("qa_id"):
                    qa_ids.add(str(item["qa_id"]))
                if item.get("path"):
                    clips.add(str(item["path"]))
        sources.append(str(path.relative_to(root)))
    for path in sorted((root / "artifacts/manifests").glob("*.csv")):
        if path.resolve() == cohort_path.resolve():
            continue
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if "qa_id" in frame:
            qa_ids.update(frame["qa_id"].astype(str))
        if "path" in frame:
            clips.update(frame["path"].astype(str))
        sources.append(str(path.relative_to(root)))
    return qa_ids, clips, sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--minimum-frames", type=int, required=True)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cohort_path = args.cohort if args.cohort.is_absolute() else root / args.cohort
    canonical = root / "artifacts/manifests/vlm_exposure_registry.jsonl"
    lock_path = canonical.with_suffix(canonical.suffix + ".lock")
    report_path = root / f"reports/{args.experiment}_exposure_reservation.json"
    if args.minimum_frames <= 0:
        raise ValueError("--minimum-frames must be positive and protocol-specific")
    cohort = pd.read_csv(cohort_path, dtype=str, keep_default_na=False)
    if FORBIDDEN_COLUMNS.intersection(map(str.lower, cohort.columns)):
        raise ValueError("Cohort is not label-blind")
    required = {"qa_id", "path", "video_relative_path", "video_sha256"}
    if not required.issubset(cohort.columns):
        raise ValueError(f"Cohort lacks required columns: {sorted(required - set(cohort.columns))}")
    if cohort.empty or cohort["qa_id"].duplicated().any() or cohort["path"].duplicated().any():
        raise ValueError("Cohort must contain unique, nonempty QA IDs and clips")

    readability = []
    for row in cohort.itertuples(index=False):
        video = root / row.video_relative_path
        if not video.is_file() or sha256(video) != row.video_sha256:
            raise ValueError(f"Video missing/hash mismatch before reservation: {video}")
        frames = frame_count(video)
        readability.append({"qa_id": row.qa_id, "path": row.path, "frames": frames})
    too_short = [item for item in readability if item["frames"] < args.minimum_frames]

    canonical.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        exposed_ids, exposed_clips, sources = all_exposures(root, cohort_path, canonical)
        conflicts = [
            {"qa_id": row.qa_id, "clip": row.path}
            for row in cohort.itertuples(index=False)
            if row.qa_id in exposed_ids or row.path in exposed_clips
        ]
        passed = not too_short and not conflicts
        event = None
        if passed and not args.audit_only:
            event = {
                "event": "atomic_fresh_cohort_reservation",
                "reservation_id": hashlib.sha256(
                    f"{args.experiment}:{sha256(cohort_path)}".encode()
                ).hexdigest(),
                "recorded_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "experiment": args.experiment,
                "cohort": str(cohort_path.relative_to(root)),
                "cohort_sha256": sha256(cohort_path),
                "label_blind": True,
                "minimum_frames": args.minimum_frames,
                "readability_rows": len(readability),
                "reserved": [
                    {"qa_id": row.qa_id, "clip": row.path}
                    for row in cohort.itertuples(index=False)
                ],
                "fresh_evidence_eligible": True,
            }
            with canonical.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    report = {
        "experiment": args.experiment,
        "decision": (
            "PASS_AUDIT_ONLY_NO_RESERVATION"
            if passed and args.audit_only
            else "PASS_ATOMIC_RESERVATION"
            if passed
            else "REJECT_FAIL_CLOSED_NO_RESERVATION"
        ),
        "passed": passed,
        "audit_only": args.audit_only,
        "cohort": str(cohort_path.relative_to(root)),
        "cohort_sha256": sha256(cohort_path),
        "label_blind": True,
        "readability_rows": len(readability),
        "minimum_frames": args.minimum_frames,
        "minimum_observed_frames": min(item["frames"] for item in readability),
        "too_short": too_short,
        "exposure_conflicts": conflicts,
        "exposure_sources_scanned": sources,
        "reservation_event": event,
        "canonical_registry_sha256": sha256(canonical),
        "code_sha256": sha256(Path(__file__)),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
