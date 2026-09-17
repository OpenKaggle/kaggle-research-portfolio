# Evidence-Gated Residual Allocation: A Systems-Negative ARC Study

Draft v0.1 — evidence placeholders are intentionally visible. This is not a
submission-ready claim of improvement.

## Abstract

ARC solvers can generate many plausible grids, but the competition accepts only
two attempts. We study candidate selection rather than another generator. Our
method places neural, recursive, and program candidates behind a common receipt,
estimates correctness from demonstration-only evidence, chooses the second
attempt by success conditional on the first attempt being wrong, and retains a
frozen neural anchor when evidence is out of support. Evaluation is
preregistered over task-grouped folds and an equal-compute anchor, with paired
benefit/harm accounting. Our current result is systems-negative: a historical
full-corpus solution audit invalidates the planned V176 generalization holdout,
and no eligible evaluator-controlled replacement corpus is presently verified.
**[PENDING: insert only eligible linked Kaggle runtime/publication evidence.]**

## Introduction

ARC-AGI-2 asks a system to infer a transformation from a few grid examples and
apply it to unseen inputs. Recent systems obtain candidates through test-time
training, recursive networks, program search, augmentation, and large
collections of decodes. Yet pass@2 creates a second problem: a larger candidate
union helps only if two outputs can be selected without discarding a correct
anchor answer.

We ask whether a label-free selector can exploit heterogeneous errors while
controlling this replacement risk. Our proposed contribution has three parts:
a provenance-bearing receipt shared across solvers; an out-of-task correctness
and residual model using evidence available from demonstrations; and a gate
that rejects unsupported overrides. The method is deliberately selective:
abstention and low coverage are preferable to an unjustified change.

## Prior work and claim boundary

Test-time training and program synthesis are established ARC approaches, and
TRM supplies a compact recursive candidate family. Algorithm portfolios,
probability calibration, and selective prediction are also established ideas.
We therefore do not claim novelty for combining solvers, using agreement, or
abstaining. The candidate novelty is specific to the two-attempt ARC objective:
learn the second slot's residual value, preserve a scored anchor outside
calibrated support, and evaluate selection on identical receipts.

A useful negative precedent is Multi-Perspective Transformers. Its reported
21.7% ARC-AGI-2 evaluation accuracy belongs to its pretrained-only TinyLM;
TTT, product-of-experts, and their combination each report 0% evaluation
accuracy and 100% failed generations. The authors attribute this to
single-view training and task-level overfitting. We consequently treat
multi-view consistency as a feature to validate, not as evidence by itself.

Cloud-agent systems report much higher public-evaluation scores, but use API
models, many concurrent sandboxes, iterative program execution, and exposed
public-evaluation traces. They are architectural precedents rather than
equal-resource Kaggle baselines; their traces are excluded from method fitting.

Other public-evaluation studies expose the same verification bottleneck: their
candidate oracle exceeds final synthesis, while without-replacement selection
can recover some cross-solver complementarity. We therefore report family-
exclusive solves and oracle-gap recovery separately from deployed pass@2.

## Method

For every task output, candidate generators emit a grid, exact grid hash,
solver family and version, seed, compute cost, rank, source hashes and licenses,
and an explicit declaration that generation and selection did not see the
target. Invalid grids and receipts fail closed. Exact duplicate grids merge
while retaining every contributing family.

The pointwise model uses demonstration reconstruction, leave-one-demonstration-
out stability, applicable transformation contracts, independent-family
agreement, structural relations, rank, and complexity. Task IDs, evaluation
correctness, and leaderboard data are forbidden. Training is task-weighted:
each task output has total weight one regardless of how many candidates a
solver emits. A regularized logistic model and isotonic calibration are fitted
with nested task-level cross-fitting.

Pointwise top-2 selection ignores an important asymmetry. Once attempt 1 is
chosen, attempt 2 is valuable only on outputs where attempt 1 fails. We fit a
second model on out-of-fold residuals and score an ordered pair as

`p(c1 exact) + (1 - p(c1 exact)) q(c2 exact | c1 wrong)`.

The frozen anchor pair always remains eligible. A proposed replacement is
accepted only if both receipts are valid, applicable contracts pass, neither
candidate is out of support, and the fifth percentile of 500 task-bootstrap
refits predicts positive utility relative to the anchor. Otherwise the original
pair is returned unchanged. All tie breaks and failure modes are deterministic.

## Validation

We froze five outer folds over all 1,000 public-training tasks before producing
an owned neural result. Each fold contains 200 tasks and exactly 50 tasks from
each input-only work quartile. Canonical D4/color and object-component
fingerprints found no provable duplicate clusters; this does not rule out
semantic analogues. Every fit, threshold, and residual estimate excludes the
evaluated task.

