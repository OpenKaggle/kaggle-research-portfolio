# Sensor-option semantics v1 rejection

Recorded: 2026-09-11T03:52:32Z

Decision: `REJECT_NO_TEST_NO_SUBMISSION`.

## Frozen scope and containment

- Read the 2026-09-11 CUHK series research/sprint plan before the result-bearing run.
- Used HAU emotion only, 809 unique QA/clips, all 18 released training subjects, one subject held out per fold, and zero fit/validation clip overlap in every fold.
- Fit separate ExtraTrees option-rankers for IMU, radar, and skeleton; no early feature fusion. A row changed only under all-modality presence and a 2-of-3 semantic vote.
- The comparison parent was the owned `nonvisual_sensor_oof.csv` prediction on HAU/emotion. Its imported `parent_prediction` field and the unknown-lineage 0.77777 vector were excluded.
- Fresh20/VLM artifacts were not read as inputs or reused as evidence.

## Frozen-gate result

- Disagreements: `270` (gate `>=30`: PASS).
- Candidate on disagreements: `101/270 = 0.374074` (gate `>=0.60`: FAIL).
- Owned parent on disagreements: `87/270 = 0.322222` (gate `<=0.40`: PASS).
- First subject half: candidate `54/134`, parent `39/134`, net `+15` (PASS).
- Second subject half: candidate `47/136`, parent `48/136`, net `-1` (FAIL).
- Recording-condition proxies: prefix 1–2 net `-1`, prefix 3–5 net `+7`, prefix 6–7 net `+8`.
- Invalid predictions: `0` (PASS).
- All 24 option permutations on all 809 rows: `19,416` semantic checks, `0` mismatches (PASS).
- Frozen synonym rewrites: `809` semantic checks, `0` mismatches (PASS).

The candidate has a small overall net improvement (`+14/809`) but fails by a wide margin on the primary disagreement-accuracy threshold and is negative in the second fixed subject half. No post-hoc confidence cut, subject selection, environment selection, or modality subset is permitted.

## Reproduction and artifact integrity

- Protocol SHA-256: `1b7772d1893ec46e30c793a9d0f8396b21c8c23483ee1348739caada58ba8757`.
- Source SHA-256: `d2363bb5c50a634be96ea7929ebc3f574244a59e7dc46c32993142913e2b15d2`.
- Final OOF SHA-256: `effe571266b15dba48e75e8dde512e0a7c1dc3ba46ecff415e31f3a4907e14a1`.
- Final validation report SHA-256: `d2f811f95f25996425d70c3329d75457a0717e6d217775fa53fc0f86643674bd`.
- Two complete replays agree exactly on QA order, every prediction, consensus/disagreement/correctness field, every aggregate metric, and the rejection decision. Only margin columns differ by at most `3.89e-16`, with no decision impact.

No test QA was read; no test prediction, candidate CSV, Kaggle submission, or leaderboard probe was produced.
