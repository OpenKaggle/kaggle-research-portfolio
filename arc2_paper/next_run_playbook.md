# ARC-AGI-2 next-run playbook

## Deadline freeze

- The current official ARC Prize overview, rechecked 2026-09-09, gives
  **November 2, 2026** for competition submissions and **November 8, 2026**
  for papers. A separate public Kaggle-page recheck confirms ARC-AGI-2 at
  November 2, 23:59 UTC and Paper Track at November 9, 23:59 UTC, matching the
  earlier authenticated snapshot. Use November 8 at 23:59 UTC as the internal
  Paper cutoff while the one-day publisher discrepancy remains.
- Architecture freeze (D-21): **October 12, 2026**.
- Notebook and dependency freeze (D-7): **October 26, 2026**.
- Validation and final selection only (D-3): **October 30, 2026**.
- The deadline receipt is
  `paper/results/official_arc_prize_deadline_recheck_2026-09-09.json`.
- The public Kaggle reconciliation receipt is
  `paper/results/public_kaggle_deadline_recheck_2026-09-09T184121+0800.json`.

## Completed prerequisites

- Qwen BF16 v1 and the preferred TRM checkpoint are complete and checksummed;
  keep `public_assets/verification.json` with any run receipt.
- Keep the current zero-hit DSL/object results as negative controls. Do not add
  either to a submission slot without a training-perfect and leave-one-out-safe
  candidate.
- Run `validate_candidate_notebook.py` and `test_selector_policy.py` after every
  notebook rebuild.

## Active post-Join sequence

1. `sync_after_join.py` completed: all six official files are hashed and aligned;
   Kaggle reports training 1000/1076, evaluation 120/172, test 240/259.
2. Private Stable V2 run ID `348340917` is complete and sealed. It produced
   48/50 on the 48-task development split, but TRM failed before candidate
   generation and one NVARC task timed out. The hard runtime/cross-family gates
   failed, so the disjoint holdout was not opened. The 2026-09-11 local receipt
   (SHA-256 `3480807c7a13111956513c5c609b4afdd58b9f18d112fb3d0a86fec9eb22c03f`)
   supersedes the earlier `RUNNING` interpretation for this kernel with official
   `COMPLETE`. Its isolated 239 output files and one log remain unreviewed,
   sealed labels remain unopened, and the exact finish time stays `UNKNOWN`
   because official time fields conflict. This is not generalization evidence.
3. The single-change TRM logger smoke V2 had already been pushed and was last
   observed `RUNNING` at 06:27:41 CST. A later local-only safety boundary arrived
   at 06:34:25 CST. Do not query its current status, upload, rerun, or submit
   anything without explicit user authorization.
4. The two shared development misses now have minimal counterexamples and fixed
   input-only rules. The locally frozen `conservative_exact_overlay_v3` preserves
   Stable-V2 attempt one and replaces attempt two only for one unique grid from
   rules exact on every demonstration. Single-rule replay gives 49/50 + 49/50;
   combined replay gives post-hoc 50/50 with no harms or ambiguities. This is
   development fit, not generalization evidence.
5. Development and disjoint planned-holdout V3 notebooks, embedded overlay
   source, and preregistrations are frozen locally, but the planned 48-task slice
   is now quarantined for V176 generalization. The earlier source audit loaded
   all 1,000 training solutions and made V176's zero-selection behavior on that
   slice knowable before a run. Re-splitting those 1,000 tasks cannot repair the
   boundary. Do not run or report that slice as holdout Accuracy, generalization,
   Progress, or Novelty. Create a new candidate/contract around an
   evaluator-controlled labeled corpus whose solutions were never available
   during method construction; if none exists, pivot V176 to systems/negative
   evidence. The active pipeline's next action is
   `REPLACE_CONTAMINATED_HOLDOUT_BEFORE_EXTERNAL_RUN`.
6. Only after that replacement is hash-bound may an explicitly authorized
   read-only check capture the existing TRM smoke's terminal status. Save the
   result as a post-boundary terminal observation
   with the exact kernel/version, raw status, timestamp, and whether terminal
   outputs were downloaded. Build its normalized local receipt with
   `paper/tools/build_runtime_smoke_receipt.py`, then bind it with
   `paper/tools/commit_runtime_smoke_receipt.py`. Both commands reject a
   non-terminal observation, mismatched V2 runtime/notebook/metadata, incomplete
   passing guards, changed source artifacts, replay, and any file outside this
   project. The commit changes no stage state and performs no external action.
7. Before and after every authorized stage, run
   `paper/tools/audit_three_stage_pipeline.py
   paper/manifests/three_stage_pipeline_v1.json`. After the prerequisite passes,
   record the user's decision in an exact `stage_authorization_v1` receipt bound
   to the current contract SHA-256, eligible stage, frozen notebook SHA-256, and
   that stage's one-run external action. Then run
   `paper/tools/authorize_stage.py`; it verifies prerequisite ordering and
   atomically changes only that stage to `RUNNING`. It does not query, upload,
   run, or submit on Kaggle, and it never authorizes a later stage. Execute the
   receipt's one external action only under the corresponding explicit user
   authorization. A contaminated integrity receipt prevents the authorizer from
   exposing any V3 stage. A successor development receipt must compare its method
   and unchanged control under the same repaired runtime with one sole
   algorithmic factor; holdout and competition may change only the frozen data
   split.
