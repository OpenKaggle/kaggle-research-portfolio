# Sensor-option semantics v1 report-literal failure

Recorded: 2026-09-11T03:48:01Z

- The deterministic run completed all 18 LOSO folds and counterfactual calculations, then failed while constructing the final Python report dictionary.
- Exact exception: `NameError: name 'false' is not defined`.
- Cause: five JSON-style boolean literals (`false`/`true`) appeared in Python report metadata; they must be `False`/`True`.
- A partial OOF was already written at the frozen path. Its SHA-256 is `302e68902a0ebd776fc2882fcb90957832b88a27bba941256ab88fef5bb66ae3`.
- No aggregate performance or gate metric was printed or inspected before the fix.
- No validation JSON, test prediction, candidate CSV, or Kaggle submission was created.
- The repair changes only those five metadata literals. Model, data, folds, features, predictions, audits, thresholds, and promotion gate are unchanged.
- Failed source SHA-256: `61033f2c65c43115e370956f6e9d7f530e03e2e876a888c50f2f51729ccb1da5`.
- Pre-amendment protocol SHA-256: `1ab0f05df5fe2508a70a22858989ec4ece9291fa7a6e0275d4c3576716909972`.

Decision: `SAFE_TO_RETRY_AFTER_REPORT_METADATA_LITERAL_FIX`.
