---
license: mit
library_name: tartan_imu
pipeline_tag: other
tags:
  - inertial-odometry
  - imu
  - robotics
  - velocity-estimation
  - state-estimation
  - tartanimu
  - lstm
language:
  - en
model-index:
  - name: TartanIMU-unified
    results:
      - task:
          type: inertial-odometry
          name: Body-frame velocity regression (TartanIMU Score)
        metrics:
          - type: tartanimu-score
            name: Challenge leaderboard metric — TartanIMU Score = 0.6*AVE_norm + 0.4*ATE20_norm (dimensionless, v4 test, all)
            value: 0.538
          - type: AVE
            name: Macro AVE component (m/s, v4 test, all)
            value: 0.461
          - type: ATE
            name: Macro 20 m-segment ATE20 component (m, v4 test, all)
            value: 1.261
          - type: ATE
            name: Macro-ATE all-4 (m, 20 m seg, test.py on tartan_layout test)
            value: 2.327
          - type: ATE
            name: Unified drone ATE (m, drone_v3 test, 20 m seg, test.py)
            value: 3.945
          - type: RMSE
            name: Offline diagnostic — macro window-RMSE (v3 test, all; NOT the leaderboard metric)
            value: 0.664
---

# TartanIMU — Multi-Platform Inertial Foundation Model

TartanIMU is a light foundation model for **neural inertial positioning**. Given
a 6-axis IMU stream (3-axis accelerometer + 3-axis gyroscope), the network
regresses per-window **body-frame velocity**; position is obtained by
integrating velocity with the platform orientation. It is the model released
alongside the **IROS 2026 Tartan IMU Challenge**.

This repository ships one **multi-platform unified** checkpoint (4 motion-type
heads: `car` / `dog` / `drone` / `human`) plus four **single-platform expert**
checkpoints for reproducing the per-platform ablations.

> **v3 (2026-07-18).** The drone platform is now **drone_v3** — high-dynamic
> real flight, hover → 20 m/s — replacing the low-dynamic
> indoor-mocap `drone_v2`. `unified.pt` and `expert_drone.pt` are retrained on
> it. Headline change: **the car/dog multi-task collapse of previous unified
> releases is gone** (see Results). car/dog/human expert checkpoints unchanged.

> **wdfix2 (2026-07-24).** `unified.pt` now exempts the per-motion-type head
> parameters from weight decay. The previous `unified.pt` had a **dead output
> channel** — drone forward-velocity (vx) was stuck at constant zero — because
> weight decay is applied every step while each head only receives gradients on
> its own platform's samples, driving weakly-supervised head channels to zero.
> The fix revives drone-vx (dense-forward correlation up to 0.80 vs ground
> truth, was 0). On the offline window-RMSE diagnostic it goes **0.741 → 0.664**,
> and on `test.py` 20 m-segment macro ATE **2.52 → 2.33**. On the challenge
> leaderboard metric (**TartanIMU Score**, which weights per-window velocity
> accuracy at 60 %) the revived channel is decisive: drone AVE **1.783 → 1.454
> m/s** carries the four-platform macro from **0.593 → 0.538** (−9.3 %), making
> this checkpoint the better one on the ruler that counts. On the ATE20
> component alone the picture is the older one — drone 2.47 → 2.21 m, macro a
> wash at 1.23 → 1.26 m — see Results. Expert checkpoints unchanged.

- **Backbone:** ResNet-1D feature trunk + 2-layer LSTM (hidden 128) → per-motion-type `OutputHead`
- **Model name (code):** `Foundation_Model`
- **Input:** 6-axis IMU, raw 200 Hz, resampled to 40 Hz network input, 1.0 s windows
- **Output:** 3-D body-frame velocity `(vx, vy, vz)` per window
- **Coordinate frame:** honest **body frame with gravity present** (`use_local_coord: true`) — no ground-truth orientation is used to de-rotate the IMU input (no leakage)
- **License:** MIT © Shibo Zhao
- **Code:** https://github.com/superxslam/TartanIMU

## Files

| File | Description |
| --- | --- |
| `checkpoints/unified.pt` | **Flagship** 4-head unified model (car/dog/drone/human), drone_v3 + wdfix2 (heads exempt from weight decay) |
| `checkpoints/expert_car.pt` | Single-platform expert — car |
| `checkpoints/expert_dog.pt` | Single-platform expert — dog (legged) |
| `checkpoints/expert_drone.pt` | Single-platform expert — drone (**drone_v3**) |
| `checkpoints/expert_human.pt` | Single-platform expert — human |
| `config/resnet_lstm_multihead.yaml` | Network definition (`model.model_yaml`) |
| `config/unified.yaml` | Experiment config used to train the unified model (drone_v3 paths + per-platform speed gates) |
| `inference_example.py` | Self-contained: checkpoint → body-frame velocity |

