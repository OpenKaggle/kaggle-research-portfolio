# Locked validation protocol

Version 0.1, frozen before any method-specific ARC-AGI-2 public-evaluation
per-task error analysis. Changes require a dated amendment and invalidate the
word “prospective” for affected experiments.

## Data boundary

### Development

- ARC-AGI-2 public training tasks may be used to build primitives, train the
  calibrator, and set thresholds.
- Any procedural/synthetic tasks must have public provenance and a compatible
  license. Synthetic descendants inherit the group of their source task.
- For each task, candidate generation sees only demonstration pairs and the
  test input. The held-out output is evaluator-only.
- Public-training tasks used to author, choose, or debug a rule are development
  data even when that rule later passes leave-one-demonstration-out checks.
  LOO protects against within-task demonstration memorization; it does not
  create task-level independence. Such results are retrospective feasibility
  evidence only.

### Grouped outer validation

Create five task-disjoint folds after grouping potential near duplicates. A
group contains a task and all its augmentations plus any task sharing a strong
canonical fingerprint:

- D4- and color-normalized input/output shape sequence;
- object-count, component-area, bbox, hole, adjacency, and palette signatures;
- normalized transformation trace when known;
- source/provenance family.

All selector training, threshold fitting, and pairwise residual estimates for a
fold use only the other folds. No candidate receipt from the evaluated task may
enter fitting.

The first executable assignment is frozen as
`manifests/grouped_folds_v1.json` (SHA-256
`c6112e37b29296b0139764de43611f01475d421cad5da7cd05f849d700a07a99`).
It covers all 1,000 tasks in five folds of exactly 200 tasks. Every fold has 50
tasks from each input-only work quartile; total estimated work ranges only from
3,571,688 to 3,572,376.

Provenance is stratified against the official ARC-AGI-1 repository pinned at
commit `399030444e0ab0cc8b4e199870fb20b863846f34`. Of the ARC-AGI-2 training
tasks, 391 match that pin's training IDs, 376 match its evaluation IDs, and 233
are absent from that pin. “Absent from the pin” is a provenance category, not a
claim that those tasks are newly authored.

The V1 exact fingerprint is invariant to a global D4 transform, global
first-occurrence color relabeling, and demonstration order through five
demonstrations. Its second fingerprint uses color-agnostic connected-component
mask, area, bounding-box, border-touch, and input/output shape relations. It
found 1,000 singleton groups and no large review clusters. This only establishes
that these detectors found no provable duplicate; it does not rule out semantic
near duplicates. A discovered source/augmentation trace or stronger semantic
detector must be recorded as a V2 amendment before affected results are used.

The fold builder reads all grids in the public-training task JSON, including
their test outputs, solely to construct structural grouping fingerprints and
the fixed partition. Those outputs are never candidate-generator, evidence,
calibrator, or selector features. Fold construction is thus evaluator-side
leakage control, not model fitting.

### First-run smoke-test manifests

Before the full grouped outer validation, the conservative-agreement control
historically froze two 48-task public-training manifests. Each contains 12 tasks
from each of four input-only estimated-work quartiles; membership is selected by
a SHA-256 deterministic order with seed `arc2026-ab-v2-work-stratified`. The two
task-ID sets have zero overlap.

That second slice is no longer a valid V176 method-generalization holdout. The
historical source-corpus audit loaded all 1,000 public-training solutions before
the paired V3 holdout preregistration and established that the two V176 rules
select only their two development source tasks. Reconstructing the planned
second slice from challenge inputs alone gives 48 tasks/49 outputs, zero overlap
with development, and zero V176-selected tasks. Thus V176 was already known to
abstain throughout the slice before any run. The slice remains unrun and may
still test unchanged-parent execution, format, and artifact integrity, but it
cannot support V176 contribution, unseen generalization, Progress, or Novelty.

No V3 development, holdout, or competition run may be promoted under the active
contract. A successor must be a new candidate/contract version and must bind an
evaluator-controlled labeled corpus whose solutions were unavailable throughout
method construction. Repartitioning the same 1,000 training tasks is
insufficient because their solutions were already consumed by the historical
audit. If no such corpus can be established, remove the V176 generalization
claim and report the work as systems/negative evidence rather than treating a
runtime-only slice as a sealed result.

### Runtime-only repair after failed development run 348340917

