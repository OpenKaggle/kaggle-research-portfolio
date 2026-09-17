# Kaggle final-selection and integrity recheck

Recorded: 2026-09-11T02:16:00Z

## Live Kaggle state

- Competition: `cuhk-x-competition-large-model-track`.
- Joined account/team visible as `Jiayi Du`; team page lists `Jiayi Du (You)` as Team Leader.
- Live deadline help text: `Tue Sep 15 2026 23:55:00 GMT+0800`, matching `2026-09-15 15:55 UTC`.
- Live submissions page reports `2/2` final selections.
- Selected entries remain:
  - `emotion_extratrees_rf_union_v1.csv` / submission `56122653`, public `0.78070`.
  - `nonvisual_sensor_union_v1.csv` / submission `56108595`, public `0.78070`.
- Other rows continue to expose the `select <filename>` action and are not selected.
- Kaggle CLI independently reports both selected submissions `COMPLETE` at public `0.78070`; no new submission exists.
- No UI state was changed during this read-only audit.

## Local integrity state

- Read-only verification of v3 manifest SHA-256 `f7d268a218c43234ccf424b3d70b4806f6d3bc6f551d592ecd979b7fd8e5aa4c`: PASS.
- Exact artifact size/hash checks: 101/101.
- Pinned Qwen model file checks: 16/16.
- Frozen selected candidate hashes: 2/2.

External organizer registration remains the only incomplete competition-closing action and still requires user-supplied real identity/contact fields and agreement to the organizer terms.
