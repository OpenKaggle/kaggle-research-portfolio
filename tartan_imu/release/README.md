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

# TartanIMU Unified Inference Package - Frozen E003 Delivery

This directory is the frozen local release payload for selected candidate E003.
It is the public, self-contained model and inference package for Kaggle
submission `56117057`. Competition data and labels are deliberately excluded.

The system predicts three-dimensional body-frame velocity from one-second,
200 Hz, six-axis IMU windows. It applies the official unified TartanIMU
ResNet-LSTM checkpoint and one platform-agnostic CatBoost multi-output
regressor through the same inference path for every platform. It does not use
platform labels, a platform classifier, routing, specialist dispatch,
ensembling, checkpoint averaging, or test-time augmentation.

## Release contents

- `MODEL_CARD.md`: method, license provenance, limitations, metrics, compliance.
- `weights/unified.pt`: official MIT-licensed shared TartanIMU checkpoint.
- `weights/final_model.cbm`: one platform-agnostic CatBoost velocity head.
- `vendor/tartan_imu/`: exact official inference source at commit
  `fba699eb96fd3d3b0cd303695143725fd3aeb082`.
- `config/unified.yaml` and `config/resnet_lstm_multihead.yaml`.
- `src/predict_frozen.py`: the offline entry point from challenge files to the
  submission CSV.
- `requirements.txt`: pinned runtime dependencies.
- `SHA256SUMS` and `REPRODUCE.md`: integrity and no-network reproduction steps.

## Non-negotiable reproduction contract

1. One model package and one shared set of weights for all 89 trajectories.
2. Input is only the released test IMU and index/sample-submission structure.
3. No test platform label, platform classifier, hard routing, manual labels,
   specialist dispatch, ensembling, checkpoint averaging, or TTA.
4. Inference runs without internet, on one GPU with at most 16 GB VRAM and in
   at most 2 hours. A CPU fallback is retained for independent audit.
5. Output row order and IDs must exactly match `sample_submission.csv`; all
   values must be finite; output SHA-256 must match the selected Kaggle CSV.

## Current selected candidate

- E003 Kaggle ref `56117057`, public score `0.63142`.
- CSV SHA-256:
  `4644bb8e11df4a02417902c83b65bff5777a0e98db5bb67923f62c73bcec267a`.
- Final model SHA-256:
  `4cc94cf49919d0b0d2cb5eaf42f482da7192ca7e87bec24ba60f708fb89a77a6`.

The authoritative cold-start offline reproduction completed in 117.42 seconds and reproduced
the selected CSV byte-for-byte without platform input or routing.

The organizer's official full-test service reported a TartanIMU score of
`0.53485`, macro AVE `0.43938 m/s`, macro ATE20 `1.37483 m`, and macro RTE@5s
`1.79401 m`, bound to CSV MD5 `f571673079b05623e658a14410ef0063`.

See `MODEL_CARD.md` for intended use, provenance, limitations, and compliance
details, and `REPRODUCE.md` for the exact offline command.
