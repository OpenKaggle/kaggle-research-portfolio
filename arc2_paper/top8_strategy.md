# ARC-AGI-2 Top-8 technical strategy

Snapshot basis: the 2026-09-08 competition scan. Recheck the leaderboard only
when a submission decision is due; do not use rank movement as a tuning label.

## Gap to close

- Observed public NVARC reference: 33.89.
- Observed rank-8 line: 34.86.
- Net gap: 0.97 percentage points, roughly two fully solved tasks on a
  120-task mean. The target is therefore a small number of genuinely
  incremental, non-destructive wins, not a broad solver rewrite.
- The downloaded TRM source reports epoch-2,000/4,000 rank-one agreement correct
  on 12 of 31 agreement outputs (38.71%) versus 4 of 136 disagreement outputs
  (2.94%). This motivates using checkpoint agreement as evidence, but it does
  not prove incremental value over NVARC rank two; the frozen A/B must measure
  that directly.

## Candidate order

| ID | Slot 1 | Slot 2 | Purpose |
| --- | --- | --- | --- |
| A0 | NVARC KGMon rank 1 | NVARC KGMon rank 2 | unchanged anchor/control |
| A1 | NVARC full-prob rank 1 | rank 2 | ranking ablation |
| A2 | NVARC portfolio rank 1 | rank 2 | candidate-diversity ablation |
| A3 | NVARC rank 1 | TRM final rank 1 | aggressive independent solver |
| A4 | NVARC rank 1 | upstream evidence/aggressive merge | public hybrid control |
| A5 | NVARC rank 1 | TRM rank 1 only on 2k/4k agreement, else NVARC rank 2 | conservative selector |
| A6 | A5 | distinct TRM rank 2 only when A5 would duplicate slot 1 | staged candidate |
| A7 | A6 with BLAKE2b task seed | same as A6 | reproducible staged candidate |

A7 is the preferred local submission candidate; A6 remains the selector-only
control. It may be promoted only after A0–A7 are
scored from the same generated candidate files on the predeclared development
split and the A6 direction persists on the sealed holdout split.

## Symbolic/object branch

- Old NeuroGolf depth <=2: 0 training-perfect programs and 0/167 on the GitHub
  evaluation checkout.
- Public V175 exact-rule library on the same evaluation checkout: 0 candidates.
- V175 on the public training corpus: 307/307 selected outputs correct after
  leave-one-demonstration-out gating, but the rules were developed against
  public corpora. Treat this only as selector-safety evidence, not unseen-task
  generalization.
- Production rule: a symbolic output may enter slot two only when it fits every
  demonstration, passes every leave-one-demonstration-out fold, is unique after
  grouping identical grids, and survives color/dihedral equivariance checks.
  Zero candidates is an acceptable outcome.

## Engineering priorities

1. Reproduce full NVARC task coverage and the public score family before
   changing training or decoding.
2. Measure incomplete and timed-out tasks by work quartile. A recovered timeout
   can be worth more than another generation pass.
3. Select between already generated candidates; do not increase generation
   count until the solver union shows at least three missing net wins that
  ranking could plausibly recover.
4. Preserve two genuinely different attempts. Fill a duplicate only with a
   valid independent candidate; never overwrite a distinct NVARC rank two on
   weak TRM evidence.
5. Freeze all thresholds on development, confirm once on sealed holdout, then
   use the leaderboard as an outcome receipt rather than an optimizer.

## Stop and pivot conditions

- Stop the candidate if the full rerun is below 29.0 or exceeds 11h30 after one
  reproducibility repair.
- Archive a selector change if it does not improve both development and sealed
  holdout under equal candidate generation.
- Pause Paper Track novelty claims if no independently testable contribution
  adds at least three evaluation outputs or one percentage point on sealed
  heldout data under equal compute.
- Do not download additional 2.16 GB TRM checkpoints, widen the Qwen model, or
  add more augmentations without a recorded ablation hypothesis and runtime
  budget.
