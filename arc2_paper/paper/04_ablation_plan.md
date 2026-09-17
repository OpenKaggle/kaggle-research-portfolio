# Equal-compute ablation plan

The canonical table lives in `results/ablation_table.csv`. Rows are frozen
before the first prospective external audit.

## Main system ablations

| ID | Candidate pool | Selector / allocation | Safety gate | Question |
| --- | --- | --- | --- | --- |
| A0 | fixed neural anchor | native two attempts | none | Reference |
| A1 | neural + TRM | top two raw ranks | none | Does another family add usable union? |
| A2 | neural + TRM + program | top two raw ranks | none | Does the object/program pool add union? |
| A3 | same as A2 | pointwise calibrated top two | none | Does correctness calibration help? |
| A4 | same as A2 | residual-diversity allocator | none | Does conditional slot 2 add coverage? |
| A5 | same as A2 | residual-diversity allocator | full gate | Full proposed method |
| A6 | same as A2 | oracle top two using labels | none | Non-deployable ceiling only |

A6 is never a system result; it quantifies remaining selector regret.

For the headline selector comparison, the same rows are also named M0–M6 so
the argument tree, analysis tables, and Writeup use one unambiguous sequence:

| ID | Canonical comparison | Maps to |
| --- | --- | --- |
| M0 | frozen neural top-2 | A0 |
| M1 | consensus-only slot 2 | first conservative selector control |
| M2 | consensus, otherwise best distinct valid candidate | stable-V2 development control |
| M3 | pointwise calibrated top-2 | A3 |
| M4 | conditional residual slot-2 allocation | A4 |
| M5 | M4 plus OOD/anchor-preserving gate | A5 |
| M6 | label oracle ceiling | A6 |

M0–M6 must consume identical frozen candidate receipts when used to support a
selector claim. M1/M2 may be run earlier as smoke tests, but those runs do not
substitute for the same-receipt M3–M5 mechanism comparison.

## Evidence ablations

Each row uses the identical candidate receipts from A5:

- E1: remove leave-one-demonstration-out evidence;
- E2: remove contract/metamorphic evidence;
- E3: remove cross-family agreement;
- E4: remove structural validity relations except hard schema checks;
- E5: remove complexity/description-length evidence;
- E6: remove support-distance/OOD abstention;
- E7: replace calibrated residual diversity with solver-family identity only;
- E8: agreement-only selector;
- E9: random second attempt among valid nonduplicates, repeated with fixed seeds.

## Budget ablations

- B25/B50/B75/B100: 25%, 50%, 75%, and 100% of the canonical candidate
  generation budget with the same stopping policy.
- P0/P1/P2: no program family, shallow typed program search, and full approved
  program budget.
- C0/C1: ungated and gated selector at identical candidate cost.

## Conditional agentic-program translation

If the cloud-agent generate/execute/feedback pattern is ever translated into
the offline candidate pool, freeze a 2×2 generation ablation before running it:

- F0R0: no demonstration-execution repair; duplicate slot-2 policy;
- F0R1: no repair; independent slot-2 generation;
- F1R0: one bounded demonstration-execution repair; duplicate slot-2 policy;
- F1R1: one bounded repair; independent slot-2 generation.

Compare pass@2, valid-output rate, duplicate rate, runtime, and candidate cost
on an equal-compute sealed split. Stop this family unless it adds at least 1.0
percentage point sealed pass@2 or three net new exact outputs on the eventual
authoritative evaluation. Cloud public-evaluation traces never enter this fit.

## Reproducibility control

- S0/S1: process-randomized task hashing in V1 versus task-ID BLAKE2b seeding in
  stable V2, with identical candidate and selector budgets. Stable V2 must
  reproduce candidate order and output hashes across fresh interpreter
  processes; V1 is retained only to quantify whether the seeding repair changes
  results rather than as the preferred submission candidate.

## Interpretation rules

1. A component is supported only if removal worsens the paired primary metric
   or materially worsens calibrated risk/coverage in at least four of five
   folds.
2. A larger oracle union with unchanged deployed pass@2 supports candidate
   diversity but refutes effective selection.
3. A higher pass@2 with a sharply higher harm rate is not evidence for the
   safety claim.
4. Runtime improvements count only when candidate quality and stopping rules
   are fixed.
5. Results with different candidate receipts are generation ablations; results
   over identical receipts are selector ablations. They are reported separately.
6. For the first conservative-agreement control, run the frozen 48-task
   development notebook before the disjoint 48-task sealed-holdout notebook.
   Do not select between policies on the holdout; it is a one-shot smoke test,
   not a substitute for the five near-duplicate-grouped folds.
7. A seed repair is supported as reproducibility engineering only if repeated
   stable-V2 runs are bitwise deterministic for all deterministic stages. Any
   accuracy difference is reported separately and cannot be credited to the
   selector logic.
8. Training retrospective precision is a support-shift diagnostic, never a
   generalization result. Paper Progress/Novelty remains closed until either
   the frozen public-evaluation method contributes at least three net new exact
   outputs over the copied anchor, or equal-compute sealed pass@2 improves by
   at least 1.0 percentage point with a causal same-receipt ablation.
9. Stop an alternate-view/TTT extension if development cannot first restore
   valid generation and exact solves, or if sealed evidence shows no gain.
   Published multi-perspective failure is a negative control, not a result to
   cite as support for agreement features.
10. Report each solver family's exclusive exact outputs, pairwise overlap,
    oracle gain over M0, selector regret, and oracle-gap recovery. If the sealed
    oracle gain is below 1.0 percentage point, stop the portfolio claim. If M5
    recovers less than 25% of a positive oracle gap, classify the result as a
    verification/selection bottleneck rather than Progress.
11. Run 348340917 is a runtime negative control, not evidence that residual
    selection fails: every available submission was byte-identical and TRM
    produced no candidate. Its first positive-initial-LR smoke repaired
    optimizer construction but failed before step one because the offline
    logger called built-in `print` with `step=`. Permit one separately versioned
    stdout-only logging shim on the identical smoke; no third patch or full run
    follows a failed guard. Any missing TRM candidate, timeout, incomplete
    decode, zero TRM-exclusive solve, or oracle gain below one output stops the
    sequence before sealed holdout.
12. The V2 stdout-logger kernel was already pushed and last observed running
    before a later local-only boundary. Local actual-source and optimizer/logger
    checks do not replace its terminal Kaggle receipt; no conditional full run
    starts until an authorized read proves every one-step guard passed.
13. The V176 overlay's two 49/50 single-rule rows and 50/50 combined row are
    post-hoc generation ablations because both rules were derived from those
    development misses. They establish code-path isolation and complementarity
    on the source corpus only; only a pre-frozen sealed result can support
    generalization, Progress, or an algorithmic novelty claim.
