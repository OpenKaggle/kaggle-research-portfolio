# Playground Series S6E9 campaign

Predict `Will_Buy_EV` with ROC AUC. The first baseline uses only the official competition files, excludes the sequential `id` field, and evaluates CatBoost, LightGBM, XGBoost, their probability mean, and their rank mean under shuffled stratified out-of-fold validation.

## Hard gates

1. Exact official schema, row count, ID order, finite probabilities, and SHA-256 receipts.
2. No target in test, no test hand-labeling, and no hidden/private label source.
3. Validation stability recorded before submission; only one candidate is selected by OOF AUC.
4. External data remains disabled until public accessibility, license, provenance, and rule compliance are documented.

## Reproduce

```bash
.venv/bin/python playground_s6e9/src/audit_data.py \
  --data-dir playground_s6e9/data/raw \
  --output playground_s6e9/reports/data_audit.json

.venv/bin/python playground_s6e9/src/train_baseline.py \
  --data-dir playground_s6e9/data/raw \
  --output-dir playground_s6e9/artifacts/baseline_3fold \
  --models lightgbm catboost xgboost \
  --folds 3 --rounds 1400 --seed 20260909

.venv/bin/python playground_s6e9/src/validate_submission.py \
  --sample playground_s6e9/data/raw/sample_submission.csv \
  --candidate playground_s6e9/artifacts/baseline_3fold/submission_rank_blend.csv
```

Official receipts are in `official/`; machine-readable audits and the experiment ledger are in `reports/`.

## First verified submission

Submission `56107927` completed with Public LB `0.94636`. It is the arithmetic mean of two local LightGBM reproductions on identical 5-fold splits; their OOF AUC gap is `0.0000222`, and the mean OOF AUC is `0.9460814`. No third-party OOF predictions were imported.

## Campaign status

Archived on 2026-09-17. Submission `56107927` remains frozen as the final campaign entry; no further training or submission is authorized. See [`reports/campaign_closeout_2026-09-17.md`](reports/campaign_closeout_2026-09-17.md).
