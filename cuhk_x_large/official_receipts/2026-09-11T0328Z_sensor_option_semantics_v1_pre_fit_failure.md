# Sensor-option semantics v1 pre-fit failure

Recorded: 2026-09-11T03:28:56Z

- The first result-script launch stopped before any model fit, prediction, or metric calculation.
- Exact exception: `AssertionError: Frozen IMU motion-column width changed`.
- Cause: the frozen selector contains 305 IMU sensor columns; 359 is the later expanded width after concatenating 54 option one-hot columns.
- No `artifacts/oof/sensor_option_semantics_v1_oof.csv` or `reports/sensor_option_semantics_v1_validation.json` existed after the failure.
- No test data were read. No test prediction, candidate CSV, or Kaggle submission was created.
- Frozen gate, task slice, parent, model family, hyperparameters, subject halves, environment-proxy bins, and counterfactual audits are unchanged.
- Failed source SHA-256: `f8de2af2b222f15c59d00fa175b753cf07b4fc53b09fb408dda049cfbc67f653`.
- Pre-amendment protocol SHA-256: `698da1612003afb2c912aa55eb06c211d508e8604f1a31d86b225e68583770d9`.

Decision: `SAFE_TO_RETRY_AFTER_NON_RESULT_WIDTH_CORRECTION`.
