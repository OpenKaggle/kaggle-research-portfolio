# HAU emotion ExtraTrees/RF submission and final-selection receipt

Recorded: 2026-09-09T12:36:00Z

## Independent model

- Task: HAU emotion option ranking.
- Model: fold-local median imputation followed by `ExtraTreesClassifier` with 500 trees, `max_features=sqrt`, `min_samples_leaf=2`, balanced class weights, seed `20260909`.
- Features: 305 official IMU motion statistics plus 54 normalized option indicators; 359 total.
- Validation: 18-fold leave-one-subject-out with clips intact.
- Training rows: 809; real sensor input on 789. Missing-sensor rows remain diagnostic only and are excluded from ExtraTrees candidate gates.
- ExtraTrees OOF accuracy: `403/809 = 0.49815`; sensor-present accuracy `0.50444`; worst-subject accuracy `0.38889`.
- Comparison: existing XGBoost `0.46477`; existing RF `0.44870`; public compact-graph OOF parent `0.32015`.

## ET/RF consensus gate

- Requirements: real ET sensor input; ExtraTrees prediction equals independent RandomForest prediction; prediction differs from the OOF compact-graph parent.
- Selected validation rows: 186.
- Expert correct: 117 (`0.62903`).
- Parent correct: 26 (`0.13978`).
- Net correct: `+91`.
- Subject coverage: 18/18; every subject net positive; worst subject net `+1`.
- Fixed odd-subject cohort: 93 rows, expert 54 correct, parent 16 correct, net `+38`.
- Fixed even-subject cohort: 93 rows, expert 63 correct, parent 10 correct, net `+53`.
- One-sided exact sign-test p-value: `2.7593188069240852e-15`.

## Test gate and candidate

- Test additionally requires the ET/RF consensus to differ from both the frozen released parent and the separately reproduced public compact graph.
- Six test rows satisfy the gate. Two (`test_0428`, `test_0455`) already exist in the base submission.
- Four new rows versus submission `56122175`:
  - `test_0444`: A -> B
  - `test_0456`: C -> A
  - `test_0464`: A -> B
  - `test_0653`: D -> B
- Candidate: `emotion_extratrees_rf_union_v1.csv`.
- Rows/order/category grammar: PASS, 682/682.
- Candidate SHA-256: `3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4`.
- Candidate MD5: `63c7247a8d967889c167ed0c12e618d7`.

## Reproducibility

- ExtraTrees script SHA-256: `9774e19a2697b318f6d2a07b1afa653ad2438ce1356cf74b7df0f007f09777d9`.
- ExtraTrees report SHA-256: `8e2ba657786423585545e94ba4bbc0cfd4df3d81fe23dcda4529527901789d31`.
- ExtraTrees OOF SHA-256: `c89c06f082d3214331ab39f8b14bb922899769b1ad7108b6b25ceaab298e8259`.
- ExtraTrees test predictions SHA-256: `2874b93d6adb0806c6f98574440a834feb2f05bb7f7885cf472506b3668e0ebb`.
- ExtraTrees model SHA-256: `4af817095c602500db2ad6a8a7637ded103de7fbae5a24cdc3765dcf7dc81a42`.
- Candidate builder SHA-256: `f0b4bbb600becf652fbc039fd3d80e8ed84077a2a4a2b7bbde629cf51ea1d2d9`.
- Candidate report SHA-256: `755c4362e844f25083e94c38be2e69148f7b108902a3e82c881005937f24c090`.

## Kaggle submission

- Submission ref: `56122653`.
- Submitted: `2026-09-09 12:32:52.593000 UTC`.
- Status: COMPLETE.
- Public score: `0.78070`.
- This was the fifth and final 2026-09-09 submission. The tie is non-diagnostic and is not used to infer any row's split membership or hidden label; no follow-up row probes are permitted.

## Final candidates

The Kaggle page was explicitly changed to 2/2 selections:

1. `56122653` — ET/RF emotion union over the linked/visual/sensor base, public `0.78070`.
2. `56108595` — independent nonvisual sensor union, public `0.78070`.

The previous `56122175` selection was removed. A fresh page reload reported `2/2`, `56122653` checked, `56108595` checked, and `56122175` unchecked, proving persistence.
