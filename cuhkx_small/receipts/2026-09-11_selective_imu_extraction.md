# CUHK-X Small Track — selective IMU extraction implementation

Implementation and verification completed: 2026-09-11 12:39 CST.

## Outcome

The storage blocker has been removed from the extraction design.  The new
reader does not download or assemble the 44,622,809,265-byte split archive.  It
instead:

1. range-reads the ZIP/ZIP64 end records and 73,843,427-byte central directory;
2. validates the known nine-disk geometry and parses all member metadata;
3. selects only `HAR/data/IMU/**`;
4. range-reads each selected local header and stored payload, including spans
   that cross a split-volume boundary;
5. rejects encrypted, compressed, duplicate, absolute, traversal, or malformed
   members; and
6. writes each file atomically only after size and CRC-32 verification.

The same reader now supports deterministic midpoint sampling within each
visual clip directory. For the frozen P2 Thermal run it keeps at most eight
frames per clip using the preregistered midpoint rule. It first verifies the
complete Thermal inventory (2,891 groups, 201,466 files, 3,524,685,759 bytes),
then retains no more than 23,128 frames. Depth_Color and IR inventories are
pinned too, but their extraction is locked until Thermal passes independently.

The frozen official selection is exactly 5,806 CSV files totaling 74,079,366
payload bytes.  Therefore the retained data path is about 148 MB for central
directory plus IMU payload, rather than 82.99 GiB for archive plus full
extraction.  Existing CRC-valid files are reused for resumability.

## Files and verification

- Reader: `src/selective_split_zip.py`.
- Reader SHA-256:
  `36d4ff5027950c46ba8da0efb6148c3e8ec680d9eab4116b91def022ca0fb55e`.
- Official source manifest: `config/training_split_drive.json`.
- Local integration test: `src/test_selective_split_zip.py`.
- Test SHA-256:
  `3fe58f4b210b3dda7b94dbb7a98b002703ce28bd326c72dc1b1f9b0bd8fd6631`.
- Both source files are original work marked `SPDX-License-Identifier:
  Apache-2.0`; no organizer implementation is incorporated.
- Reverification command from `cuhkx_small/src`:
  `python3 -m unittest test_selective_split_zip` followed by
  `python3 -m py_compile selective_split_zip.py test_selective_split_zip.py
  train_imu_length_smoke.py audit_subject_splits.py`.
- Tests passed:
  - regular multi-volume stored ZIP, including target-only extraction, skipped
    modality, cross-volume payload, CRC validation, and reuse;
  - synthetic ZIP64 end record and locator parsing.
  - deterministic midpoint selection within clip directories.

The production selection boundary is a member whitelist, not a filename
substring search: the requested prefix is normalized through the safe-path
validator, the nine-volume manifest pins central-directory geometry, and the
manifest pins the expected available file count and payload byte count for each
supported prefix. Any absolute/traversal path, duplicate, archive geometry
change, count change, or byte-count change aborts before extraction; the fetched
central directory's SHA-256 is recorded for all later resumes.

## Live official-mirror attempt

The official Google Drive route was attempted with a 16 KiB maximum range and
stopped before creating the central-directory cache.  Google returned HTTP 200
HTML titled `Google Drive - Quota exceeded` instead of the required HTTP 206
byte range.  A probe against the first split volume returned the same quota
page, so the quota is not limited to the final volume.

The organizer's Kaggle data page lists only Baidu Wangpan, Google Drive, and the
Hugging Face mirror and states that all three contain identical data. The
Hugging Face repository currently returns a gated-repository response until
the user shares contact information; that authorization was not granted.

The organizer's public Baidu Wangpan mirror was then checked through Baidu's
own current web endpoints. Password verification succeeded, the share listing
returned the same nine training volumes and exact sizes, and the official
template endpoint returned a short-lived `sign` and `timestamp`. A signed,
single-file `/api/sharedownload` request for `HAR.zip` returned `errno: 0`, but
its `list` value was a 1,868-character encrypted/client-handoff string rather
than a file record containing an HTTP `dlink`. Repeating the request with the
browser's user agent and normal request headers produced the same result. No
archive volume was downloaded. Response bodies used for this audit had
SHA-256 `a27b5319196bf4d496a650a283299b3150e65aa51c3d4518662297e9832b240d`
(template response) and
`910f9c98ae1b3e1b056bbbd9471fd47fbcc916e5a35cbe7c4dbe298b181584ac`
(download-link response). Short-lived signing and share-session values are not
retained in the campaign.

Therefore the roughly 148 MB selective-acquisition design is locally verified,
but both official public transports are currently blocked: Google by quota and
Baidu by anonymous client handoff. Public search found no additional
traceable, ungated copy of the IMU members.

## Resume condition

When the public Google quota clears, or when an official Baidu route exposes a
normal range-capable HTTP `dlink`, run the reader without `--index-only`. It
will first cache and validate the central directory, then fetch only the
official IMU members. The run must produce
`EXTRACTED_AND_CRC_VERIFIED`, 5,806 files, and 74,079,366 bytes before raw-IMU
training is allowed.

For P2, run the same reader with prefix `HAR/data/Thermal/` and
`--frames-per-clip 8`. The first two model folds remain forbidden until its
report is `EXTRACTED_AND_CRC_VERIFIED` and validates all pinned source counts.

No test archive, test label, leaderboard, or submission was touched by this
work.
