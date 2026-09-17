#!/usr/bin/env python3
"""Selectively index and extract stored files from a remote split ZIP archive.

The tool first reads only the end records and central directory, then fetches
the local header and payload ranges for members matching a safe path prefix.
It never needs to retain the complete split archive.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import argparse
import binascii
import bisect
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import struct
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


EOCD_SIGNATURE = b"PK\x05\x06"
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"
ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
CENTRAL_SIGNATURE = b"PK\x01\x02"
LOCAL_SIGNATURE = b"PK\x03\x04"
CONTENT_RANGE = re.compile(r"bytes (\d+)-(\d+)/(\d+|\*)$")
HF_TOKEN_HOST = "huggingface.co"


class ArchiveError(RuntimeError):
    """Raised when the archive or transport violates the expected contract."""


def _https_authority(url: str) -> tuple[str, int]:
    """Return a normalized HTTPS authority, rejecting ambiguous credentials."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ArchiveError("remote archive URL and redirects must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ArchiveError("remote archive URL must not contain user information")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ArchiveError("remote archive URL has an invalid port") from exc
    return parsed.hostname.lower(), port


class SafeBearerRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep Authorization only on redirects within its original authority."""

    def __init__(self, authorized_authority: tuple[str, int]) -> None:
        super().__init__()
        self.authorized_authority = authorized_authority

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None
        destination = _https_authority(newurl)
        if destination != self.authorized_authority:
            # urllib's default handler copies Authorization across hosts. HF
            # resolve URLs redirect to signed CDN URLs, which still need Range
            # but must never receive the account token.
            redirected.remove_header("Authorization")
        return redirected


@dataclass(frozen=True)
class Part:
    disk: int
    name: str
    source: str
    size: int
    sha256: str | None = None


@dataclass(frozen=True)
class DirectoryLocation:
    disk: int
    offset: int
    size: int
    entries: int
    total_disks: int


@dataclass(frozen=True)
class Entry:
    name: str
    disk: int
    local_offset: int
    compressed_size: int
    uncompressed_size: int
    crc32: int
    method: int
    flags: int
    external_attributes: int

    @property
    def is_directory(self) -> bool:
        return self.name.endswith("/")


@dataclass(frozen=True)
class SelectedEnvelope:
    """A selected member bounded by it and the next local header."""

    entry: Entry
    start: int
    end: int


@dataclass(frozen=True)
class PhysicalRange:
    """One HTTP-safe range wholly contained in one physical split volume."""

    disk: int
    offset: int
    length: int
    absolute_start: int


@dataclass(frozen=True)
class CoalescedRange:
    """A logical merged span and the selected envelopes inside it."""

    start: int
    end: int
    envelopes: tuple[SelectedEnvelope, ...]
    requests: tuple[PhysicalRange, ...]


@dataclass(frozen=True)
class CoalescedPlan:
    """Immutable offline transport plan derived only from central metadata."""

    gap_bytes: int
    max_request_bytes: int
    payload_bytes: int
    download_bytes: int
    ranges: tuple[CoalescedRange, ...]
    per_disk: tuple[dict[str, int | str], ...]

    @property
    def request_count(self) -> int:
        return sum(len(row.requests) for row in self.ranges)

    @property
    def envelopes(self) -> tuple[SelectedEnvelope, ...]:
        return tuple(envelope for row in self.ranges for envelope in row.envelopes)

    def summary(self) -> dict[str, Any]:
        request_count = self.request_count
        return {
            "gap_bytes": self.gap_bytes,
            "max_request_bytes": self.max_request_bytes,
            "files": len(self.envelopes),
            "payload_bytes": self.payload_bytes,
            "download_bytes": self.download_bytes,
            "extra_bytes_over_payload": self.download_bytes - self.payload_bytes,
            "logical_ranges": len(self.ranges),
            "nominal_requests": request_count,
            # The reader reserves one additional byte while proving that a
            # response did not exceed its exact Content-Range.
            "minimum_transport_byte_cap": (
                self.download_bytes + 1 if request_count else 0
            ),
            "per_disk": list(self.per_disk),
            "payload_downloaded": False,
        }


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or name.startswith(("/", "\\")) or path.is_absolute():
        raise ArchiveError(f"unsafe absolute member path: {name!r}")
    if "\\" in name or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveError(f"unsafe member path: {name!r}")
    return path


def _zip64_values(
    extra: bytes,
    uncompressed_size: int,
    compressed_size: int,
    local_offset: int,
    disk: int,
) -> tuple[int, int, int, int]:
    cursor = 0
    zip64: bytes | None = None
    while cursor + 4 <= len(extra):
        field_id, field_size = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        if cursor + field_size > len(extra):
            raise ArchiveError("truncated central-directory extra field")
        if field_id == 0x0001:
            zip64 = extra[cursor : cursor + field_size]
            break
        cursor += field_size

    needs_zip64 = (
        uncompressed_size == 0xFFFFFFFF
        or compressed_size == 0xFFFFFFFF
        or local_offset == 0xFFFFFFFF
        or disk == 0xFFFF
    )
    if needs_zip64 and zip64 is None:
        raise ArchiveError("ZIP64 sentinel without ZIP64 extended information")
    if zip64 is None:
        return uncompressed_size, compressed_size, local_offset, disk

    cursor = 0

    def take(fmt: str) -> int:
        nonlocal cursor
        size = struct.calcsize(fmt)
        if cursor + size > len(zip64):
            raise ArchiveError("truncated ZIP64 extended information")
        value = int(struct.unpack_from(fmt, zip64, cursor)[0])
        cursor += size
        return value

    if uncompressed_size == 0xFFFFFFFF:
        uncompressed_size = take("<Q")
    if compressed_size == 0xFFFFFFFF:
        compressed_size = take("<Q")
    if local_offset == 0xFFFFFFFF:
        local_offset = take("<Q")
    if disk == 0xFFFF:
        disk = take("<I")
    return uncompressed_size, compressed_size, local_offset, disk


def parse_central_directory(blob: bytes, expected_entries: int) -> list[Entry]:
    entries: list[Entry] = []
    cursor = 0
    fixed = struct.Struct("<4s6H3I5H2I")
    while cursor < len(blob):
        if cursor + fixed.size > len(blob):
            raise ArchiveError("truncated central-directory header")
        values = fixed.unpack_from(blob, cursor)
        if values[0] != CENTRAL_SIGNATURE:
            raise ArchiveError(
                f"unexpected central-directory signature at byte {cursor}"
            )
        (
            _,
            _made_by,
            _needed,
            flags,
            method,
            _mtime,
            _mdate,
            crc32,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
            comment_length,
            disk,
            _internal_attributes,
            external_attributes,
            local_offset,
        ) = values
        variable_start = cursor + fixed.size
        variable_end = variable_start + name_length + extra_length + comment_length
        if variable_end > len(blob):
            raise ArchiveError("truncated central-directory variable fields")
        name_bytes = blob[variable_start : variable_start + name_length]
        extra = blob[
            variable_start + name_length : variable_start + name_length + extra_length
        ]
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        name = name_bytes.decode(encoding)
        safe_member_path(name)
        uncompressed_size, compressed_size, local_offset, disk = _zip64_values(
            extra, uncompressed_size, compressed_size, local_offset, disk
        )
        entries.append(
            Entry(
                name=name,
                disk=disk,
                local_offset=local_offset,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
                crc32=crc32,
                method=method,
                flags=flags,
                external_attributes=external_attributes,
            )
        )
        cursor = variable_end
    if len(entries) != expected_entries:
        raise ArchiveError(
            f"central-directory entry count {len(entries)} != {expected_entries}"
        )
    if len({entry.name for entry in entries}) != len(entries):
        raise ArchiveError("duplicate member names are not allowed")
    return entries


def uniform_indices(length: int, count: int) -> list[int]:
    if length <= 0 or count <= 0:
        return []
    if length <= count:
        return list(range(length))
    return [
        min(length - 1, ((2 * index + 1) * length) // (2 * count))
        for index in range(count)
    ]


def select_entries(
    entries: list[Entry],
    prefix: str,
    frames_per_clip: int | None,
    subjects: set[int] | None = None,
) -> tuple[list[Entry], dict[str, int]]:
    available = [
        entry
        for entry in entries
        if not entry.is_directory and entry.name.startswith(prefix)
    ]
    matches = (
        available
        if subjects is None
        else [entry for entry in available if entry_subject(entry) in subjects]
    )
    details = {
        "groups": 0,
        "available_files": len(available),
        "available_payload_bytes": sum(
            entry.uncompressed_size for entry in available
        ),
    }
    if subjects is not None:
        details.update(
            {
                "eligible_files": len(matches),
                "eligible_payload_bytes": sum(
                    entry.uncompressed_size for entry in matches
                ),
            }
        )
    if frames_per_clip is None:
        return matches, details
    if frames_per_clip <= 0:
        raise ArchiveError("frames per clip must be positive")
    groups: dict[str, list[Entry]] = {}
    for entry in matches:
        parent = str(PurePosixPath(entry.name).parent)
        groups.setdefault(parent, []).append(entry)
    selected: list[Entry] = []
    for parent in sorted(groups):
        candidates = sorted(groups[parent], key=lambda entry: entry.name)
        selected.extend(
            candidates[index]
            for index in uniform_indices(len(candidates), frames_per_clip)
        )
    details["groups"] = len(groups)
    return selected, details


class ArchiveReader:
    def __init__(
        self,
        parts: list[Part],
        max_range_bytes: int = 16_384,
        retries: int = 4,
        bearer_token_env: str | None = None,
        transport_byte_cap: int | None = None,
    ) -> None:
        if [part.disk for part in parts] != list(range(len(parts))):
            raise ArchiveError("manifest disks must be contiguous and zero-based")
        if any(part.size <= 0 for part in parts):
            raise ArchiveError("manifest part sizes must be positive")
        if bearer_token_env is not None and re.fullmatch(
            r"[A-Z_][A-Z0-9_]*", bearer_token_env
        ) is None:
            raise ArchiveError("bearer token environment-variable name is invalid")
        if transport_byte_cap is not None and transport_byte_cap <= 0:
            raise ArchiveError("transport byte cap must be positive")
        if bearer_token_env is not None:
            for part in parts:
                if _https_authority(part.source) != (HF_TOKEN_HOST, 443):
                    raise ArchiveError(
                        "bearer-authenticated archive sources must use "
                        f"https://{HF_TOKEN_HOST}"
                    )
        self.parts = parts
        self.max_range_bytes = max_range_bytes
        self.retries = retries
        self.transport_byte_cap = transport_byte_cap
        # Store only the environment-variable name.  The secret itself is read
        # immediately before a request and is never retained in reports/errors.
        self.bearer_token_env = bearer_token_env
        self._http_opener = (
            urllib.request.build_opener(
                SafeBearerRedirectHandler((HF_TOKEN_HOST, 443))
            )
            if bearer_token_env is not None
            else None
        )
        self._bytes_read = 0
        self._requests = 0
        self._attempted_requests = 0
        self._attempted_range_bytes = 0
        self._wire_bytes = 0
        self._failed_wire_bytes = 0
        self._reserved_wire_bytes = 0
        self._lock = threading.Lock()

    @property
    def bytes_read(self) -> int:
        return self._bytes_read

    @property
    def requests(self) -> int:
        return self._requests

    @property
    def wire_bytes(self) -> int:
        return self._wire_bytes

    def transport_stats(self) -> dict[str, int | None]:
        with self._lock:
            return {
                "attempted_requests": self._attempted_requests,
                "successful_requests": self._requests,
                "failed_requests": self._attempted_requests - self._requests,
                "attempted_range_bytes": self._attempted_range_bytes,
                "successful_body_bytes": self._bytes_read,
                "wire_bytes": self._wire_bytes,
                "failed_wire_bytes": self._failed_wire_bytes,
                "transport_byte_cap": self.transport_byte_cap,
                "transport_byte_cap_remaining": (
                    None
                    if self.transport_byte_cap is None
                    else self.transport_byte_cap - self._wire_bytes
                ),
            }

    def ensure_capacity(self, body_bytes: int, safety_bytes: int = 0) -> None:
        """Fail before transport when a complete planned run cannot fit."""
        if body_bytes < 0 or safety_bytes < 0:
            raise ArchiveError("transport capacity check cannot be negative")
        with self._lock:
            if (
                self.transport_byte_cap is not None
                and self._wire_bytes
                + self._reserved_wire_bytes
                + body_bytes
                + safety_bytes
                > self.transport_byte_cap
            ):
                raise ArchiveError(
                    "transport byte cap is below the complete planned run"
                )

    def _begin_attempt(self, requested_length: int, reserve_bytes: int) -> None:
        with self._lock:
            if (
                self.transport_byte_cap is not None
                and self._wire_bytes + self._reserved_wire_bytes + reserve_bytes
                > self.transport_byte_cap
            ):
                raise ArchiveError("transport byte cap exhausted before request")
            self._reserved_wire_bytes += reserve_bytes
            self._attempted_requests += 1
            self._attempted_range_bytes += requested_length

    def _finish_attempt(
        self,
        reserve_bytes: int,
        wire_bytes: int,
        *,
        success: bool,
    ) -> None:
        if not 0 <= wire_bytes <= reserve_bytes:
            raise AssertionError("wire byte accounting exceeded reservation")
        with self._lock:
            self._reserved_wire_bytes -= reserve_bytes
            self._wire_bytes += wire_bytes
            if success:
                self._bytes_read += wire_bytes
                self._requests += 1
            else:
                self._failed_wire_bytes += wire_bytes

    def _read_one(self, part: Part, start: int, length: int) -> bytes:
        if start < 0 or length < 0 or start + length > part.size:
            raise ArchiveError(
                f"invalid range for {part.name}: offset={start}, bytes={length}"
            )
        parsed = urllib.parse.urlparse(part.source)
        if parsed.scheme in {"", "file"}:
            self._begin_attempt(length, length)
            try:
                path = Path(urllib.request.url2pathname(parsed.path))
                with path.open("rb") as handle:
                    handle.seek(start)
                    payload = handle.read(length)
                if len(payload) != length:
                    self._finish_attempt(length, len(payload), success=False)
                    raise ArchiveError(f"short local read from {part.name}")
                self._finish_attempt(length, length, success=True)
                return payload
            except ArchiveError:
                raise
            except Exception:
                self._finish_attempt(length, 0, success=False)
                raise

        end = start + length - 1
        for attempt in range(self.retries + 1):
            # The extra byte makes an ignored or oversized response observable
            # without ever consuming an unbounded body.
            reservation = length + 1
            headers = {
                "Range": f"bytes={start}-{end}",
                "User-Agent": "cuhkx-selective-split-zip/1.0",
            }
            if self.bearer_token_env is not None:
                token = os.environ.get(self.bearer_token_env, "").strip()
                if not token:
                    raise ArchiveError(
                        f"required bearer token environment variable "
                        f"{self.bearer_token_env} is not set"
                    )
                headers["Authorization"] = f"Bearer {token}"
            request = urllib.request.Request(
                part.source,
                headers=headers,
            )
            self._begin_attempt(length, reservation)
            attempt_settled = False
            try:
                open_request = (
                    self._http_opener.open
                    if self._http_opener is not None
                    else urllib.request.urlopen
                )
                with open_request(request, timeout=60) as response:
                    # A server that ignores Range must not cause a multi-GB
                    # response to be consumed before the status is rejected.
                    payload = response.read(length + 1)
                    content_range = response.headers.get("Content-Range", "")
                    match = CONTENT_RANGE.fullmatch(content_range)
                    if response.status != 206 or match is None:
                        content_type = response.headers.get("Content-Type", "")
                        self._finish_attempt(
                            reservation, len(payload), success=False
                        )
                        attempt_settled = True
                        raise ArchiveError(
                            f"{part.name} rejected range {start}-{end}: "
                            f"status={response.status}, content-type={content_type!r}, "
                            f"bounded-body-bytes={len(payload)}"
                        )
                    got_start, got_end, total = match.groups()
                    if (
                        int(got_start) != start
                        or int(got_end) != end
                        or total == "*"
                        or int(total) != part.size
                        or len(payload) != length
                    ):
                        self._finish_attempt(
                            reservation, len(payload), success=False
                        )
                        attempt_settled = True
                        raise ArchiveError(
                            f"{part.name} returned inconsistent Content-Range"
                        )
                    self._finish_attempt(reservation, length, success=True)
                    attempt_settled = True
                    return payload
            except urllib.error.HTTPError as exc:
                # Authorization failures remain body-blind. For retryable HTTP
                # failures, count a bounded error body when urllib exposes one.
                failed_body = b""
                if exc.code not in {401, 403}:
                    try:
                        failed_body = exc.read(reservation)
                    except OSError:
                        failed_body = b""
                self._finish_attempt(
                    reservation, len(failed_body), success=False
                )
                attempt_settled = True
                if exc.code in {401, 403}:
                    raise ArchiveError(
                        f"{part.name} authorization failed with HTTP {exc.code}; "
                        "credential value was not logged"
                    ) from exc
                if attempt == self.retries:
                    raise ArchiveError(
                        f"{part.name} range {start}-{end} failed with HTTP {exc.code}"
                    ) from exc
            except ArchiveError:
                if not attempt_settled:
                    self._finish_attempt(reservation, 0, success=False)
                raise
            except (OSError, urllib.error.URLError) as exc:
                self._finish_attempt(reservation, 0, success=False)
                attempt_settled = True
                if attempt == self.retries:
                    raise ArchiveError(
                        f"failed range {start}-{end} from {part.name}: {exc}"
                    ) from exc
                time.sleep(min(2**attempt, 8))
        raise AssertionError("unreachable")

    def read(self, disk: int, offset: int, length: int) -> bytes:
        """Read a logical span, crossing split-volume boundaries if needed."""
        if not 0 <= disk < len(self.parts):
            raise ArchiveError(f"invalid disk index {disk}")
        chunks: list[bytes] = []
        remaining = length
        current_disk = disk
        current_offset = offset
        while remaining:
            if current_disk >= len(self.parts):
                raise ArchiveError("logical span runs past final split volume")
            part = self.parts[current_disk]
            if current_offset > part.size:
                raise ArchiveError(f"offset past end of {part.name}")
            available = part.size - current_offset
            if available == 0:
                current_disk += 1
                current_offset = 0
                continue
            take_from_part = min(remaining, available)
            part_cursor = current_offset
            part_remaining = take_from_part
            while part_remaining:
                take = min(part_remaining, self.max_range_bytes)
                chunks.append(self._read_one(part, part_cursor, take))
                part_cursor += take
                part_remaining -= take
            remaining -= take_from_part
            current_disk += 1
            current_offset = 0
        return b"".join(chunks)

    def advance(self, disk: int, offset: int, length: int) -> tuple[int, int]:
        """Advance a logical split-archive position and normalize it."""
        if length < 0:
            raise ArchiveError("cannot advance by a negative length")
        current_disk = disk
        current_offset = offset
        remaining = length
        while remaining:
            if current_disk >= len(self.parts):
                raise ArchiveError("logical position runs past final split volume")
            available = self.parts[current_disk].size - current_offset
            if available < 0:
                raise ArchiveError("logical position starts past a split volume")
            if remaining < available:
                return current_disk, current_offset + remaining
            remaining -= available
            current_disk += 1
            current_offset = 0
        if current_disk < len(self.parts) and current_offset == self.parts[current_disk].size:
            return current_disk + 1, 0
        return current_disk, current_offset


def entry_subject(entry: Entry) -> int | None:
    for component in PurePosixPath(entry.name).parts:
        match = re.fullmatch(r"user(\d+)", component, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def find_directory(reader: ArchiveReader) -> DirectoryLocation:
    last = reader.parts[-1]
    tail_size = min(last.size, 131_072)
    tail_start = last.size - tail_size
    tail = reader.read(last.disk, tail_start, tail_size)
    eocd_relative = tail.rfind(EOCD_SIGNATURE)
    if eocd_relative < 0 or eocd_relative + 22 > len(tail):
        raise ArchiveError("ZIP end-of-central-directory record not found")
    (
        _,
        eocd_disk,
        cd_disk,
        entries_on_disk,
        total_entries,
        cd_size,
        cd_offset,
        comment_length,
    ) = struct.unpack_from("<4s4H2IH", tail, eocd_relative)
    if eocd_relative + 22 + comment_length > len(tail):
        raise ArchiveError("truncated ZIP comment")

    zip64_required = (
        eocd_disk == 0xFFFF
        or cd_disk == 0xFFFF
        or entries_on_disk == 0xFFFF
        or total_entries == 0xFFFF
        or cd_size == 0xFFFFFFFF
        or cd_offset == 0xFFFFFFFF
    )
    if zip64_required:
        locator_relative = tail.rfind(
            ZIP64_LOCATOR_SIGNATURE, 0, eocd_relative
        )
        if locator_relative < 0 or locator_relative + 20 > len(tail):
            raise ArchiveError("ZIP64 locator not found")
        _, zip64_disk, zip64_offset, total_disks = struct.unpack_from(
            "<4sIQI", tail, locator_relative
        )
        record_prefix = reader.read(zip64_disk, zip64_offset, 56)
        if record_prefix[:4] != ZIP64_EOCD_SIGNATURE:
            raise ArchiveError("ZIP64 end record signature mismatch")
        (
            _,
            record_size,
            _made_by,
            _needed,
            eocd_disk,
            cd_disk,
            entries_on_disk,
            total_entries,
            cd_size,
            cd_offset,
        ) = struct.unpack_from("<4sQ2H2I4Q", record_prefix)
        if record_size < 44:
            raise ArchiveError("invalid ZIP64 end record size")
    else:
        total_disks = eocd_disk + 1

    if eocd_disk != len(reader.parts) - 1 or total_disks != len(reader.parts):
        raise ArchiveError(
            f"manifest has {len(reader.parts)} disks but archive reports {total_disks}"
        )
    if entries_on_disk > total_entries:
        raise ArchiveError("invalid entry counts in ZIP end record")
    return DirectoryLocation(
        disk=int(cd_disk),
        offset=int(cd_offset),
        size=int(cd_size),
        entries=int(total_entries),
        total_disks=int(total_disks),
    )


def load_manifest(path: Path) -> tuple[dict[str, Any], list[Part]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    parts = [
        Part(
            disk=int(row["disk"]),
            name=str(row["name"]),
            source=str(row["source"]),
            size=int(row["size"]),
            sha256=str(row["sha256"]) if row.get("sha256") else None,
        )
        for row in raw["parts"]
    ]
    parts.sort(key=lambda part: part.disk)
    return raw, parts


def load_or_fetch_directory(
    reader: ArchiveReader,
    cache_path: Path,
    manifest: dict[str, Any],
) -> tuple[DirectoryLocation, bytes, bool]:
    expected = manifest.get("expected_directory", {})
    geometry_keys = ("disk", "offset", "size", "entries", "total_disks")
    expected_hash = expected.get("sha256") if isinstance(expected, dict) else None

    # A cache with a fully pinned location and digest is an immutable local
    # control-plane artifact. Validate it before any request, so reruns do not
    # needlessly re-read the remote ZIP tail. An unpinned cache is never used
    # and never triggers a silent network fallback.
    if cache_path.is_file():
        missing = [
            key
            for key in (*geometry_keys, "sha256")
            if not isinstance(expected, dict) or key not in expected
        ]
        if missing:
            raise ArchiveError(
                "cached central directory requires pinned geometry and SHA-256"
            )
        if not isinstance(expected_hash, str) or re.fullmatch(
            r"[0-9a-f]{64}", expected_hash
        ) is None:
            raise ArchiveError("cached central-directory SHA-256 is invalid")
        location = DirectoryLocation(
            disk=int(expected["disk"]),
            offset=int(expected["offset"]),
            size=int(expected["size"]),
            entries=int(expected["entries"]),
            total_disks=int(expected["total_disks"]),
        )
        if (
            not 0 <= location.disk < len(reader.parts)
            or location.offset < 0
            or location.size <= 0
            or location.entries < 0
            or location.total_disks != len(reader.parts)
        ):
            raise ArchiveError("cached central-directory geometry is invalid")
        # Prove that the pinned logical span fits the manifest parts without
        # reading any remote bytes.
        remaining = location.size
        disk = location.disk
        offset = location.offset
        while remaining:
            if disk >= len(reader.parts) or offset > reader.parts[disk].size:
                raise ArchiveError("cached central-directory span exceeds archive")
            take = min(remaining, reader.parts[disk].size - offset)
            if take == 0:
                disk += 1
                offset = 0
                continue
            remaining -= take
            disk += 1
            offset = 0
        blob = cache_path.read_bytes()
        if len(blob) != location.size:
            raise ArchiveError("cached central-directory size mismatch")
        if sha256_bytes(blob) != expected_hash:
            raise ArchiveError("cached central-directory SHA-256 mismatch")
        return location, blob, True

    location = find_directory(reader)
    for key, actual in {
        "disk": location.disk,
        "offset": location.offset,
        "size": location.size,
        "entries": location.entries,
        "total_disks": location.total_disks,
    }.items():
        if key in expected and int(expected[key]) != actual:
            raise ArchiveError(
                f"central-directory {key}={actual}, expected {expected[key]}"
            )
    blob = reader.read(location.disk, location.offset, location.size)
    actual_hash = sha256_bytes(blob)
    if expected_hash and actual_hash != expected_hash:
        raise ArchiveError("central-directory SHA-256 mismatch")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(cache_path.suffix + ".partial")
    temporary.write_bytes(blob)
    os.replace(temporary, cache_path)
    return location, blob, False


def data_location(reader: ArchiveReader, entry: Entry) -> tuple[int, int]:
    fixed = reader.read(entry.disk, entry.local_offset, 30)
    if fixed[:4] != LOCAL_SIGNATURE:
        raise ArchiveError(f"local header signature mismatch for {entry.name}")
    (
        _,
        _needed,
        flags,
        method,
        _mtime,
        _mdate,
        _crc32,
        _compressed_size,
        _uncompressed_size,
        name_length,
        extra_length,
    ) = struct.unpack("<4s5H3I2H", fixed)
    if flags != entry.flags or method != entry.method:
        raise ArchiveError(f"local/central header mismatch for {entry.name}")
    variable_disk, variable_offset = reader.advance(entry.disk, entry.local_offset, 30)
    variable = reader.read(variable_disk, variable_offset, name_length + extra_length)
    encoding = "utf-8" if flags & 0x0800 else "cp437"
    local_name = variable[:name_length].decode(encoding)
    if local_name != entry.name:
        raise ArchiveError(f"local filename mismatch for {entry.name}")
    return reader.advance(variable_disk, variable_offset, name_length + extra_length)


def allocate_span_by_disk(
    reader: ArchiveReader, disk: int, offset: int, length: int
) -> dict[int, int]:
    """Allocate a logical payload span across split volumes without reading it."""
    allocated: dict[int, int] = {}
    remaining = length
    current_disk = disk
    current_offset = offset
    while remaining:
        if current_disk >= len(reader.parts):
            raise ArchiveError("planned payload runs past final split volume")
        part = reader.parts[current_disk]
        if current_offset > part.size:
            raise ArchiveError("planned payload starts past split volume")
        take = min(remaining, part.size - current_offset)
        if take == 0:
            current_disk += 1
            current_offset = 0
            continue
        allocated[current_disk] = allocated.get(current_disk, 0) + take
        remaining -= take
        current_disk += 1
        current_offset = 0
    return allocated


def volume_starts(parts: list[Part]) -> tuple[int, ...]:
    """Return absolute starts, plus one final total-size sentinel."""
    starts = [0]
    for part in parts:
        starts.append(starts[-1] + part.size)
    return tuple(starts)


def absolute_position(
    parts: list[Part], starts: tuple[int, ...], disk: int, offset: int
) -> int:
    if not 0 <= disk < len(parts) or not 0 <= offset <= parts[disk].size:
        raise ArchiveError("logical archive position is outside its split volume")
    return starts[disk] + offset


def physical_ranges_for_span(
    parts: list[Part],
    starts: tuple[int, ...],
    start: int,
    end: int,
    max_request_bytes: int,
) -> tuple[PhysicalRange, ...]:
    """Split an absolute half-open span at volume and request boundaries."""
    if not 0 <= start < end <= starts[-1]:
        raise ArchiveError("coalesced span is outside the split archive")
    if not 1 <= max_request_bytes <= 16 * 1024 * 1024:
        raise ArchiveError("coalesced request size must be within 1..16777216")
    result: list[PhysicalRange] = []
    cursor = start
    while cursor < end:
        disk = bisect.bisect_right(starts, cursor) - 1
        if disk >= len(parts):
            raise ArchiveError("coalesced span runs past the final volume")
        volume_end = starts[disk + 1]
        take = min(end - cursor, volume_end - cursor, max_request_bytes)
        if take <= 0:
            raise ArchiveError("coalesced range planning made no progress")
        result.append(
            PhysicalRange(
                disk=disk,
                offset=cursor - starts[disk],
                length=take,
                absolute_start=cursor,
            )
        )
        cursor += take
    return tuple(result)


def build_coalesced_plan(
    parts: list[Part],
    directory: DirectoryLocation,
    all_entries: list[Entry],
    selected_entries: list[Entry],
    gap_bytes: int,
    max_request_bytes: int,
) -> CoalescedPlan:
    """Build a header-safe plan using every entry's next local-header bound."""
    if gap_bytes < 0:
        raise ArchiveError("coalesce gap must be non-negative")
    if len({entry.name for entry in all_entries}) != len(all_entries):
        raise ArchiveError("all-entry list contains duplicate member names")
    if len({entry.name for entry in selected_entries}) != len(selected_entries):
        raise ArchiveError("selected-entry list contains duplicate member names")

    starts = volume_starts(parts)
    directory_start = absolute_position(
        parts, starts, directory.disk, directory.offset
    )
    ordered = sorted(
        all_entries,
        key=lambda entry: absolute_position(
            parts, starts, entry.disk, entry.local_offset
        ),
    )
    positions = [
        absolute_position(parts, starts, entry.disk, entry.local_offset)
        for entry in ordered
    ]
    if len(set(positions)) != len(positions):
        raise ArchiveError("local-header positions are not unique")
    if not positions or positions[-1] >= directory_start:
        raise ArchiveError("local-header position reaches the central directory")
    by_name = {entry.name: (entry, index) for index, entry in enumerate(ordered)}

    envelopes: list[SelectedEnvelope] = []
    for selected in selected_entries:
        indexed = by_name.get(selected.name)
        if indexed is None or indexed[0] != selected:
            raise ArchiveError("selected entry is absent from the all-entry index")
        entry, index = indexed
        if entry.is_directory:
            raise ArchiveError("coalesced extraction cannot select a directory")
        if entry.flags & 0x0001:
            raise ArchiveError(f"encrypted member is not supported: {entry.name}")
        if entry.flags & 0x0008:
            raise ArchiveError(
                f"data-descriptor member is not supported: {entry.name}"
            )
        if entry.method != 0 or entry.compressed_size != entry.uncompressed_size:
            raise ArchiveError(
                f"coalesced extraction requires a stored member: {entry.name}"
            )
        start = positions[index]
        end = positions[index + 1] if index + 1 < len(positions) else directory_start
        if end - start < 30 + entry.compressed_size:
            raise ArchiveError(f"member envelope is too short: {entry.name}")
        envelopes.append(SelectedEnvelope(entry=entry, start=start, end=end))
    envelopes.sort(key=lambda envelope: envelope.start)

    if not envelopes:
        return CoalescedPlan(
            gap_bytes=gap_bytes,
            max_request_bytes=max_request_bytes,
            payload_bytes=0,
            download_bytes=0,
            ranges=(),
            per_disk=(),
        )

    logical: list[tuple[int, int, list[SelectedEnvelope]]] = []
    range_start = envelopes[0].start
    range_end = envelopes[0].end
    range_envelopes = [envelopes[0]]
    for envelope in envelopes[1:]:
        gap = envelope.start - range_end
        if gap < 0:
            raise ArchiveError("selected member envelopes overlap")
        if gap <= gap_bytes:
            range_end = envelope.end
            range_envelopes.append(envelope)
        else:
            logical.append((range_start, range_end, range_envelopes))
            range_start = envelope.start
            range_end = envelope.end
            range_envelopes = [envelope]
    logical.append((range_start, range_end, range_envelopes))

    coalesced: list[CoalescedRange] = []
    per_disk: dict[int, dict[str, int | str]] = {}
    for start, end, members in logical:
        requests = physical_ranges_for_span(
            parts, starts, start, end, max_request_bytes
        )
        for request in requests:
            row = per_disk.setdefault(
                request.disk,
                {
                    "disk": request.disk,
                    "part": parts[request.disk].name,
                    "download_bytes": 0,
                    "nominal_requests": 0,
                },
            )
            row["download_bytes"] = int(row["download_bytes"]) + request.length
            row["nominal_requests"] = int(row["nominal_requests"]) + 1
        coalesced.append(
            CoalescedRange(
                start=start,
                end=end,
                envelopes=tuple(members),
                requests=requests,
            )
        )

    download_bytes = sum(row.end - row.start for row in coalesced)
    return CoalescedPlan(
        gap_bytes=gap_bytes,
        max_request_bytes=max_request_bytes,
        payload_bytes=sum(entry.uncompressed_size for entry in selected_entries),
        download_bytes=download_bytes,
        ranges=tuple(coalesced),
        per_disk=tuple(per_disk[disk] for disk in sorted(per_disk)),
    )