8. After an authorized labeled stage produces terminal artifacts, leave its
   contract state as `RUNNING`. First seal the raw benchmark with
   `finalize_kaggle_benchmark.py`, including the authoritative completion time
   and observed peak memory. Then run the contract-bound, local-only
   `paper/tools/build_stage_measurement.py` to independently rescore method and
   anchor, verify every finalized source hash and format guard, and generate the
   seven-bucket demonstration-only primary-family table plus the exact
   measurement payload. Pass that payload to `paper/tools/build_stage_receipt.py`.
   The V2 real-artifact replay is a regression check only; it correctly remains
   48/50 with one timeout and failed promotion gates. Bind a passing receipt with
   `paper/tools/commit_stage_receipt.py`; that command revalidates both the
   receipt and prospective contract before atomically adding the SHA-256 and
   marking only that stage `COMPLETE`. Rerun the pipeline audit before promoting
   to the next stage.
9. If a stage terminates without passing its gates, do not use a partial success
   receipt. Create a `stage_failure_receipt_v1` record and check format, cache,
   seed, then budget in that exact order. Only after all four pass may the cause
   be classified as solver failure, which requires a seven-bucket failure table,
   minimal counterexample, and single-variable ablation. Two no-improvements
   require a different solver family; three same-class failures additionally
   require a completed, hash-bound reproduction of cited public research. Bind
   the validated record with `paper/tools/commit_stage_failure_receipt.py`; it
   atomically marks only that authorized running stage `FAILED` and returns
   `STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT`. Do not reset that stage in
   place: preserve its receipt and create a new candidate/contract version for
   any permitted single-change repair or solver-family switch.

### Cached complementarity audit

Before proposing any new selector, use only completed NVARC/TRM/program artifacts
to report pairwise overlap, exclusive solves, the two-slot oracle, and the
oracle-to-final gap on development. Do not extend the analysis to the quarantined
48-task slice as accuracy evidence. A successor may run the same diagnostic once
on a genuinely untouched, frozen evaluator-controlled holdout. This is a
diagnostic, not permission to tune on that split.

- Stop selector work if the sealed two-slot oracle improves on KGMon top-2 by
  less than one percentage point, or if every additional solver has zero
  exclusive solves.
- If an oracle gap exists, first compare unchanged top-2 with a no-replacement
  best-distinct allocator at equal generation cost.  A learned selector is only
  justified if the simple allocator cannot recover the gap on development.
- Treat PoTRE (arXiv:2607.20268) and Compositional Neuro-Symbolic Reasoning
  (arXiv:2604.02434) as public-evaluation, external-model evidence for the
  *measurement protocol* only.  Their reported scores are not offline Kaggle
  baselines and do not relax the no-evaluation-label selection boundary.

## First competition rerun

- Do not enter this section under the contaminated V3 contract. It requires a
  passing successor development and genuinely untouched holdout receipt.
- Freeze code and input versions from the passing benchmark.
- Confirm internet off, four L4 GPUs, and the exact dataset/model attachments in
  `kernel-metadata.json`.
- Run once; validate task keys, output counts, attempt keys, 1–30 dimensions,
  rectangularity, and colors 0–9 before finalization.
- Save the notebook version, submission ID, wall time, observed peak memory,
  completed/timed-out task list, output hash, public score, and failure tail.
- Capture those fields exactly once in a
  `competition_observation_v1.schema.json` receipt with mode
  `READ_ONLY_KAGGLE_SUBMISSION_RECEIPT`, authoritative `COMPLETE` status, source
  hashes for notebook/submission/input manifest/run log/kernel metadata, and
  `public_leaderboard_used_for_selection=false`. While the competition stage
  remains `RUNNING`, pass that receipt and the downloaded files to
  `paper/tools/build_stage_measurement.py`; then pass its output to the existing
  stage-receipt builder and atomic commit tool. The measurement builder performs
  no Kaggle action and refuses non-terminal, hash-drifted, over-budget, or
  hidden-correctness-bearing observations.
- Hidden test labels are unavailable: record only the Kaggle-returned aggregate
  score. Per-family competition reporting is operational coverage/failure only;
  do not infer per-output, attempt-level, or per-family correctness from the
  leaderboard value.
- Report the third-stage gap only as `returned score - 0.85`, using the
  precommitted official target and source-receipt hash in the stage contract.
  Preserve `score_scope`; a public-leaderboard gap is contextual and is not an
  estimate of private-evaluation accuracy or a same-task anchor delta.
- If score is below 29.0 or runtime exceeds 11h30, allow one reproducibility
  repair. Otherwise stop that version and diagnose the missing 3–5 point gap by
  solver union and timeout families before changing algorithms.

## Paper-safe record

Every run gets one row in `experiment_log.csv`. Attach provenance, licenses,
input hashes, fixed candidate and selector policies, per-family failures,
runtime, solver overlap, and the single changed factor. Public-evaluation labels
may score a frozen policy but may never enter candidate generation or policy
selection. Hidden test outputs and leaderboard-only cherrypicking are excluded.
