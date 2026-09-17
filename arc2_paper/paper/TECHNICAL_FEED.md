# ARC-AGI-2 technical artifact intake

This paper task reads technical artifacts but does not own or rewrite the
leaderboard pipeline.

## Watched locations

- `../experiment_log.csv`
- `../artifacts/`
- `../public_notebooks/`
- `../candidate_notebooks/`
- `../public_assets/trm_source/receipts/`
- `../verify_public_assets.py`
- any new top-level ARC-AGI-2 experiment/result/report directory added to the
  workspace

The paper directory itself and the official dataset checkout are excluded from
“new experiment” detection.

## Intake procedure

For each newly observed artifact:

1. record relative path, modification time, SHA-256, producer/version, and
   parent experiment;
2. classify it as `proposal`, `projection`, `local_result`, `public_eval`, or
   `completed_kaggle_receipt`;
3. record which labels were accessible to generation, selection, and scoring;
4. record runtime, candidate budget, selector policy, and comparison anchor;
5. check whether the result is equal-compute and prospective;
6. admit it into `07_evidence_registry.md` only if its claim and limitation are
   explicit;
7. update ablation/failure tables without changing preregistered definitions.

## Current watch baseline

`results/technical_artifact_watch.csv` began as the 2026-09-08 baseline and is
current through the dated rows appended on 2026-09-09. Future reads
compare hashes and modification times against it. A changed file is reviewed as
a new version; it is never silently treated as the previous evidence.

The watch now includes both private conservative-agreement pairs, preferring
stable V2's BLAKE2b task seed while retaining V1 as a process-randomization
control; the strict V175 public-evaluation and retrospective-training audits;
the frozen 48/48 manifests; the run playbook; and the asset verifier. Notebook
preflight, a successful local unit test, or a source-author receipt can promote
an item from `unreviewed`, but none of them is a completed accuracy result.
Large model files receive a byte hash only after the completeness verifier
passes. Qwen's earlier gzip EOF was captured while its archive was still being
written, so it remains a corrected in-progress observation rather than final
corruption. The later extracted ten-file Qwen set and TRM checkpoint now pass
the final size/hash verifier; the asset gate is closed, while neural run,
runtime, and score evidence remain absent.

The first private stable-V2 development run is now a sealed runtime negative
receipt. Kaggle reports `COMPLETE`, but TRM failed before generating a candidate
and one NVARC task ended with an incomplete decode; every available policy was
byte-identical to the 48/50 KGMon anchor. The holdout remains sealed. A single
positive-initial-learning-rate compatibility smoke repaired checkpoint and
optimizer construction but failed before step one when its offline logger
passed `step=` to built-in `print`. No full rerun followed. One final
separately-versioned stdout-only logging smoke is preregistered with the same
task and unchanged data, policy, seed, optimizer, scheduler, budget, and timeout
semantics; a failed guard ends this TRM path. Published multi-perspective
TTT/PoE evaluation failures remain a literature negative control; they stop
view-compute expansion unless development first shows valid generations,
representation diversity, and exact-success association.

The one allowed AdamAtan2 bootstrap-LR repair was then exercised in a private,
solution-blind one-task/one-step Kaggle smoke. Checkpoint load and optimizer
construction passed, but the next pre-existing offline-logging adapter failed
before step 1 and produced no candidate. The smoke's fail-closed stop rule is
now active: no full stable-V2 rerun and no sealed-holdout access are authorized.

Confluence and Symbolica public-evaluation agent traces are literature intake,
not candidate receipts. They may inform the generate/execute/feedback pattern
only; cloud APIs, concurrency, cost, and public-label exposure prevent their
reported scores from serving as the Kaggle offline equal-compute anchor, and
their traces are excluded from the frozen holdout.

## Paper-side status labels

- `unreviewed`: detected but not read;
- `transient_partial`: download/extraction state; never paper evidence;
- `reviewed_not_evidence`: understood but missing provenance, control, or receipt;
- `negative_control`: valid evidence of a failed hypothesis;
- `supporting_evidence`: valid secondary evidence;
- `headline_candidate`: prospective equal-compute result awaiting final receipt;
- `headline_evidence`: completed, reproducible, and tied to a frozen policy.
