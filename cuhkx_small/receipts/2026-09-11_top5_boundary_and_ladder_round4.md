# CUHK-X Small — Top-5 boundary and preregistered ladder, round 4

Frozen: `2026-09-11T06:27:11Z`, before any accepted Small training sensor
payload or real P2 fold was available.

## Outcome

`PASS_RESEARCH_BOUNDARY_BLOCKED_DATA / REJECT_NO_TEST_CANDIDATE`.

The round produced a fail-closed boundary harness and a three-stage causal
submission ladder. It did not produce scientific model evidence: the official
training payload remains unavailable, so no real fold was fit, no test payload
or label was read, and no submission was created.

The current public aggregate leaderboard was read once through the Kaggle API,
without downloading the leaderboard or querying rows. At the freeze time:

- first place: `0.98507`;
- fifth place: `0.94029`;
- sixth place: `0.91542`.

This snapshot fixes the scale of the Top-5 objective. It is not used to choose
features, thresholds, folds, augmentations, or predictions.

## Full boundary matrix

| Boundary | Frozen requirement | Implemented check | Current state |
|---|---|---|---|
| Subject leakage | Train and validation subject sets have empty intersection; LOSO order 6, 18, 5, 21 | Synthetic positive and leaking cases in `test_small_boundary_harness.py` | `PASS_HARNESS`; real folds `NOT_RUN` |
| Clip leakage | Canonical clip keys are unique and disjoint; split manifest hash freezes before fit | Duplicate/overlap rejection in `audit_split_records` | `PASS_HARNESS`; real manifest absent |
| Missing modality | Availability mask exactly equals present inputs; no silent zero fill; training dropout only | Missing, present, mismatched-mask, and unsupported-missing cases | `PASS_HARNESS`; S2 locked |
| Sensor order | Strictly increasing finite timestamps, no duplicates; natural numeric frame order; pinned IMU channel order | Reordered timestamp rejection and `frame1, frame2, frame10` ordering test | `PASS_HARNESS`; real sensor audit absent |
| Scale drift | Per-channel median/IQR fit on training fold only; validation cannot update it; extreme robust-z slice is reported/rejected | Clean and 999-unit drift synthetic cases | `PASS_HARNESS`; real slice absent |
| One checkpoint | Exactly one learned-weight file; FP32 `<95,000,000` bytes or INT8 `<100,000,000` bytes; INT8 loss at most 0.005 | Package enumeration, hash, size, second-weight rejection, and quantization gate | `PASS_HARNESS`; no trained checkpoint |
| Static no-LLM inference | `uses_llm=false`; approved small CNN/TSM/MLP family; no LLM imports | AST scan rejects `transformers`, `openai`, etc.; current P2 source has no forbidden import | `PASS_HARNESS` |
| License/provenance | Every code/data/weight asset has public URL, version, license, SHA-256, and `APPROVED`; no conflict or quarantined path | Hash/license inventory validator and unresolved-license negative test | `PASS_HARNESS`; release inventory absent |
| Offline/network | Inference has no network import/use; all assets local; two clean outputs hash-identical | Static network-import scan and two-output release check | `PASS_HARNESS`; final replay absent |
| Submission frequency | Official maximum 5/day; campaign maximum 3/day; one causal mechanism per qualified submission | CSV UTC/unique-ID/per-day audit | `PASS`, one recorded submission on 2026-09-08 |

The release validator also fails if any weight-like file in the package is not
the single enumerated checkpoint, a local hash differs, a quarantined mirror is
referenced, output hashes differ, the scientific gate is false, or test labels
or inference networking are declared.

## Three-submission preregistered ladder

The ladder is sequential. A stage cannot consume a Kaggle submission unless
its predecessor passes all offline gates. A public score may confirm an already
frozen candidate but cannot select the next mechanism.

1. **S1 — Thermal TSM + TDN, at most 10 hours after payload.** Compare the
   existing B0 temporal-mean model with the identical backbone,
   initialization, frames, optimizer, schedule, and resolution plus only
   zero-parameter TSM and signed positive/negative frame-difference channels.
   Kill after subjects 6 and 18 if both gains are below +1 point. Promote after
   four subjects only for median gain at least +2 points, at least 3/4
   nonnegative, and worst gain at least -2 points.
2. **S2 — conditional Thermal + IMU fusion, at most 9 additional hours.** It is
   locked until S1 passes and an official IMU payload exists. Freeze the S1
   visual path; add only a small IMU MLP, explicit availability mask, gated
   fusion, and train-only modality dropout. Kill after two folds for median
   gain below +0.5 point or a missing-Thermal ablation drop above 10 points.
   Promote after four folds for median gain at least +1 point, at least 3/4
   nonnegative, worst at least -1 point, and no missing-modality regression
   above 2 points.