The first stable-V2 run completed on Kaggle but did not execute the intended
cross-family test. TRM stopped during optimizer construction because the
installed AdamAtan2 asserts a strictly positive initial learning rate while the
upstream launcher supplied zero; one NVARC task also hit the unchanged
1,200-second guard after three of four decode batches. The failed output,
receipts, logs, and zero-delta paired analysis remain frozen.

The first compatibility repair initialized AdamAtan2 with the configured
positive learning rate while retaining the original warmup scheduler as the
per-step authority, including its step-zero value. Its solution-blind
one-task/one-step private smoke confirmed checkpoint loading and optimizer
construction, then failed before the first step because the offline patch had
translated `wandb.log(payload, step=value)` into built-in
`print(payload, step=value)`.

One separately versioned exploratory logging repair is now allowed: route the
same payload and optional `step` argument through a local stdout-only helper
that performs no network I/O and cannot alter model, optimizer, scheduler,
dataset, or RNG state. Repeat the identical task/checkpoint/epoch smoke. It must
verify the first scheduler-controlled step, a saved step-one checkpoint, one
schema-valid TRM grid, and new hashes before any full rerun. No third runtime
patch is permitted on this path.

Kernel version 1 of that logging repair had already been pushed and was last
observed `RUNNING` at 06:27:41 CST before a local-only safety boundary arrived
at 06:34:25 CST. Its terminal status is unknown; no later Kaggle status read,
artifact download, rerun, upload, or holdout access is authorized without
explicit approval. A local regression over the actual patched source and a
CPU micro-smoke with the exact bundled AdamAtan2 package pass, but neither can
satisfy the authoritative model/checkpoint/GPU/submission guards.

Separately, a 2026-09-11 immutable receipt reconciles the historical
`RUNNING` snapshot for Stable V2 development run 348340917—not the logging
repair smoke—to official `COMPLETE`. Its terminal capture is isolated as 239
output files plus one log, but no file content was reviewed and no sealed label
was opened. Conflicting official time fields leave the exact finish time
`UNKNOWN`; the receipt supplies operational provenance only and no
generalization evidence.

Even if that smoke passes, it does not unlock the contaminated V3 sequence. A
full external rerun requires the replacement candidate/holdout contract above;
within any authorized successor run, task order, seeds, candidate and selector
policies, model/checkpoint, budgets, and the 1,200-second task guard remain
frozen.

No stage is activated by a manual state edit. After its prerequisite is bound
and passes, an explicit user decision must be captured in an exact
`stage_authorization_v1` receipt. The receipt binds the current contract bytes,
candidate, sole eligible stage, frozen notebook, and one allowed external
action; it permits exactly one run, requires terminal evidence to be read, and
sets both leaderboard-based selection and future-stage authorization to false.
`tools/authorize_stage.py` verifies that the receipt postdates the prerequisite,
audits the prospective contract, and atomically changes only that stage to
`RUNNING`. The tool performs no Kaggle operation, and the receipt never advances
or authorizes the next stage.

If the logging-repair smoke fails any guard, do not launch the full rerun. If
the full rerun has an invalid/missing TRM candidate, any timeout/incomplete
decode, no TRM-exclusive exact output, or less than one output of oracle gain
over KGMon, stop before the sealed holdout and report the runtime-to-coverage
result. No solution-label inspection may motivate any compatibility change.

### Public evaluation disclosure

The authenticated Kaggle 2026 public evaluation contains 120 tasks and 172
outputs and is authoritative. The pinned GitHub checkout contains the same 120
task IDs but 167 outputs. A frozen revision audit found that all 1,000 training
tasks are exact across the two sources, while only 114/120 evaluation tasks are
exact: four have changed test inputs and two have changed training examples.
Therefore the grouped training folds remain valid, but all new evaluation
claims use the Kaggle manifest and 172-output denominator.

The public evaluation is not pristine. Two fixed, label-free negative controls
have been scored:

- an unmodified 29-primitive NeuroGolf DSL produced 0/167 at depth 1 and depth
  2 on the older GitHub checkout;
- the public V175 exact-rule library produced zero unique candidates after
  strict leave-one-demonstration-out filtering on both versions: 0 selected and
  0/167 in 103.946 seconds on GitHub, and an independently rerun 0 selected and
  0/172 in 31.129 seconds on the authenticated Kaggle files.

