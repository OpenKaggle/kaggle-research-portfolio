# ARC Prize 2026 Paper Track research workspace

This directory is the paper-side record for the ARC-AGI-2 entry. It is kept
separate from leaderboard engineering. Technical artifacts are admitted here
only after their provenance, data boundary, result status, and limitations are
recorded.

## Current decision

- Paper Track status: **active conditional GO**.
- Registration: **both Paper Track and ARC-AGI-2 joined** as of 2026-09-09.
  Authenticated CLI snapshots report `userHasEntered=True`, all six ARC files
  were downloaded and hashed, and the Paper Track `NOTE.md` access probe
  succeeded. No competition notebook submission or prediction submission has
  yet been made.
- Working contribution: **risk-controlled allocation of two ARC attempts from
  a heterogeneous neural/program portfolio using demonstration-only evidence,
  calibration, residual diversity, and an anchor-preserving safety gate**.
- Paper continuation gate: demonstrate a prospective, reproducible improvement
  beyond a copied public notebook. The minimum evidence is either at least
  three additional exact public-evaluation outputs or at least 1.0 percentage
  point held-out pass@2 improvement at equal compute, plus an ablation that
  isolates why the gain occurs.
- Current symbolic evidence is negative: the archived 29-primitive DSL scored
  0/167 on the older GitHub evaluation checkout. The public V175 exact-rule
  library selected 0/167 there and, in a new label-detached reproduction,
  selected 0/172 on the authoritative Kaggle 2026 files under the same strict
  leave-one-demonstration-out policy. This refutes direct library transfer; it
  does not test the proposed typed object IR.
- The same V175 policy selected 307/1,076 public-training outputs with 100%
  retrospective precision, then selected none on the current evaluation set.
  Because the library was developed on public corpora, this is not a
  generalization estimate. It is a warning that within-task LOO evidence can
  collapse under task-distribution shift, and it justifies task-grouped outer
  validation plus support-distance abstention.
- The owned conservative-agreement controls now have frozen, disjoint 48-task
  development and 48-task planned-holdout notebooks, each balanced over four
  input-only work quartiles. All four notebook metadata files are private and
  both V1 and stable V2 pairs passed static preflight; stable V2 replaces the
  process-randomized task hash with BLAKE2b and is the preferred candidate.
  Stable V2 now has a completed failed-development receipt; no holdout run was
  launched. A later full-corpus V176 audit consumed all 1,000 training
  solutions, so the same planned slice is no longer pristine for a V176
  generalization claim. V1 remains an unrun control, and neither is a full
  paper method or a promotable accuracy result.
- A deterministic five-fold manifest now assigns all 1,000 public-training
  tasks to five 200-task folds, each with 50 tasks per input-work quartile and
  balanced ARC-AGI-1 provenance. The present canonical/object detector found
  no non-singleton groups; this means no duplicates were proven by those
  fingerprints, not that semantic analogues do not exist.
- Dataset revision audit shows Kaggle and the pinned GitHub checkout have the
  same 1,000 training tasks byte-for-structure, so the grouped training folds
  remain valid. Their evaluation task IDs also match, but only 114/120 tasks are
  exact: four have changed test inputs and two have changed training examples,
  raising the output denominator from 167 to 172. Kaggle files control all new
  evaluation claims.
- The TRM checkpoint and all ten Qwen files are complete and hashed. The
  fail-closed asset verifier passes with a frozen receipt, so the minimal neural
  asset set is reproducible. A neural development runtime receipt now exists,
  but it failed the cross-family and decode-completeness gates and is not a
  hidden score or a positive method result.
- The first private stable-V2 48-task development smoke test is sealed as a
  completed negative receipt. Kaggle finished within a 4,548-second upper
  bound with 16,082 MB observed peak allocation; all 48 task receipts and all
  submission schemas are present. KGMon and every fallback policy were 48/50
  and byte-identical. TRM produced no candidate because AdamAtan2 rejected the
  upstream zero optimizer initialization, and one NVARC task timed out after
  three of four decode batches. The development gate failed and the sealed
  holdout remains unopened. This is runtime negative evidence, not a
  cross-family accuracy result.
- A separate 2026-09-11 terminal-capture receipt now reconciles the historical
  `RUNNING` snapshot for that Stable V2 development kernel to official
  `COMPLETE`. The isolated capture contains 239 output files and one log; their
  contents were not reviewed, sealed labels were not opened, and conflicting
  official time fields leave the exact finish time `UNKNOWN`. The receipt is
  operational provenance only and supplies no generalization evidence. It does
  not describe the distinct logging-only V2 repair smoke below.
