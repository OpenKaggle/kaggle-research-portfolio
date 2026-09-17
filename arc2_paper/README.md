# ARC-AGI-2 + Paper Track execution audit

External facts were checked on 2026-09-09 (Asia/Shanghai); the local Stable V2
terminal-capture receipt was synchronized on 2026-09-11. The account owner
explicitly accepted the ARC-AGI-2 rules; this task did not accept them. Official
files and a private development run are now in scope. Nothing has been submitted
to the competition.

## Current execution state: 2026-09-09

- The authenticated Kaggle API now reports `userHasEntered=True`. All six
  official files passed alignment and SHA-256 checks: training 1000/1076,
  evaluation 120/172, and hidden test 240/259. The competition manifest SHA-256
  is `d789efe03efb29a5bb8df6301cc12b7d8959d7bf3e790427142b1c8219e6c43f`.
- Private stable-v2 development Kernel version 1 (`run 348340917`) completed on
  four L4 GPUs at 48/50, but failed its hard runtime gate: TRM emitted no
  candidate and one NVARC task timed out. The disjoint holdout and competition
  rerun did not start. The 2026-09-11 terminal-capture receipt, SHA-256
  `3480807c7a13111956513c5c609b4afdd58b9f18d112fb3d0a86fec9eb22c03f`,
  reconciles this development kernel's earlier `RUNNING` snapshot to official
  `COMPLETE`. Its isolated capture contains 239 output files and one log, none
  reviewed here; sealed labels remain unopened, and conflicting official time
  fields leave the exact finish time `UNKNOWN`. This is operational evidence,
  not generalization evidence. The separately pushed V2 logging-only repair
  smoke is a different kernel: it was last observed `RUNNING` before the later
  local-only authorization boundary, and its current terminal state remains
  unknown.
- Public source dependencies and four additional public notebook variants are
  under `public_assets/` and `public_notebooks/`. The minimal large-asset plan
  is one 7.27 GB Qwen model version and one 2.16 GB TRM checkpoint; the other
  six duplicate-size TRM checkpoints are intentionally skipped.
- The selected Qwen and TRM assets are now complete. Exact byte counts and
  per-file SHA-256 values are recorded in `public_assets/verification.json`;
  the receipt SHA-256 is
  `1823852c94d0231c52d846b8fb1d6e1ea480562657c3154a5de0d8f4adaa12c5`.
- `run_exact_rule_heldout_audit.py` evaluated the public V175 exact-rule/object
  portfolio with test outputs detached before inference and strict
  leave-one-demonstration-out admission. It produced zero candidates on all
  167 outputs in the official GitHub checkout at commit `f3283f7` (120 tasks,
  dated 2025-05-15). Kaggle's 2026 evaluation files may be a different revision;
  the downloaded V175 receipt reports 172 outputs. The audit therefore confirms
  the local negative control but must be repeated on the Kaggle files after
  Join before claiming exact competition-evaluation parity. The fixed audit was
  subsequently repeated on the verified Kaggle 2026 revision and again selected
  zero candidates on all 172 outputs in 31.13 local CPU seconds. The symbolic
  branch therefore remains a negative control and abstains from submission.
- A submission-ready owned notebook is staged under
  `candidate_notebooks/conservative_agreement_v1/`. It is derived from the
  public safe 11-hour NVARC/TRM notebook and uses a fixed label-free policy:
  NVARC rank one in slot one; checkpoint-agreed TRM rank one in slot two;
  otherwise NVARC rank two; distinct TRM rank two only when the slot would be a
  duplicate. Static dependency, syntax, runtime-guard, and submission-schema
  preflights pass. It has not been pushed or scored.
- `benchmark_manifests.json` freezes two disjoint 48-task, work-stratified
  subsets before neural results are visible. The development notebook uses the
  first subset; `candidate_notebooks/conservative_agreement_v1_holdout/` uses
  the second. The competition-rerun path is identical in both.
- `candidate_notebooks/conservative_agreement_stable_v2/` and its holdout
  sibling apply the public stable-seed fix: augmentation scoring derives its
  seed from BLAKE2b(task ID), rather than Python's process-randomized `hash()`.
  V2 is the preferred reproducible candidate; V1 remains the selector-only
  control. All owned candidate metadata is private by default, and the static
  validator fails if that pre-submission boundary is removed.

The active gate is an explicitly authorized read-only status check of the
already-pushed V2 runtime smoke. A passing, hash-bound terminal receipt is
required before a repaired 48-task development run may start. Promote to the
sealed holdout and then the competition rerun only after the corresponding
earlier stage passes; no public-leaderboard result may be used to select policy.

