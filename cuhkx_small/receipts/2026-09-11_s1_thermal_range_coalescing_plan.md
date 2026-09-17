# CUHK-X Small S1 Thermal: offline safe Range-coalescing plan

Date: 2026-09-11 (Asia/Shanghai)

Scope: the complete 18-subject training-side Thermal set, retaining at most 8
uniformly selected JPEG frames per semantic clip. This is a metadata-only,
offline transport plan. It did not use a token, contact the network, inspect
test data, or create a submission. It does not change
`src/selective_split_zip.py`.

## Pinned evidence

- Central-directory cache:
  `artifacts/transport/hf_central_directory.bin`
- Cache size: 73,843,427 bytes
- Cache SHA-256:
  `a0cefe0405ff6a1b2cd3f7beeae4bb0e1f11126250c0d6a5fe2f4994bed7eaa8`
- Parsed entries: 491,879, all unique.
- All 491,879 entries use ZIP method 0 (stored).
- Flags are either `0` or UTF-8-only `0x0800`; no entry is encrypted and no
  entry sets the data-descriptor bit `0x0008`.
- Sorting every entry by the logical absolute position
  `sum(previous volume sizes) + local_header_offset` gives strictly increasing
  local-header positions.
- For every one of the 491,879 entries, including the final entry before the
  central directory, the following central-metadata residual is exactly 28
  bytes:

  ```text
  next_local_header - current_local_header
    - 30 - encoded_central_name_length - compressed_size = 28
  ```

  This proves a tight 28-byte envelope residual conditional on the required
  local/central filename equality. It is not permission to assume that the
  local extra field itself is 28 bytes: the downloader must still parse and
  validate each local header before locating its payload.

## Exact S1 selection

- Thermal clips/groups present: 2,891.
- Selected frames: 22,734. The count is below `2,891 * 8` because clips with
  fewer than 8 frames retain all available frames.
- Selected stored payload: 397,884,606 bytes (379.452 MiB).
- Selected entry start volumes: disk 7 (`HAR.z08`) and disk 8 (`HAR.zip`) only.
  Disks 0--6 need no Range request for S1 Thermal.
- Payload bytes grouped by the volume in which each selected local header
  starts (not a download allocation):
  - `HAR.z08`: 188,167,832 bytes across 10,776 files.
  - `HAR.zip`: 209,716,774 bytes across 11,958 files.

Per-subject selected counts and payload bytes:

| Subject | Files | Payload bytes |
|---:|---:|---:|
| 1 | 1,203 | 19,573,519 |
| 2 | 757 | 12,747,342 |
| 3 | 1,180 | 18,669,115 |
| 4 | 1,115 | 17,744,384 |
| 5 | 1,233 | 20,510,674 |
| 6 | 1,560 | 27,641,218 |
| 7 | 1,441 | 23,991,748 |
| 8 | 1,304 | 21,069,795 |
| 9 | 1,481 | 24,036,875 |
| 16 | 1,469 | 28,332,214 |
| 17 | 1,262 | 23,861,648 |
| 18 | 1,397 | 25,001,440 |
| 19 | 1,458 | 27,092,804 |
| 20 | 1,266 | 24,024,582 |
| 21 | 1,045 | 19,608,473 |
| 22 | 1,343 | 23,979,147 |
| 23 | 1,056 | 19,540,755 |
| 24 | 1,164 | 20,458,873 |

## Safe one-pass envelope algorithm

The local header length is unknown before reading its fixed 30-byte portion.
It is unnecessary to issue a separate header probe for every file.

1. Parse and validate the pinned central-directory bytes. Reject duplicate or
   unsafe names, non-stored methods, encryption, data descriptors, inconsistent
   disk indices, and any logical local-header position outside its pinned
   volume.
2. Reproduce the existing deterministic selection: group Thermal entries by
   clip parent, sort filenames, and take `uniform_indices(length, 8)`.
3. Sort **all** archive entries by logical local-header position. For each
   selected entry `i`, define its safe envelope as
   `[local_header_i, local_header_(i+1))`; for the archive's final entry, use
   the pinned central-directory start as the end. This endpoint is known from
   the central directory even though the selected member's local extra length
   is not.
4. Merge consecutive selected envelopes only when the byte gap between them is
   at most the chosen `gap_threshold`. The gap deliberately contains
   unselected archive bytes; it is transport-only and must never be written as
   training examples.
5. Split every merged logical interval first at physical volume boundaries and
   then into requests of at most 16 MiB. Never attempt a Range spanning two HF
   files. Require HTTP 206 and an exact `Content-Range`; read at most requested
   length plus one byte before rejecting an ignored Range.
