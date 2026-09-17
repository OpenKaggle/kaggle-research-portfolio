# CUHK-X Small Model Track campaign

## Post-competition closeout — 2026-09-17

- Kaggle marks the competition completed; the official deadline was
  `2026-09-15 23:59:00` and the leaderboard now states that it reflects the
  final standings. Do not treat the visible **Late Submission** action as an
  official competition submission.
- The solo team `Jiayi Du` (`jahyee`) made exactly one valid submission,
  `56107602`. Its final scores are public `0.03482` and private `0.04901`.
  Final positions are public `309/326` and private `305/326`.
- The official P2 Thermal run did **not** complete into an auditable result.
  No P2 process is running and no P2 output directory, run binding, progress
  file, fold receipt, report, or checkpoint exists. The termination cause is
  not recoverable from the preserved artifacts, so this is
  `NOT_COMPLETED_UNKNOWN_TERMINATION`, not a scientific rejection of P2.
- Consequently P2's preregistered gate was never evaluated, S2/S3 were never
  unlocked, and no learned Small-track candidate was submitted. The only
  Kaggle entry remains the organizer sample-schema smoke test.
- Reusable assets remain intact: the official eight-frame Thermal subset is
  CRC-verified (22,734 files, 2,891 clips), the frozen LOSO/TSM experiment and
  fail-closed resume harness are preserved, and the full Small test suite
  passes 25/25 on 2026-09-17. No test labels were read.

See `receipts/2026-09-17_postcompetition_closeout.md` for the evidence,
artifact inventory, and next-edition handoff.

Status as of 2026-09-11T06:33:53Z:

- Current independent gates: Transport=`BLOCKED`,
  Scientific=`NOT_RUN_PAYLOAD_BLOCKED`,
  Release=`REJECT_NO_TEST_CANDIDATE`. Harness work alone does not advance any
  of these gates, and no model progress is claimed before an accepted real
  sensor payload arrives.
- This workspace is bound to the campaign-wide `../CUHK_X_CONTROL_PLANE.md`:
  legal-public transport only, fail-closed public-asset licensing, the frozen
  P2 fast-kill, and exactly one inference checkpoint below 100 MB. The user has
  explicitly authorized the official Hugging Face repository to receive the
  current HF username and email; all other contact transfers remain disabled
  without exact authorization.
