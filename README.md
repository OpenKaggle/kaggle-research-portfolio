# OpenKaggle Research Portfolio

This is a public, sanitized research archive prepared from a larger local workspace named `kagglepred` on 2026-09-17.

> [!NOTE]
> The OpenKaggle organization first mirrored the original public history through
> commit `33ee5bfc2fc2b4b6aff9610cc61c509fa4fc2b29`, then updated this index to
> point at the competition-level organization repositories. See
> [`OPENKAGGLE_MIGRATION.md`](OPENKAGGLE_MIGRATION.md) for the preservation and
> migration boundary.

The full local workspace is about 112 GiB. This repository intentionally contains only reproducible research material: source code, small configuration files, experiment notes, technical reports, and environment specifications. It excludes raw competition data, downloaded models, checkpoints, generated submissions, local virtual environments, third-party notebook mirrors, and large binary artifacts.

## Publication status

This repository is public for research inspection and reproducibility. It is an
archive, not yet a uniformly licensed software distribution: the retained
campaigns have mixed provenance, so no blanket open-source license is asserted
over files whose authorship or upstream license has not been verified. Reuse is
governed by the notices attached to individual files and their upstream sources.

Standalone competition archives extracted from the same local research corpus:

- [NVIDIA Nemotron reasoning research](https://github.com/OpenKaggle/nemotron-reasoning-research)
- [Nemotron evaluation records](https://github.com/OpenKaggle/nemotron-evaluation-records)
- [NeuroGolf 2026 ONNX research](https://github.com/OpenKaggle/neurogolf-2026-onnx-research)
- [Maze Crawler research](https://github.com/OpenKaggle/maze-crawler-research)
- [ARC-AGI-2 and Paper Track research](https://github.com/OpenKaggle/arc-agi-2-paper-track-research)
- [ARC-AGI-3 2026 research](https://github.com/OpenKaggle/arc3-2026-research)
- [BioHub cell-tracking research](https://github.com/OpenKaggle/biohub-cell-tracking-research)
- [CUHK-X research](https://github.com/OpenKaggle/cuhk-x-research)
- [Kaggriculture research](https://github.com/OpenKaggle/kaggriculture-research)
- [TartanIMU research](https://github.com/OpenKaggle/tartan-imu-iros-2026-research)
- [Traffic-flow forecasting research](https://github.com/OpenKaggle/traffic-flow-2026-research)
- [Hyperspectral tree-species research](https://github.com/OpenKaggle/tree-species-hsi-2026-research)

The Tree Species repository preserves an explicit source-and-evidence overlay
from a dirty local workspace without publishing its restricted 13 GB data,
model, submission, cache, or absolute-symlink payloads. The original dirty
workspace remains untouched.

## Campaigns represented

The archive contains work associated with these locally recorded campaigns:

| Campaign | Directory | Status | Research repository | Public-eligible-after (UTC) |
|---|---|---|---|---|
| IEEE Big Data Traffic Flow Bench | `traffic` | Active — final selection due 2026-11-04, deadline 2026-11-07 |
| CUHK-X Small Model Track and Large Model Track | `cuhkx_small`, `cuhk_x_large` | Ended — closed (2026-09-15) |
| ARC-AGI-2 plus Paper Track execution audits | `arc2_paper` | Active — evidence line (paper track); leaderboard anchor sealed at 28.89 |
| ARC Prize 2026 / ARC-AGI-3 clean-room research | `arc3_2026` | Sealed — local baseline gate failed (2026-10-15); entry window closed |
| Hyperspectral Tree Species Identification Challenge 2026 | `tree_species_hsi_2026` | Ended — sealed (2026-09-25) |
| Hyperspectral Object Detection Challenge 2026 | `hyperspectral_od_2026` | Ended — frozen (2026-09-24) |
| TartanIMU IROS 2026 | `tartan_imu` | Delivery complete (2026-09-20) |
| Kaggle Playground Series S6E9 | `playground_s6e9` | Ended — frozen (2026-09-30) |
| BioHub Cell Tracking | `biohub_cell_tracking` | Ended — frozen (2026-09-29) |
| Kaggriculture | `kaggriculture` | Ended — closeout (2026-10-15) |
| Detect Suspicious Value Transfers in Poker | `poker` | Ended — sealed after infrastructure failure (2026-09-20) |
| Gemma 4 Developer Agent Paper Track | `gemma_paper_2026` | Joined 2026-10-31, Active — writeup due 2026-11-12 |
| Verifiable Quantum Circuit Compilation | `quantum_2026` | Joined 2026-10-31, Active — final 2027-01-20 |
| NFL Big Data Bowl 2027 | `nfl_2027` | Joined 2026-10-31, Active — final 2027-01-06 |
| NeurIPS 2026 Smart Buildings | `buildings_2026` | Joined 2026-10-31, Active — final 2027-01-15 |

Full registered-competition sweep 2026-10-31: 12 joined total (7 active, 5 ended).

The ROGII Wellbore Geology Prediction record and other workspace folders without a dedicated directory in this archive are not covered by the status table above. Local directories for the four 2026-10-31 additions exist under the same root naming scheme.

Status column updated 2026-10-31 from internal portfolio state; statuses are terminal-state labels, not quality judgments.

These names describe the local research folders and do not imply affiliation with the competition organizers.

**Publication gate** = the line's competition submission end. Research repositories stay private until at least that time; flipping visibility is a separate human decision. Four additional repositories predate this table and carry their own gate statements: `maze-crawler-research` (2026-06-16T23:59Z, elapsed), `neurogolf-2026-onnx-research` (2026-07-15T23:59Z, elapsed), `nemotron-reasoning-research` (2026-06-15T23:59Z, elapsed), `rogii-wellbore-geology-research` (2026-08-05T23:59Z, elapsed, verified 2026-11-02 via authenticated Kaggle API). Gate column added 2026-11-02; on the same date the two repositories whose gates had not yet passed (`traffic-flow-2026-research`, `arc-agi-2-paper-track-research`) were set to private, and the four 2026-10-31 line repositories were created private with gate statements.

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

The [public sanitized Kaggle mirror](https://www.kaggle.com/datasets/jahyee/kaggle-research-portfolio-sanitized)
preserves the same category of reviewable research material for Kaggle-native
discovery. It deliberately excludes the restricted material listed above. A
remote upload is not considered a backup until its file list and sizes have
been verified.

## Reproducibility

Start with the `README.md` and dependency files inside an individual campaign directory. Data and model paths are intentionally absent; obtain those inputs from the original competition or another authorized source. The manifests in `inventory/` document the excluded local material without redistributing it.

## Data and licensing note

No license is granted here for excluded competition data or third-party artifacts. Individual source files may retain their own notices. Before reusing a campaign, review the applicable competition rules and upstream licenses.
