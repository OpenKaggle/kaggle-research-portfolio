# Method specification

## 1. Heterogeneous candidate pool

For each task output, every solver emits zero or more candidate receipts:

```text
task_id, output_index, grid, solver_family, solver_version, candidate_id,
generation_seed, compute_spent, provenance, explanation/program,
demo_predictions, structural_metadata
```

The normative receipt contract is
`schemas/candidate_receipt_v1.schema.json`. The fail-closed validator also
recomputes the exact grid hash, requires rectangular 1–30 grids with colors
0–9, rejects duplicate candidate IDs and label-like evidence keys, and requires
explicit declarations that neither generation nor selection saw the target.
Correctness fields belong only in a separate evaluator receipt.

The initial families are:

- **NVARC/Qwen grid model** with independently seeded/augmented decodes;
- **TRM test-time training** with checkpointed candidates;
- **object/program solver** using connected components, masks, bounding boxes,
  palette relations, symmetry, lines/rays, holes, crop/paint/tile operations,
  and cost-ordered typed program search.

Deduplication is by exact output grid. Solver-family provenance is retained even
when multiple families produce the same grid because agreement is evidence.

## 2. Demonstration-only evidence

No test-output label is available to the candidate generator or selector. Each
unique grid receives a fixed evidence vector:

1. **Demo fit:** exact reconstruction count across all demonstrations.
2. **Leave-one-demo-out stability:** infer or fit on all-but-one pairs and
   reconstruct the held-out pair; aggregate exact rate and worst case.
3. **Contract consistency:** apply only contracts that are valid on every
   demonstration for that hypothesis, such as allowed color permutations,
   dihedral covariance, zero-frame translation/padding, and irrelevant-object
   insertion. Record passes, failures, and inapplicable cases separately.
4. **Cross-family agreement:** number and identity of independent families that
   generate the exact grid, not merely number of stochastic samples.
5. **Structural validity:** rectangular 1–30 grids, palette constraints,
   output-size relation, object-count relation, and other invariants induced
   from demonstrations.
6. **Complexity:** program description length, transformation depth, or neural
   decoding cost. Complexity is a prior, never a correctness certificate.
7. **Support distance:** distance of the evidence vector and task structural
   fingerprint from calibration data; used to trigger abstention.

Contracts are declared before inspecting their failures. A failed contract may
be removed only with a task-semantic reason that was already visible in the
demonstrations; it cannot be removed because it hurts an evaluation score.

## 3. Calibrated correctness model

A small monotone or regularized calibrator estimates
`P(candidate exact | evidence, family, task structure)`. Training uses only
out-of-task receipts from development folds. Candidate receipts from the same
task, its augmentations, and near-duplicate tasks remain in the same group.

The calibrator outputs both a point estimate and a conservative lower bound.
Out-of-support inputs receive no confident extrapolation; they are marked OOD
and sent to the anchor-preserving branch.

The exact primary feature transformations, nested cross-fitting, task weights,
regularization, OOD threshold, task-bootstrap uncertainty, and deterministic
tie breakers are frozen in `11_selector_preregistration.md`. Any alternative
calibrator is an ablation or a new declared method version.

## 4. Two-attempt allocation

Attempt 1 maximizes calibrated probability of exactness subject to validity.
Attempt 2 maximizes marginal coverage:

```text
U(c1, c2) = P(c1 correct)
          + P(c1 wrong) * P(c2 correct | c1 wrong)
          - risk_penalty(c1, c2)
```

The conditional term is learned from out-of-fold residuals and regularized by
solver-family dependence. Two superficially different decodes from the same
failure mode are penalized; a lower-confidence program candidate may occupy
slot 2 when it historically solves residuals left by the neural candidate.

The deployed selector evaluates ordered pairs containing distinct exact grids;
candidate one is the member with higher pointwise exactness probability. The
anchor pair is always among the eligible pairs. The ungated allocator chooses
the largest estimated conditional pass@2 utility; the full method replaces the
anchor only through the safety gate below.

## 5. Anchor-preserving hidden-set safety gate

The frozen public neural policy supplies two anchor attempts. The selector may
replace a slot only when all conditions hold:

1. the candidate is structurally valid and fully traceable;
2. all applicable demonstration contracts pass;
3. the evidence vector is inside calibrated support;
4. the conservative estimated marginal gain over the displaced anchor is
   positive at the preregistered threshold;
5. the pair is not more correlated than the anchor pair without compensating
   evidence;
6. the exact policy was frozen before evaluation-label access.

Otherwise the method abstains and retains the original anchor slot. This is a
selective prediction system: coverage may be low by design.

## 6. Hidden-set boundary

The gate does not use public-evaluation or Kaggle test labels. It may use task
demonstrations, input grids, public models, and calibration learned on disjoint
development tasks. All features are computable inside the offline 12-hour
Kaggle notebook.
