#!/usr/bin/env python3
"""Resume a public HTTP download with bounded, verified byte-range requests."""

from __future__ import annotations

import argparse
import hashlib
import re
import time
import urllib.request
from pathlib import Path


CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-size", type=int, required=True)
    parser.add_argument("--chunk-mib", type=int, default=32)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    current = args.output.stat().st_size if args.output.exists() else 0
    if current > args.expected_size:
        raise ValueError(f"Existing file is too large: {current}")
    chunk_size = args.chunk_mib * 1024 * 1024
    started = time.perf_counter()
    with args.output.open("ab") as target:
        while current < args.expected_size:
            end = min(args.expected_size - 1, current + chunk_size - 1)
            request = urllib.request.Request(
                args.url,
                headers={"Range": f"bytes={current}-{end}", "User-Agent": "Mozilla/5.0"},
            )
            last_error = None
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(request, timeout=120) as response:
                        content_type = response.headers.get("Content-Type", "")
                        match = CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
                        if response.status != 206 or not match or "text/html" in content_type:
                            preview = response.read(256)
                            raise RuntimeError(
                                f"Invalid range response status={response.status} type={content_type!r} "
                                f"content_range={response.headers.get('Content-Range')!r} preview={preview!r}"
                            )
                        got_start, got_end, total = map(int, match.groups())
                        if (got_start, got_end, total) != (current, end, args.expected_size):
                            raise RuntimeError(
                                f"Unexpected Content-Range {(got_start, got_end, total)}; "
                                f"wanted {(current, end, args.expected_size)}"
                            )
                        body = response.read()
                        if len(body) != end - current + 1:
                            raise RuntimeError(f"Short range body: {len(body)} bytes")
                        target.write(body)
                        target.flush()
                        current = end + 1
                        elapsed = max(time.perf_counter() - started, 1e-6)
                        print(
                            f"{current}/{args.expected_size} ({100 * current / args.expected_size:.1f}%) "
                            f"{current / elapsed / 1024 / 1024:.1f} MiB/s",
                            flush=True,
                        )
                        last_error = None
                        break
                except Exception as exc:  # network retries preserve the last verified byte
                    last_error = exc
                    if attempt < 3:
                        time.sleep(2 ** attempt)
            if last_error is not None:
                raise last_error
    if args.output.stat().st_size != args.expected_size:
        raise ValueError("Final byte size mismatch")
    if args.expected_sha256:
        digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
        if digest != args.expected_sha256:
            raise ValueError(f"Final SHA-256 mismatch: {digest}")
        print(f"sha256={digest}", flush=True)


if __name__ == "__main__":
    main()