def plan_selected_payload_ranges(
    reader: ArchiveReader, entries: list[Entry]
) -> dict[str, Any]:
    """Probe local headers, then return exact per-volume payload byte totals."""
    before_bytes = reader.bytes_read
    before_requests = reader.requests
    per_disk: dict[int, dict[str, int | str]] = {}
    for entry in entries:
        if entry.method != 0 or entry.compressed_size != entry.uncompressed_size:
            raise ArchiveError(f"range planning requires stored member: {entry.name}")
        payload_disk, payload_offset = data_location(reader, entry)
        allocation = allocate_span_by_disk(
            reader, payload_disk, payload_offset, entry.compressed_size
        )
        for disk, payload_bytes in allocation.items():
            row = per_disk.setdefault(
                disk,
                {
                    "disk": disk,
                    "part": reader.parts[disk].name,
                    "payload_bytes": 0,
                    "member_spans": 0,
                },
            )
            row["payload_bytes"] = int(row["payload_bytes"]) + payload_bytes
            row["member_spans"] = int(row["member_spans"]) + 1
    return {
        "files": len(entries),
        "payload_bytes": sum(entry.uncompressed_size for entry in entries),
        "per_disk": [per_disk[disk] for disk in sorted(per_disk)],
        "header_probe_bytes": reader.bytes_read - before_bytes,
        "header_probe_requests": reader.requests - before_requests,
        "payload_downloaded": False,
    }


