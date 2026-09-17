# Organizer baseline and IP audit

Audit completed: `2026-09-08T22:13:40Z` / `2026-09-09T06:13:40+08:00`.

This is a static compliance/readiness audit only. No organizer source was edited,
no model was developed, and no training was run. That boundary is intentional:
the Small Model Track explicitly forbids closed-source APIs or LLMs for
development.

## Source snapshot

- Official repository: `https://github.com/openaiotlab/CUHK-X`
- Local read-only reference: `vendor/CUHK-X`
- Commit: `df03910a6960db5af9179e370e130bf61d9616d0`
- Commit timestamp: `2026-09-07T15:10:46+08:00`
- Working tree: clean, `main...origin/main`
- The checkout is shallow (`grafted`), so the receipt pins the exact tree but
  does not claim to contain complete repository history.
- No `.pth`, `.pt`, `.ckpt`, `.bin`, `.onnx`, `.npy`, or `.npz` model artifact
  is present below `SM/`.
- No competition inference entry point or `sample_submission.csv` writer is
  present in the repository.

## License/IP discrepancy

The currently distributed `LICENSE` is CUHK-X License v2.0 and states that it:

- governs all project materials, including source code, data, annotations,
  splits, benchmarks, and documentation;
- supersedes the earlier MIT and CC BY terms;
- permits third-party use only for non-commercial research, academic, and
  educational purposes;
- makes the dataset non-redistributable and requires explicit written
  permission before data access;
- terminates the granted rights on breach.

The repository READMEs are stale relative to that file: they still display MIT
badges and state that the code is MIT licensed. The official registration PDF,
`IP_CLAUSES_BILINGUAL.pdf`, separately requires a prize-winning submission and
its source code to be licensed under Apache 2.0 without restricting commercial
use. The challenge webpage applies an Apache 2.0 open-source obligation to Top-6
finalists within 30 days of the final.

Operational consequence: code derived from the organizer baseline should not be
included in a finalist solution until the organizer confirms in writing that
the two licensing requirements are compatible or grants an applicable
exception. The organizer checkout is therefore retained as an unmodified
reference only. This is a compliance flag, not a legal conclusion.

- Local `LICENSE` SHA-256:
  `f91f3c1aee1491a919a88cf2cdcd247532ef0d21b2b412882163ccac5ea06a03`
- Official IP clauses PDF SHA-256:
  `9b2fe15a4ad88544e365cb08cd83148c515a363ee0ab27e0aaf576b39c82c033`
- Organizer contacts shown in the official materials:
  `syjiang [AT] ie.cuhk.edu.hk` for dataset/licensing and
  `cuhkx.competition@gmail.com` on the IP clauses PDF.

## Static readiness findings

The published code cannot be treated as a ready-to-submit competition baseline.
The material findings below are reproducible directly from the pinned tree.

### IMU path

- `train_transformer.py` passes `train_dataset` twice to `DataLoader` and also
  supplies `batch_size=`. At runtime this gives multiple values for the batch
  size argument before training begins.
- Its `--random_init` branch refers to `model.conv_layers`, but the constructed
  `SupervisedTransformer` exposes the layers under
  `model.cnn_transformer.conv_layers`.
- The training program records metrics and predictions in JSON but never saves
  a PyTorch model state/checkpoint.
- Its evaluation loader expects labeled `data_type == "test"` rows. It is not an
  inference path for the 405 anonymous competition test clips.
- The supplied 40-class fold CSVs each contain 2,768 rows and labels 0-39. They
  are within-subject trial folds over the 18 training users, not the competition
  cross-subject test split. Fold 4's local test partition contains 39 classes;
  the other four contain 40.
- `Code/imu/data_imu/activity_40/dataset_cross_env.csv` contains a header only.

### Skeleton path

- Both `dstformer.yaml` and `dstformer_smaller.yaml` specify
  `action_classes: 44`; the competition task has 40 classes.
- `ActionNet` accepts `hidden_dim` but does not forward it to
  `ActionHeadClassification`, whose default is 2,048. The apparent 256/1,024
  head setting in the YAML files is therefore ignored.
- On non-CUDA systems the model is not wrapped with `DataParallel`, but the
  optimizer unconditionally accesses `model.module`. The supplied training
  path therefore does not run as written on this Mac's CPU/MPS environment.
- Resume/evaluation logic assumes a `module.head.fc2.weight` checkpoint key;
  no checkpoint is distributed in the repository.
- The training validator consumes labeled split files and does not emit the
  required Kaggle `path,prediction` file.

### RGB and environment mismatch

- The challenge excludes RGB at training, validation, and inference; RGB code
  in the repository is not a competition input path.
- Several RGB examples use ImageNet-pretrained ResNet backbones, while the
  track prohibits large pretrained backbones. No such example should be
  assumed compliant without organizer clarification.
- `SM/requirements.txt` pins PyTorch 2.3.0 plus Linux/CUDA 12 packages. The
  current machine has Python 3.13.2 and no PyTorch; the official environment is
  not directly reproducible here as written.

## Current non-code blockers

- The official external registration form is still open, but all fields remain
  empty. It needs user-provided contact email, affiliation, country/region, and
  member name before any identity data can be transmitted.
- No training or test sensor archive was found on the Desktop, and no external
  storage volume is mounted. A recheck at `2026-09-08T22:20:26Z` found only
  about 12 GiB free on the system volume, below the 47.4 GB compressed mirror
  size and far below extraction/training headroom. The campaign directory itself
  is only about 193 MB, so this change was not caused by CUHK-X data downloads.

## Goal-state revalidation

Revalidated at `2026-09-08T22:20:26Z`:

- Kaggle submission `56107602` remains `COMPLETE` with public score `0.03482`.
- The organizer baseline remains clean at the pinned commit and still contains
  no model artifacts.
- The official registration page was reopened in a visible in-app browser and
  its form was handed off for the user to enter identity/contact fields.
- No additional submission was made and no daily quota was consumed.