## Decision

- **ARC-AGI-2: GO after explicit rule acceptance.** The first operational
  target is a reproducible copy of the public 31.11–31.39 leaderboard family,
  followed by an evidence-gated hybrid. Do not start from the old NeuroGolf
  DSL alone: its current depth-1 and depth-2 searches scored 0/167 exact public
  evaluation outputs.
- **Paper Track: conditional GO, developed in parallel.** Keep an experiment
  ledger from day one. Continue the paper only when the work produces a
  reproducible positive result beyond a copied public notebook: at least three
  additional public-evaluation outputs solved or a >=1.0 percentage-point
  held-out improvement under equal compute, plus an ablation that identifies
  why it works.
- **AI4S: NO-GO for now.** External registration, public repository/video,
  long report/defense, and joint ownership language make it a poor immediate
  side bet without explicit IP acceptance.
- **Hyperspectral Object Detection: conditional NO-GO.** Only reopen if a
  first-day public checkpoint reaches >=0.60; the observed prize cutoff was
  about 0.639 with roughly 140 teams and a near deadline.

## Registration and deadlines

ARC-AGI-2 is joined. Paper Track registration remains a separate user/account
action and must not be inferred from ARC-AGI-2 entry.

### ARC-AGI-2

1. Open the Kaggle competition and click **Join Competition**.
2. Read and accept the separate binding rules. There is no external form.
3. Entry/team-merger deadline: 2026-10-26 23:59 UTC (2026-10-27 07:59 CST).
4. Final notebook submission: 2026-11-02 23:59 UTC (2026-11-03 07:59 CST).

Operational constraints:

- One submission per day; up to two final submissions.
- Code Competition: CPU or GPU notebook <=12 hours, internet disabled.
- Public, freely available external data and pretrained models are allowed.
- Kaggle currently provides L4 x4 accelerators for this competition.
- Output must be named `submission.json`. Every hidden task ID and every test
  output must have exactly `attempt_1` and `attempt_2` grids.
- Exact-match pass@2 is scored per task output.

License/IP boundary:

- Competition data: Apache-2.0.
- Winning submission and source must be open; Kaggle states CC BY 4.0 and the
  ARC Prize overview asks submitter-authored methods to use a permissive
  public-domain-style license such as CC0/MIT-0. Use MIT-0 for new orchestration
  and retain Apache-2.0 notices for inherited components.
- A winner must deliver training/inference code and documentation and support
  a sponsor interview/technical writeup. Do not attach proprietary core assets
  that cannot be released.

### Paper Track

1. Join the separate Kaggle Hackathon and accept its rules.
2. Submit a final Kaggle Writeup, not a draft.
3. Kaggle's controlling page says 2026-11-09 23:59 UTC (2026-11-10 07:59
   CST). The ARC Prize overview says papers are due November 8; use November 8
   as the internal hard deadline until organizers reconcile the discrepancy.

Required package:

- Kaggle Writeup, <=1,500 words, with the ARC-AGI-2 track selected.
- Media Gallery with a required cover image.
- Attached public Kaggle Notebook in Project Links and the matching ARC-AGI-2
  submission ID. The code score supplies the rubric's Accuracy component.
- Optional publicly accessible project/PDF link.
- A private Kaggle resource attached to the public Writeup becomes public after
  the deadline.

The paper is scored equally on Accuracy, Universality, Progress, Theory,
Completeness, and Novelty. A low code score is allowed, but a copied public
baseline has weak Novelty and Progress and is not a viable paper by itself.

## Public score anchors and first run

Leaderboard snapshot at audit time:

| Rank | Public score |
| ---: | ---: |
| 1 | 76.67 |
| 2 | 72.08 |
| 3 | 40.83 |
| 8 | 34.86 |
| 10 | 33.89 |

Public reproducible anchors:

- `sorenravn/arc2-vanilla-exact`: 31.39, one public Qwen grid model, displayed
  notebook runtime 25m15s. Its API download is disabled (403), so copy it from
  Kaggle UI after joining.
- `christopherdaleman/arc-2026-nvarc-trm-evidence-cost-v1`: 31.11,
  Apache-2.0 inherited code plus MIT-0 orchestration. A local copy is under
  `public_notebooks/nvarc_trm/`. It uses the public Qwen grid model, an attached
  public TRM source bundle/checkpoint, four L4 GPUs, a 12-hour guard, NVARC/TRM
  candidate generation, and label-free agreement/evidence selection.
- `prvsiyan/arc-agi-2-public-frontier-perfpatch-evidence-lab`: 29.03.

First submission gate after rule acceptance:

