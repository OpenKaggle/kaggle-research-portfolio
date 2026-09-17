# HAU linked-question/sensor submission and final-selection receipt

Recorded: 2026-09-09T12:16:03Z

## Method and validation

- Target: HAU `single` questions.
- Label-free structural rule: use the compact-graph prediction for the same clip's `combination` question as an action set, then select the unique single-question option contained in that set.
- Deployment gate: the unique structural inference and the independent sensor model must agree, real sensor input must be present, and both must differ from the frozen target parent prediction.
- Ground-truth-source logical upper bound: `633/633 = 1.00000`, all 18 subjects, worst-subject accuracy `1.00000`.
- Deployed compact-graph OOF structural inference: `601/620 = 0.96935`, all 18 subjects, worst-subject accuracy `0.88000`.
- Structural disagreements versus target parent: `25/30` expert correct versus `5/30` parent correct, net `+20`.
- Sensor-confirmed disagreement gate: `8/8` expert correct versus `0/8` parent correct, net `+8`, seven represented subjects, worst represented-subject net `+1`.
- Fixed parity cohorts: odd subject IDs `4/4`, even subject IDs `4/4`, each net `+4`.
- One-sided exact sign-test p-value: `0.00390625`.
- Prediction-structure transport: OOF combination `790/790` and single `809/809` are one-letter predictions; official test combination `139/139` and single `144/144` are also one-letter predictions.

## Candidate

- Base submission: `56116980`.
- Candidate: `hau_linked_single_consensus_v1.csv`.
- Only new row: `test_0050`, A -> B.
- Test evidence: linked combination row `test_0272` predicts option D, whose action set is `Checking body temperature, Getting dressed`; only single option B belongs to that set; the independent sensor model also predicts B with real input present.
- Rows/order/category grammar: PASS, 682/682.
- Candidate SHA-256: `cec3cde9c7b207c4e202a2623f88213bedccedebc108dd2afcb00782bb101106`.
- Candidate MD5: `e57d51cdad9255b45726cb873d644790`.
- Code SHA-256: `4c2aa998d38a0a7fef19f4d2f8dcdaab7b2d8fb6cbc2c964e2c5dfb081c16a56`.
- Report SHA-256: `c03169a8c47e3f61c1bac466a5efa924c75cd606f7496584e3e3cceaa0c53091`.

## Kaggle submission

- Submission ref: `56122175`.
- Submitted: `2026-09-09 12:11:16.720000 UTC`.
- Status: COMPLETE.
- Public score: `0.78070`.
- The tie with the prior best is treated as non-diagnostic; it is not used to infer whether `test_0050` belongs to the public split or what its hidden label is. No row-level follow-up probe is permitted.

## Final candidates

The Kaggle submissions page was explicitly updated to 2/2 selections:

1. `56122175` — linked-question/sensor enhancement, public `0.78070`.
2. `56108595` — independent nonvisual sensor union, public `0.78070`.

The previous `56116980` selection was removed. A fresh page reload showed `2/2`, with `hau_linked_single_consensus_v1.csv` and `nonvisual_sensor_union_v1.csv` checked, proving that the new selection persisted.