3. **S3 — train-only robust augmentation, at most 7 additional hours.** Keep
   the accepted S2 graph fixed; change only clip-consistent Thermal crop and
   intensity jitter plus IMU scale/time jitter. Kill after two folds for median
   gain below +0.3 point. Promote after four for median gain at least +0.5
   point, 3/4 nonnegative, worst at least -0.5 point, and no corruption-slice
   regression. Scalar temperature is trained on inner training folds and
   reported for reliability only; it cannot claim an accuracy gain because it
   does not change argmax.

The full ladder therefore costs at most 26 experiment hours after the required
official modalities arrive, and at most three qualified submissions. A failed
fast-kill consumes no submission.

## Top-5 feasibility interval and evidence threshold

The planning interval is deliberately conservative and is not presented as a
statistically calibrated probability:

- **now, unconditional:** `0.1%–1%`; there is no accepted training payload or
  real Small fold, while the current public fifth-place score is `0.94029`;
- **conditional on every frozen evidence gate passing:** `15%–40%`; hidden
  subjects and the public/private split can still differ materially even after
  strong subject-disjoint validation.

The campaign may call a model a **Top-5 candidate** only if all of the
following exist before test inference:

1. all three causal stage gates pass on subjects 6, 18, 5, and 21;
2. their median absolute accuracy is at least `0.90`, worst subject at least
   `0.82`, and present-class macro recall at least `0.86`;
3. two preregistered confirmatory subjects, 9 and 24, remain untouched until
   the ladder is frozen, then have pooled accuracy at least `0.90` and no more
   than a 3-point drop from the four-subject median;
4. Thermal-blank, IMU-missing, timestamp reordered/duplicated, and IMU-scale
   drift slices are all reported and satisfy their stage gates;
5. one-checkpoint, deterministic replay, static no-LLM/offline inference, and
   complete license/provenance gates all pass.

Passing these gates raises the candidate into a plausible range; it does not
guarantee `0.94029` on Kaggle. Failing any gate means
`REJECT_NO_TEST_CANDIDATE`, not “submit and see.”

## Official dataset portal addendum

The organizer-linked dataset browser at
`https://aiot-public-dataset-cuhk-x.cuhkaiot.com/` was inspected without
requesting a data object. Its referenced `script.js` documents the interface:

- directory listings: `/api/files<path>/` as Nginx autoindex JSON;
- file downloads: `/data<path>`, but only for a filename actually returned by
  a listing.

At `2026-09-11T06:33:53Z`, the root API returned the public directories
`CUHK-S`, `CUHK-X`, and `CUHK-X-Challenge`. The challenge directory returned
`Large-Model-Track` and `Small-Model-Track`, and Small returned `Test` and
`Train`. However:

- `/api/files/CUHK-X-Challenge/Small-Model-Track/Train/` returned HTTP 200 and
  exact body `[]`;
- `/api/files/CUHK-S/HAR/` returned HTTP 200 and exact body `[]`;
- `/api/files/CUHK-S/source_data/` returned HTTP 200 and exact body `[]`;
- `/api/files/CUHK-X/` returned HTTP 200 and exact body `[]`.

`source_data` is a sibling of `HAR`, not its child. The empty directories have
historical modification timestamps between March and June 2026, but expose no
current object name, size, hash, or download URL. The transport decision is
therefore `OFFICIAL_PORTAL_EMPTY_LISTING`: first-party and legal to monitor,
but it supplies zero training files and cannot unblock P2. No guessed `/data`
URL was requested.

## Implemented artifacts and verification

- `config/top5_preregistered_ladder.json`, SHA-256
  `59b7c19040353527751fdd786b334c636635c7953213442d632dff13e65b82dd`;
- `src/small_boundary_harness.py`, SHA-256
  `2bf91c6e6df8aef7e6dac57e4ce9ba30ac4814f86fa7f4d0d1bbe5171be828ca`;
- `src/test_small_boundary_harness.py`, SHA-256
  `9d82420067fdc0fe7f7b9da0ffaaa1dc41087f6b13be345b71d8337bc76c23ba`.

The Small suite passed `12/12` tests in `12.640s`. The standalone boundary
audit returned `PASS_RESEARCH_BOUNDARY_BLOCKED_DATA`: all ten boundary classes
are frozen, the current submission cadence is valid, and the P2 source has no
forbidden LLM/network import. This is harness readiness only. At the same
check, the host had about 27 GiB free, still far below the full-archive plan.

The campaign-wide deep harness then passed in research mode: Large unit tests
`20/20`, Large plain-function tests `10/10`, Small tests `12/12`, all three
Large candidate grammar checks, the 235-file deep reproducibility manifest,
the 1,265-event exposure registry, and the new Small boundary command passed.
The unified result was correctly `PASS_RESEARCH_BLOCK_RELEASE`; release stayed
false rather than being masked by the research checks.