1. Copy the 31.39 vanilla notebook in the Kaggle UI; copying preserves the
   model attachment that the CLI download could not retrieve.
2. Confirm internet is off and all input/model licenses are recorded.
3. Commit no algorithmic changes on the first run. Validate that every hidden
   task has two nonempty, rectangular, 1–30 by 1–30, color-0–9 attempts.
4. Submit once. **Continue only if the completed rerun is >=29.0 and finishes
   within 11h30.** A lower score or timeout gets one dependency/runtime repair,
   not broad tuning.

## What is reusable from NeuroGolf old Neuroest NeuroGolf work

Reusable as research infrastructure:

- Grid transforms and object primitives: color maps, rotations/reflections,
  crop/bounding box, connected components, run compression, flood fill,
  thickening/hollowing, tiling, and transform-bank matching.
- Search machinery: typed primitive enumeration, depth-limited program search,
  cost ordering, and exact demonstration-pair validation.
- Generalization guards: leave-one-example-out checks, generated contracts,
  pseudo-hidden tests, transform invariance and exact decoded-output checks.
- Portfolio idea: use a symbolic candidate only when all demonstrations and
  invariance checks agree; otherwise leave both attempts to independent neural
  families.

Not reusable directly:

- ONNX golf bundles solve a fixed, numbered set with per-task models and cannot
  infer transformations for unseen ARC-AGI-2 task IDs.
- Visible-only lookup/cherrypick assets violate the generalization objective.
- The current 29-primitive, depth<=2 DSL is not an ARC-AGI-2 baseline. The
  audited run found zero training-perfect programs and 0/167 public-evaluation
  exact outputs at both depth 1 and depth 2. Keep it as a verifier and proposal
  branch; do not spend a daily Kaggle submission on it.

Reproduce that negative control with:

```bash
$HOME/Desktop/kaggleonnx/.venv/bin/python \
  arc2_paper/run_neurogolf_dsl_baseline.py --max-depth 2
```

## 48-hour research gate

Run two lanes without using public-evaluation labels during candidate
generation or selection:

1. **Neural anchor:** reproduce the public Qwen/NVARC or NVARC+TRM output and
   capture runtime, candidate diversity, augmentation votes, and failure logs.
2. **Symbolic evidence branch:** port object/relational proposals from
   NeuroGolf, but require leave-one-example-out exactness, dihedral/color
   equivariance, and agreement across at least two independent formulations.

Hard gate at 48 hours:

- Kaggle runner generated a valid `submission.json`, completed below 11h30,
  and achieved >=29.0; and
- the experiment ledger contains a fixed, label-free selector with complete
  provenance; and
- the symbolic branch passes all demonstrations and invariance checks on at
  least 5% of evaluation tasks, even if it is not yet selected.

If the first condition fails: stop ARC execution. If only the third fails:
continue the ARC leaderboard lane but mark the Paper Track **NO-GO** until a
real, independently testable contribution exists.

## Paper-synchronous experiment record

Append one row per run; never reconstruct these fields from memory later.

| Field | Required content |
| --- | --- |
| Experiment ID | UTC timestamp + short slug |
| Hypothesis | One falsifiable sentence |
| Contribution | Candidate generation / evidence / selector / compute policy |
| Parent artifact | Git commit, notebook version, and parent submission ID |
| Data boundary | Training or public eval; confirm no public-eval labels entered selection |
| Provenance | Source URL/version, author, license, local hash for every code/model/data input |
| Compute | Image version, GPU/CPU, worker count, seed, wall time, peak memory |
| Candidate policy | Solvers, augmentations, beam/search budget, stopping rule |
| Selector policy | Input-only signals; fixed before looking at labels |
| Metrics | Public eval pass@2, attempt-1, attempt-2, solver union/overlap, runtime |
| Ablation | Single changed factor and equal-compute control |
| Outcome | Confirmed / refuted / inconclusive |
| Decision | Promote / repeat once / archive |
| Artifacts | Submission JSON hash, logs, per-task receipts, plots |

Paper figures to update automatically from the ledger:

1. Solver-set overlap and incremental union.
2. Accuracy versus compute budget.
3. Selector calibration: predicted confidence versus exact success.
4. Failure taxonomy by output-size change, object relation, transformation
   depth, and candidate disagreement.

## Official sources

- <https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/overview>
- <https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-2/rules>
- <https://www.kaggle.com/competitions/arc-prize-2026-paper-track/overview>
- <https://arcprize.org/competitions/2026>
- <https://arcprize.org/competitions/2026/paper>
- <https://github.com/arcprize/ARC-AGI-2>