- A solution-blind one-task/one-step compatibility smoke confirmed that the
  positive-LR repair loads the checkpoint and constructs the optimizer, then
  failed before step one because an offline logging rewrite passed `step=` to
  built-in `print`. It emitted no grid or submission, so no full rerun began.
- The final versioned stdout-only logging smoke was pushed as private kernel
  version 1 and was last observed `RUNNING` at 06:27:41 CST, before a later
  local-only boundary at 06:34:25 CST. Its terminal status is unknown. Local
  actual-source regression and exact-package CPU micro-smoke checks pass, but
  cannot replace the Kaggle guards. Reading status or downloading artifacts
  requires explicit authorization; do not upload a duplicate.
- Two input-only overlay rules derived after inspecting the two development
  misses give separate 49/50 ablations and a combined 50/50 local replay with
  no harms or ambiguities. This is post-hoc implementation/complementarity
  evidence only, not Accuracy, Progress, Novelty, or unseen generalization. The
  frozen V3 notebooks have not been pushed. A historical-integrity audit shows
  that the earlier source audit loaded all 1,000 training solutions, selected
  only the two development tasks, and thereby made V176's zero-selection
  behavior on the disjoint 48-task slice knowable before any run. That slice is
  unrun but contaminated for V176 method-generalization evidence; it may support
  unchanged-parent runtime/format checks only. V3 holdout promotion is blocked
  until a new candidate version uses an evaluator-controlled labeled corpus
  whose solutions were never available during method construction. Re-splitting
  the same 1,000 tasks cannot repair this boundary.
- A local corpus-eligibility audit now finds no verified replacement that is
  simultaneously labeled, rule-frozen before solution access, license-clear,
  nonoverlapping, and comparable enough to support an ARC-AGI-2 distribution
  claim. ARC-AGI-1 train/evaluation, ARC-AGI-2 train/evaluation, and ConceptARC
  were all covered by the bundled five-corpus V175 audit (2,080 tasks/2,563
  outputs); the parent source reports complete ConceptARC coverage at 160/160
  tasks and 480/480 outputs. V176 therefore defaults to a systems-negative
  paper. 1D-ARC, MiniARC, community, or synthetic sets may be used only as
  explicitly labeled domain-shift mechanism tests unless a separate
  comparability proof exists.
- A genuinely separate fixed typed-object correspondence family was frozen
  before a one-shot internal audit on 181 grouped-fold tasks/197 outputs that
  exclude both 48-task benchmark splits and all preimplementation task displays.
  It selected one output, which was exact, with zero incorrect selections in
  108.293 local CPU seconds and 317 MiB peak RSS. That sole hit was already
  solved by frozen V175 `scale:3`; exclusive and union gain were zero. V1 is
  therefore stopped and cannot be tuned on that audit fold. This is prospective
  implementation evidence but not development-stage, holdout, public-evaluation,
  or Kaggle evidence.
- A 1,672 × 941 score-free cover candidate now depicts heterogeneous candidates,
  an evidence sieve, two output slots, and an explicit anchor fallback. Its
  prompt, SHA-256, alt text, and public-risk audit are frozen; Kaggle attachment
  remains pending.
- Published multi-perspective TTT/PoE results are retained as a negative
  boundary: their evaluation variants failed generation. View agreement is
  therefore an unvalidated feature, and view-based extensions stay stopped
  until valid-generation and exact-success evidence exists on development.
- A high leaderboard score alone is not the contribution. A larger candidate
  pool without a trustworthy selection result is also not the contribution.

## Files

- `00_rules_and_registration.md`: controlling rules, deadlines, team and
  license constraints.
- `01_research_questions.md`: falsifiable research questions and claim limits.
- `02_method.md`: candidate pool, evidence model, selector, attempt allocator,
  and safety gate.
- `03_validation_protocol.md`: locked data boundaries, leakage controls,
  metrics, uncertainty, and promotion gates.
- `04_ablation_plan.md`: equal-compute ablations and interpretation rules.
- `05_failure_taxonomy.md`: mutually exclusive primary failure labels and
  secondary tags.
