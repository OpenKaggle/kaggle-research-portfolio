# Selector preregistration

Version 1, frozen 2026-09-09 before any owned neural accuracy result. This
policy applies to the full A3–A5 method, not to the narrower fixed
checkpoint-agreement smoke-test notebooks.

## Unit and label boundary

The modeling unit is one deduplicated candidate grid for one task output. The
binary training label is exact grid match against that public-training output.
Labels live only in evaluator receipts. Feature construction reads the task's
demonstrations, test input, candidate receipts, and fold assignment; it never
reads the target output or evaluator correctness field.

All exact-grid duplicates are collapsed before fitting. The merged row retains
the sorted set of contributing solver families and candidate IDs. Candidate
generation versions, budgets, and caps are frozen in the run manifest before
receipts are scored.

## Frozen feature dictionary

Positive-direction continuous features:

- demonstration exact rate and worst-demonstration exact indicator;
- leave-one-demonstration-out same-grid survival rate and worst-fold indicator;
- fraction and count of applicable preregistered contracts passed;
- number of independent solver families producing the exact grid;
- reciprocal within-family rank.

Cost/complexity features:

- log one plus generation seconds;
- program description length or neural decode rank, with a family-specific
  missing indicator;
- output/input cell ratio and absolute dimension deltas inferred without the
  target;
- task train-pair count, test-input dimensions, palette size, connected
  component count, and input-only work quartile.

Categorical features are solver-family set, output-size relation hypothesis,
and which contract families were applicable. Hard grid validity is a filter,
not a learned feature. Missing positive evidence is imputed to zero and gets a
missing indicator; missing cost/complexity is median-imputed within the outer
training folds and also gets an indicator. Task IDs, fold IDs, target-derived
features, evaluator fields, public-evaluation correctness, and leaderboard data
are forbidden.

## Pointwise correctness model

The primary model is L2-regularized logistic regression with intercept and
regularization strength 1.0. Continuous features are centered by the median and
scaled by the interquartile range computed only on the outer training folds;
zero-IQR features are dropped for that fit. Categorical values are one-hot
encoded, with unseen levels marked out of support.

Each task output receives total fitting weight one, divided equally among its
deduplicated candidate rows. This prevents a solver that emits many candidates
from dominating the fit. No class reweighting or hyperparameter search is used.

For each outer test fold, the other four folds are also used as four inner
cross-fitting blocks. Each block is predicted by a model fitted on the other
three, producing label-separated out-of-fold point predictions. A one-dimensional
isotonic map is fitted on those inner out-of-fold predictions and labels. The
base model is then refitted on all four outer-training folds and followed by
that fixed isotonic map for the outer test fold. If an inner fit has only one
class or the isotonic fit is undefined, the fold is invalid rather than repaired
after seeing its result.

## Conditional residual model

For every task output in the inner out-of-fold receipts, form ordered pairs of
distinct candidate grids. Candidate one is the member with the higher calibrated
pointwise probability; exact ties use lexicographic candidate ID. Train only on
rows where candidate one is evaluator-wrong. The target is whether candidate
two is exact.

The residual model is another L2 logistic regression with strength 1.0 and the
same task-output weighting. It uses candidate-two pointwise probability and
evidence, the two solver-family sets, their intersection size, exact agreement
provenance count, and structural/grid-distance features that do not use the
target. It is isotonic-calibrated from inner out-of-fold residual predictions.
No pairwise feature or interaction is added after inspecting an outer-fold or
public-evaluation result.

For ordered pair `(c1, c2)`, estimated pass@2 utility is

```text
p(c1 exact) + (1 - p(c1 exact)) * q(c2 exact | c1 wrong).
```

The pointwise A3 baseline instead selects the two distinct grids with the
highest `p`, ordered by `p`. A4 selects the ordered pair with greatest residual
utility. The frozen neural anchor pair is always included even if it falls
outside the learned candidate cap.

## Out-of-support rule

Continuous features use the robust scaling above. Within each solver-family
set, compute every outer-training candidate's distance to its nearest candidate
from a different task. The support threshold is the 95th percentile of these
leave-one-task-out nearest-neighbor distances. A candidate is OOD if its family
set was unseen, a required feature is missing, or its distance exceeds that
threshold. Pair OOD is true if either member is OOD.

This distance is a detector, not a probability guarantee. Report acceptance
coverage separately for in-support and OOD rows.

## Conservative pair gate

Uncertainty is estimated with 500 bootstrap refits resampling whole tasks from
the four outer-training folds. Each refit repeats pointwise fitting,
calibration, and residual fitting. Failed or single-class refits vote for the
anchor. For every proposed pair, compute the bootstrap distribution of its
predicted utility minus the predicted utility of the frozen anchor pair.

A5 accepts a non-anchor pair only when all conditions hold:

1. every candidate receipt passes the V1 validator;
2. both grids are distinct and structurally valid;
3. neither candidate fails an applicable preregistered contract;
4. the pair is in support;
5. at least 450 of 500 bootstrap refits are valid; and
6. the fifth percentile of predicted utility difference is strictly positive.

Otherwise A5 returns the anchor pair unchanged. There is no tuned positive
margin in V1. A different quantile, bootstrap count, support percentile, or
minimum-valid-refit count is a new method version, not a quiet repair.

## Determinism and failure behavior

All row orders are `(task_id, output_index, grid_sha256)`. Solver-family sets are
sorted. Random-operation seeds use BLAKE2b of the global seed, outer-fold index,
and operation label; per-task operations additionally include the task ID.
Exact utility ties prefer the anchor pair, then fewer total generation seconds,
then lexicographic candidate IDs.

Any schema failure, forbidden label key, missing fold, duplicate candidate ID,
single-class required fit, non-finite coefficient, or fewer than 450 valid
bootstrap refits fails closed to the anchor and emits a machine-readable reason.
Manual per-task overrides are prohibited.

## Locked reporting

Report all five outer folds and their pooled task-output result. Primary
comparison is A5 versus the frozen anchor. A3 versus A4 tests conditional
residual allocation; A4 versus A5 tests the gate. Report pass@2, attempt-1 and
incremental attempt-2 exact rates, whole-task bootstrap interval, benefit/harm,
sign test, coverage, selective exactness, Brier score, ECE, and risk-coverage
AUC. The public evaluation remains a single prospective audit after this policy
and all generator versions are frozen.
