#!/usr/bin/env python3
"""Download one byte interval using small verified HTTP Range requests.

The official CUHK-X Google Drive mirror currently rejects large range reads
with a quota page while accepting 16 KiB reads.  This tool makes the transport
explicit and auditable: every chunk must return HTTP 206, an exact
Content-Range, and the requested number of bytes before it is written.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import os
import re
import time
import urllib.request
from pathlib import Path


CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)$")


def fetch(url: str, start: int, end: int, retries: int) -> tuple[int, bytes, int]:
    expected = end - start + 1
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            headers={"Range": f"bytes={start}-{end}", "User-Agent": "cuhkx-range-audit/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
                content_range = response.headers.get("Content-Range", "")
                match = CONTENT_RANGE.fullmatch(content_range)
                if response.status != 206 or match is None:
                    raise RuntimeError(
                        f"range {start}-{end}: status={response.status} "
                        f"content-range={content_range!r}"
                    )
                got_start, got_end, total = match.groups()
                if int(got_start) != start or int(got_end) != end or len(payload) != expected:
                    raise RuntimeError(
                        f"range {start}-{end}: returned {got_start}-{got_end}, "
                        f"bytes={len(payload)}, expected={expected}"
                    )
                return start, payload, int(total) if total != "*" else -1
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2**attempt, 8))
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("start", type=int)
    parser.add_argument("end", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--chunk-bytes", type=int, default=16_384)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--retries", type=int, default=4)
    args = parser.parse_args()
    if args.start < 0 or args.end < args.start:
        raise SystemExit("invalid interval")
    if not 1 <= args.chunk_bytes <= 16_384:
        raise SystemExit("chunk-bytes must be within 1..16384 for this mirror")

    intervals = [
        (offset, min(offset + args.chunk_bytes - 1, args.end))
        for offset in range(args.start, args.end + 1, args.chunk_bytes)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.output, os.O_CREAT | os.O_TRUNC | os.O_RDWR, 0o600)
    try:
        os.ftruncate(descriptor, args.end - args.start + 1)
        totals: set[int] = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(fetch, args.url, start, end, args.retries): (start, end)
                for start, end in intervals
            }
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                absolute_start, payload, total = future.result()
                os.pwrite(descriptor, payload, absolute_start - args.start)
                totals.add(total)
                completed += 1
                if completed % 256 == 0 or completed == len(intervals):
                    print(f"chunks={completed}/{len(intervals)}", flush=True)
        if len(totals) != 1:
            raise RuntimeError(f"inconsistent remote sizes: {sorted(totals)}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        f"OK bytes={args.output.stat().st_size} remote_total={totals.pop()} "
        f"sha256={digest} output={args.output}"
    )


if __name__ == "__main__":
    main()