def verify_existing(path: Path, entry: Entry) -> bool:
    if not path.is_file() or path.stat().st_size != entry.uncompressed_size:
        return False
    crc = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            crc = binascii.crc32(chunk, crc)
    return crc & 0xFFFFFFFF == entry.crc32


def partition_verified_existing(
    entries: list[Entry], output_root: Path
) -> tuple[list[Entry], list[Entry]]:
    """Split entries by verified output before any remote range is planned."""
    verified: list[Entry] = []
    pending: list[Entry] = []
    for entry in entries:
        relative = safe_member_path(entry.name)
        target = output_root.joinpath(*relative.parts)
        if verify_existing(target, entry):
            verified.append(entry)
        else:
            pending.append(entry)
    return verified, pending


def extract_envelope_blob(
    envelope: SelectedEnvelope, blob: bytes, output_root: Path
) -> str:
    """Validate one complete envelope and atomically publish only its payload."""
    entry = envelope.entry
    if len(blob) != envelope.end - envelope.start or len(blob) < 30:
        raise ArchiveError(f"incomplete member envelope: {entry.name}")
    (
        signature,
        _needed,
        flags,
        method,
        _mtime,
        _mdate,
        local_crc32,
        local_compressed_size,
        local_uncompressed_size,
        name_length,
        extra_length,
    ) = struct.unpack_from("<4s5H3I2H", blob)
    if signature != LOCAL_SIGNATURE:
        raise ArchiveError(f"local header signature mismatch for {entry.name}")
    if flags != entry.flags or method != entry.method:
        raise ArchiveError(f"local/central header mismatch for {entry.name}")
    if flags & 0x0001 or flags & 0x0008:
        raise ArchiveError(f"unsupported local flags for {entry.name}")
    if method != 0 or entry.compressed_size != entry.uncompressed_size:
        raise ArchiveError(f"coalesced member is not stored: {entry.name}")
    if local_crc32 != entry.crc32:
        raise ArchiveError(f"local/central CRC mismatch for {entry.name}")
    if local_compressed_size not in {entry.compressed_size, 0xFFFFFFFF}:
        raise ArchiveError(f"local compressed-size mismatch for {entry.name}")
    if local_uncompressed_size not in {entry.uncompressed_size, 0xFFFFFFFF}:
        raise ArchiveError(f"local uncompressed-size mismatch for {entry.name}")

    variable_end = 30 + name_length + extra_length
    payload_end = variable_end + entry.compressed_size
    if variable_end > len(blob) or payload_end > len(blob):
        raise ArchiveError(f"payload exceeds member envelope: {entry.name}")
    encoding = "utf-8" if flags & 0x0800 else "cp437"
    try:
        local_name = blob[30 : 30 + name_length].decode(encoding)
    except UnicodeDecodeError as exc:
        raise ArchiveError(f"invalid local filename encoding for {entry.name}") from exc
    if local_name != entry.name:
        raise ArchiveError(f"local filename mismatch for {entry.name}")

    payload = bytes(blob[variable_end:payload_end])
    if len(payload) != entry.uncompressed_size:
        raise ArchiveError(f"extracted-size mismatch for {entry.name}")
    if binascii.crc32(payload) & 0xFFFFFFFF != entry.crc32:
        raise ArchiveError(f"CRC-32 mismatch for {entry.name}")

    relative = safe_member_path(entry.name)
    root = output_root.resolve()
    target = output_root.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise ArchiveError(f"output path escapes root: {entry.name}") from exc
    if verify_existing(target, entry):
        return "reused"

    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".partial",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.stat().st_size != entry.uncompressed_size:
            raise ArchiveError(f"temporary-size mismatch for {entry.name}")
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return "extracted"


