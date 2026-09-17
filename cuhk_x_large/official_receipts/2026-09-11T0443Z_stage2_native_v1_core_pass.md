# Stage2-native v1 core — PASS receipt

- Terminal time: 2026-09-11T04:43:57Z (2026-09-11 12:43:57 CST)
- Decision: `PASS_CORE_ALLOW_NETWORK_FREE_TEST_BUILD`
- Scope: all 4,087 official training QA rows, 1,333 intact clips, 18 subject-disjoint LOSO folds.
- Test QA read: no.
- Test predictions/candidate/submission: none.
- Fixed third-party 682-row answer vector: not read.

Frozen-gate evidence:

- Stage2-native accuracy: 0.621972 (2,542/4,087).
- Owned semantic base accuracy: 0.563249 (2,302/4,087).
- Net gain: +240 rows / +5.8723 percentage points.
- Subject halves: +127 and +113; worst individual subject net gain: +4.
- HARn/single accuracy: 0.785548.
- HAU/emotion ET–RF consensus disagreement slice: 117/186 = 0.629032 versus base 26/186 = 0.139785; net +91.
- Prediction grammar invalids: 0.
- Option-permutation counterfactual: 24 permutations, 98,088 row checks, 0 mismatches.

Artifacts:

- `reports/stage2_native_v1_preregistered_protocol.json` — SHA256 `5c521089d3b327e6d6374f7baf552e2b5e22f733bff3f3bdeac493df60dc9b70`
- `reports/stage2_native_v1_oof_validation.json` — SHA256 `2f3caffe9e4aec49cd38ee722b1e3c403e6e009527703fbc1358cfd919bf5288`
- `artifacts/oof/stage2_native_v1_oof.csv` — SHA256 `8cf9879a1e147456db67dffe3246bb108e2816170dc787347ce24e93a8f7d1b7`
- `scripts/run_stage2_native_oof_v1.py` — SHA256 `156072ebdfeec071863f726944f2afc1ded4fa0b375cea3af3fbac3a829de7f2`

This receipt authorizes only a separate network-free test build and deterministic replay. It does not authorize a Kaggle submission.
