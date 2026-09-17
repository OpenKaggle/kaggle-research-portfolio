# Final reproducibility freeze v2 receipt

Recorded: 2026-09-09T13:57:30Z

## Snapshot

- Current manifest: `reports/final_reproducibility_manifest_2026-09-09_v2.json`.
- Manifest SHA-256: `ca99cd74e7e3e8f01930c914b119916cb8117d3c73cde2f16a4be4c987fae4be`.
- Independent verification: `reports/final_reproducibility_verification_2026-09-09_v2.json`.
- Verification SHA-256: `1a6b8f7e700ce0e6b2e2076084ff0b43f45e13e9f70d6fe8ff92642ff0fae336`.
- Verification status: `PASS` at `2026-09-09T13:57:14.706577+00:00`.
- Project artifacts verified: 84/84 by exact byte size and SHA-256.
- Pinned Qwen3-VL-4B files verified: 16/16 by exact byte size and SHA-256.
- Selected candidate files verified: 2/2, each 682 rows in exact official ID order with valid category grammar.
- Experiment log verified: 55 rows with the fixed 16-column schema and both selected submission references present.

## Superseded snapshot

The v2 manifest supersedes `reports/final_reproducibility_manifest_2026-09-09.json` (SHA-256 `b5ad21e638d47b8fb0fc406a59cb7442635a921bd2c969a99c6cbcbb1d252c4d`). The original remains preserved as historical evidence. Version 2 adds the complete official test archive/extraction lineage, the Small20 deterministic replay classification, the read-only subject/task audit, the VLM hard stop, updated ledger/README, and their source code and receipts.

## Frozen final candidates

1. Submission `56122653`: `candidates/emotion_extratrees_rf_union_v1.csv`, SHA-256 `3a76a36e6d3060979370f5b598e090c0e2436689d9eda6b17416ae8bc0aee3e4`, public `0.78070`.
2. Submission `56108595`: `candidates/nonvisual_sensor_union_v1.csv`, SHA-256 `a5d300381a79e751c08c03a36036cf56137121fc3f987832e64062b534204702`, public `0.78070`.

No candidate or submission was created from the Small20 replay, historical post-hoc audit, or the two newly visible test-time VLM consensus rows.
