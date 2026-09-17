# TartanIMU IROS 2026 campaign

This directory is an auditable, competition-only workspace for the
[TartanIMU Challenge](https://www.kaggle.com/competitions/tartan-imu-challenge-iros2026).
The competition data is licensed CC BY-NC-SA 4.0 and may be used only for the
competition and non-commercial academic research. Do not copy it into public
artifacts or use it for commercial work.

## Current hard deadlines

- Final Kaggle prediction and, conservatively, public model weights/inference
  package: **2026-09-20 23:55 UTC / 2026-09-21 07:55 China Standard Time**.
- Technical report and final Submission Form: **2026-09-23 23:59 EDT / 
  2026-09-24 03:59 UTC / 2026-09-24 11:59 China Standard Time**.

The live Kaggle Rules page still says report and weights are due 2026-09-27
23:55 UTC, but the newer organizer announcement and challenge website set the
stricter dates above. This campaign uses the strictest published deadline.

## Compliance boundary

- One unified model and one disclosed weight package for all platforms.
- Test inference uses raw 6-axis IMU only. No test pose, orientation, velocity,
  platform label, hand labeling, private labels, or leaderboard probing.
- Platform labels may supervise training, but no separately trained
  per-platform expert dispatch is allowed at inference.
- Public/free external resources are not used unless their exact version and
  test-overlap risk have been checked and documented. The initial baseline uses
  only the released competition train/validation data.
- Every upload passes schema, ID/order, finite-value, leakage, stability, and
  rules checks. Exact CSVs and hashes are retained.

## Layout

- `data/raw/`: original Kaggle archive (never publish).
- `data/extracted/`: extracted competition data (never publish).
- `official/`: official open-source baseline repository.
- `artifacts/`: feature caches and model files.
- `submissions/`: immutable candidate CSVs and their manifests.
- `reports/`: campaign status, validation summaries, and error analyses.
- `src/`: reproducible audit, feature, training, scoring, and validation code.

## First baseline

The first honest model is a single CatBoost multi-output regressor over
deterministic IMU window and same-trajectory context features. It predicts
`vx, vy, vz` directly without platform routing. The official validation split
is held out for selection, and the released exact metric code is used locally.

