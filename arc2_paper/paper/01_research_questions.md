# Research questions and prospective claims

## Working title

**Evidence-Gated Attempt Allocation for Heterogeneous ARC Solvers**

## Central research question

Can a heterogeneous portfolio improve ARC-AGI-2 pass@2 without making hidden
performance depend on brittle, label-informed solver selection?

The paper studies selection, not merely ensembling. A neural generator, a
test-time-trained neural solver, and an object/program solver fail differently,
but pass@2 only exposes two slots. The research problem is how to allocate those
slots using evidence available from the task demonstrations alone, while
abstaining when that evidence is weak or out of distribution.

## Proposed contribution

A risk-controlled attempt allocator with four components:

1. A common receipt format for heterogeneous candidates.
2. Demonstration-only evidence: leave-one-demonstration-out reconstruction,
   consistent task contracts, cross-family agreement, structural validity, and
   program complexity.
3. A calibrated residual-diversity model that chooses the second attempt for
   marginal probability of success rather than raw rank.
4. An anchor-preserving safety gate that can decline a proposed override when
   confidence is uncalibrated, evidence is out of support, or the lower-bound
   gain is non-positive.

This is independent of any specific Qwen, TRM, or DSL implementation. Those
systems instantiate the candidate pool; the method is the evidence-and-risk
layer over them.

## Falsifiable hypotheses

### H1 — candidate complementarity

Under equal total compute, adding an object/program family increases the oracle
union over the fixed neural anchor on held-out task outputs. Failure to add at
least three exact outputs or 1.0 percentage point prospectively makes the Paper
Track a no-go even if the engineering entry itself remains competitive.

### H2 — evidence predicts correctness

The preregistered evidence vector predicts candidate exactness out of fold. It
must improve both Brier score and selective accuracy over raw solver score or
cross-solver agreement alone. Calibration is assessed only on task-disjoint
folds.

### H3 — diversity improves the second slot

Choosing attempt 2 by estimated success conditional on attempt 1 being wrong
improves exact pass@2 over choosing the two candidates with highest independent
confidence, with the candidate pool and compute held fixed.

### H4 — the safety gate controls harm

Relative to an ungated learned selector, the anchor-preserving gate reduces the
rate of outputs made worse than the fixed neural two-attempt anchor by at least
50%, while retaining at least 60% of the ungated selector's beneficial changes.

## Mandatory same-receipt comparison

The evidence chain is M0 frozen neural top-2, M1 consensus-only, M2 consensus
then best distinct, M3 calibrated pointwise top-2, M4 conditional residual
slot-2 allocation, M5 M4 plus the anchor-preserving OOD gate, and M6 a label
oracle shown only as a ceiling. M4 must outperform M3, and M5 must reduce harm
relative to M4 without erasing most benefit. A larger M6 union with no M5 gain
is a selection failure, not progress.

## Primary endpoint

Paired difference in exact pass@2 per task output versus the frozen two-attempt
neural anchor, under equal candidate-generation compute.

## Evidence position at protocol freeze

Two direct-transfer baselines are already refuted. The archived shallow
NeuroGolf DSL solved 0/167 on the older GitHub evaluation revision. The public
V175 exact-rule library produced no candidate that survived strict
leave-one-demonstration-out selection on either that revision or the
authenticated Kaggle 2026 revision (0/172 selected and correct). Therefore H1
is currently unsupported. A genuinely separate fixed typed-object
correspondence family was subsequently frozen before a one-shot audit on 181
grouped-fold tasks/197 outputs excluding the existing development and holdout
splits. It made one exact selection and no incorrect selections, but that task
was already solved by V175 `scale:3`; its exclusive and union gain were zero.
The family is stopped and may not be tuned on that audit fold. Any successor
must change solver mechanism and first show nonzero incremental union on a new
precommitted data boundary.

On the 1,000 public-training tasks, that same fixed V175 policy selected 307 of
1,076 outputs and all 307 were exact. The rule library was built against public
corpora, so this is retrospective coverage, not an unbiased estimate. Its
contrast with zero evaluation coverage is the strongest current motivation for
H2 and for explicit out-of-support detection: task-internal LOO consistency is
insufficient evidence of task-distribution transfer.

The first owned notebook family is narrower than the proposed contribution. V1
is a fixed checkpoint-agreement control with a process-randomized task hash;
stable V2 repairs that seed with task-ID BLAKE2b while leaving candidate budgets
and selector logic unchanged. Both private development/holdout pairs pass
static and selector tests, but neither has produced an accuracy receipt.

## Secondary endpoints

- attempt-1 exact accuracy;
- incremental exact solves from attempt 2;
- oracle union and selector regret to that union;
- beneficial override rate, harmful override rate, and abstention coverage;
- Brier score, expected calibration error, and risk-coverage curve;
- runtime, peak memory, candidates generated, and valid-candidate rate;
- performance by preregistered failure family.

## Claim limits

- No claim of solving general intelligence or universally certifying ARC
  solutions.
- No claim that metamorphic checks prove correctness; they only falsify some
  brittle hypotheses.
- No claim that old NeuroGolf models transfer to unseen ARC task IDs.
- No leaderboard claim from the NVARC/TRM notebook's 40.0419% projection; it is
  explicitly unscored metadata until a completed Kaggle receipt exists.
- If only the neural anchor scores and the selector contributes no prospective
  lift, the paper must report a negative study or stop; it cannot present the
  portfolio wiring as novelty.
- Training retrospective precision cannot open the Progress or Novelty claim.
  That gate requires at least three net new exact public-evaluation outputs
  over the copied anchor, or at least +1.0 percentage point on equal-compute
  sealed pass@2 plus a causal same-receipt ablation.
- Alternate-view and TTT variants stop unless development first demonstrates
  valid generation, representation diversity, and an exact-success association;
  the published MPT evaluation failure is a negative boundary, not support.
- The bundled V175 multi-corpus receipt and TRM statistics are source-author
  reports from a different dataset revision. They can motivate hypotheses but
  cannot support a headline result until independently reproduced under this
  protocol.