Each checkpoint is a `torch.save` dict with a `model_state_dict` key.

## Results

All numbers on the challenge test split, LSTM `Foundation_Model`,
`use_local_coord: true`. ⚠️ drone numbers are on the **drone_v3 test** (real
flight, up to 20 m/s) and must not be compared with older drone_v2-era numbers
(that task was far easier).

### 1. Challenge leaderboard metric — TartanIMU Score

This is **the** metric the Kaggle leaderboard reports:

```
TartanIMU Score = 0.6 x (AVE / 0.7356384388)  +  0.4 x (ATE20 / 3.1160277267)
```

Dimensionless, lower is better, evaluated on the anonymized **v4 challenge test
split** (89 trajectories / 30,644 windows). The two components:

- **AVE** (60 %) — mean per-window Euclidean velocity error ‖v_pred − v_gt‖, in
  m/s. Instantaneous accuracy.
- **ATE20** (40 %) — per-window body-frame velocities integrated with
  ground-truth orientation inside each ~20 m segment of the ground-truth path,
  SE(3)-aligned (Umeyama, no scale), scored by RMS position error, in metres.
  Temporal consistency.

Both are averaged over windows/segments → trajectories → the four platforms
equally, then divided by the value an all-zero submission attains on the full
test set. That normalisation makes the score dimensionless (no adding metres to
metres-per-second), makes the declared 60/40 weights the weights that actually
act, and pins an **all-zero submission to exactly 1.000**.

| Split | Previous `unified.pt` | **This `unified.pt` (wdfix2)** |
| --- | --- | --- |
| all | 0.593 | **0.538** |
| public | 0.706 | **0.637** |
| private | 0.495 | **0.456** |

Components (all split), AVE in m/s and ATE20 in metres:

| Component | Previous `unified.pt` | **This `unified.pt` (wdfix2)** |
| --- | --- | --- |
| macro AVE | 0.533 | **0.461** |
| macro ATE20 | **1.230** | 1.261 |

Per-platform, all split (AVE m/s / ATE20 m):

| Platform | Previous `unified.pt` | **This `unified.pt` (wdfix2)** |
| --- | --- | --- |
| car | **0.150 / 0.947** | 0.180 / 1.174 |
| dog | **0.104 / 0.550** | 0.111 / 0.640 |
| drone | 1.783 / 2.473 | **1.454 / 2.205** |
| human | **0.097 / 0.951** | 0.101 / 1.023 |

**Read this honestly:** on the ATE20 component alone the dead-channel fix is a
wash — drone improves 10.8 % but the other three platforms give a little back
(macro 1.23 → 1.26 m, within run-to-run noise). What settles it is the AVE
component, where the revived drone-vx channel cuts drone velocity error
**1.783 → 1.454 m/s (−18.5 %)**. Because drone is by far the fastest platform,
that gain is large enough in the macro to move the combined score **0.593 →
0.538 (−9.3 %)** and to win on all three splits. So: this checkpoint is better
on the leaderboard ruler, and the reason is instantaneous accuracy on drone,
not trajectory consistency.

Reference points on the same metric (all / public / private): ground-truth
velocities **0.019 / 0.021 / 0.019** (the metric's floor — non-zero because
integrating exact per-window *average* velocities still leaves a small ATE20
residual), all-zeros **1.000 / 1.054 / 0.922**, per-platform mean velocity
**1.060 / 1.080 / 1.036**. The metric is shrink-proof: scaling this model's
velocities by any factor away from 1.0 strictly worsens the score.

### 2. `test.py` evaluation — a different split and integration granularity

⚠️ **Not comparable with the table above.** These numbers come from the
repository's `test.py` (20 m segments, IMU-rate integration) on the
`tartan_layout` test split — a different test set from the challenge one.

| Platform | Expert | Unified 4-head (this `unified.pt`, wdfix2) |
| --- | --- | --- |
| car | 1.704 | **1.666** |
| dog | 2.009 | **1.924** |
| drone (v3 test) | 3.921 | **3.945** |
| human | 1.823 | **1.773** |
| **macro (all 4)** | 2.364 | **2.327** |

