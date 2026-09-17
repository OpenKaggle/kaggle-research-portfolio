#!/usr/bin/env python3
"""Conservatively register every QA/clip appearing in any local VLM log."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    registry_path = root / "reports/vlm_exposure_registry.jsonl"
    existing: dict[tuple[str, str, str], dict[str, object]] = {}
    if registry_path.exists():
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                existing[(item["qa_id"], item["path"], item["source_log"])] = item

    added = 0
    for log_path in sorted((root / "artifacts/vlm").glob("*.jsonl")):
        relative = str(log_path.relative_to(root))
        observed_utc = datetime.fromtimestamp(log_path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
        source_script = (
            "scripts/run_stage2_native_qwen_missing_v1.py"
            if log_path.name == "stage2_native_qwen_missing_sensor_v1.jsonl"
            else "UNKNOWN_HISTORICAL_RUNNER_CONSERVATIVELY_REGISTERED"
        )
        log_sha = sha256(log_path)
        for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            qa_id = str(item.get("qa_id", ""))
            path = str(item.get("path", ""))
            if not qa_id or not path:
                continue
            key = (qa_id, path, relative)
            if key in existing:
                continue
            existing[key] = {
                "qa_id": qa_id,
                "path": path,
                "exposure_utc": observed_utc,
                "source_script": source_script,
                "source_log": relative,
                "source_log_sha256": log_sha,
                "source_line": line_number,
                "fresh_evidence_eligible": False,
            }
            added += 1

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(existing.values(), key=lambda item: (item["qa_id"], item["path"], item["source_log"]))
    registry_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in ordered),
        encoding="utf-8",
    )
    current_log = "artifacts/vlm/stage2_native_qwen_missing_sensor_v1.jsonl"
    current = [item for item in ordered if item["source_log"] == current_log]
    if len(current) != 40:
        raise ValueError(f"Expected 40 current Stage2 exposures, found {len(current)}")
    print(
        json.dumps(
            {
                "registry": str(registry_path),
                "registry_sha256": sha256(registry_path),
                "records": len(ordered),
                "unique_qa_ids": len({item["qa_id"] for item in ordered}),
                "unique_clips": len({item["path"] for item in ordered}),
                "added": added,
                "current_stage2_records": len(current),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
