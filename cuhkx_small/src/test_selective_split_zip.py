#!/usr/bin/env python3
"""Local integration test for selective_split_zip.py.

Copyright 2026 Jiayi Du
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import hashlib
import io
import os
import struct
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from selective_split_zip import (
    ArchiveError,
    ArchiveReader,
    DirectoryLocation,
    Entry,
    Part,
    SafeBearerRedirectHandler,
    build_coalesced_plan,
    data_location,
    extract_coalesced_plan,
    extract_one,
    find_directory,
    load_or_fetch_directory,
    load_manifest,
    parse_central_directory,
    partition_verified_existing,
    plan_selected_payload_ranges,
    select_entries,
    uniform_indices,
)


class FakeResponse:
    def __init__(self, status: int, headers: dict[str, str], payload: bytes) -> None:
        self.status = status
        self.headers = headers
        self.payload = payload
        self.read_limits: list[int] = []

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self.payload[:limit]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class SelectiveSplitZipTest(unittest.TestCase):
    def test_env_only_bearer_and_exact_range_semantics(self) -> None:
        part = Part(0, "HAR.z01", "https://huggingface.co/HAR.z01", 100)
        with self.assertRaisesRegex(ArchiveError, "variable name is invalid"):
            ArchiveReader([part], bearer_token_env="hf_token-value")
        with self.assertRaisesRegex(ArchiveError, "huggingface.co"):
            ArchiveReader(
                [Part(0, "HAR.z01", "https://example.invalid/HAR.z01", 100)],
                bearer_token_env="CUHKX_TEST_TOKEN",
            )
        missing = ArchiveReader(
            [part], retries=0, bearer_token_env="CUHKX_TEST_TOKEN"
        )
        with patch.dict(os.environ, {"CUHKX_TEST_TOKEN": ""}):
            with patch.object(missing._http_opener, "open") as opener:
                with self.assertRaisesRegex(ArchiveError, "environment variable"):
                    missing.read(0, 0, 4)
                opener.assert_not_called()

        response = FakeResponse(
            206, {"Content-Range": "bytes 10-13/100"}, b"abcd"
        )
        captured: list[object] = []

        def open_ok(request: object, timeout: int) -> FakeResponse:
            self.assertEqual(60, timeout)
            captured.append(request)
            return response

        reader = ArchiveReader(
            [part], retries=0, bearer_token_env="CUHKX_TEST_TOKEN"
        )
        secret = "unit-test-secret-not-for-logs"
        with patch.dict(os.environ, {"CUHKX_TEST_TOKEN": secret}):
            with patch.object(reader._http_opener, "open", side_effect=open_ok):
                self.assertEqual(b"abcd", reader.read(0, 10, 4))
        self.assertEqual([5], response.read_limits)
        self.assertEqual(
            f"Bearer {secret}", captured[0].get_header("Authorization")
        )
        self.assertEqual("bytes=10-13", captured[0].get_header("Range"))
        self.assertEqual("CUHKX_TEST_TOKEN", reader.bearer_token_env)
        self.assertNotIn(secret, repr(reader.__dict__))

    def test_401_and_ignored_range_fail_without_secret_or_unbounded_read(self) -> None:
        part = Part(0, "HAR.zip", "https://huggingface.co/HAR.zip", 100)
        reader = ArchiveReader(
            [part], retries=3, bearer_token_env="CUHKX_TEST_TOKEN"
        )
        secret = "never-echo-this-token"

        def unauthorized(request: object, timeout: int) -> FakeResponse:
            raise urllib.error.HTTPError(
                request.full_url, 401, "Unauthorized", {}, None
            )

        with patch.dict(os.environ, {"CUHKX_TEST_TOKEN": secret}):
            with patch.object(
                reader._http_opener, "open", side_effect=unauthorized
            ) as opener:
                with self.assertRaises(ArchiveError) as caught:
                    reader.read(0, 20, 4)
        self.assertEqual(1, opener.call_count)
        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("HTTP 401", str(caught.exception))

        ignored = FakeResponse(200, {"Content-Type": "application/octet-stream"}, b"x" * 100)
        no_auth = ArchiveReader([part], retries=0)
        with patch(
            "selective_split_zip.urllib.request.urlopen", return_value=ignored
        ):
            with self.assertRaisesRegex(ArchiveError, "status=200"):
                no_auth.read(0, 20, 4)
        self.assertEqual([5], ignored.read_limits)
        self.assertEqual(
            {
                "attempted_requests": 1,
                "successful_requests": 0,
                "failed_requests": 1,
                "attempted_range_bytes": 4,
                "successful_body_bytes": 0,
                "wire_bytes": 5,
                "failed_wire_bytes": 5,
                "transport_byte_cap": None,
                "transport_byte_cap_remaining": None,
            },
            no_auth.transport_stats(),
        )

    def test_retry_wire_bytes_debit_cap_and_are_reported(self) -> None:
        part = Part(0, "HAR.zip", "https://example.invalid/HAR.zip", 100)
        reader = ArchiveReader(
            [part], retries=1, transport_byte_cap=10
        )
        failure = urllib.error.HTTPError(
            part.source, 500, "error", {}, io.BytesIO(b"error")
        )
        success = FakeResponse(
            206, {"Content-Range": "bytes 10-13/100"}, b"abcd"
        )
        with patch(
            "selective_split_zip.urllib.request.urlopen",
            side_effect=[failure, success],
        ):
            self.assertEqual(b"abcd", reader.read(0, 10, 4))
        stats = reader.transport_stats()
        self.assertEqual(2, stats["attempted_requests"])
        self.assertEqual(1, stats["successful_requests"])
        self.assertEqual(1, stats["failed_requests"])
        self.assertEqual(9, stats["wire_bytes"])
        self.assertEqual(5, stats["failed_wire_bytes"])
        self.assertEqual(1, stats["transport_byte_cap_remaining"])

        exhausted = ArchiveReader(
            [part], retries=1, transport_byte_cap=5
        )
        failure = urllib.error.HTTPError(
            part.source, 500, "error", {}, io.BytesIO(b"error")
        )
        with patch(
            "selective_split_zip.urllib.request.urlopen",
            side_effect=[failure, AssertionError("second request must not start")],
        ):
            with self.assertRaisesRegex(ArchiveError, "cap exhausted"):
                exhausted.read(0, 10, 4)
        self.assertEqual(1, exhausted.transport_stats()["attempted_requests"])

    def test_redirects_strip_cross_host_auth_and_require_https(self) -> None:
        handler = SafeBearerRedirectHandler(("huggingface.co", 443))
        original = urllib.request.Request(
            "https://huggingface.co/datasets/example/resolve/revision/HAR.zip",
            headers={
                "Authorization": "Bearer must-not-leak",
                "Range": "bytes=10-13",
            },
        )
        cross_host = handler.redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "https://cdn.attacker.invalid/signed-object",
        )
        self.assertIsNotNone(cross_host)
        self.assertIsNone(cross_host.get_header("Authorization"))
        self.assertEqual("bytes=10-13", cross_host.get_header("Range"))

        lookalike = handler.redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "https://huggingface.co.attacker.invalid/signed-object",
        )
        self.assertIsNone(lookalike.get_header("Authorization"))

        same_host = handler.redirect_request(
            original,
            None,
            302,
            "Found",
            {},
            "https://huggingface.co/redirected-object",
        )
        self.assertEqual(
            "Bearer must-not-leak", same_host.get_header("Authorization")
        )
        with self.assertRaisesRegex(ArchiveError, "HTTPS"):
            handler.redirect_request(
                original,
                None,
                302,
                "Found",
                {},
                "http://cdn.example.invalid/signed-object",
            )

    def test_content_range_unknown_total_is_rejected(self) -> None:
        part = Part(0, "HAR.zip", "https://example.invalid/HAR.zip", 100)
        response = FakeResponse(
            206, {"Content-Range": "bytes 10-13/*"}, b"abcd"
        )
        reader = ArchiveReader([part], retries=0)
        with patch(
            "selective_split_zip.urllib.request.urlopen", return_value=response
        ):
            with self.assertRaisesRegex(ArchiveError, "inconsistent Content-Range"):
                reader.read(0, 10, 4)
        self.assertEqual([5], response.read_limits)

    def test_pinned_directory_cache_is_offline_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blob = b"pinned-central-directory"
            cache = root / "central.bin"
            cache.write_bytes(blob)
            digest = hashlib.sha256(blob).hexdigest()
            reader = ArchiveReader(
                [Part(0, "HAR.zip", str(root / "HAR.zip"), 1024)], retries=0
            )
            expected = {
                "disk": 0,
                "offset": 100,
                "size": len(blob),
                "entries": 3,
                "total_disks": 1,
                "sha256": digest,
            }
            with patch("selective_split_zip.find_directory") as discover:
                location, loaded, from_cache = load_or_fetch_directory(
                    reader, cache, {"expected_directory": expected}
                )
                discover.assert_not_called()
            self.assertTrue(from_cache)
            self.assertEqual(blob, loaded)
            self.assertEqual(0, location.disk)
            self.assertEqual(0, reader.requests)

            cache.write_bytes(b"x" * len(blob))
            with patch("selective_split_zip.find_directory") as discover:
                with self.assertRaisesRegex(ArchiveError, "SHA-256 mismatch"):
                    load_or_fetch_directory(
                        reader, cache, {"expected_directory": expected}
                    )
                discover.assert_not_called()

            cache.write_bytes(blob)
            without_hash = dict(expected)
            without_hash.pop("sha256")
            with patch("selective_split_zip.find_directory") as discover:
                with self.assertRaisesRegex(ArchiveError, "pinned geometry"):
                    load_or_fetch_directory(
                        reader, cache, {"expected_directory": without_hash}
                    )
                discover.assert_not_called()

    def test_uniform_selection_is_deterministic(self) -> None:
        self.assertEqual([1, 3, 6, 8], uniform_indices(10, 4))
        self.assertEqual([0, 1, 2], uniform_indices(3, 8))
        entries = [
            Entry(
                name=f"HAR/data/Thermal/action_00/user1/clip1/frame_{index:04d}.jpg",
                disk=0,
                local_offset=index,
                compressed_size=1,
                uncompressed_size=1,
                crc32=0,
                method=0,
                flags=0,
                external_attributes=0,
            )
            for index in range(10)
        ]
        selected, details = select_entries(entries, "HAR/data/Thermal/", 4)
        self.assertEqual(
            ["frame_0001.jpg", "frame_0003.jpg", "frame_0006.jpg", "frame_0008.jpg"],
            [PurePosixPath(entry.name).name for entry in selected],
        )
        self.assertEqual(
            {"groups": 1, "available_files": 10, "available_payload_bytes": 10},
            details,
        )
        other_subject = Entry(
            name="HAR/data/Thermal/action_00/user2/clip9/frame_0000.jpg",
            disk=0,
            local_offset=99,
            compressed_size=1,
            uncompressed_size=1,
            crc32=0,
            method=0,
            flags=0,
            external_attributes=0,
        )
        subject_selected, subject_details = select_entries(
            entries + [other_subject], "HAR/data/Thermal/", 4, {1}
        )
        self.assertEqual(4, len(subject_selected))
        self.assertEqual(11, subject_details["available_files"])
        self.assertEqual(10, subject_details["eligible_files"])

    def test_huggingface_manifest_is_commit_locked_and_matches_official_hashes(self) -> None:
        small_root = Path(__file__).resolve().parents[1]
        hf, hf_parts = load_manifest(
            small_root / "config/training_split_huggingface.json"
        )
        google, google_parts = load_manifest(
            small_root / "config/training_split_drive.json"
        )
        self.assertEqual(
            "ca37a2e9c6a06271309be03bbfbe16f29e40d8b4",
            hf["repository"]["revision"],
        )
        self.assertEqual("CUHKX_HF_TOKEN", hf["authentication"]["bearer_token_env"])
        self.assertEqual(9, len(hf_parts))
        self.assertEqual(
            [(part.name, part.size, part.sha256) for part in google_parts],
            [(part.name, part.size, part.sha256) for part in hf_parts],
        )
        revision = hf["repository"]["revision"]
        for row in hf["parts"]:
            self.assertIn(revision, row["source"])
            self.assertIn(row["repository_path"], row["source"])
        serialized = json.dumps(hf, sort_keys=True)
        self.assertNotIn("hf_", serialized)

    def test_real_thermal_one_mib_coalesced_plan_is_exact_and_offline(self) -> None:
        small_root = Path(__file__).resolve().parents[1]
        manifest, parts = load_manifest(
            small_root / "config/training_split_huggingface.json"
        )
        expected = manifest["expected_directory"]
        cache = small_root / "artifacts/transport/hf_central_directory.bin"
        blob = cache.read_bytes()
        self.assertEqual(expected["sha256"], hashlib.sha256(blob).hexdigest())
        entries = parse_central_directory(blob, int(expected["entries"]))
        selected, details = select_entries(
            entries, "HAR/data/Thermal/", 8, None
        )
        plan = build_coalesced_plan(
            parts,
            DirectoryLocation(
                disk=int(expected["disk"]),
                offset=int(expected["offset"]),
                size=int(expected["size"]),
                entries=int(expected["entries"]),
                total_disks=int(expected["total_disks"]),
            ),
            entries,
            selected,
            gap_bytes=1024 * 1024,
            max_request_bytes=16 * 1024 * 1024,
        )
        self.assertEqual(2_891, details["groups"])
        self.assertEqual(22_734, len(selected))
        self.assertEqual(397_884_606, plan.payload_bytes)
        self.assertEqual(3_447_355_366, plan.download_bytes)
        self.assertEqual(249, plan.request_count)
        self.assertEqual({7, 8}, {int(row["disk"]) for row in plan.per_disk})

    def test_reads_zip64_end_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            central = b"central-placeholder"
            zip64_offset = len(central)
            zip64 = struct.pack(
                "<4sQ2H2I4Q",
                b"PK\x06\x06",
                44,
                45,
                45,
                0,
                0,
                70_000,
                70_000,
                len(central),
                0,
            )
            locator = struct.pack("<4sIQI", b"PK\x06\x07", 0, zip64_offset, 1)
            eocd = struct.pack(
                "<4s4H2IH",
                b"PK\x05\x06",
                0xFFFF,
                0xFFFF,
                0xFFFF,
                0xFFFF,
                0xFFFFFFFF,
                0xFFFFFFFF,
                0,
            )
            archive = root / "zip64-fixture.zip"
            archive.write_bytes(central + zip64 + locator + eocd)
            reader = ArchiveReader(
                [Part(0, archive.name, str(archive), archive.stat().st_size)],
                max_range_bytes=64,
                retries=0,
            )
            location = find_directory(reader)
            self.assertEqual(0, location.disk)
            self.assertEqual(0, location.offset)
            self.assertEqual(len(central), location.size)
            self.assertEqual(70_000, location.entries)
            self.assertEqual(1, location.total_disks)

    def test_coalesced_split_zip_resume_crc_headers_cap_no_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            imu = source / "HAR/data/IMU/action_00/user1/clip1"
            thermal = source / "HAR/data/Thermal/action_00/user1/clip1"
            imu.mkdir(parents=True)
            thermal.mkdir(parents=True)
            up = (b"up,imu,values\n" * 6000)[:82_000]
            down = (b"down,imu,values\n" * 6000)[:91_000]
            skipped = (b"jpeg-placeholder" * 7000)[:96_000]
            (imu / "up.csv").write_bytes(up)
            (imu / "down.csv").write_bytes(down)
            (thermal / "0001.jpeg").write_bytes(skipped)

            archive = root / "fixture.zip"
            subprocess.run(
                ["zip", "-0", "-q", "-r", "-s", "64k", str(archive), "HAR"],
                cwd=source,
                check=True,
            )
            split_parts = sorted(root.glob("fixture.z[0-9][0-9]")) + [archive]
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "parts": [
                            {
                                "disk": disk,
                                "name": path.name,
                                "source": str(path),
                                "size": path.stat().st_size,
                            }
                            for disk, path in enumerate(split_parts)
                        ]
                    }
                ),
                encoding="utf-8",
            )

            manifest, parts = load_manifest(manifest_path)
            self.assertEqual({}, {k: v for k, v in manifest.items() if k != "parts"})
            reader = ArchiveReader(parts, max_range_bytes=4096, retries=0)
            location = find_directory(reader)
            directory = reader.read(location.disk, location.offset, location.size)
            entries = parse_central_directory(directory, location.entries)
            selected = [
                entry
                for entry in entries
                if not entry.is_directory and entry.name.startswith("HAR/data/IMU/")
            ]
            self.assertEqual(2, len(selected))
            plan = plan_selected_payload_ranges(reader, selected)
            self.assertEqual(len(up) + len(down), plan["payload_bytes"])
            self.assertFalse(plan["payload_downloaded"])
            self.assertGreater(plan["header_probe_bytes"], 0)
            output = root / "output"
            for entry in selected:
                self.assertEqual("extracted", extract_one(reader, entry, output))
                self.assertEqual("reused", extract_one(reader, entry, output))
            self.assertEqual(up, (output / "HAR/data/IMU/action_00/user1/clip1/up.csv").read_bytes())
            self.assertEqual(
                down,
                (output / "HAR/data/IMU/action_00/user1/clip1/down.csv").read_bytes(),
            )
            self.assertFalse((output / "HAR/data/Thermal").exists())

            coalesced = build_coalesced_plan(
                parts,
                location,
                entries,
                selected,
                gap_bytes=1024 * 1024,
                max_request_bytes=4096,
            )
            self.assertGreater(coalesced.request_count, 1)
            self.assertTrue(
                all(
                    request.length <= 4096
                    for row in coalesced.ranges
                    for request in row.requests
                )
            )
            coalesced_reader = ArchiveReader(
                parts,
                max_range_bytes=4096,
                retries=0,
                transport_byte_cap=coalesced.download_bytes + 1,
            )
            coalesced_output = root / "coalesced-output"
            outcomes = extract_coalesced_plan(
                coalesced_reader, coalesced, coalesced_output
            )
            self.assertEqual({"extracted": 2, "reused": 0}, outcomes)
            self.assertEqual(
                up,
                (coalesced_output / next(
                    entry.name for entry in selected if entry.name.endswith("up.csv")
                )).read_bytes(),
            )
            self.assertEqual(
                down,
                (coalesced_output / next(
                    entry.name for entry in selected if entry.name.endswith("down.csv")
                )).read_bytes(),
            )
            self.assertFalse((coalesced_output / "HAR/data/Thermal").exists())
            self.assertEqual(
                coalesced.download_bytes,
                coalesced_reader.transport_stats()["wire_bytes"],
            )

            verified, pending = partition_verified_existing(
                selected, coalesced_output
            )
            self.assertEqual(2, len(verified))
            self.assertEqual([], pending)
            empty_resume = build_coalesced_plan(
                parts,
                location,
                entries,
                pending,
                gap_bytes=1024 * 1024,
                max_request_bytes=4096,
            )
            self.assertEqual(0, empty_resume.download_bytes)
            self.assertEqual(0, empty_resume.request_count)
            self.assertEqual(0, empty_resume.summary()["minimum_transport_byte_cap"])
            empty_reader = ArchiveReader(
                parts, max_range_bytes=4096, retries=0, transport_byte_cap=1
            )
            self.assertEqual(
                {"extracted": 0, "reused": 0},
                extract_coalesced_plan(
                    empty_reader, empty_resume, coalesced_output
                ),
            )
            self.assertEqual(0, empty_reader.transport_stats()["attempted_requests"])

            up_target = coalesced_output / next(
                entry.name for entry in selected if entry.name.endswith("up.csv")
            )
            original_up = up_target.read_bytes()
            up_target.write_bytes(
                bytes([original_up[0] ^ 0xFF]) + original_up[1:]
            )
            verified, pending = partition_verified_existing(
                selected, coalesced_output
            )
            self.assertEqual(1, len(verified))
            self.assertEqual(1, len(pending))
            self.assertTrue(pending[0].name.endswith("up.csv"))
            missing_only = build_coalesced_plan(
                parts,
                location,
                entries,
                pending,
                gap_bytes=1024 * 1024,
                max_request_bytes=4096,
            )
            self.assertLess(missing_only.download_bytes, coalesced.download_bytes)
            up_target.write_bytes(original_up)

            fresh_verified, fresh_pending = partition_verified_existing(
                selected, root / "fresh-output"
            )
            self.assertEqual([], fresh_verified)
            fresh_plan = build_coalesced_plan(
                parts,
                location,
                entries,
                fresh_pending,
                gap_bytes=1024 * 1024,
                max_request_bytes=4096,
            )
            self.assertEqual(coalesced.summary(), fresh_plan.summary())

            blocked_reader = ArchiveReader(
                parts,
                max_range_bytes=4096,
                retries=0,
                transport_byte_cap=coalesced.download_bytes,
            )
            with self.assertRaisesRegex(ArchiveError, "complete planned run"):
                extract_coalesced_plan(
                    blocked_reader, coalesced, root / "blocked-output"
                )
            self.assertEqual(0, blocked_reader.transport_stats()["attempted_requests"])
            self.assertFalse((root / "blocked-output").exists())

            first = coalesced.envelopes[0].entry
            first_part = Path(parts[first.disk].source)
            with first_part.open("r+b") as handle:
                handle.seek(first.local_offset)
                original_signature_byte = handle.read(1)
                handle.seek(first.local_offset)
                handle.write(b"X")
            corrupt_header_reader = ArchiveReader(
                parts,
                max_range_bytes=4096,
                retries=0,
                transport_byte_cap=coalesced.download_bytes + 1,
            )
            with self.assertRaisesRegex(ArchiveError, "signature mismatch"):
                extract_coalesced_plan(
                    corrupt_header_reader,
                    coalesced,
                    root / "corrupt-header-output",
                )
            self.assertFalse((root / "corrupt-header-output").exists())
            with first_part.open("r+b") as handle:
                handle.seek(first.local_offset)
                handle.write(original_signature_byte)

            with first_part.open("r+b") as handle:
                handle.seek(first.local_offset + 30)
                original_name_byte = handle.read(1)
                handle.seek(first.local_offset + 30)
                handle.write(bytes([original_name_byte[0] ^ 0x01]))
            corrupt_name_reader = ArchiveReader(
                parts,
                max_range_bytes=4096,
                retries=0,
                transport_byte_cap=coalesced.download_bytes + 1,
            )
            with self.assertRaisesRegex(ArchiveError, "filename mismatch"):
                extract_coalesced_plan(
                    corrupt_name_reader,
                    coalesced,
                    root / "corrupt-name-output",
                )
            self.assertFalse((root / "corrupt-name-output").exists())
            with first_part.open("r+b") as handle:
                handle.seek(first.local_offset + 30)
                handle.write(original_name_byte)

            locator = ArchiveReader(parts, max_range_bytes=4096, retries=0)
            payload_disk, payload_offset = data_location(locator, first)
            payload_part = Path(parts[payload_disk].source)
            with payload_part.open("r+b") as handle:
                handle.seek(payload_offset)
                original_payload_byte = handle.read(1)
                handle.seek(payload_offset)
                handle.write(bytes([original_payload_byte[0] ^ 0xFF]))
            corrupt_crc_reader = ArchiveReader(
                parts,
                max_range_bytes=4096,
                retries=0,
                transport_byte_cap=coalesced.download_bytes + 1,
            )
            with self.assertRaisesRegex(ArchiveError, "CRC-32 mismatch"):
                extract_coalesced_plan(
                    corrupt_crc_reader,
                    coalesced,
                    root / "corrupt-crc-output",
                )
            self.assertFalse((root / "corrupt-crc-output").exists())
            with payload_part.open("r+b") as handle:
                handle.seek(payload_offset)
                handle.write(original_payload_byte)
            self.assertEqual([], list(root.rglob("*.partial")))


if __name__ == "__main__":
    unittest.main()
