# ARC-AGI-2 offline and Kaggle resource budget

Snapshot: 2026-09-09, Asia/Shanghai.

## Access boundary

- Authenticated Kaggle status: joined (`userHasEntered=True`) after the account
  owner explicitly accepted the rules on 2026-09-09.
- All six competition files were downloaded and hashed successfully.
- Available without Join: official Apache-2.0 ARC-AGI-2 Git repository,
  public notebooks, public source datasets, public Qwen model, and public TRM
  checkpoint.
- This task did not accept rules. Private development Kernel version 1 is
  running; no competition submission has been made.
- The available GitHub checkout is commit `f3283f7` from 2025-05-15 and has
  120 evaluation tasks / 167 outputs. The Kaggle 2026 files are now verified as
  a distinct 120-task / 172-output revision; their manifest SHA-256 is
  `d789efe03efb29a5bb8df6301cc12b7d8959d7bf3e790427142b1c8219e6c43f`.

## Minimal reproducible asset set

| Asset | Exact remote size | Local role | Decision |
| --- | ---: | --- | --- |
| `qwen3_4b_grids15_sft139`, BF16 v1 | 7,267,271,302 B | NVARC neural anchor | Keep one complete version |
| TRM `step_220708` | 2,159,719,349 B | Preferred TRM initialization | Keep this checkpoint only |
| TRM source/wheels/rule receipts | about 6 MB | Offline runtime and audit | Downloaded |
| NVARC/TRM safe notebook | under 0.1 MB | Kaggle orchestration | Downloaded and staged |
| Six other TRM checkpoints | 12,958,316,094 B total | Alternate initializations | Skip until an ablation justifies them |

The selected large assets total 9,426,990,651 bytes (about 8.78 GiB). The host
had about 55 GiB free before downloads, so the minimal set fits. Keep at least
15 GiB free for archives, temporary extraction, logs, and derived submissions.

The preferred TRM file completed on 2026-09-08 and passed the exact-size gate;
its SHA-256 is `dbf771737d9799b84faf009c24c5376831f095d2cfd66debbe9a505a445bfc31`.
The Qwen model completed on 2026-09-09. All 10 files total exactly
7,267,271,302 bytes and passed `verify_public_assets.py --hash`; the durable
receipt is `public_assets/verification.json` with SHA-256
`1823852c94d0231c52d846b8fb1d6e1ea480562657c3154a5de0d8f4adaa12c5`.
The host had about 37 GiB free after extraction and removal of the archive.

## Kaggle wall-clock plan

- Required accelerator: four Nvidia L4 GPUs, matching the public notebook
  metadata and worker layout.
- Hard competition limit: 12 hours.
- Candidate scheduling cutoff: 11 hours. The final hour is reserved for an
  in-flight puzzle, TRM shutdown, merge, schema validation, and Kaggle
  finalization.
- NVARC: workers 0–2 begin immediately; worker 3 starts after TRM releases GPU
  3. Puzzles are ordered by an input-only estimate of augmented token and
  output-decoding work. Each NVARC puzzle has a 1,200-second cap.
- TRM: one GPU, epochs 2,000 and 4,000 exported, batch 112, 128 augmentations.
- Disk inputs on Kaggle: about 9.43 GB plus the injected Unsloth utility bundle
  and competition JSON files.

## Local-machine boundary

The host is Apple ARM64/macOS, not a CUDA-equivalent reproduction environment.
Local work therefore covers source and license auditing, exact-rule replay,
held-out selection tests, dependency checksums, notebook construction, and
submission validation. Full Qwen/TRM runtime and memory measurements must be
captured on Kaggle's four-L4 image; local timing must not be used to predict
the 12-hour rerun.

## GPU-run gates

1. Normal notebook run: fixed 48-task, four-work-quartile sample from the 1,000
   public training tasks, capped at six hours.
2. Require complete task coverage, zero invalid grids, and saved per-policy hit
   sets/runtime receipts.
3. Compare unchanged KGMon top two, portfolio, full-probability, TRM top two,
   NVARC1+TRM1, and conservative checkpoint-agreement merge at equal compute.
4. Freeze the selector before any labeled public-evaluation or leaderboard
   result is inspected.
5. First competition rerun gate: valid `submission.json`, total runtime below
   11h30, and public score at least 29.0. One dependency/runtime repair is
   allowed; broad tuning after a failed run is not.
