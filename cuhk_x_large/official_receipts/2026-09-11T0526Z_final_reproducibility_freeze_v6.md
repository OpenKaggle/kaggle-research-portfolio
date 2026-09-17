# Final reproducibility freeze v6 receipt

- Recorded UTC: `2026-09-11T05:26:10Z`
- Manifest: `reports/final_reproducibility_manifest_2026-09-11_v6.json`
- Manifest SHA-256: `2c25c50a34e8c59581ec3ff01427701e990f2f70b0077c6d7b0f5858288ed386`
- Independent verification: `reports/final_reproducibility_verification_2026-09-11_v6.json`
- Verification SHA-256: `9c8f3eaea84e539a87f7ed37bf6ece726676ca7ba2667bfb1eed037b845526ee`
- Decision: `PASS_ARTIFACT_FREEZE_BLOCK_OWNED_FINALIST_PACKAGE`

The verifier passed 182 project artifacts, all 16 pinned local Qwen files, both selected Kaggle candidates, the unsubmitted owned Stage2 research candidate, and the 71-row/16-column experiment ledger. Selected refs remain `56122653` and `56108595`; no Kaggle submission or finalist selection was changed.

The owned candidate remains `candidates/stage2_native_owned_v1.csv`, SHA-256 `40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8`. v6 does not mark it finalist-ready: the current package lacks an offline raw-organizer-input sensor-to-feature path and the current `inference.sh` does not call the owned builder.

P1 remains terminally rejected. Its completed screen failed the scientific invalid-output gate and cannot satisfy the newer pre-freeze atomic reservation/minimum-frame controls retroactively. Future Large VLM cohorts must pass `scripts/reserve_vlm_fresh_cohort.py` before protocol freeze.
