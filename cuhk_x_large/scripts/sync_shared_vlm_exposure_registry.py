#!/usr/bin/env python3
"""Append this thread's complete VLM exposures to the shared event registry."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


SOURCES = [
    ("artifacts/vlm/stage2_native_qwen_missing_sensor_v1.jsonl", "scripts/run_stage2_native_qwen_missing_v1.py"),
    ("artifacts/vlm/p1_decomposed_sensor_fresh48_v1.jsonl", "scripts/run_p1_decomposed_sensor_screen_v1.py"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = root / "artifacts/manifests/vlm_exposure_registry.jsonl"
    existing_lines = [line for line in registry.read_text(encoding="utf-8").splitlines() if line.strip()]
    existing = [json.loads(line) for line in existing_lines]
    keys = {(item.get("event"), item.get("source_log"), item.get("source_log_sha256")) for item in existing}
    appended = []
    for relative, script in SOURCES:
        path = root / relative
        digest = sha256(path)
        key = ("full_vlm_exposure_registration", relative, digest)
        if key in keys:
            continue
        excluded = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                excluded.append({"qa_id": str(item["qa_id"]), "clip": str(item["path"])})
        event = {
            "event": "full_vlm_exposure_registration",
            "recorded_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_script": script,
            "source_log": relative,
            "source_log_sha256": digest,
            "source_rows": len(excluded),
            "excluded": excluded,
            "fresh_evidence_eligible": False,
            "exclusion_policy": "Exclude the union of every registered qa_id and clip from all future fresh screens; never reuse or refill after viewing outcomes.",
        }
        with registry.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        appended.append({"source_log": relative, "rows": len(excluded)})
    print(json.dumps({"registry": str(registry), "registry_sha256": sha256(registry), "events": len(existing) + len(appended), "appended": appended}, indent=2))


if __name__ == "__main__":
    main()
