---
license: cc-by-nc-sa-4.0
library_name: catboost
pipeline_tag: tabular-regression
tags:
  - inertial-odometry
  - imu
  - tartanimu
  - iros-2026
base_model: Tartan-IMU/TartanIMU
---

# Unified TartanIMU Stacked Regressor

Frozen public model card for selected candidate E003.

## Model description

The system predicts three-dimensional body-frame velocity from one-second,
200 Hz, six-axis IMU windows. It consists of the official unified TartanIMU
ResNet–LSTM checkpoint and one platform-agnostic CatBoost multi-output
regressor. The regressor consumes deterministic IMU/context features, the
shared 128-dimensional temporal representation, and all four continuous output
vectors produced by the unified checkpoint simultaneously.

There is no platform-label input, platform classifier, hard routing, specialist
dispatch, ensembling, checkpoint averaging, or test-time augmentation.

## Intended use

- Reproduce the team's TartanIMU Challenge submission offline.
- Non-commercial academic research in inertial odometry.

Do not use the model for safety-critical navigation without independent
validation. The source competition data is CC BY-NC-SA 4.0 and the derived
regression weights are distributed under the same non-commercial share-alike
terms. The upstream `Tartan-IMU/TartanIMU` checkpoint and code retain their MIT
license and attribution.

## Inputs and outputs

- Input: released challenge trajectory `.npz` files containing `imu` with
  `[ax, ay, az, gx, gy, gz]`, plus `index/test_windows.csv`.
- Output: `window_id,vx,vy,vz`, exactly one row per released test window.
- Test pose, orientation, velocity, and platform identity are neither required
  nor accepted by the inference entry point.

## Current results

| Candidate | Validation score | Public score | Kaggle ref |
|---|---:|---:|---:|
| E002 fallback | 0.42560 | 0.63718 | 56115700 |
| E003 selected | 0.41305 | 0.63142 | 56117057 |

Lower is better. Validation uses the official trajectory-disjoint validation
split and exact released organizer metric. Public score is provisional; final
ranking requires organizer re-execution and a technical report.

The organizer's official full-test scoring service reported **0.53485** for
E003 (macro AVE **0.43938 m/s**, macro ATE20 **1.37483 m**, macro RTE@5s
**1.79401 m**), bound to submission MD5
`f571673079b05623e658a14410ef0063`. Per-sequence official-test results are
kept outside this public release and are not used for model selection.

## Reproducibility

- Dataset archive SHA-256:
  `ca8d6c15894064e2a4db25d1f01f6c3db7f51454eea0b52afa81d835aa394d8d`
- Upstream source commit:
  `fba699eb96fd3d3b0cd303695143725fd3aeb082`
- Official unified checkpoint SHA-256:
  `ca8cc3e15a42ec91c0cda4c63ade1b068ea92039469104b40ea63f18130e97f4`
- Selected regression model SHA-256:
  `4cc94cf49919d0b0d2cb5eaf42f482da7192ca7e87bec24ba60f708fb89a77a6`.
- Expected CSV SHA-256:
  `4644bb8e11df4a02417902c83b65bff5777a0e98db5bb67923f62c73bcec267a`.

See `REPRODUCE.md`. A cold offline run reproduced the exact expected CSV in
117.42 seconds with 723,648,512 bytes maximum resident memory, below the 16 GB
and two-hour limits.

## Limitations

- High-dynamic drone motion is the dominant residual error regime.
- E001 demonstrated substantial validation-to-public distribution shift, so
  small validation gains are not sufficient evidence for additional uploads.
- The upstream backbone was released by the organizers and is not trained from
  scratch in this work.

## Compliance

The final package contains one shared backbone and one unified regression head.
It does not infer a platform category or route a trajectory to a specialist.
All model selection uses only released train/validation data; leaderboard
results are recorded for confirmation, not converted into test labels or used
for per-trajectory decisions.
