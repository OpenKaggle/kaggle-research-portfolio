# CUHK-X Small S1 coalesced extractor implementation receipt

Date: 2026-09-11 (Asia/Shanghai)

Implemented in `src/selective_split_zip.py` without any network request or
token access.

## Delivered controls

- Explicit `--coalesce-gap-bytes`; the legacy per-member path remains the
  default when this option is absent.
- Explicit `--transport-byte-cap`, required for real coalesced extraction.
- Offline plan construction from every central-directory entry's next local
  header, split first by physical ZIP volume and then at a maximum 16 MiB.
- Whole-run cap preflight before the first payload request. Each request and
  retry also reserves bounded body capacity fail-closed.
- Separate attempted request/range bytes, successful requests/body bytes,
  total observed wire bytes, failed wire bytes, and remaining-cap reporting.
- Authorization failure bodies remain unread; retryable HTTP error bodies and
  invalid bounded responses are counted when observable.
- Streaming coalesced extraction retains only the current selected envelope,
  discards coalesced gaps, and validates local signature, flags, method,
  filename, sizes, payload bounds, and CRC-32 before atomic publication.
- Failure tests prove no output or `*.partial` file remains after bad local
  signature, bad local filename, or payload CRC.

## Frozen real-archive offline result

With the pinned central-directory cache, all 18 subjects, Thermal, at most 8
frames per clip, a 1 MiB gap, and a 16 MiB request cap:

- selected files: 22,734
- selected payload: 397,884,606 bytes
- logical merged ranges: 60
- nominal physical requests: 249
- nominal download: 3,447,355,366 bytes
- minimum extraction cap: 3,447,355,367 bytes
- `HAR.z08`: 1,879,742,558 bytes / 141 requests
- `HAR.zip`: 1,567,612,808 bytes / 108 requests
- remote attempts and wire bytes during this verification: zero

## Verification

- `test_real_thermal_one_mib_coalesced_plan_is_exact_and_offline`: pass.
- `test_individual_and_coalesced_split_zip_crc_headers_cap_no_partial`: pass.
- Small tests: 20/20 pass.
- Unified CUHK-X research harness: `PASS_RESEARCH_BLOCK_RELEASE`.
- Release remains blocked because no real official training payload was read
  in this offline implementation run.

Source SHA-256 at verification:

- `src/selective_split_zip.py`:
  `83d53e7f8702825d201d62e62934342d5b673e934412a86e27f6c7e09f94e667`
- `src/test_selective_split_zip.py`:
  `73d110b71673aeb0f084436d12a0a7ea42eba3a7ecae1979b92384f4b5303822`

No test labels were read and no Kaggle submission was created.
