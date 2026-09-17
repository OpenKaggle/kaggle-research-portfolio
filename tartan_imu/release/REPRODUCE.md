# Offline reproduction protocol

This is a working protocol. Paths and the selected regressor hash are frozen
only after final model selection.

## Resource contract

- Internet disabled for inference.
- One GPU with at most 16 GB VRAM; CPU execution is also supported.
- Wall-clock limit: 2 hours.
- No competition labels or hidden metadata in the runtime directory.

## Required input layout

```text
challenge/
├── index/test_windows.csv
├── sample_submission.csv
└── test/<traj_id>.npz
```

Each test `.npz` must contain only released inference fields such as `imu`,
`ts`, and `fs`. The entry point rejects ID/order and non-finite output errors.

## Command

From the working repository, the current reproducibility command is:

```bash
python src/predict_frozen.py \
  --data-root /input/challenge \
  --sample /input/challenge/sample_submission.csv \
  --output /output/submission.csv \
  --work-dir /output/cache \
  --scripts-dir src \
  --official-source vendor/TartanIMU \
  --official-config config/unified.yaml \
  --model-yaml config/resnet_lstm_multihead.yaml \
  --official-checkpoint weights/unified.pt \
  --regressor weights/final_model.cbm \
  --expected-sha256 4644bb8e11df4a02417902c83b65bff5777a0e98db5bb67923f62c73bcec267a
```

The command recomputes both deterministic raw IMU features and official shared
temporal representations, then applies the single frozen unified regressor.
`--reuse-cache` exists only for local debugging and is not used for the final
cold-start timing test.

## Acceptance checks

- 30,644 output rows.
- Exact columns: `window_id,vx,vy,vz`.
- Exact ID values and order from `sample_submission.csv`.
- All velocity components finite.
- Output SHA-256 exactly equals the selected Kaggle CSV.
- Receipt records runtime, model hashes, and `platform_input_or_routing=false`.