- `06_reproducibility_checklist.md`: release and rerun checklist.
- `07_evidence_registry.md`: source-to-claim chain, including negative results.
- `08_writeup_skeleton.md`: 1,500-word Kaggle Writeup structure and budget.
- `09_authorship_and_submission_manifest.md`: team-match, author contribution,
  linked-artifact, license, and final sign-off record.
- `10_related_work_and_claim_boundaries.md`: primary-source citation plan and
  novelty boundaries.
- `11_selector_preregistration.md`: frozen feature, calibration, conditional
  allocation, OOD, uncertainty, and tie-breaking policy for the full method.
- `12_argument_tree_and_evidence_gaps.md`: six-dimension scorecard, claim tree,
  milestones, and lowest-dimension repair loop.
- `13_publication_binding_checklist.md`: cover, public notebook, submission ID,
  project-link, permission, and public-disclosure binding record.
- `14_license_and_public_risk_audit.md`: asset-by-asset license evidence,
  public-package allowlist, redaction rules, and release blockers.
- `drafts/writeup_v0.1.md`: saved English draft with explicit receipt
  placeholders and no projected score presented as fact.
- `TECHNICAL_FEED.md`: intake protocol for new ARC-AGI-2 technical artifacts.
- `manifests/grouped_folds_v1.json`: deterministic five-fold task assignment.
- `manifests/typed_object_family_audit_v1.json`: implementation-sealed fold-0
  audit IDs and file hashes, excluding the existing development/holdout splits
  and preimplementation task displays.
- `schemas/candidate_receipt_v1.schema.json`: machine-readable candidate
  receipt contract.
- `tools/build_grouped_folds.py`: leakage-resistant fold builder.
- `tools/build_typed_object_audit_manifest.py`: deterministic builder for the
  typed-object family's one-shot, label-blind internal audit manifest.
- `tools/validate_candidate_receipts.py`: fail-closed candidate receipt check.
- `tools/analyze_paired_results.py`: whole-task bootstrap, paired sign test,
  oracle gain, selector regret, and oracle-gap recovery.
- `tools/analyze_family_coverage.py`: evaluator-side exclusive-solve,
  pairwise-overlap, and oracle-union audit for complete family result tables.
- `tools/validate_failure_log.py`: primary-code and gate-state consistency
  checks for failure adjudication.
- `tools/audit_dataset_revision.py`: authenticated Kaggle-versus-GitHub task
  revision audit and evaluator-only materialization.
- `tools/audit_release_manifest.py`: fail-closed exact-file hash, path,
  notebook-output, credential, and evaluator-label audit for public packages.
- `tools/audit_notebook_dependencies.py`: exact notebook/metadata dependency
  inventory and fail-closed public-access/license receipt audit.
- `tools/audit_writeup.py`: deterministic word-budget, section, six-dimension,
  numerical-claim evidence, official no-training-performance rule, placeholder,
  and final platform-binding audit.
- `tools/audit_submission_readiness.py`: one local aggregate gate over the
  Writeup, pipeline, release, dependencies, cover, bindings, and approvals.
- `tools/audit_three_stage_pipeline.py`: fail-closed development → sealed
  holdout → competition ordering, score arithmetic, seven-family coverage,
  runtime/memory/failure, format, hash, submission-ID, hidden-label boundary,
  anti-tuning, ordered failed-stage diagnostics, and persistent revalidation of
  every bound runtime-smoke source path/hash. It also verifies the frozen
  holdout-integrity receipt and blocks any contaminated holdout promotion.
- `tools/audit_v3_holdout_integrity.py`: reconstructs only task identities from
  public challenge inputs, never reads the training-solution file, and proves
  why the historical full-corpus V176 audit invalidates the planned 48-task
  slice as sealed method-generalization evidence.
- `tools/build_runtime_smoke_receipt.py`: local-only conversion of an already
  captured read-only terminal-status manifest and any downloaded outputs into
  a fixed-identity receipt. It rehashes the pushed notebook/metadata and the
  source log, grid, and smoke receipt; it never invokes Kaggle.
- `tools/commit_runtime_smoke_receipt.py`: revalidates every source path/hash,
  audits a prospective contract, and atomically sets only the smoke prerequisite
  to `PASSED` or `FAILED`. A pass exposes development as the next action but does
  not authorize or start it.
- `tools/authorize_stage.py`: local-only, atomic transition from the sole eligible
  unbound stage to `RUNNING`. It requires an exact one-run user-authorization
  receipt bound to the current contract bytes and frozen notebook, verifies that
  it postdates the preceding terminal receipt, and performs no Kaggle action.