Generation and selection in both audits were performed with test outputs
detached. The labels were used only by the evaluator. Paper planning has used
only the aggregate outcomes, although per-output receipts exist locally. These
results motivate rejecting direct library transfer and must not be used to
tune a successor family task by task.

For the new method, public evaluation is a prospective external audit:

- freeze solver versions, evidence features, thresholds, and compute budgets;
- store a manifest hash before scoring;
- run once; return aggregate metrics and preregistered taxonomy counts;
- do not change the headline method after inspecting per-task labels without
  declaring a new exploratory phase.

The older bundled source receipt also reports zero coverage on a 172-output
slice but does not include the authenticated Kaggle file hashes. The current
Kaggle reproduction independently confirms only its aggregate zero-coverage
claim. The Kaggle hidden rerun is the decisive generalization result.

### Retrospective feasibility audit

The same fixed V175/LOO runner was also evaluated on the 1,000-task public
training split: 307/1,076 outputs were selected and all 307 were exact (28.53%
coverage; 100% direct precision; 1,252.983 local CPU seconds). This nearly
reproduces the source receipt's 310 all-training-unique outputs, but it is not
an outer-fold result because the rule library was developed using public
corpora. The training-to-evaluation coverage change (28.53% to 0%) is reported
as an evidence-support shift diagnostic, never as a method score.

## Equal-compute comparison

All headline rows use the same total 12-hour-compatible budget, fixed candidate
caps, solver seeds, and stopping rules. A solver added to the portfolio must be
paid for by an explicitly reported budget allocation. Also report a
same-candidate-pool selector-only comparison so candidate generation and
selection gains are not conflated.

Operational target: complete in at most 11h30, preserving 30 minutes for merge,
validation, receipts, and `submission.json` creation.

## Metrics

Primary:

- exact pass@2 per task test output;
- paired delta from the frozen neural anchor.

Secondary:

- attempt-1 exact, incremental attempt-2 exact;
- per-family exclusive exact coverage and pairwise solve overlap;
- oracle union, oracle gain over anchor, selector regret, and oracle-gap
  recovery `(method - anchor) / (oracle - anchor)` when the denominator is
  positive;
- benefit/harm/neutral counts relative to the anchor pair;
- selector coverage and selective exactness;
- Brier score, ECE with preregistered bins, and risk-coverage AUC;
- valid-output rate, wall time, peak memory, and per-family candidate counts.

Every metric denominator is task output, matching the competition. Task-level
figures may be secondary and must state their denominator.

Family coverage is computed from the complete Cartesian evaluator table in
`results/family_results_template.csv`: every task output must have one binary
row for every frozen solver family. `tools/analyze_family_coverage.py` rejects
missing or duplicate family rows before reporting exclusive solves, pairwise
overlap, Jaccard overlap, and oracle union. This table is evaluator-only and
cannot become a selector feature.

The three-stage receipt uses a separate, coarse **primary task-family** view.
`tools/build_stage_measurement.py` assigns each task once from its training
demonstrations only; test outputs are structurally rejected. The frozen
precedence is: counting (small output size matches an input component/color
count), color (same canvas and occupied mask with changed values), object
(strict smaller exact subgrid), composition (interior full-span separator or
strict expansion), geometry (remaining shape change), topology (same-canvas
four-connected component-count change), then search as the residual bucket.
These are deterministic operational labels, not ground-truth ARC concepts and
never selector inputs. A task is solved within its bucket only when every test
output is exact under pass@2; runtime failures are counted once by task. The
seven task counts must sum to stage task scope, and their failure counts must
sum to the stage runtime failure count.

For the competition rerun, the same demonstration-only classifier records
operational task/failure coverage, but every per-output, per-attempt, aggregate
local-accuracy, and per-family correctness field is null. The only accuracy-like
quantity is the Kaggle-returned aggregate score with its explicit score scope.
The terminal observation must satisfy
`schemas/competition_observation_v1.schema.json`: COMPLETE kernel and submission,
submission ID, notebook version/slug, ordered timestamps, exact wall time,
positive peak memory, failure/timeout IDs, no leaderboard-based selection, and
hashes for notebook, submission, input manifest, run log, and metadata. The
local measurement builder rehashes every source and enforces the 11h30 bound
before the normalized receipt may be constructed.

## Statistical analysis

- Report paired bootstrap 95% intervals over whole tasks, not independently
  resampled outputs, to preserve within-task dependence.