- Kaggle rules accepted and competition joined.
- Kaggle team name: `Jiayi Du` (solo team, user `jahyee`).
- First valid submission completed: ID `56107602`, public score `0.03482`.
- Official challenge-site registration was confirmed on 2026-09-11 at 04:22 UTC for the solo team `Jiayi Du`, covering both the Small and Large Model tracks. The registered affiliation is `Stiftung Louisenlund`, country/region is `Germany`, and faculty advisor is blank.
- The official 2.787 GB test archive is now downloaded from the public Google Drive mirror, hash-matched, ZIP-integrity-tested, and path-reconciled against all 405 `test.csv` rows. It remains unextracted by design.
- The official 841-byte `class_mapping.csv` is now downloaded from the public Google Drive mirror and validated as an exact, ordered 40-class `0`–`39` mapping; SHA-256 `09f5794978faedb2bb478f41de0bf8545bf346e2b49b85eabb9504e238d0b7cb`.
- Full training + test mirror size is 47.4 GB. The system had about 37 GiB free at the latest check and no suitable external data volume, far below the verified 82.99 GiB minimum for retaining and extracting the stored training archive before experiment headroom.
- Exact organizer-linked Google Drive IDs for all nine training volumes and `class_mapping.csv` are recorded, so acquisition can resume without rediscovery when adequate storage is available.
- A bounded 70.4 MiB HTTP-range audit of the training ZIP64 central directory recovered all 491,879 entries without downloading payloads: 3,036 clips, exact 40-class and 18-training-subject schema, explicit missing-modality coverage, and no unsafe paths. Because every member is stored rather than compressed, archive plus extracted payload needs at least 82.99 GiB before experiment headroom.
- Organizer baseline source is pinned, unmodified, at commit `df03910a6960db5af9179e370e130bf61d9616d0` under `vendor/CUHK-X`.
- Static audit found that the organizer tree contains no weights or competition inference/submission path and has several run-blocking defaults; it is not a ready baseline.
- CUHK-X License v2.0 conflicts operationally with the Apache 2.0 finalist obligation if organizer code is incorporated. Keep `vendor/CUHK-X` as reference-only pending written clarification.
- Official host clarification supersedes the earlier over-strict reading of “No LLMs for development”: AI coding assistants are allowed for writing/debugging, but the final inference model cannot be an LLM and every learned inference weight must fit in one checkpoint under 100 MB.
- Public external datasets and pretrained models are allowed only when reproducibly accessible and fully disclosed. Every experiment must also pass frozen subject-disjoint and clip-disjoint validation plus source/license and checkpoint-size audits before submission.
- No new model submission has been made. The existing smoke submission is `0/2` manually selected but is an explicit Kaggle auto-selection candidate.
- The visible public 0.711/0.716 YOLO + R(2+1)D baseline family was re-audited. Its model dataset is currently API-readable: the two real weight files total 93,688,142 bytes and match the published schema, but remain split across `ensemble_packed.pt` and `yolo11n.pt`. Only two aggregate parent fold scores are supplied, no subject/clip manifest or per-subject/per-class evidence can be independently reproduced, and the AGPL YOLO component leaves an unresolved finalist Apache-2.0 boundary. It remains research-only and was not run or submitted.
- An original Apache-2.0 split-audit utility now validates three fixed six-subject folds over the organizer's 2,768-row IMU index. Every fold has zero subject overlap and zero clip overlap; the constant-control accuracies are 12.50%, 8.86%, and 12.13%. Training payload readiness remains 0/2,768, so the current decision is `REJECT_NO_TEST_CANDIDATE`.
- A preregistered IMU-index metadata smoke completed with zero subject/clip leakage and one deterministic 39,123,979-byte non-LLM checkpoint, but failed the offline promotion gate: mean accuracy 4.18% versus an 11.16% majority control and mean macro recall 3.87%. Two clean repeats were byte-identical. It is explicitly `REJECT`, retained only as a pipeline control, and was not submitted.
- An original selective split-ZIP/ZIP64 reader now reduces the raw-IMU acquisition plan to the 73,843,427-byte central directory plus exactly 5,806 CRC-verified IMU CSVs totaling 74,079,366 bytes. Local regular-split and ZIP64 tests pass. The first official-mirror run stopped safely because Google returned a quota page before any cache or training payload was written.
- The organizer's public Baidu mirror was also audited without downloading a volume. Password verification, the nine-part file listing, and short-lived request signing all worked, but anonymous `sharedownload` returned only a 1,868-character encrypted/client-handoff value rather than a verifiable HTTP download URL. The selective reader is implementation-complete, but raw training payload remains `BLOCKED_TRANSPORT` on both official public routes.
- A third-round one-byte matrix rechecked every Google training volume at `2026-09-11T05:34:43Z`: all nine independently returned the same HTTP 200, 2,009-byte quota HTML and no `Content-Range`. A new bounded probe records all responses and transfers at most 64 KiB per volume; only nine exact HTTP 206 responses can unlock the selective reader.
- A public 3.62 GB Kaggle Thermal copy was rejected before use because its uploader labels the CUHK-X competition data CC0 even though the organizer's CUHK-X License v2.0 says the data is not redistributable. Its interrupted 1,191,182,336-byte partial file has a machine-readable quarantine sentinel, remains unextracted, and is excluded from training; P2 discovery now hard-rejects every `public_mirror` path and the guard has a passing regression test. Public notebook inventory found no other accepted training payload; the strongest Thermal notebook publishes method code but no trained weights or attached training data.
- The host has additionally clarified that INT8 and similar quantization are allowed and encouraged; the binding packaging rule remains that every inference weight must live in one on-disk checkpoint smaller than 100 MB. Quantization will only be evaluated after an FP32 candidate passes its frozen OOF gate.
- P2 is preregistered and implementation-complete: single-modality Thermal first, an eight-frame MobileNetV3-Small comparison of temporal mean pooling against zero-parameter TSM plus positive/negative signed frame differences. Four LOSO subjects are frozen as 6, 18, 5, and 21 with a two-fold early kill. The 1,558,856-parameter scaffold passes local split-ZIP, ZIP64, training, checkpoint, and deterministic replay tests, but its real folds remain `PREREGISTERED_PAYLOAD_BLOCKED`; Depth/IR and missing-modality fusion stay locked.
- The public aggregate leaderboard was frozen once for planning: fifth place was `0.94029` and sixth place `0.91542` at `2026-09-11T06:27:11Z`. These scores are not feature, threshold, fold, or hyperparameter selectors. Current unconditional Top-5 feasibility is only a `0.1%–1%` planning range because no accepted Small training payload or real P2 fold exists.
- A three-submission ladder is now frozen before data access: S1 Thermal TSM + signed temporal differences, S2 conditional Thermal/IMU fusion only after S1 passes, and S3 train-only robustness augmentation only after S2 passes. Every stage changes one causal mechanism, has a two-fold fast-kill, requires four subject-disjoint folds, and consumes no submission on failure. A separate untouched confirmation uses subjects 9 and 24.
- The Small boundary harness now covers subject and clip leakage, explicit missing-modality masks, sensor ordering, train-only robust scaling, single-checkpoint packaging, static no-LLM/offline inference, asset license/hash inventory, deterministic replay, and submission cadence. The Small suite passes 15/15 tests, including the HF auth/Range boundary; this advances research readiness only, not the scientific or release gates.
- The organizer-linked dataset browser exposes a documented JSON listing API and direct-data path, but the current Small `Train`, historical `CUHK-S/HAR`, `CUHK-S/source_data`, and `CUHK-X` listings all return HTTP 200 with empty arrays. It is first-party and safe to monitor, but no filename or legal download object is currently exposed, so it is `OFFICIAL_PORTAL_EMPTY_LISTING` and does not unblock P2.
- Official Hugging Face browser access is now granted, but the CLI has no token because creating/viewing one requires the user to confirm their own password. A revision-locked nine-volume HF manifest and environment-only Bearer transport are ready: missing auth fails before networking, 401/403 bodies are not read, ignored Range responses are bounded, and exact subject/per-volume planning downloads no member payload. No password or token value was handled or stored.