def extract_coalesced_plan(
    reader: ArchiveReader, plan: CoalescedPlan, output_root: Path
) -> dict[str, int]:
    """Stream a plan, discarding gaps and publishing selected files only."""
    # One safety byte is reserved because remote reads request length+1 to
    # detect a server that ignored the exact Range.
    reader.ensure_capacity(
        plan.download_bytes, safety_bytes=1 if plan.request_count else 0
    )
    outcomes = {"extracted": 0, "reused": 0}
    for logical in plan.ranges:
        envelope_index = 0
        envelope_blob = bytearray()
        expected_request_start = logical.start
        for request in logical.requests:
            if request.absolute_start != expected_request_start:
                raise ArchiveError("physical coalesced requests are not contiguous")
            chunk = reader._read_one(
                reader.parts[request.disk], request.offset, request.length
            )
            chunk_cursor = 0
            chunk_end = request.absolute_start + len(chunk)
            while chunk_cursor < len(chunk):
                absolute_cursor = request.absolute_start + chunk_cursor
                if envelope_index >= len(logical.envelopes):
                    chunk_cursor = len(chunk)
                    continue
                envelope = logical.envelopes[envelope_index]
                if absolute_cursor < envelope.start:
                    chunk_cursor += min(
                        len(chunk) - chunk_cursor,
                        envelope.start - absolute_cursor,
                    )
                    continue
                expected_envelope_cursor = envelope.start + len(envelope_blob)
                if absolute_cursor != expected_envelope_cursor:
                    raise ArchiveError("member envelope stream is discontinuous")
                take = min(
                    len(chunk) - chunk_cursor,
                    envelope.end - absolute_cursor,
                )
                envelope_blob.extend(chunk[chunk_cursor : chunk_cursor + take])
                chunk_cursor += take
                if envelope.start + len(envelope_blob) == envelope.end:
                    outcome = extract_envelope_blob(
                        envelope, bytes(envelope_blob), output_root
                    )
                    outcomes[outcome] += 1
                    envelope_index += 1
                    envelope_blob.clear()
            if chunk_end != request.absolute_start + request.length:
                raise ArchiveError("coalesced request returned a short body")
            expected_request_start = chunk_end
        if expected_request_start != logical.end:
            raise ArchiveError("coalesced physical ranges do not cover logical span")
        if envelope_index != len(logical.envelopes) or envelope_blob:
            raise ArchiveError("coalesced range ended with an incomplete member")
    if sum(outcomes.values()) != len(plan.envelopes):
        raise ArchiveError("coalesced extraction outcome count mismatch")
    return outcomes