- Report exact paired benefit-versus-harm counts and a two-sided sign/binomial
  test as a robustness check.
- Calibration intervals are computed strictly out of fold.
- Report all five fold results; never select the best fold.
- Multiple ablations are descriptive unless a Holm-corrected family is
  preregistered. The primary comparison is the full gated method versus the
  frozen anchor.

## Promotion gates

A run cannot become paper evidence unless:

1. all source/model/data hashes and licenses are present;
2. output schema validation passes for every task/output/attempt;
3. candidate generation and selection logs contain no evaluation labels;
4. all five outer folds and all preregistered ablations completed;
5. the full method adds at least three exact outputs or 1.0 percentage point on
   the prospective external audit under equal compute;
6. at least one ablation isolates a causal component of the gain;
7. no unreported manual per-task override exists;
8. the final Kaggle run finishes within 11h30 and has a completed receipt.

If gate 5 fails, report the negative result or stop the Paper Track. If the
candidate oracle improves but the selector does not, the valid conclusion is a
selection failure, not a successful portfolio.

If the sealed candidate oracle itself improves by less than 1.0 percentage
point over the anchor, stop the portfolio claim before tuning the selector. If
the oracle improves but the frozen selector recovers less than 25% of that gap,
report a verification/selection bottleneck rather than portfolio progress.

## Failed-stage diagnostic gate

A stage marked `FAILED` must have a hash-bound terminal receipt. Diagnose in
the fixed order **format → cache → seed → budget**: the first failed check stops
the sequence and all later checks are recorded as `NOT_REACHED`; a solver
failure is admissible only when all four checks pass. Every failure records the
seven frozen task-family buckets, runtime/memory/failure rate, format guards,
and notebook/input/log/artifact hashes. A solver failure additionally requires
a task/output-level minimal counterexample and a completed single-variable
control/treatment ablation.

The receipt carries prior/current no-improvement and same-failure streaks. The
first failed attempt keeps the current family, the second consecutive
no-improvement must switch to a different solver family, and a third same-class
failure must include a hash-bound reproduction of a cited public method before
the receipt is accepted. These records diagnose a stopped stage; they do not
authorize a rerun, unseal the holdout, or provide accuracy evidence.
`tools/commit_stage_failure_receipt.py` revalidates the record, requires that
the run did not start before its bound authorization, audits the prospective
contract, and atomically marks only the running stage `FAILED`. A failed
candidate contract is terminal: any permitted repair or solver-family switch
must use a new candidate/contract version that hash-links the prior failure,
never an in-place reset that discards history.

## Amendment log

