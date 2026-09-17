# Sensor-option semantics v1 pre-result runtime abort

Recorded: 2026-09-11T03:33:53Z

- The corrected retry passed immutable-input checks and began LOSO fitting.
- It was manually interrupted while fitting the second subject fold, before all folds, aggregation, or any artifact write.
- No aggregate accuracy, disagreement, half-cohort, environment, or promotion metric was observed.
- No `artifacts/oof/sensor_option_semantics_v1_oof.csv` or `reports/sensor_option_semantics_v1_validation.json` existed after interruption.
- No test data were read. No test prediction, candidate CSV, or Kaggle submission was created.
- The implementation had redundantly invoked the same independent option scorer for every permutation. Because each option is scored independently, an A/B/C/D permutation is exactly a column reindex of the four scores already computed for that row.
- The replacement performs all 24 exhaustive permutations by that exact reindex. Model, features, fitted scores, tie-break, task slice, gate, hyperparameters, subject halves, and environment-proxy bins are unchanged.
- Interrupted source SHA-256: `9a52e1fc783cf1112efe8707d91f2a66817d1541861d2f4c143ce5ed13430e7c`.
- Pre-amendment protocol SHA-256: `12bc209945b96fb5ad4a8bfd866da0594f3896b409bba269963945449c4fefe5`.

Decision: `SAFE_TO_RETRY_AFTER_EXACT_RUNTIME_OPTIMIZATION`.