def extract_one(reader: ArchiveReader, entry: Entry, output_root: Path) -> str:
    if entry.is_directory:
        return "directory"
    if entry.flags & 0x0001:
        raise ArchiveError(f"encrypted member is not supported: {entry.name}")
    if entry.method != 0:
        raise ArchiveError(
            f"only stored members are supported; {entry.name} uses method {entry.method}"
        )
    if entry.compressed_size != entry.uncompressed_size:
        raise ArchiveError(f"stored-size mismatch for {entry.name}")

    relative = safe_member_path(entry.name)
    target = output_root.joinpath(*relative.parts)
    if verify_existing(target, entry):
        return "reused"
    target.parent.mkdir(parents=True, exist_ok=True)
    disk, offset = data_location(reader, entry)
    temporary = target.with_suffix(target.suffix + ".partial")
    crc = 0
    remaining = entry.compressed_size
    current_disk = disk
    current_offset = offset
    with temporary.open("wb") as handle:
        while remaining:
            take = min(remaining, 1024 * 1024)
            payload = reader.read(current_disk, current_offset, take)
            handle.write(payload)
            crc = binascii.crc32(payload, crc)
            remaining -= take
            current_disk, current_offset = reader.advance(
                current_disk, current_offset, take
            )
        handle.flush()
        os.fsync(handle.fileno())
    if temporary.stat().st_size != entry.uncompressed_size:
        raise ArchiveError(f"extracted-size mismatch for {entry.name}")
    if crc & 0xFFFFFFFF != entry.crc32:
        raise ArchiveError(f"CRC-32 mismatch for {entry.name}")
    os.replace(temporary, target)
    return "extracted"


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--prefix",
        action="append",
        default=None,
        help="Safe archive prefix; repeat to plan/extract multiple modalities.",
    )
    parser.add_argument(
        "--subjects",
        default=None,
        help="Optional comma-separated user numbers for an exact subject slice.",
    )
    parser.add_argument(
        "--frames-per-clip",
        type=int,
        default=None,
        help="Uniformly retain at most this many files from each member directory.",
    )
    parser.add_argument("--central-directory-cache", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--index-only", action="store_true")
    parser.add_argument(
        "--exact-range-plan",
        action="store_true",
        help="With --index-only, probe member headers and report exact payload bytes per volume.",
    )
    parser.add_argument(
        "--bearer-token-env",
        default=None,
        help="Name of an environment variable containing a Bearer token; never a token value.",
    )
    parser.add_argument(
        "--coalesce-gap-bytes",
        type=int,
        default=None,
        help=(
            "Enable header-envelope coalescing and merge selected spans across "
            "at most this many unselected bytes."
        ),
    )
    parser.add_argument(
        "--transport-byte-cap",
        type=int,
        default=None,
        help=(
            "Hard cap for all response body bytes, including bounded failed "
            "responses and retries. Required for coalesced extraction."
        ),
    )
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-range-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--retries", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.max_range_bytes <= 16 * 1024 * 1024:
        raise SystemExit("--max-range-bytes must be within 1..16777216")
    if not 1 <= args.workers <= 64:
        raise SystemExit("--workers must be within 1..64")
    if args.exact_range_plan and not args.index_only:
        raise SystemExit("--exact-range-plan requires --index-only")
    if args.coalesce_gap_bytes is not None and args.coalesce_gap_bytes < 0:
        raise SystemExit("--coalesce-gap-bytes must be non-negative")
    if args.transport_byte_cap is not None and args.transport_byte_cap <= 0:
        raise SystemExit("--transport-byte-cap must be positive")
    if args.coalesce_gap_bytes is not None and args.exact_range_plan:
        raise SystemExit(
            "--coalesce-gap-bytes cannot be combined with --exact-range-plan"
        )
    if (
        args.coalesce_gap_bytes is not None
        and not args.index_only
        and args.transport_byte_cap is None
    ):
        raise SystemExit(
            "coalesced extraction requires an explicit --transport-byte-cap"
        )
    prefixes = [
        str(safe_member_path(value.rstrip("/"))) + "/"
        for value in (args.prefix or ["HAR/data/IMU/"])
    ]
    if len(set(prefixes)) != len(prefixes):
        raise SystemExit("duplicate --prefix values are not allowed")
    subjects: set[int] | None = None
    if args.subjects is not None:
        try:
            subjects = {int(value) for value in args.subjects.split(",") if value}
        except ValueError as exc:
            raise SystemExit("--subjects must be comma-separated integers") from exc
        if not subjects or any(subject <= 0 for subject in subjects):
            raise SystemExit("--subjects must contain positive integers")

    manifest, parts = load_manifest(args.manifest.resolve())
    bearer_token_env = args.bearer_token_env or manifest.get(
        "authentication", {}
    ).get("bearer_token_env")
    reader = ArchiveReader(
        parts,
        args.max_range_bytes,
        args.retries,
        bearer_token_env=bearer_token_env,
        transport_byte_cap=args.transport_byte_cap,
    )
    location, directory_blob, from_cache = load_or_fetch_directory(
        reader, args.central_directory_cache.resolve(), manifest
    )
    entries = parse_central_directory(directory_blob, location.entries)
    selected: list[Entry] = []
    details_by_prefix: dict[str, dict[str, int]] = {}
    for prefix in prefixes:
        prefix_selected, selection_details = select_entries(
            entries, prefix, args.frames_per_clip, subjects
        )
        selected.extend(prefix_selected)
        details_by_prefix[prefix] = selection_details
    if not selected:
        raise ArchiveError(f"no files match prefixes {prefixes!r}")
    if len({entry.name for entry in selected}) != len(selected):
        raise ArchiveError("selected prefixes overlap")
    if any(entry.method != 0 for entry in selected):
        raise ArchiveError("selected members are not all stored")

    selected_bytes = sum(entry.uncompressed_size for entry in selected)
    for prefix in prefixes:
        selection_details = details_by_prefix[prefix]
        expected_selection = manifest.get("expected_selections", {}).get(prefix)
        if expected_selection:
            if int(expected_selection["files"]) != selection_details["available_files"]:
                raise ArchiveError("available file count differs from manifest expectation")
            if (
                int(expected_selection["payload_bytes"])
                != selection_details["available_payload_bytes"]
            ):
                raise ArchiveError("available payload bytes differ from manifest expectation")
            if (
                subjects is None
                and "groups" in expected_selection
                and args.frames_per_clip is not None
                and int(expected_selection["groups"]) != selection_details["groups"]
            ):
                raise ArchiveError("available clip-group count differs from expectation")

    verified_existing: list[Entry] = []
    coalesced_selected = selected
    if args.coalesce_gap_bytes is not None and not args.index_only:
        verified_existing, coalesced_selected = partition_verified_existing(
            selected, args.output_root.resolve()
        )

    exact_range_plan = (
        plan_selected_payload_ranges(reader, selected)
        if args.exact_range_plan
        else None
    )
    coalesced_plan = (
        build_coalesced_plan(
            parts,
            location,
            entries,
            coalesced_selected,
            args.coalesce_gap_bytes,
            args.max_range_bytes,
        )
        if args.coalesce_gap_bytes is not None
        else None
    )

    def transport_report() -> dict[str, int | None]:
        return {
            "bytes_read": reader.bytes_read,
            "range_requests": reader.requests,
            **reader.transport_stats(),
        }

    base_report: dict[str, Any] = {
        "manifest": str(args.manifest.resolve()),
        "prefix": prefixes[0] if len(prefixes) == 1 else None,
        "prefixes": prefixes,
        "central_directory": {
            "disk": location.disk,
            "offset": location.offset,
            "bytes": location.size,
            "entries": location.entries,
            "sha256": sha256_bytes(directory_blob),
            "from_cache": from_cache,
        },
        "selection": {
            "files": len(selected),
            "payload_bytes": selected_bytes,
            "start_disks": sorted({entry.disk for entry in selected}),
            "frames_per_clip": args.frames_per_clip,
            "subjects": sorted(subjects) if subjects is not None else None,
            "by_prefix": details_by_prefix,
            **(details_by_prefix[prefixes[0]] if len(prefixes) == 1 else {}),
        },
        "transport": transport_report(),
        "test_data_read": False,
        "submission_created": False,
    }
    if exact_range_plan is not None:
        base_report["exact_range_plan"] = exact_range_plan
    if coalesced_plan is not None:
        base_report["coalesced_plan"] = coalesced_plan.summary()
        base_report["resume"] = {
            "preverified_files": len(verified_existing),
            "preverified_payload_bytes": sum(
                entry.uncompressed_size for entry in verified_existing
            ),
            "pending_files": len(coalesced_selected),
            "pending_payload_bytes": sum(
                entry.uncompressed_size for entry in coalesced_selected
            ),
            "preverification": "size_and_crc32_before_transport_plan",
        }
    if args.index_only:
        base_report["status"] = "INDEXED_NOT_EXTRACTED"
        write_report(args.report.resolve(), base_report)
        print(json.dumps(base_report, indent=2, sort_keys=True))
        return

    required_output_bytes = (
        sum(entry.uncompressed_size for entry in coalesced_selected)
        if coalesced_plan is not None
        else selected_bytes
    )
    free_bytes = shutil.disk_usage(args.output_root.resolve().parent).free
    if required_output_bytes > free_bytes:
        raise ArchiveError(
            f"pending payload needs {required_output_bytes} bytes but only "
            f"{free_bytes} free"
        )
    outcomes: dict[str, int]
    if coalesced_plan is not None:
        try:
            outcomes = extract_coalesced_plan(
                reader, coalesced_plan, args.output_root.resolve()
            )
            outcomes["reused"] += len(verified_existing)
        except Exception as exc:
            base_report["status"] = "FAILED_CLOSED_DURING_EXTRACTION"
            base_report["error"] = str(exc)
            base_report["transport"] = transport_report()
            write_report(args.report.resolve(), base_report)
            raise
    else:
        outcomes = {"extracted": 0, "reused": 0, "directory": 0}
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    extract_one, reader, entry, args.output_root.resolve()
                ): entry
                for entry in selected
            }
            try:
                for future in concurrent.futures.as_completed(futures):
                    outcome = future.result()
                    outcomes[outcome] += 1
            except Exception:
                for future in futures:
                    future.cancel()
                raise
    base_report["status"] = "EXTRACTED_AND_CRC_VERIFIED"
    base_report["outcomes"] = outcomes
    base_report["transport"] = transport_report()
    if coalesced_plan is not None:
        base_report["coalesced_plan"]["payload_downloaded"] = bool(
            coalesced_plan.request_count
        )
    write_report(args.report.resolve(), base_report)
    print(json.dumps(base_report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
