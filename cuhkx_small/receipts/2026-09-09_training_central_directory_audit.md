# CUHK-X Small Model Track: training split central-directory audit

Audit completed: `2026-09-09T12:58Z` / `2026-09-09 20:58+08:00`.

Purpose: recover and validate the full training archive's schema without downloading or extracting the 41.558 GiB split archive onto a disk with only about 23 GiB free.

## Live competition and registration recheck

- Kaggle still reports deadline `2026-09-15 15:55:00 UTC`, equal to `2026-09-15 23:55:00 Asia/Shanghai`; `userHasEntered=True` and the live team count is 307.
- Submission ID `56107602` remains `COMPLETE` with public score `0.03482` and no private score.
- The organizer site still renders the required registration form and continues to state worldwide eligibility, except that AIoT Lab members and direct collaborators are ineligible for prizes.
- No organizer registration was submitted because contact email, affiliation, country/region, and team-leader name remain user-supplied identity fields.
- The pinned organizer repository remains clean and unchanged locally and upstream at `df03910a6960db5af9179e370e130bf61d9616d0`.

## Bounded transfer evidence

Official public Google Drive file: `HAR.zip`, ID `1nlJIpcRuL2FRcapJaFVS3eC-uZuedtqh`.

- Server metadata: 1,673,136,305 bytes, `Accept-Ranges: bytes`, last modified 2026-06-18.
- Probe 1 fetched only the final 8,388,608 bytes, range `1664747697-1673136304`; runtime 4.3 seconds; SHA-256 `084b31c874ab3ccc203446b1fe72dc50477e9d3dfb8529b529990368ab5f5ef0`.
- That probe located the ZIP64 end record and showed that the central directory begins at byte 1,599,292,780 of `HAR.zip`.
- Probe 2 fetched the exact central-directory-plus-footer range `1599292780-1673136304`: 73,843,525 bytes (70.423 MiB); runtime 25.3 seconds; SHA-256 `729bbdac313c2d1961174c39aea62cfae8230f2f3de3c8707a8f57bae387fca3`.
- ZIP64 record: final disk 8, central-directory start disk 8, 491,879 entries, central-directory size 73,843,427 bytes, offset 1,599,292,780.
- The parser consumed exactly all 73,843,427 central-directory bytes and reached the ZIP64 end signature. The bounded probes were deleted after the derived audit was recorded.

No training payload was downloaded, no archive member was extracted, and no gated mirror or contact-data exchange was used.

## Archive integrity and safety metadata

- 491,879 total entries: 23,846 directory entries and 468,033 files.
- 491,879 unique normalized names; no duplicates.
- No absolute paths, parent traversal components, symlinks, hidden-path residue, or unexpected files.
- No encrypted entries.
- Every member uses ZIP method 0 (stored, not compressed).
- Sum of member payload sizes: 44,482,163,093 bytes (41.427 GiB). Because the archive is stored rather than compressed, retaining all nine volumes while extracting would require about 82.985 GiB before filesystem and experiment headroom. This confirms the capacity guard with substantially more margin than the archive size alone suggested.

## Training schema

The canonical hierarchy is:

`HAR/data/<modality>/<action_id>_<action_name>/<userN>/<clip_id>/<files>`

Skeleton frame JSON files add one `predictions/` level below the clip directory. All 468,033 files conform to these layouts.

- Exactly 40 action folders; every folder name matches the downloaded `class_mapping.csv` exactly.
- Exactly 18 subjects: `user1`–`user9` and `user16`–`user24`, matching the published training-side cross-subject split.
- 3,036 unique semantic clips across all modalities.
- Modality coverage: 2,748 clips contain all six modalities; 176 contain five; 7 contain four; 2 contain two; 103 contain one. Missing modalities are therefore part of the official training archive and must be handled explicitly by any independently developed solution.

| Modality | Clips | Missing vs. 3,036 union | Files | Payload bytes | Files/clip min–median–max | Type |
|---|---:|---:|---:|---:|---:|---|
| Depth_Color | 2,931 | 105 | 85,879 | 14,188,792,524 | 1–24–236 | PNG |
| IMU | 2,903 | 133 | 5,806 | 74,079,366 | 2–2–2 | CSV |
| IR | 2,933 | 103 | 85,918 | 26,461,897,975 | 1–24–236 | PNG |
| Radar | 2,914 | 122 | 2,914 | 55,278,578 | 1–1–1 | CSV |
| Skeleton | 2,931 | 105 | 86,050 | 177,428,891 | 1–24–236 | JSON |
| Thermal | 2,891 | 145 | 201,466 | 3,524,685,759 | 1–55–595 | JPEG |

This is a metadata-only data-contract audit. It does not inspect labels beyond organizer-supplied directory names, generate predictions, author model code, or use LLM/API labeling.

Offline model metric: not applicable. The only live model result remains submission ID `56107602`, public accuracy `0.03482`.
