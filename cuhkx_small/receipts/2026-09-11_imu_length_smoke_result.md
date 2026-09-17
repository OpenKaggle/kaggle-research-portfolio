# CUHK-X Small Track — IMU length smoke result

Run completed: 2026-09-11 12:30 CST.

## Decision

`REJECT`

The run used the gate frozen in
`2026-09-11_imu_length_smoke_preregistration.md`.  It verified the complete
subject-disjoint training and single-checkpoint engineering path, but the
organizer-published IMU row-count metadata is not an adequate activity signal.
No test data was opened, no test feature or prediction was generated, and no
Kaggle submission was made.

## Input and leakage controls

- Organizer IMU index: 2,768 clips, 18 training subjects, 40 classes.
- SHA-256: `b8899369d158c8fe6c8c20fce1bed21a8340026c541013b6c90f7cd5595b0f6b`.
- Predictors: five device row counts, deterministic count transforms, and four
  availability flags; 26 features total.
- Explicitly excluded: activity label/name, subject ID/name, clip identifier,
  paths, and the organizer's `data_type` fold indicator.
- All three folds had zero subject overlap and zero clip overlap.

## Frozen-gate results

| Fold | Model accuracy | Majority control | Gain | Macro recall |
|---|---:|---:|---:|---:|
| 0 | 0.04167 | 0.12500 | -0.08333 | 0.04363 |
| 1 | 0.03952 | 0.08862 | -0.04910 | 0.03597 |
| 2 | 0.04419 | 0.12127 | -0.07708 | 0.03656 |
| Mean | 0.04179 | 0.11163 | -0.06984 | 0.03872 |

Failed conditions:

- every-fold accuracy gain at least +0.02;
- mean accuracy gain at least +0.05;
- mean macro recall at least 0.10.

Passed engineering conditions:

- zero subject and clip overlap in every fold;
- deterministic non-LLM estimator;
- exactly one inference checkpoint;
- checkpoint strictly below 100,000,000 bytes;
- no test read and no submission.

## Checkpoint and reproducibility

- File: `artifacts/imu_length_smoke/checkpoint.joblib`.
- Size: 39,123,979 bytes.
- SHA-256: `b619fa23abbdee7f9e2142fba9703d39bb3a03fb920f24235b67f955ccc11922`.
- Contents: one fitted ExtraTrees estimator, feature schema, classes, source
  hash, and compliance metadata; no pretrained or external weights.
- A clean repeat produced a byte-identical checkpoint and report.  Loading the
  checkpoint, rebuilding its feature schema, and predicting eight training
  rows succeeded.
- The verified runtime used Python 3.13.2, scikit-learn 1.6.1, and joblib
  1.4.2. Both dependencies report BSD-3-Clause licensing in installed package
  metadata.

The checkpoint is retained only as a reproducibility artifact.  Because the
offline gate failed and the features are metadata rather than sensor signals,
it is not a submission candidate.
