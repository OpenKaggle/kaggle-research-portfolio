# Stage2-native v1 network-free candidate — PASS receipt

- Terminal time: 2026-09-11T04:56:38Z (2026-09-11 12:56:38 CST)
- Decision: `PASS_DETERMINISTIC_NETWORK_FREE_CANDIDATE_BUILD`
- Builder: `scripts/build_stage2_native_candidate_v1.py` — SHA256 `21bcf764fb145f7879ccff5d512e2dc02fa5658f3133a342fd7fcc9f0eb71567`
- Network: disabled inside each independent process; socket probes blocked.
- Fixed third-party 682-row answer vector: not read.
- Qwen: rejected by its frozen gate and excluded from test predictions.

Two independent runs both produced SHA256 `40361ab2b6a87d5b73da3114aada27b982b37c09d205864ec8ed272701ae06b8` and were byte-identical. The promoted candidate has 682 unique QA IDs over 208 test clips, zero invalid predictions, and passed `scripts/validate_submission.py`.

Prediction sources are 559 owned semantic-base rows, 41 owned HARn skeleton-RF rows, and 82 owned HAU emotion ET–RF consensus rows.

The same builder also passed a network-free arbitrary-ID/clip-key smoke: six QA rows over two clips had every QA ID and clip key replaced, the identical feature values were registered under the new unit keys, and predictions remained identical by row with zero invalids. This proves ID/key independence once new-clip features are present; raw-sensor feature-extraction packaging remains a separate boundary.

- Candidate: `candidates/stage2_native_owned_v1.csv`
- Verification: `reports/stage2_native_v1_network_free_replay_verification.json`
- Submission: not attempted; this receipt does not authorize one.
