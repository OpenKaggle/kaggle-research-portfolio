# Kaggle Prediction & Research Archive

This is a public, sanitized research archive prepared from a larger local workspace named `kagglepred` on 2026-09-17.

The full local workspace is about 112 GiB. This repository intentionally contains only reproducible research material: source code, small configuration files, experiment notes, technical reports, and environment specifications. It excludes raw competition data, downloaded models, checkpoints, generated submissions, local virtual environments, third-party notebook mirrors, and large binary artifacts.

## Publication status

This repository is public for research inspection and reproducibility. It is an
archive, not yet a uniformly licensed software distribution: the retained
campaigns have mixed provenance, so no blanket open-source license is asserted
over files whose authorship or upstream license has not been verified. Reuse is
governed by the notices attached to individual files and their upstream sources.

Standalone competition archives extracted from the same local research corpus:

- [NVIDIA Nemotron reasoning research](https://github.com/Jah-yee/nemotron-reasoning-research)
- [NeuroGolf 2026 ONNX research](https://github.com/Jah-yee/neurogolf-2026-onnx-research)
- [Maze Crawler research](https://github.com/Jah-yee/maze-crawler-research)

## Campaigns represented

The archive contains work associated with these locally recorded campaigns:

- IEEE Big Data Traffic Flow Bench
- CUHK-X Small Model Track and Large Model Track
- ARC-AGI-2 plus Paper Track execution audits
- ARC Prize 2026 / ARC-AGI-3 clean-room research
- Hyperspectral Tree Species Identification Challenge 2026
- Hyperspectral Object Detection Challenge 2026
- TartanIMU IROS 2026
- Kaggle Playground Series S6E9
- ROGII Wellbore Geology Prediction
- BioHub Cell Tracking
- additional local workspaces under `kaggriculture`, `poker`, and related research folders

These names describe the local research folders and do not imply affiliation with the competition organizers.

## Repository structure

- Each top-level campaign directory contains the small, reviewable code and documentation retained from that workspace.
- `scripts/` contains cross-campaign automation and analysis utilities.
- `research/` contains compact research notes.
- `inventory/TOP_LEVEL_USAGE.tsv` records the original local directory sizes.
- `inventory/LARGE_ARTIFACTS.tsv` indexes excluded files larger than 100 MiB so the local research state can be audited and reconstructed from authorized sources.

## Excluded material

The following are deliberately not published to GitHub:

- Kaggle-provided or organizer-provided raw datasets
- model weights, checkpoints, archives, Parquet/CSV outputs, and submission bundles
- third-party notebooks, public mirrors, and official upstream repositories
- `.venv`, caches, temporary work directories, and local application state
- credentials, tokens, `.env` files, and private configuration

Large first-party artifacts may be mirrored separately to private Kaggle Datasets. A remote upload is not considered a backup until its file list and sizes have been verified.

## Reproducibility

Start with the `README.md` and dependency files inside an individual campaign directory. Data and model paths are intentionally absent; obtain those inputs from the original competition or another authorized source. The manifests in `inventory/` document the excluded local material without redistributing it.

## Data and licensing note

No license is granted here for excluded competition data or third-party artifacts. Individual source files may retain their own notices. Before reusing a campaign, review the applicable competition rules and upstream licenses.
