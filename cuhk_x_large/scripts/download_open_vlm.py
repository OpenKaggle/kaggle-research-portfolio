#!/usr/bin/env python3
"""Download and hash the pinned, ungated Apache-2.0 local VLM."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from huggingface_hub import snapshot_download


REPO_ID = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
REVISION = "2fd8dacbdb8f1e54b8c005f081ec5bf79c56376b"
LICENSE = "apache-2.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / "cache/models/Qwen3-VL-4B-Instruct-4bit"
    report_path = root / "reports/qwen3_vl_4b_mlx_model_manifest.json"
    started = time.perf_counter()
    resolved = snapshot_download(
        repo_id=REPO_ID,
        revision=REVISION,
        local_dir=destination,
    )
    files = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or ".cache" in path.parts:
            continue
        files.append(
            {
                "path": str(path.relative_to(destination)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    required = {"config.json", "model.safetensors", "tokenizer.json", "preprocessor_config.json"}
    present = {item["path"] for item in files}
    if not required.issubset(present):
        raise ValueError(f"Missing required model files: {sorted(required - present)}")
    report = {
        "repo_id": REPO_ID,
        "revision": REVISION,
        "license": LICENSE,
        "gated": False,
        "resolved_local_path": str(resolved),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
        "runtime_seconds": time.perf_counter() - started,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2))
    print(f"manifest_sha256={sha256(report_path)}")


if __name__ == "__main__":
    main()