Authenticated Kaggle files contain 1,000 training tasks/1,076 outputs and 120
public-evaluation tasks/172 outputs. Training is identical to the pinned GitHub
checkout, but six evaluation tasks differ and the older checkout has only 167
outputs. All new evaluation claims therefore use the Kaggle hashes and 172
denominator.

The mandatory same-receipt comparison is: frozen neural top-2; consensus-only;
consensus then best distinct; calibrated pointwise top-2; conditional residual
allocation; residual allocation plus the safety gate; and a label oracle shown
only as a ceiling. We report exact pass@2 per task output, attempt-1 and
incremental attempt-2 exact rates, complete-task bootstrap intervals,
beneficial and harmful overrides, calibration, coverage, oracle union,
selector regret, runtime, and failures.

## Current evidence and pending result

The present evidence is negative but constraining. A fixed public V175 rule
library was developed on public corpora, so its public-training fit is
retrospective and intentionally omitted from this Writeup. Under the same strict
leave-one-demonstration-out policy it selected zero candidates on both the old
167-output checkout and the authenticated 172-output Kaggle evaluation. A
shallow archived DSL also scored 0/167. These results show that within-task
consistency can coexist with complete cross-distribution coverage collapse.
They motivate support detection; they do not validate the proposed selector or
new object reasoning.

The first private stable-V2 public-training smoke is retained only as a runtime
negative control: TRM exited with code 1 after 47.9 seconds when its optimizer
rejected a nonpositive learning rate during train-state creation, and one NVARC
task exceeded the fixed 1,200-second guard after three of four decode batches.
The cross-family comparison therefore did not execute, the development gate
failed, and no planned holdout run was launched. A later integrity audit found
that the source-corpus analysis had already loaded every public-training
solution before the V3 holdout preregistration and made the overlay's complete
abstention on that slice knowable. The slice is therefore quarantined for
method-generalization claims even though it remains unrun; it may support only
unchanged-parent runtime, format, and artifact checks. Internal training-split
accuracy remains in the engineering receipt and is not reported here.

A solution-blind one-task/one-step repair smoke then confirmed checkpoint load
and optimizer construction, but failed before its first step because an
offline logging shim passed `step=` to Python's built-in `print`. It emitted no
grid or submission, so no full development rerun was launched.

| Evidence | Frozen time | Receipt SHA-256 | Result |
| --- | --- | --- | --- |
| T19 | 2026-09-09; no time-of-day recorded | `d04c5599a17bb23e2cb941daf258886d8e4263c86ba80a764ae2617b6e4f5333` | `CONTAMINATED_FOR_V176_GENERALIZATION`; runtime/format only |
| T20 | 2026-09-09 21:45 CST / 13:45 UTC | `3cb7c33b99d439e4ddc6eaafc2e00757cce2a2c19687f04f61f2e6c06f00e8a2` | no verified eligible corpus; `PIVOT_V176_TO_SYSTEMS_NEGATIVE` |

The local inventory verifies no eligible labeled replacement: the bundled
parent had already evaluated ARC-AGI-1 and ARC-AGI-2
train/evaluation plus ConceptARC, totaling 2,080 tasks/2,563 outputs, with
ConceptARC complete. Re-splitting these tasks cannot restore solution isolation.
We therefore report V176 as systems-negative and remove its generalization,
Progress, and Novelty claims. 1D-ARC, MiniARC, community, or synthetic tasks may
be reported only as preregistered domain-shift mechanism tests. A positive route
can reopen only after solver, metrics, corpus rules, provenance, zero-overlap,
license, and one-shot evaluation are frozen before acquisition or answer view.

## Limitations and conclusion

Demonstrations can underdetermine a transformation, contract libraries are
incomplete, and calibrated support can shift on hidden tasks. Candidate
generation may also time out under the 12-hour limit. Our gate cannot certify a
grid; it can only reject some unsupported replacements.

The central test is therefore modest and falsifiable: does conditional slot-2
allocation close part of a real candidate-union gap without increasing harmful
overrides? Here, runtime failures and a failed solution-isolation audit stop the
positive test before admissible generalization evidence exists. The contribution
is the reproducible failure boundary, not an ensemble-success claim.
**[PENDING: final runtime conclusion, public notebook, source commit, and ARC
submission ID.]**

References: [ARC-AGI-2](https://arxiv.org/abs/2505.11831),
[ARC Prize 2024](https://arxiv.org/abs/2412.04604),
[test-time training](https://arxiv.org/abs/2411.07279),
[TRM](https://arxiv.org/abs/2510.04871),
[MPT](https://arxiv.org/html/2605.01154v1),
[PoTRE](https://arxiv.org/html/2607.20268),
[compositional neuro-symbolic reasoning](https://arxiv.org/html/2604.02434),
[algorithm portfolios](https://arxiv.org/abs/2012.13315),
[calibration](https://proceedings.mlr.press/v70/guo17a.html), and
[selective prediction](https://proceedings.mlr.press/v97/geifman19a.html).
