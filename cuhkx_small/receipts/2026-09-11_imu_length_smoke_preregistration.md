# CUHK-X Small Track — IMU length smoke preregistration

Date frozen: 2026-09-11, before the first model fit.

## Purpose and permitted inputs

This is a metadata-only engineering smoke while the raw training archive is
blocked by local capacity and Google Drive quota.  It may read only the
organizer-published IMU training index with SHA-256
`b8899369d158c8fe6c8c20fce1bed21a8340026c541013b6c90f7cd5595b0f6b`.
Permitted predictors are the five device row counts (`WTLA`, `WTC`, `WTRA`,
`WTRL`, `WTLL`), deterministic transforms of those counts, and the four
availability flags.  Subject IDs, clip IDs, paths, fold labels, `data_type`, and
activity labels are forbidden as model features.

The run must not open the test archive, generate test features, create a
submission, or contact the Kaggle leaderboard.

## Frozen validation

Use the three pre-audited six-subject holdouts:

- fold 0: subjects 3, 6, 9, 18, 21, 24
- fold 1: subjects 2, 5, 8, 17, 20, 23
- fold 2: subjects 1, 4, 7, 16, 19, 22

Every fold must have zero subject overlap and zero clip overlap.  Compare each
fold with a constant predictor fitted to that fold's training majority class.

## Frozen promotion gate

All conditions must pass:

1. Zero subject overlap and zero clip overlap in every fold.
2. Every fold accuracy exceeds its majority control by at least 0.02 absolute.
3. Mean fold accuracy exceeds mean majority-control accuracy by at least 0.05.
4. Mean fold macro recall is at least 0.10.
5. The final non-LLM estimator and all learned inference weights are serialized
   in exactly one checkpoint strictly smaller than 100,000,000 bytes.

A pass means only `PROMOTE_TO_RAW_IMU_ACQUISITION`.  It does not make this
metadata model submission-eligible.  A failed condition means `REJECT`; in
either case, no Kaggle submission is permitted from this run.

## Model and provenance plan

Fit an original Apache-2.0 script around scikit-learn's deterministic,
non-pretrained `ExtraTreesClassifier` with a fixed seed.  Record the input hash,
feature schema, fold metrics, dependency versions/licenses, one-checkpoint size
and hash, and every gate result in a machine-readable report.
