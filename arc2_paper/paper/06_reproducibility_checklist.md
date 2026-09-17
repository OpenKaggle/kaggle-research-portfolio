# Reproducibility and release checklist

## Identity and scope

- [ ] Paper title, version, date, authors, author order, and contributions fixed.
- [ ] Paper team exactly matches the linked ARC-AGI-2 team; effective size ≤5.
- [ ] Every member joined both competitions and accepted the same team membership.
- [ ] Linked Kaggle submission ID and public notebook version recorded.
- [ ] No competition code was privately shared outside the official team.

## Data and leakage boundary

- [x] Authenticated ARC-AGI-2 six-file manifest, per-file hashes, GitHub commit,
  and Apache-2.0 notice recorded.
- [x] Development, calibration, grouped validation, public evaluation, and
  hidden Kaggle boundaries documented.
- [x] V1 near-duplicate/augmentation groups generated before folds; manifest
  SHA-256 is
  `c6112e37b29296b0139764de43611f01475d421cad5da7cd05f849d700a07a99`.
- [x] ARC-AGI-1 provenance reference pinned at commit
  `399030444e0ab0cc8b4e199870fb20b863846f34`.
- [ ] Known source/augmentation traces added if they become available; semantic
  analogue review completed before a headline outer-fold result.
- [ ] Candidate generator and selector read demonstrations/test inputs only,
  never held-out outputs.
- [x] Prior public-evaluation exposure disclosed.
- [x] Kaggle-versus-GitHub revision audit completed; training is exact and six
  evaluation tasks differ, so 172-output Kaggle files control new results.
- [ ] Any human intervention is timestamped and excluded from hidden inference.

## Code, models, and licenses

- [x] A dated license/public-risk audit distinguishes direct evidence,
  declarations, missing notices, release allowlists, and blockers in
  `14_license_and_public_risk_audit.md`.
- [ ] Original code released under MIT-0.
- [ ] Paper/writeup and required winning-submission grant covered by CC BY 4.0.
- [x] Third-party code/model/data source, author, version, URL, license, and
  SHA-256 recorded.
- [x] Exact Qwen and TRM asset APIs returned public access on 2026-09-09;
  version, license, size, and local hashes are frozen in the asset receipt.
- [x] `verify_public_assets.py --hash` passes before any neural run; receipt
  SHA-256 is
  `1823852c94d0231c52d846b8fb1d6e1ea480562657c3154a5de0d8f4adaa12c5`.
- [x] No hash from a partial download or extraction was entered into the final
  asset manifest.
- [ ] Apache, MIT, CC0, and other inherited notices preserved verbatim.
- [ ] No dependency prevents commercial use or public reproduction under the
  controlling rules.
- [x] Exact TRM checkpoint license/public-access receipt and exact Qwen
  variation license snapshot archived; neither is inferred from model ancestry
  or a downstream notebook.
- [x] The antlr4 4.9.3 wheel's missing notice is supplied from the official
  exact-version tag and hashed in the release audit.
- [x] Fail-closed exact-file release auditor and regression exist; the
  11-file/two-external-asset preliminary V2-smoke manifest passes with no
  violations and cannot be mistaken for a final release manifest.
- [ ] Frozen V3 notebook dependency inventory resolves every source in its
  Kaggle metadata to a current public-access and license receipt. Hash and
  set coverage pass, but the source dataset and bootstrap notebook remain
  explicitly unverified and block a public-notebook claim.

## Environment and compute

- [ ] Kaggle image/docker version recorded.
- [ ] Accelerator type/count, CPU/RAM, Python/CUDA/library versions recorded.
- [ ] Internet disabled in the final notebook.
- [ ] Global and per-solver seeds fixed and logged.
- [ ] Candidate caps, augmentation counts, epochs, beam/search budgets, and
  stopping rules frozen.
- [ ] Wall time ≤11h30, peak memory, and per-stage timings recorded.
- [ ] A clean rerun from attached inputs completes without manual action.
- [x] The already-pushed V2 smoke's last `RUNNING` observation, later
  local-only boundary, and unknown terminal state are separately hash-bound;
  local checks are not treated as a Kaggle completion receipt.
- [x] Stable V2 development run 348340917 is separately reconciled to official
  `COMPLETE` by the 2026-09-11 terminal-capture receipt. Its 239 output files
  and one log remain unreviewed, sealed labels remain unopened, exact finish
  time is `UNKNOWN`, and the receipt is not generalization evidence.

## Candidate and selector receipts

- [x] Candidate receipt V1 schema and fail-closed validator implemented and
  covered by a valid fixture regression.
