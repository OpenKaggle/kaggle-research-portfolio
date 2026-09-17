# Data and artifact lineage

| Asset | Source | License | Frozen evidence |
| --- | --- | --- | --- |
| Competition data | Kaggle `biohub-cell-tracking-during-development` | CC0 plus competition rules | `official/receipt.json`, `official/file_manifest.csv` |
| 0.946 Notebook | Kaggle `reyhanksatria/biohub-cell-tracking-0-946-lb` | Public competition code; use remains subject to competition open-source rules | `public_notebooks/reyhanksatria_0946/` |
| Primary TemporalUNet3D support pack | Kaggle `pilkwang/biohub-tracking-support-pack-50ep-v1` | CC0-1.0 | `public_assets/primary/` |
| DeepCenter auxiliary detector | Kaggle `pilkwang/biohub-deepcenter-unet3d-center-prior-v1` | CC0-1.0 | `public_assets/deepcenter/` |
| Secondary seed model | Kaggle `pilkwang/biohub-temporal-unet3d-seed314159-v1` | CC0-1.0 | `public_assets/secondary/` |

Pinned checkpoint hashes:

- Primary: `12f6881ee3620a831697ca098ff8f48e687a24225f4e048b538deec3562fe771`
- DeepCenter best checkpoint: `8040999a92f6b7bbd98fa8cf458141e045c0f9ad7c936bdb3b18e1f7edafe2a0`
- Secondary seed: `9bac2fa0dadc4a6fc1899e0caf187f4b553e0a7cd90ba1261a68b35ffe9e305f`

The reproduction changes only dataset owner/slug paths from inaccessible author mirrors to the public originals above. The generated `REPRO_RECEIPT.json` records the source and target Notebook hashes and exact replacement counts.

