# CUHK-X Large Stage2-native v1 — fail-closed receipt

- Recorded UTC: `2026-09-11T04:49:48Z`
- Outcome: `REJECTED_IMPLEMENTATION_ABORT_NO_CANDIDATE`
- Network-isolation preflight: `PASS`
- Frozen cohort: 48 unique QA IDs and 48 unique clips, label-blind, subject-disjoint, with zero QA/clip overlap against the append-only VLM history at freeze time.
- Earlier shared-log contamination: 7 rows, permanently excluded by both QA ID and clip path and recorded in `artifacts/manifests/vlm_exposure_registry.jsonl`.
- Attempted: 35/48; parse-valid: 35/35; logged inference errors: 0.
- Abort: row 36 (`training_3656`) pointed to an official clip containing only 5 frames, while the immutable protocol required exactly 8. The code was not changed and the run was not resumed after fresh outputs existed.
- Performance gates: not evaluated on an incomplete cohort.
- Test VLM inference: not started.
- Candidate CSV: not created.
- Kaggle submission: not attempted.
- Public leaderboard: not used for tuning.

Frozen hashes:

- Protocol: `d2811db969f8f632b99a458f1b18b894d218d513fb436f2869b10858cfd6a0d7`
- Selection: `b85726035ac2489f3d1510b2bdc4fce5f1035dc0667da62af66005b5fdbc1ed5`
- Runner: `cfc8e91f4b0a17e0adb133a8154c3c053f123453d17129bad3c089e56c1baf36`
- Partial fresh log: `5fc095edf5b1c9fac27095e0cce0f385fe0dd94bbf64bea5934abefa1975cb70`

This receipt is terminal for v1. Any future fixed-frame padding experiment must be a separately named protocol and must exclude all 35 newly exposed QA IDs and clips before its first inference.