- `tools/build_stage_measurement.py`: local-only bridge from completed V3 run
  evidence to the exact stage-measurement payload. For labeled stages it
  independently re-scores method and anchor and decomposes both attempts. For
  competition it rejects hidden correctness and accepts only the captured
  terminal submission ID/aggregate score. Both branches validate grids, source
  hashes, runtime/memory/failures, and assign one deterministic primary task
  family from demonstrations only; the taxonomy is operational rather than a
  ground-truth ARC concept label.
- `tools/build_stage_receipt.py`: creates a normalized receipt only for an
  already-authorized `RUNNING` stage, injects its frozen policy, hashes the
  real notebook/input/submission/artifact files, derives the precommitted
  competition target gap, and validates the result before writing it.
- `tools/commit_stage_receipt.py`: revalidates a terminal receipt, audits the
  prospective contract, detects concurrent contract/receipt changes, and then
  atomically binds the receipt hash and marks only that running stage complete.
- `tools/commit_stage_failure_receipt.py`: revalidates a terminal diagnostic
  receipt and atomically marks only its authorized running stage `FAILED`. The
  failed candidate contract is stopped and preserved; a retry requires a new
  version rather than erasing failure history.
- `schemas/stage_receipt_v1.schema.json`: Draft 2020-12 normalized receipt
  contract, with separate labeled-stage and hidden-competition branches and a
  precommitted competition-score reference.
- `schemas/stage_failure_receipt_v1.schema.json`: Draft 2020-12 failed-stage
  contract for ordered format/cache/seed/budget checks, seven family buckets,
  counterexample/ablation evidence, and solver-family stopping rules.
- `schemas/stage_authorization_v1.schema.json`: exact-field, one-stage user
  authorization contract binding the current contract bytes, frozen notebook,
  allowed external action, one-run limit, terminal evidence collection, no
  leaderboard selection, and no future-stage authorization.
- `schemas/competition_observation_v1.schema.json`: exact-field terminal
  observation contract for the scored competition run; it requires a completed
  submission ID, aggregate score/scope, runtime/memory/failures, and five source
  hashes while forbidding hidden-correctness fields and leaderboard selection.
- `tests/test_paper_tools.py`: regression check for the paper-side tooling.
- `tests/test_release_audit.py`: positive and fail-closed release-audit
  regressions.
- `tests/test_notebook_dependency_audit.py`: clean-inventory positive fixture
  plus undeclared, unverified, private, hash-drift, and dirty-notebook failures.
- `tests/test_v3_dependency_local_evidence.py`: recomputes the local source
  hashes and clean historical bootstrap-kernel metadata without network access.
- `tests/test_writeup_audit.py`: draft-pass and final-fail-closed Writeup
  regressions.
- `tests/test_submission_readiness.py`: active-state blocker inventory,
  all-green, hash-drift, and premature-final-state regressions.
- `tests/test_trm_compat_v2.py`: actual-source, artifact-hash, scheduler,
  logger, notebook, and post-push safety-boundary regression for V2.
- `tests/test_deadline_receipt.py`: frozen deadline arithmetic, prior-snapshot
  hash, source URL, and conservative reconciliation regression.
- `tests/test_public_kaggle_deadline_receipt.py`: public Kaggle deadline,
  prior-receipt identity, cross-source agreement, and no-private-access boundary
  regression.
- `tests/test_three_stage_pipeline.py`: complete-pipeline positive fixture plus
  premature holdout, holdout regression, missing submission ID, leaderboard
  tuning, missing-family, wrong-scope, and preregistration-drift fail-closed
  regressions, plus rejection of fabricated hidden-test correctness and
  unregistered receipt fields.
- `tests/test_three_stage_pipeline_audit.py`: active-boundary regressions for
  terminal-smoke evidence, last-state hashes, stage authorization, contract
  completion state, holdout-integrity binding, and exact task/output scope.
- `tests/test_v3_holdout_integrity.py`: deterministic reproduction of the
  contamination finding, including 48 tasks/49 outputs, zero V176 selections,
  a task-ID-set hash without task-ID disclosure, and the no-solution-read
  boundary.
- `tests/test_runtime_smoke_receipt.py`: passing and terminal-error transitions,
  plus rejection of running observations, missing COMPLETE artifacts, and
  pre-commit or post-bind source drift and unregistered terminal fields without
  silently advancing the contract.