- [ ] Every unique candidate has task/output ID, family, version, seed, grid
  hash, compute, and provenance.
- [ ] Exact deduplication retains all contributing family identities.
- [ ] Evidence vector is recomputable from demonstrations only.
- [ ] Calibration model and fold assignment hashes recorded.
- [x] Primary selector features, model class, nested cross-fitting, weighting,
  support rule, bootstrap gate, fail-closed behavior, and tie breaks frozen
  before an owned neural accuracy result.
- [ ] Attempt allocation and every abstention/override have a machine-readable
  reason.
- [ ] Anchor policy and displaced candidates are retained for comparison.

## Results

- [x] Whole-task paired bootstrap/sign-test analyzer implemented and covered by
  a small regression fixture.
- [x] Failure-code precedence and machine consistency checks frozen before any
  result row was created.
- [ ] All preregistered A/E/B ablations completed or marked missing with reason.
- [ ] Equal-compute and same-candidate-pool comparisons clearly separated.
- [ ] Exact pass@2 denominator matches task outputs.
- [ ] Paired task bootstrap interval and benefit/harm counts reported.
- [ ] Oracle union is labeled non-deployable and never called a score.
- [x] Current negative results and failed gates are retained, including run
  348340917 and the failed first TRM compatibility smoke.
- [x] V3 development/holdout notebooks and preregistrations are frozen; its
  50/50 development replay is labeled post-hoc and the planned holdout remains
  unrun but is classified `CONTAMINATED_FOR_V176_GENERALIZATION` because an
  earlier audit consumed all 1,000 source-corpus solutions.
- [x] A hash-bound three-stage contract enforces terminal smoke evidence,
  expected task/output scope, authorization, same-notebook receipts,
  anti-leaderboard tuning, final submission identifiers, and a hard block on
  promotion through the contaminated V176 holdout.
- [ ] Obtain a rule-frozen, evaluator-controlled labeled corpus whose solutions
  were never available during method construction; otherwise keep the paper a
  systems/negative result and make no V176 generalization, Progress, or Novelty
  claim. Repartitioning the same 1,000 tasks is not acceptable.
- [x] Local eligibility audit found no currently verified replacement corpus;
  ARC-AGI-1/2 train/evaluation and ConceptARC were already solution-exposed by
  the bundled parent audit. The current manuscript therefore follows the
  systems-negative branch.
- [ ] If 1D-ARC, MiniARC, a community set, or synthetic tasks are used, label
  them only as domain-shift mechanistic stress tests and freeze provenance,
  solution access, overlap, license, and one-shot rules before viewing answers.
- [ ] Public leaderboard value has a completed Kaggle receipt, not a projection.

## Submission artifact

- [ ] `submission.json` contains every hidden task ID in input order.
- [ ] Every test output has exactly `attempt_1` and `attempt_2`.
- [ ] Every grid is nonempty, rectangular, 1–30 by 1–30, integer colors 0–9.
- [ ] Submission JSON, notebook, logs, receipts, and source archive hashes saved.
- [ ] Up to two final ARC-AGI-2 submissions selected deliberately.
- [ ] Exact final public archive passes `audit_release_manifest.py` in
  `FINAL_RELEASE_CANDIDATE` mode; the current preliminary pass is insufficient.
- [x] Aggregate local readiness audit binds the current Writeup, pipeline,
  release, dependency, cover, deadline, authorship, and publication artifacts;
  it passes structurally while reporting `final_ready=false` and eight blocker
  classes.

## Entry and binding state

- [x] Authenticated account reports `userHasEntered=True` for both Paper Track
  and ARC-AGI-2.
- [x] Paper Track `NOTE.md` and all six ARC files are downloadable under the
  accepted access state.
- [x] Cross-track team names and member lists verified identical on 2026-09-09;
  repeat immediately before final binding.
- [ ] Every private input/resource attached to the final public notebook has
  been reviewed for post-deadline public disclosure and license compatibility.

## Paper package

- [ ] Kaggle Writeup ≤1,500 words after the platform's own count.
- [ ] Required cover image and only evidence-backed figures attached.
- [ ] Public notebook is accessible without login/paywall after publication.
- [ ] ARC-AGI-2 submission ID is correct.
- [ ] Optional PDF/project link is public and version-matched.
- [ ] Final Writeup is submitted, not left in draft.
- [ ] Internal November 8 safety cutoff met; public and prior authenticated
  Kaggle timelines agree on November 9 at 23:59 UTC, while the ARC Prize
  overview remains one day earlier.
