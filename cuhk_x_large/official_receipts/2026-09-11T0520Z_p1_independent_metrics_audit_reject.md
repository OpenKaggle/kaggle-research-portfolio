# P1 decomposed-sensor independent metrics audit — rejection receipt

- Decision: `REJECT_P1_NO_CANDIDATE_NO_SUBMISSION`
- Audit mode: read-only recomputation of the existing 48/48 P1 log; no VLM inference and no test QA read.
- Exposure registry v2: final log hash registered for all 48 QA/clip pairs; overlap with all earlier inference logs was 0 QA and 0 clips. An earlier 18-row partial registry snapshot remains append-only and is not treated as a conflict.
- Hashes: protocol, selection manifest, prediction log, and current runner all match the sibling terminal report. The protocol did not preregister the runner hash, which is an additional governance failure.
- Fair comparator: both arms use the same local model revision, Depth video, per-QA 1 FPS loader, 48-token ceiling, temperature 0, sensor OOF, semantic-base OOF, thresholds, and route.
- Reconstructed paired frame budget: 48/48 videos readable and hash-matched; both arms receive the same frames per QA; frame count ranges from 4 to 12 across QAs under the 1 FPS policy.
- Recomputed routed accuracy: P1 `33/48` versus generic parent `12/48`, net `+21`.
- Action: `12/24` versus `9/24`, net `+3`.
- Object: `21/24` versus `3/24`, net `+18`.
- Subject macro gain: `+0.37778`; worst-subject delta: `0.0`; fixed halves: `+11/+10`.
- Temporal field: all 48 use an allowed bucket, but 44/48 say `throughout`; this is a model-output stratum, not independent temporal ground truth, and is descriptive only.
- Hard failures: generic invalid `28`, P1 invalid `1`, P1 evidence-schema invalid `1`, plus no preregistered runner hash. The apparent gain is therefore dominated by output truncation/format reliability and cannot qualify the reasoning mechanism.
- Candidate CSV: not created.
- Kaggle submission: not attempted.
- Leaderboard tuning: not used.

Artifacts:

- Independent audit: `reports/p1_decomposed_sensor_fresh48_independent_audit_v1.json`, SHA-256 `9532b4dd72b0592b6840b7860f64c5c50879c75c931ed07dd0654065a54befce`
- Registry-v2 audit: `reports/vlm_exposure_registry_v2_audit_2026-09-11_p1.json`, SHA-256 `a60f513fbb76d1250ca99b13efb5a5e02d96907e2cba97664fa6af40da719c57`
- Label-blind P2 readiness proposal: `reports/p2_unexposed_video_preflight_and_proposal_v1.json`, SHA-256 `66afa0b4ea857c9087feb534d3337b00add717cc24d8884367e62c9f3b4172ca`
- P2 readiness table: `artifacts/preflight/p2_unexposed_video_readiness_v1.csv`, SHA-256 `3822dd0fb2f9670ff00d86c3fa1fbb15f784c183a4771d67593d5e5848c20fa1`

The remaining unexposed HARn pool has 218 QA rows / 214 clips; all are readable and hash-matched, while 206 rows satisfy a strict `total_frames >= 8` gate. Twelve short rows were detected before any new cohort freeze or inference. P2 remains proposed, not frozen.
