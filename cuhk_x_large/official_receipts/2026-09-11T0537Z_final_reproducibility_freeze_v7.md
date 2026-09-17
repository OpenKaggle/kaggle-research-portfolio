# Final reproducibility freeze v7 receipt

- Recorded UTC: `2026-09-11T05:37:10Z`
- Manifest: `reports/final_reproducibility_manifest_2026-09-11_v7.json`
- Manifest SHA-256: `c853249b4fb90a2c1bfc3991a957255ed583e1879de15201e298ba3c05862dfb`
- Independent verification: `reports/final_reproducibility_verification_2026-09-11_v7.json`
- Verification SHA-256: `39f4a2c38eed852a23b1494f003414b03f1b19ea478565239bbdf20c368c6f72`
- Decision: `PASS_ARTIFACT_FREEZE_BLOCK_OWNED_FINALIST_PACKAGE`

v7 supersedes v6 after concurrent independent audit material changed two v6-managed documents. The new freeze preserves that work instead of overwriting it: P1 metrics were independently recomputed with the same terminal rejection, and a label-blind P2 media-readiness scan was added. P2 remains proposed, not frozen, and no new VLM inference occurred.

The verifier passed 192 project artifacts, all 16 pinned local Qwen files, both selected Kaggle candidates, the unsubmitted owned Stage2 research candidate, and the 74-row/16-column experiment ledger. Selected refs remain `56122653` and `56108595`; no Kaggle submission or finalist selection changed.

The owned candidate remains `candidates/stage2_native_owned_v1.csv`, SHA-256 `40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8`, with package state `BLOCKED_RAW_INPUT_PACKAGING_INCOMPLETE`. Any new Large VLM cohort must pass the label-blind, atomic `scripts/reserve_vlm_fresh_cohort.py` gate before protocol freeze.
