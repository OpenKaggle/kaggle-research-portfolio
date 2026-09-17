# Third-party model and code declaration

## Ultralytics YOLO11m

- Use: initial single-model object detector and COCO-pretrained checkpoint
- Model identifier: `yolo11m.pt`
- Source: https://github.com/ultralytics/ultralytics
- Model documentation: https://docs.ultralytics.com/models/yolo11/
- License: AGPL-3.0 (OSI-approved)
- Pretraining data: COCO, as published by Ultralytics
- Runtime package constraint: `ultralytics>=8.3,<9`; the exact resolved version is written to each run's `run_summary.json`

The competition host explicitly permits public ImageNet/COCO pretrained backbones when the model, source, and license are declared. The competition also requires winning solutions to be open source. If this solution reaches code review, the complete corresponding training/inference source and fine-tuned weight required by both the competition and the applicable open-source terms must be delivered without redistributing competition data.

