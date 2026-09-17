# CUHK-X Small Model Track: Google Drive transfer manifest

Audit time: 2026-09-09T08:31:28Z (2026-09-09 16:31:28 +08:00)

Purpose: preserve the organizer-linked public transfer coordinates without downloading the full training corpus onto an undersized local disk.

## Provenance

- Challenge Google Drive root: `1wZOPpTFLqDKjBLJGjMdOZyuJygLHbwCZ`
- Training-data folder: `1k7Ow9L-ErWAOESMTXBUhARaJz6JG7ql_`
- The file IDs below were recovered from Google's embedded folder listing for the organizer-linked Drive tree.
- The official dataset browser API currently returns empty arrays for the Small Model Track `Train/` and `Test/` directories, so the organizer-linked Drive/Hugging Face mirrors remain the available public transfer sources.

## Training split-volume file IDs

| File | Google Drive file ID |
|---|---|
| `HAR.z01` | `1uue29l0fGuAmFkurs3idiZtLfX5vTtVo` |
| `HAR.z02` | `19yYqCAJP2TBN0d0BO4rRrCU5phzMajv-` |
| `HAR.z03` | `1QbsW4TupA2QMuE8ckph-YT9kP_MKRakV` |
| `HAR.z04` | `1l88H18t2RGS4_FVNDjjEaojV78YjMYrZ` |
| `HAR.z05` | `1OwnMopVOWZC1UGooUZE2Xq4ouin3tBDR` |
| `HAR.z06` | `1N0DivixXvFV9p9XdxMmcf5yHOneTqL-u` |
| `HAR.z07` | `1Hrap5N8T_bUeEX9V59oAIlsCKTzUQc3D` |
| `HAR.z08` | `1HW5nxo03oNkw1_Xk1k5Pw6fQH2U_q5XK` |
| `HAR.zip` | `1nlJIpcRuL2FRcapJaFVS3eC-uZuedtqh` |
| `class_mapping.csv` | `1P01HMoKSrkC-Lx3G_kkIZ-Q0ajHe77AG` |

Exact byte sizes and SHA-256 digests are recorded in `../OFFICIAL_DATA_MANIFEST.csv`. The nine training volumes total 44,622,809,265 bytes (41.558 GiB) before extraction.

## Capacity guard and actions

- Local free space at audit time: 33 GiB on `/System/Volumes/Data`.
- No separate data volume is available; `/Volumes/ChatCut` and `/Volumes/Macintosh HD` are not suitable external storage targets.
- The 41.558 GiB compressed training archive alone exceeds current free space, before accounting for extraction or experiment headroom. Training download is therefore intentionally deferred.
- No training archive bytes were retained during this audit, and no gated mirror/contact-information flow was used.
- The already-downloaded test archive remains hash-matched to the public mirror metadata and is documented separately in `2026-09-09_test_archive_audit.md`.