6. Assemble each planned interval in order (or stream chunks with absolute
   offsets). At every selected local-header offset, parse the 30-byte local
   header, validate signature, flags, method, decoded filename, and that
   `payload_start + central_compressed_size <= next_local_header`. Reject any
   mismatch; do not fall back to a guessed 65,535-byte extra-field allowance.
7. Slice only the selected stored payload, compute CRC-32 while writing, and
   atomically publish the target only after size and CRC match the central
   entry. Discard all local-header and coalesced-gap bytes.
8. Resume by rechecking existing target size and CRC. Bind a plan digest to the
   central-directory SHA, archive revision, selection policy, gap threshold,
   and 16 MiB cap. A changed digest invalidates partial transport state.

This one-pass design is safer and cheaper than a two-phase scheme. A strict
two-phase implementation needs at least 45,468 HTTP requests merely to fetch
the fixed and variable local-header pieces, then another 22,734 payload
requests (68,202 total before chunking). The envelope design needs 22,170
requests with zero gap coalescing because 564 selected envelopes already touch.

## Exact nominal Range budgets

The table is calculated entirely from pinned central positions. Request counts
assume one ordinary contiguous HTTP Range per physical interval, a 16 MiB
maximum request body, no multipart-Range extension, and no retry. `Extra over
payload` includes local headers plus deliberately coalesced unselected gaps.
The already-cached 73,843,427-byte central directory is excluded.

| Gap threshold | Logical merged ranges | HTTP requests | Download bytes | Extra over payload | `HAR.z08` bytes / req | `HAR.zip` bytes / req |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 22,170 | 22,170 | 400,598,143 | 2,713,537 | 189,474,013 / 10,594 | 211,124,130 / 11,576 |
| 4 KiB | 22,099 | 22,099 | 400,606,352 | 2,721,746 | 189,475,656 / 10,581 | 211,130,696 / 11,518 |
| 16 KiB | 21,563 | 21,563 | 408,907,244 | 11,022,638 | 191,772,938 / 10,432 | 217,134,306 / 11,131 |
| 32 KiB | 19,827 | 19,827 | 447,814,570 | 49,929,964 | 204,371,831 / 9,875 | 243,442,739 / 9,952 |
| 64 KiB | 15,614 | 15,614 | 652,928,623 | 255,044,017 | 280,091,581 / 8,345 | 372,837,042 / 7,269 |
| 128 KiB | 9,043 | 9,046 | 1,288,925,924 | 891,041,318 | 573,903,338 / 5,319 | 715,022,586 / 3,727 |
| 256 KiB | 2,573 | 2,609 | 2,491,168,846 | 2,093,284,240 | 1,271,877,631 / 1,618 | 1,219,291,215 / 991 |
| 1 MiB | 60 | 249 | 3,447,355,366 | 3,049,470,760 | 1,879,742,558 / 141 | 1,567,612,808 / 108 |

At gap 0, the envelope overhead is exactly 2,713,537 bytes (2.588 MiB),
consisting of selected local-header/name/residual envelopes. The inter-selected
gap distribution explains the tradeoff: median 105,887 bytes, 90th percentile
275,623 bytes, and 99th percentile 588,839 bytes. Therefore small thresholds
save few requests, while thresholds above 64 KiB increasingly approach the
complete 3.525 GB Thermal payload.

## Recommended operating point and hard guards

- Default to **32 KiB** for the first real S1 pull: 447,814,570 bytes
  (427.069 MiB), only 49,929,964 bytes above selected payload, with 19,827
  nominal requests. It is the conservative bandwidth choice.
- If observed HF request setup/throttling dominates and transfer accounting is
  healthy, a separately recorded restart may use **64 KiB**: 652,928,623
  bytes (622.681 MiB) and 15,614 requests. Do not adapt the threshold from model
  results.
- Do not use 128 KiB or larger by default: 128 KiB already spends 1.289 GB to
  save about 10.8k requests; 256 KiB spends 2.491 GB.
- Enforce a body-byte hard cap equal to the selected nominal row before issuing
  the first request. Retries must also debit the cap; on exhaustion, stop and
  require an explicit new transport run rather than silently exceeding it.
- Keep coalesced bytes streaming-only. With an 8-worker, 16 MiB request cap,
  temporary response storage is bounded to 128 MiB plus the 397,884,606-byte
  verified output and filesystem overhead. Do not persist a 0.65--3.45 GB
  coalesced transport cache.
- Pin concurrency initially to 8 and use bounded backoff. HTTP retries can make
  actual wire bytes exceed the exact nominal table; the report must record
  successful body bytes, failed partial body bytes when observable, request
  attempts, and final per-volume totals separately.

## Release boundary

This plan only makes official training transport more efficient. It does not
unlock IMU, tune S1, change the preregistered 6/18 fast-kill folds, read test
labels, authorize a Kaggle submission, or support a Top-5 claim. S1 evidence
gates still apply after CRC-verified extraction.
