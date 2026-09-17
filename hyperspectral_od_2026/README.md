# Hyperspectral Object Detection Challenge 2026

Private, competition-only workspace for the Kaggle competition:

- Competition: https://www.kaggle.com/competitions/hyperspectral-object-detection-challenge-2026
- Final deadline: 2026-09-24 16:00 UTC / 2026-09-25 00:00 Asia/Shanghai
- Phase 2 ranking-set release: 2026-09-23 (time not specified on the official page)
- Metric: COCO mAP@[0.5:0.95], with mAP@0.5 reported secondarily
- Daily submission limit: 3
- Maximum team size: 5

## Compliance boundary

Competition data stays in this private workspace or the private Kaggle notebook. It may only be used for this competition and must not be redistributed, commercially used, cross-channel polluted, or used in a paper without explicit provider permission. Manual test/ranking labels, human prediction of held-out records, private sharing outside the Kaggle team, and any evaluation-system attack are prohibited.

The final prediction must come from one trained detection model. Multiple checkpoints/models may not be combined by voting, weighted fusion, WBF, or post-NMS fusion. The host has explicitly allowed public ImageNet/COCO pretrained weights when model/source/license are declared, and has allowed TTA or multi-scale inference from the same single checkpoint.

## Layout

- `official/`: official receipts, metadata, file inventory, and leaderboard snapshots
- `raw/core/`: class list, corrected sample submission, official pseudo-RGB script, and minimal samples
- `raw/full/`: optional local competition-only download
- `kaggle_notebook/`: private Kaggle GPU baseline source and metadata
- `scripts/`: schema, data, and submission checks
- `runs/`: experiment ledger and downloaded run outputs
- `submissions/`: files that passed all local gates

## First baseline

The initial baseline is a single COCO-pretrained YOLO11m checkpoint trained on deterministic per-image pseudo-RGB made from bands `[5, 8, 13]`, a documented alternative in the official demo. It uses a fixed 80/20 train/validation split with seed `20260909`, reports validation mAP, and generates test predictions with one checkpoint only. It is deliberately conservative: no pseudo-labeling, no external remote-sensing teacher, and no model ensemble.
