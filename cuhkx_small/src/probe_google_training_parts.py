#!/usr/bin/env python3
"""Bounded readiness probe for the nine official Google Drive split volumes.

Each request asks for exactly byte zero and reads at most 64 KiB.  The script
never downloads an archive payload and never touches test data.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONTENT_RANGE = re.compile(r"bytes 0-0/(?P<size>\d+)$")
MAX_BODY = 65_536


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def probe(part: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        str(part["source"]),
        headers={"Range": "bytes=0-0", "User-Agent": "cuhkx-readiness-probe/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_BODY + 1)
            status = int(response.status)
            content_type = response.headers.get("Content-Type", "")
            content_range = response.headers.get("Content-Range", "")
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BODY + 1)
        status = int(exc.code)
        content_type = exc.headers.get("Content-Type", "")
        content_range = exc.headers.get("Content-Range", "")
    except Exception as exc:
        return {
            "disk": int(part["disk"]),
            "name": str(part["name"]),
            "ready": False,
            "classification": "TRANSPORT_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }

    match = CONTENT_RANGE.fullmatch(content_range)
    expected_size = int(part["size"])
    ready = (
        status == 206
        and match is not None
        and int(match.group("size")) == expected_size
        and len(body) == 1
        and "text/html" not in content_type.casefold()
    )
    lowered = body[:4096].lower()
    if ready:
        classification = "RANGE_READY"
    elif b"quota exceeded" in lowered or b"too many users" in lowered:
        classification = "GOOGLE_QUOTA"
    elif status == 200 and "text/html" in content_type.casefold():
        classification = "HTML_NOT_RANGE"
    else:
        classification = "INVALID_RANGE_RESPONSE"
    return {
        "disk": int(part["disk"]),
        "name": str(part["name"]),
        "ready": ready,
        "classification": classification,
        "status": status,
        "content_type": content_type,
        "content_range": content_range,
        "body_bytes_bounded": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_truncated": len(body) > MAX_BODY,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    results = [probe(part, args.timeout) for part in manifest["parts"]]
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "ALL_RANGE_READY" if all(item["ready"] for item in results) else "BLOCKED",
        "probe_contract": "one requested byte per volume; response body capped at 65536 bytes",
        "parts": results,
        "test_data_read": False,
        "submission_created": False,
    }
    if args.output:
        atomic_json(args.output.resolve(), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "ALL_RANGE_READY" else 2)


if __name__ == "__main__":
    main()
