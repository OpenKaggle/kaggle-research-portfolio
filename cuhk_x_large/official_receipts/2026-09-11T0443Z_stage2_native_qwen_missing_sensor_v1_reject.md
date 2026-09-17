# Stage2-native Qwen missing-sensor fallback — REJECT receipt

- Terminal time: 2026-09-11T04:43:57Z (2026-09-11 12:43:57 CST)
- Decision: `REJECT_KEEP_QWEN_DIAGNOSTIC_ONLY`
- Cohort: every HARn/single training row whose frozen skeleton feature row was numerically absent; 40 QA rows / 40 clips.
- Selection used labels or historical VLM predictions: no.
- Network: disabled before local model import/load; socket probe blocked.
- Test QA read: no.
- Test predictions/candidate/submission: none.

Frozen-gate evidence:

- Overall Qwen accuracy: 18/40 = 0.450000; required at least 0.600000 — FAIL.
- Valid outputs: 39/40 = 0.975000; required 1.000000 — FAIL.
- Subject halves: 5/14 = 0.357143 and 13/26 = 0.500000; both required at least 0.500000 — FAIL.
- Owned semantic base: 10/40 = 0.250000; Qwen net +8, so the non-decrease check alone passed.
- Historically unobserved subset: 11/29 = 0.379310; previously observed subset: 7/11 = 0.636364. This split is diagnostic only and did not alter the frozen all-row decision.

Artifacts:

- `reports/stage2_native_qwen_missing_sensor_v1_protocol.json` — SHA256 `201f85ed09a8ac3d49d0361cb6cf98a0523b4fc76bc9b3615da0cbfb34b2ce23`
- `artifacts/manifests/stage2_native_qwen_missing_sensor_v1.csv` — SHA256 `85e178c7d33134ffc2e2093267d72986e6f8dda3836cc3f0571d5a3c17f35245`
- `reports/stage2_native_qwen_missing_sensor_v1_validation.json` — SHA256 `4d093c43141963a4be9c19db35cdc11bef0251cacd0ed475f3b93435da0cae18`
- `artifacts/vlm/stage2_native_qwen_missing_sensor_v1.jsonl` — SHA256 `892fa26e92000104b30761ae577da85d5425c48b20eb90c3a0a4f79df7d1d1a4`
- `reports/vlm_exposure_registry.jsonl` — all 40 QA/clip pairs are registered as ineligible for future fresh evidence.

The Qwen branch is diagnostic-only. Deployment retains the semantic-base fallback on missing-sensor HARn/single rows; no invalid output is repaired manually.