- `tests/test_stage_receipt_schema.py`: three valid stage fixtures plus schema
  rejection of hidden correctness, missing families, invalid scores/timestamps,
  and unregistered fields; run with the repository virtual environment.
- `tests/test_stage_failure_receipt.py`: valid format/solver/streak fixtures plus
  fail-closed diagnostic order, counterexample, family, solver-switch, and
  public-research reproduction regressions.
- `tests/test_commit_stage_failure_receipt.py`: positive atomic failure commits
  for all three stages plus byte-preserving rejection of pre-authorization
  starts, wrong-stage/complete receipts, project-external receipts, and inactive
  target stages.
- `tests/test_build_stage_receipt.py`: receipt-builder regressions for frozen
  policy injection and actual file hashes, plus rejection of an unauthorized
  stage, notebook substitution, extra measurement fields, and fabricated
  hidden-test correctness.
- `tests/test_build_stage_measurement.py`: replays the real Stable-V2 artifacts
  to recover 48/50, its timeout/failure, and failed promotion gates; synthetic
  labeled and competition fixtures exercise measurement → normalized receipt
  end to end, including null hidden correctness, task/failure reconciliation,
  submission ID/score propagation, and rejection of leaked correctness fields.
- `tests/test_competition_observation_schema.py`: schema/tool field parity plus
  valid terminal, hidden-field, leaderboard-selection, non-terminal, and
  duplicate-timeout regressions.
- `tests/test_stage_authorization_schema.py`: schema/tool field parity plus
  rejection of multi-run, future-stage, leaderboard-selection, naive-timestamp,
  and unregistered-field receipts.
- `tests/test_stage_authorization.py`: positive atomic transitions for all three
  stages plus byte-preserving rejection of wrong action scope, stale contract
  identity, and development activation while the runtime smoke remains unknown.
- `tests/test_commit_stage_receipt.py`: positive partial/final transition
  regressions plus byte-preserving rejection of invalid, wrong-stage,
  out-of-project, and currently unauthorized receipts.
- `results/ablation_table.csv`: preregistered result table.
- `results/failure_log.csv`: per-output failure record.
- `results/paired_results_template.csv`: input contract for paired analysis.
- `results/family_results_template.csv`: complete per-family evaluator input
  contract for coverage and overlap analysis.
- `results/technical_artifact_watch.csv`: current shared-artifact snapshot.
- `results/typed_object_family_audit_v1_2026-09-09.json`: frozen one-shot
  typed-object result, code/runner/manifest hashes, resource use, and claim
  boundary; its single exact selection adds zero union over V175.
- `results/development_stable_v2_status_*.json`: immutable point-in-time copies
  of mutable Kaggle run manifests; running status never counts as a result.
- `results/development_stable_v2_failed_smoke_2026-09-09.json`: fail-closed
  paper decision from the first completed development report, linked sealed
  receipt, paired analysis, and runtime logs.
- `results/development_stable_v2_terminal_capture_receipt_2026-09-11_v1.json`:
  immutable reconciliation of Stable V2 development kernel version 1 to
  official `COMPLETE`, with a 239-output/one-log unreviewed capture inventory,
  `UNKNOWN` exact finish time, unopened sealed labels, and no generalization
  claim; SHA-256
  `3480807c7a13111956513c5c609b4afdd58b9f18d112fb3d0a86fec9eb22c03f`.
- `results/trm_adam_lr_compat_smoke_failed_2026-09-09.json`: terminal receipt
  for the solution-blind one-task/one-step optimizer compatibility smoke.
- `results/trm_wandb_log_compat_smoke_v2_local_ready_2026-09-09.json`: immutable
  historical pre-push V2 manifest; the later pushed/running boundary is kept in
  `../kaggle_runs/trm_wandb_log_compat_smoke_v2/local_preflight_receipt.json`.
- `results/trm_wandb_log_compat_smoke_v2_local_behavioral_regression_2026-09-09.json`:
  local-only behavior and boundary receipt; forbidden as Accuracy evidence.
- `results/exact_overlay_v3_posthoc_development_2026-09-09.json`: frozen
  post-hoc V3 development replay, ablations, hashes, and claim limits.
- `results/v3_holdout_integrity_audit_2026-09-09.json`: frozen finding that
  the planned V176 holdout is ID-disjoint but not method-sealed because the
  earlier full-corpus audit exposed all 1,000 solutions; it blocks promotion
  and permits runtime/format claims only.