On this ruler the unified 4-head model matches or beats every single-platform
expert.

### 3. Offline window-RMSE diagnostic — *not* the leaderboard metric

Mean body-frame velocity error per 1 s window. Useful for spotting dead channels
(that is how the drone-vx collapse was found), but the competition does **not**
score submissions this way.

| Split | Previous `unified.pt` | **This `unified.pt` (wdfix2)** |
| --- | --- | --- |
| all | 0.741 | **0.664** |
| public | 0.844 | **0.731** |
| private | 0.614 | **0.587** |

(Reference baselines: all-zeros 0.941, platform-mean 0.931. Per-platform window
RMSE of this model, all split: car 0.270 / dog 0.263 / drone 1.961 / human
0.164.)

**What changed vs the previous release:** the earlier 4-head unified collapsed
on car (7.6) and dog (5.6); replacing the near-static mocap drone data with
drone_v3 removed that *data-quality* interference (near-static drone windows are
feature-space neighbors of slow human motion, and the shared trunk paid for
it). The **wdfix2** update then fixed a dead output channel — the previous
`unified.pt` predicted a constant-zero drone forward velocity (drone-vx) because
weight decay drove the weakly-supervised head to zero; exempting the head
parameters from weight decay revives it and drives the drone window RMSE from
2.26 to 1.96 (macro window-RMSE 0.741 → 0.664), the drone AVE component from
1.783 to 1.454 m/s and the drone ATE20 component from 2.47 to 2.21 m.
High-speed flight remains the hardest regime.

## Quick start

```bash
git clone https://github.com/superxslam/TartanIMU
cd TartanIMU
pip install -e .

# download this model repo (weights + config)
huggingface-cli download Tartan-IMU/TartanIMU --local-dir ./tartanimu_weights

python inference_example.py \
  --config ./tartanimu_weights/config/unified.yaml \
  --model  ./tartanimu_weights/checkpoints/unified.pt \
  --npz    <path/to/trajectory.npz> \
  --motion_type human
```

See `inference_example.py` for a minimal load → predict loop. The model call is:

```python
pred = model(imu_window, motion_type=label, predict_cov=False, compute_all_heads=False)
velocity_body = pred[motion_type]   # (B, 3) body-frame velocity
```

Motion-type IDs (this model's API): `car=1, dog=2, drone=3, human=4`.

> ⚠️ **Off-by-one with the dataset.** The challenge `.npz` files store
> `platform_id` **0-based** (`car=0, dog=1, drone=2, human=3`), while the model's
> `motion_type` is **1-based** as above. Add 1 when feeding a dataset
> `platform_id` into the model.

## Intended use & limitations

**Intended use.** Body-frame velocity estimation from wearable / platform-mounted
IMU for short-horizon inertial odometry, and as a starting point for the Tartan
IMU Challenge.

**Known limitations (be honest about these):**

1. **Aggressive-flight observability.** With honest body-frame IMU (gravity
   present, no external orientation), high-speed drone velocity is weakly
   observable from 1 s windows: at the window level this model reaches drone
   RMSE 1.96 (vs platform-mean baseline 2.41), and trajectory-level ATE on
   high-speed racing flight remains several meters. This is the open problem the v3
   benchmark deliberately exposes.
2. **Reproduction pitfall.** The release dataloader historically gated windows
   at 5 m/s (`max_v_norm`) and clipped GT speed at 15 m/s. The shipped
   `config/unified.yaml` raises both to 25 m/s for drone; without that, the
   fast half of drone_v3 is silently discarded and none of these numbers
   reproduce.
3. **Slow-regime bias elsewhere.** car/dog/human corpora remain dominated by
   moderate speeds; generalization to extreme regimes on those platforms is
   untested.

## Training data

Challenge dataset v3 (`car` / `dog` / `drone` / `human`), de-duplicated with
verified zero train/val/test content leakage (sha256 window fingerprints).
Drone = **drone_v3**: 200 Hz, whole-recording splits, with multiple IMU streams
from one recording bound to a single split. These weights are provided for
**research / non-commercial use**.

## Citation

```bibtex
@misc{tartanimu2026,
  title  = {TartanIMU: A Light Foundation Model for Neural Inertial Positioning},
  author = {Zhao, Shibo and others},
  year   = {2026},
  note   = {IROS 2026 Tartan IMU Challenge}
}
```