| Date | Change | Reason | Prospective claims affected |
| --- | --- | --- | --- |
| 2026-09-08 | Initial protocol | Paper workspace creation | None |
| 2026-09-08 | Disclosed V175 exact-rule audit | A fixed external rule library was evaluated after the initial protocol; 0/167 with zero selected outputs | Direct-transfer symbolic claims; not the frozen typed-object successor |
| 2026-09-08 | Classified V175 training audit as retrospective | Rules were developed on public corpora, so task-internal LOO is not task-level holdout | H2 motivation only; no headline accuracy claim |
| 2026-09-09 | Froze executable grouped-fold V1 manifest and grouping disclosure | Replace a prose intention with a deterministic, hashed partition and state its detection limits | Future outer-fold results must use this manifest or declare a new version |
| 2026-09-09 | Froze selector/calibration preregistration | Remove post-result freedom in features, cross-fitting, OOD, uncertainty, pair scoring, and tie breaks | Headline A3–A5 comparisons must use this policy or declare a new version |
| 2026-09-09 | Switched evaluation authority to authenticated Kaggle 172-output manifest | Both competitions were joined and six official files became available; GitHub and Kaggle differ on six evaluation tasks | All new evaluation claims use Kaggle hashes and 172 outputs; older 167-output audits remain versioned controls |
| 2026-09-09 | Added oracle-gap recovery and family-exclusive coverage | Recent public-eval agentic systems expose large candidate-oracle versus final-selection gaps; the paper must separate candidate coverage from selector recovery | Headline rows require `oracle_pool_correct`; public traces remain excluded from fitting |
| 2026-09-09 | Preregistered one runtime-only repair after failed run 348340917 | TRM failed before candidate generation because AdamAtan2 rejected the upstream zero initialization; the development comparison therefore never occurred | One positive optimizer-construction compatibility change is permitted after a one-task/one-step preflight; all data, policy, seed, budget, scheduler, and timeout semantics remain frozen |
| 2026-09-09 | Versioned a second, logging-only smoke after the first preflight failed | The first repair passed checkpoint and optimizer guards, then the offline `wandb.log` shim called built-in `print` with an unsupported `step` keyword before any optimizer step or result | One stdout helper accepting `step` may be tested on the identical solution-blind smoke; no third patch or full rerun is allowed unless every guard passes |
| 2026-09-09 | Recorded the pre-boundary V2 run state and local-only verification | Kernel version 1 was pushed and last observed `RUNNING` before the later safety boundary; actual-source and exact-package local checks pass without querying Kaggle | Running and local checks are not a passing smoke or Accuracy evidence; terminal status/artifacts require explicit authorization |
| 2026-09-09 | Classified V176 exact-overlay development replay as post-hoc | Both rules were authored after inspecting the two frozen development misses, although generation later uses demonstrations and test input only | The 49/50 single-rule and 50/50 combined replay may support implementation/complementarity only; Progress, Novelty, and generalization require prospective sealed evidence |
| 2026-09-09 | Added a hash-bound three-stage execution contract | Prevent an unknown runtime smoke, failed development gate, regressed holdout, missing task-family/runtime/format evidence, or leaderboard-tuned policy from advancing to competition | The V3 development comparison must use one shared repaired runtime for control and method, with the exact overlay as the sole algorithmic factor; every later stage is data-split-only and requires a normalized receipt. Competition hidden labels are unavailable, so only the returned Kaggle aggregate score and operational family coverage may be recorded there; per-output or per-family correctness is rejected. Its third reported gap is precommitted as score minus the official 0.85 target, with both score scopes retained so this contextual gap cannot be mistaken for an anchor delta or private-evaluation estimate |
| 2026-09-09 | Added a hash-bound failed-stage diagnostic contract | The prior failed-stage branch required only terminal status and a free-text class, so it could not prove the requested diagnostic order, family accounting, counterexample/ablation work, or solver-family stopping rules | A `FAILED` stage now requires ordered format/cache/seed/budget evidence, seven-bucket operational failures, runtime/format/artifact records, and exact streak actions; solver failures require a minimal counterexample and single-variable ablation, two no-improvements force a family switch, and three same-class failures require a completed public-method reproduction |
| 2026-09-09 | Added exact one-stage authorization receipts and an atomic local transition | A passing prerequisite previously exposed a next action but left the `RUNNING` state change and authorization scope as an unaudited manual step | Each stage now requires a current-contract and frozen-notebook-bound user receipt for exactly one named action. The local authorizer rejects stale, wrong-stage, wrong-action, pre-prerequisite, multi-run, future-stage, or leaderboard-selection authorization and performs no Kaggle action |
| 2026-09-09 | Added atomic failed-stage commitment and start-after-authorization enforcement | A validated failure receipt still required a manual state/hash edit, and completion-after-authorization alone did not prove the run itself began after authorization | The committer rejects pre-authorization starts and invalid/substituted receipts, preserves the failed candidate contract, and requires every retry or solver-family switch to use a new version linked to the failure receipt |
| 2026-09-09 | Reclassified the planned V3 48-task holdout as contaminated for V176 generalization | The preexisting source-corpus audit loaded all 1,000 training solutions and established V176 coverage before the paired holdout preregistration; the disjoint slice therefore has known zero V176 selection even though it remains unrun | V3 promotion is machine-blocked. The slice may support unchanged-parent runtime/format evidence only; a new candidate and evaluator-controlled never-seen labeled corpus are required, otherwise V176 generalization, Progress, and Novelty claims must be removed |
| 2026-09-09 | Audited replacement-corpus eligibility and selected the systems-negative path | The bundled V175 receipt covers ARC-AGI-1 train/evaluation, ARC-AGI-2 train/evaluation, and ConceptARC across 2,080 tasks/2,563 outputs; the parent source reports ConceptARC complete. No current local evidence verifies a labeled, never-accessed, license-clear, target-comparable replacement | V176 is systems/negative by default. 1D-ARC, MiniARC, community, and synthetic sets may support only preregistered domain-shift mechanism tests. Reopening a positive route requires a full provenance/solution-access/overlap/license/comparability contract frozen before acquisition or solution view |