Authoritative links:

- Kaggle: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track
- Kaggle rules: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/rules
- Kaggle data page: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/data
- Official team registration: https://openaiotlab.github.io/CUHK-X-Challenge/#registration
- Official challenge details: https://www.ubicomp.org/ubicomp-iswc-2026/cuhk-x-competition/
- Official AI-assistant clarification: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724942
- Official external-data clarification: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724404
- Official single-checkpoint / ensemble clarification: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/729056
- Official quantization / checkpoint clarification: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/740749
- Official code: https://github.com/openaiotlab/CUHK-X
- Officially linked Hugging Face mirror: https://huggingface.co/datasets/Kevin-Pal/CUHK-X_Small_Model_Track
- Officially linked Google Drive mirror: https://drive.google.com/drive/folders/1wZOPpTFLqDKjBLJGjMdOZyuJygLHbwCZ?usp=drive_link

See `receipts/2026-09-09_official_status.md`,
`receipts/2026-09-09_baseline_and_ip_audit.md`, and
`receipts/2026-09-09_test_archive_audit.md`, and
`receipts/2026-09-09_drive_transfer_manifest.md`, and
`receipts/2026-09-09_class_mapping_audit.md`, and
`receipts/2026-09-09_training_central_directory_audit.md`, and
`receipts/2026-09-11_official_discussion_rule_clarification.md`, and
`receipts/2026-09-11_public_baseline_gate_audit.md`, and
`receipts/2026-09-11_research_and_split_sprint.md`, and
`receipts/2026-09-11_official_team_registration.md`, and
`receipts/2026-09-11_imu_length_smoke_preregistration.md`, and
`receipts/2026-09-11_imu_length_smoke_result.md`, and
`receipts/2026-09-11_selective_imu_extraction.md`, and
`receipts/2026-09-11_p2_tsm_preregistration.md`, and
`receipts/2026-09-11_p2_tsm_scaffold.md`, and
`receipts/2026-09-11_control_plane_binding.md`, and
`receipts/2026-09-11_transport_matrix_round3.md`, and
`receipts/2026-09-11_top5_boundary_and_ladder_round4.md`, and
`receipts/2026-09-11_small_research_decision_map_round4.md`, and
`receipts/2026-09-11_huggingface_handoff_round5.md`, and
`receipts/2026-09-11_small_execution_state.md`, and
`receipts/2026-09-11_topdown_strategy_review.md` for the evidence logs.