- `results/v176_independent_corpus_availability_audit_2026-09-09.json`: local
  five-corpus solution-access inventory and the fail-closed decision that no
  eligible ARC-AGI-2 generalization corpus is currently verified; it records
  systems-negative as the default and a pre-access contract for reopening.
- `../artifacts/trm_optimizer_logger_micro_smoke/local_micro_smoke_receipt.json`:
  deterministic exact-package CPU path check; not a Kaggle smoke substitute.
- `results/official_arc_prize_deadline_recheck_2026-09-09.json`: historical
  public ARC Prize date-only receipt that records its November 8 Paper date
  against the prior Kaggle November 9 snapshot; preserved as the earlier side
  of the still-open cross-site discrepancy.
- `results/public_kaggle_deadline_recheck_2026-09-09T184121+0800.json`: public
  Kaggle-page confirmation of ARC November 2, 23:59 UTC and Paper November 9,
  23:59 UTC, while preserving November 8 as the conservative internal cutoff.
- `results/model_asset_license_access_2026-09-09.json`: direct, point-in-time
  Kaggle public-access, version, license, size, and local-identity receipt for
  the exact Qwen and TRM model assets.
- `results/v3_dependency_local_evidence_2026-09-09.json`: local identity,
  embedded license files, and historical `is_private=false` metadata for the
  two unresolved V3 dependencies; not a current access receipt.
- `manifests/public_release_preflight_v1.json`: passing preliminary allowlist
  for the local V2 smoke and publication assets; explicitly not a final scored
  release manifest.
- `manifests/v3_notebook_dependency_inventory_v1.json`: exact frozen-V3
  dependency inventory; intentionally blocked on two unverified public inputs.
- `manifests/writeup_evidence_contract_v1.json`: hash-bound 1,500-word and
  six-rubric-dimension contract for the current draft and eventual final
  platform submission.
- `manifests/submission_readiness_v1.json`: hash-bound aggregate submission
  state; a structural pass with blockers is explicitly not final readiness.
- `manifests/three_stage_pipeline_v1.json`: active V3 execution state and
  immutable stage hypotheses plus the frozen evaluator-side measurement-builder
  hash; a structural pass is explicitly not a stage or Kaggle result.
- `media/cover_candidate_v2.png` and `media/cover_manifest.md`: preferred
  score-free cover candidate, exact prompt, alt text, hash, and public-risk
  audit. The file is not yet attached to Kaggle.
- `results/dataset_revision_audit_2026-09-09.json`: deterministic
  Kaggle-versus-GitHub revision audit.
- `evaluator_only/kaggle_evaluation_2026_09_09/`: hashed, segregated copy of
  the current 120-task/172-output evaluation set used only by evaluators.
- `../typed_object_correspondence.py`, `../run_typed_object_audit.py`, and
  `../analyze_typed_object_complementarity.py`: frozen independent solver,
  one-shot label-detached evaluator, and post-run V175 union audit.
- `../test_typed_object_correspondence.py` and
  `../test_typed_object_audit.py`: synthetic inference, determinism,
  test-output rejection, evaluator detachment, and task-hash regressions.

## Non-negotiable claim discipline

1. A projection, oracle union, local estimate, or notebook metadata field is
   never reported as a Kaggle score.
2. Public-evaluation labels never enter candidate generation or the deployed
   selector. Any prior inspection is disclosed in the validation protocol.
3. NeuroGolf is evidence for engineering and hidden-set failure modes, not
   evidence that a solver generalizes to ARC-AGI-2.
4. Results are reported per task output using exact match and pass@2, matching
   the competition metric.
5. A result becomes paper evidence only with a frozen policy, input hashes,
   runtime receipt, and rerunnable artifact.
6. The Kaggle 2026 evaluation has 172 outputs and is authoritative. The older
   GitHub checkout has 167 and remains only a versioned negative control. The
   source-bundle 172-output receipt lacks Kaggle file hashes; its zero-coverage
   slice is now independently reproduced on the authenticated Kaggle files but
   cannot support any positive result.
7. An asset under download or extraction has no stable hash and cannot support
   reproducibility. Qwen's earlier gzip EOF was observed while an active
   download was extending the archive and is retained only as a corrected
   transport observation. The final extracted files now pass the fail-closed
   size/hash verifier; that proves asset identity, not model performance.
