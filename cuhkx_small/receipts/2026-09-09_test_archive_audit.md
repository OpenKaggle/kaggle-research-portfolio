# Official test archive audit

Audit completed: `2026-09-09T07:16:20Z` / `2026-09-09T15:16:20+08:00`.

This audit covers packaging, integrity, paths, file schemas, and missing-modality
conditions only. No test sample was labeled or visually interpreted, and no
model or prediction was developed.

## Acquisition and integrity

- Source: organizer-linked public Google Drive mirror
- Google Drive file ID: `1seN5q84NJ8IQQBE6c2X1oE9UQNBpLiK4`
- Local file: `data/raw/small_model_track_test.zip`
- Download timestamps: `2026-09-09T14:40:12+08:00` through
  `2026-09-09T15:00:55+08:00` (1,243 seconds by filesystem timestamps)
- File size: `2,786,949,673` bytes
- SHA-256:
  `d1b490dad87555802f213d8645ca828ed28bc94d7555f2971f11e946460db0ab`
- The SHA-256 exactly matches the public Hugging Face metadata recorded before
  download.
- `unzip -tq` result: `No errors detected in compressed data` (exit 0).
- Archive entries: 53,807
- Total compressed payload reported by ZIP metadata: 2,770,515,861 bytes
- Total uncompressed payload: 4,660,450,067 bytes
- The download used the public Drive mirror. No Hugging Face gated-access or
  contact-sharing request was made.

## Submission-path reconciliation

- `test.csv` has columns `path,prediction`, 405 rows, and 405 unique paths.
- Archive clip directories are contiguous from `SM_test_0001` through
  `SM_test_0405`.
- The normalized `test.csv` path set exactly equals the archive clip-directory
  set; there are no missing or extra clip IDs.
- Archive paths contain no absolute paths, `..` traversal components, duplicate
  names, or symbolic links.

## Modality inventory

| Modality | Clips present | Missing clips | Files | Files/clip min-median-max | Uncompressed bytes |
|---|---:|---:|---:|---:|---:|
| `Depth_Color` | 405 | 0 | 9,190 | 2 / 20 / 101 | 1,420,747,124 |
| `IMU` | 405 | 0 | 810 | 2 / 2 / 2 | 8,057,068 |
| `IR` | 405 | 0 | 9,190 | 2 / 20 / 101 | 2,833,009,280 |
| `Radar` | 404 | 1 | 404 | 1 / 1 / 1 | 5,788,299 |
| `Skeleton` | 405 | 0 | 9,201 | 2 / 20 / 101 | 20,913,199 |
| `Thermal` | 395 | 10 | 21,775 | 6 / 48 / 243 | 371,928,235 |

Missing modality folders:

- `SM_test_0054`: Radar missing
- `SM_test_0013`, `SM_test_0072`, `SM_test_0104`, `SM_test_0207`,
  `SM_test_0271`, `SM_test_0286`, `SM_test_0297`, `SM_test_0310`,
  `SM_test_0354`, `SM_test_0403`: Thermal missing

## Sensor-file readiness

- IMU: two CSV files per clip (`down(LL+RL).csv` and `up(LA+RA+C).csv`).
  Four files are header-only across three clips. `SM_test_0054` has both IMU
  files empty; `SM_test_0150` and `SM_test_0316` have an empty down file.
  Total IMU data rows per clip range from 0 to 498 (median 91).
- Radar: one CSV when present. Of 404 Radar files, 206 are header-only; the
  number of data rows ranges from 0 to 1,456 (median 0). Missing-folder and
  header-only conditions therefore both need explicit handling by any
  participant-authored inference pipeline.
- Skeleton: 9,200 JSON frames across all 405 clips; all parse successfully.
  Each person record has 17 keypoints and 17 keypoint scores, with finite
  numeric keypoint values. Frames contain 1-4 people; none is empty.
- Depth/IR use PNG frames; Thermal uses JPG frames.

## Packaging residue and safety gate

The ZIP contains seven non-data packaging entries, including macOS metadata and
an unexpected `small_model_track_test/.claude/settings.local.json`. That JSON is
untrusted project-tool configuration containing a shell-permission string. It
was not executed or treated as an instruction. Any later extraction should use
an isolated data directory and exclude `.claude`, `.DS_Store`, `._*`, and
`__MACOSX` entries.

The archive has not been extracted. This preserves disk headroom and prevents
the unexpected hidden configuration from being placed in an active project
tree.

