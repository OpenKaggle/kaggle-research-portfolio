# HAU multi-answer pairwise experiment and submission receipt

Recorded: 2026-09-09 08:03 UTC

## Offline experiment

- Model: one binary XGBoost option classifier over 955 official sensor features plus a 40-value option-text vocabulary.
- Validation: 18-fold leave-one-subject-out over 809 HAU `multi` questions; clips remain intact.
- Answer threshold: `0.45`, selected from the fixed `0.30`–`0.70` grid by exact-match accuracy, worst-subject accuracy, then closeness to `0.50`.
- Direct exact-match accuracy: `0.3337453646`; compact-graph OOF parent: `0.3114956737`.
- Predeclared overlay gate: minimum option-boundary confidence `>= 0.05`.
- Overlay exact-match accuracy: `0.3609394314`; net `+40 / 809` correct versus the compact-graph OOF proxy; worst subject `0.2380952381` versus `0.2142857143`.
- Model script SHA-256: `b2c31913983ef3b7d73c2c6bb80819977296477d68b291a3c09537d9ce4a87ac`.
- Summary SHA-256: `e6eaa4fbfbd580cc24f7a7bbad22b1e479fc232256594bab1cbfe9f2c53912b9`.
- OOF SHA-256: `1f6adee33bacf80c8b8fa678792578e229c63f6cfa1b266c135d361d569e78d8`.
- Test-prediction SHA-256: `3e69feeb5e30091bc3668f3ce5c99eaec73dfbbb363f42ea9a2b3f4bd29fc727`.
- Model artifact SHA-256: `4a9e203a3c2cba9a2e1d886bd52a095892570af2e0b71e58ee01bb29492e2ccc`.

## Candidate and official result

- Base: submission `56116980`, public score `0.78070`.
- Candidate: `multi_pairwise_conf005_union_v1.csv`, 49 new HAU multi overrides and 56 total changes versus the frozen public parent.
- Candidate SHA-256: `7200aded1502a48b32003bac78946c338a0683e3cf13210b154984ffd309dd6b`.
- Candidate builder SHA-256: `aa212e0a64f28aad344bf2525867212d9a35ff79c07e7dc8ebf59413e863dfd1`.
- Candidate report SHA-256: `50cd037afbf7319ca542c87a49e2ab6362aa8c1bbbc342b14d25854324a73ab8`.
- Official local validation: 682 rows, exact official ID order, all category grammars valid; MD5 `bb89dcb520e3b561d65342d3f6926f04`.
- Kaggle submission ref: `56117539`.
- Kaggle status: `COMPLETE`.
- Public score: `0.72807`.
- Decision: `REJECTED`; submission `56116980` remains the current private-robustness candidate.

## Postmortem and guardrail

The failure is not a schema, ordering, empty-output, or answer-grammar defect. The
compact-graph OOF proxy emitted one-letter multi answers on `93.45%` of training
rows, while the frozen test anchor emitted one-letter answers on only `40.97%` of
multi rows; the training truth was `38.57%`. The sensor overlay therefore looked
strong relative to an unrealistic OOF parent but replaced many plausibly strong
two- and three-letter test answers with one-letter predictions.

No row labels are inferred from the leaderboard result. The entire mechanism is
rejected and no confidence-threshold variants will be submitted. Future overlay
promotion requires the held-out parent proxy to reproduce the submitted parent's
structural output distribution, including answer-set cardinality.
