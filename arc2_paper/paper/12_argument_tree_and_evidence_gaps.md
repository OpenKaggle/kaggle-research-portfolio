# Argument tree and evidence gaps

Status: v1.1, 2026-09-09. The root statement below is a hypothesis until every
promotion gate passes.

## Root claim

Under equal candidate-generation compute, a preregistered residual slot-2
selector can improve exact ARC pass@2 over a frozen neural top-2 anchor while
an out-of-support, anchor-preserving gate limits harmful overrides.

The claim has six required branches:

1. **Accuracy:** a completed linked ARC submission and exact paired results.
2. **Universality:** the same receipt/evidence/gate applies across neural,
   recursive, and program candidates and remains useful across grouped folds
   and structural strata.
3. **Progress:** improvement is measured against frozen top-2, not against a
   weak or unequal-compute baseline; oracle union and selector regret show what
   was actually closed.
4. **Theory:** conditional residual success matches the two-attempt objective;
   calibration and OOD abstention explain when an override is accepted.
5. **Completeness:** versions, data boundaries, compute, receipts, failures,
   ablations, public code, and rerun instructions are present.
6. **Novelty:** the contribution is the receipt-backed residual allocation and
   safety protocol, not TTT, TRM, program synthesis, generic ensembling,
   calibration, or abstention by themselves.

## Current six-dimension scorecard

| Dimension | Current 0–5 | Evidence already frozen | Decisive missing evidence |
| --- | ---: | --- | --- |
| Accuracy | 0 | Negative symbolic controls, a failed stable-V2 development run, a failed first repair smoke, passing local-only V2 source/API checks, and a frozen audit proving the planned V3 holdout is contaminated for V176 generalization | A new candidate with an evaluator-controlled never-seen labeled holdout, followed by passing development/holdout, public evaluation, and linked submission receipts |
| Universality | 1 | Common receipt/schema and grouped folds exist; a frozen typed-object family transferred one exact output but added zero union over V175 | Consistent incremental gains across folds, solver families, work quartiles, and structural strata |
| Progress | 1 | Frozen anchor, go/no-go threshold, oracle/regret metrics, post-hoc V3 diagnostics, a stopped typed-object zero-union result, and an explicit contaminated-holdout stop | Equal-compute ≥+1.0 pp on a rule-frozen never-seen labeled corpus or ≥3 new exact public-evaluation outputs; neither post-hoc 50/50, the contaminated 48-task slice, nor a duplicated symbolic hit counts |
| Theory | 3 | Conditional utility, calibration, OOD rule, bootstrap gate, and causal ablations preregistered | Empirical calibration and A3→A4→A5 mechanism evidence |
| Completeness | 3 | Rules, data hashes, tools, taxonomy, asset/runtime receipts, frozen V3 candidates, fail-closed three-stage execution contract, draft, and checklists exist | Completed rerun package, public notebook, figures, submission ID, authorship and license sign-off |
| Novelty | 2 | Prior-art boundary and selector-specific novelty statement are explicit; the narrow post-hoc V3 rules and contaminated slice are excluded from novelty evidence | Same-receipt ablation on a valid never-seen corpus proving residual selection/gating adds value beyond consensus-only |

Lowest dimension: **Accuracy**. The decisive next step is local protocol repair,
not another external run: quarantine the planned 48-task V3 slice and version a
successor around an evaluator-controlled labeled corpus whose solutions were
never available during method construction. The earlier full-corpus audit read
all 1,000 training solutions and made V176's zero-selection behavior on the
planned slice knowable, so re-splitting those tasks cannot restore a seal. If no
No eligible independent corpus is currently verified, so V176 is now retained
as systems/negative evidence. The already-pushed logging-only smoke remains useful
only for later runtime/format evidence; its status still requires explicit
authorization and cannot repair the data boundary. Do not upload a duplicate,
tune the frozen rules again, or repair the experimental deficit with prose.

## Mandatory main comparison

Using identical generated candidates and equal compute:

- M0: frozen neural top-2 anchor;
- M1: consensus-only slot 2;
- M2: consensus, otherwise best distinct valid candidate;
- M3: pointwise calibrated top-2;
- M4: conditional residual slot-2 allocation;
- M5: M4 plus OOD/anchor-preserving gate;
- M6: label oracle, reported only as the non-deployable ceiling.

The full paper claim requires M4 to beat M3 and M5 to reduce harm relative to
M4 without erasing most benefit. A larger M6 oracle with no M5 gain is a
selection failure, not progress.

## Evidence gap queue

| Priority | Gap | Acceptance test | Owner/source |
| ---: | --- | --- | --- |
| 1 | Systems-negative default; reopen only under a new pre-access corpus contract | Current audit finds no eligible replacement. A future candidate/contract must freeze solver, metrics, inclusion/exclusion, license, provenance, solution-access, zero-overlap, comparability, and one-shot evaluation before acquisition or answer view; same-1,000-task re-splits are rejected | Joint |
| 2 | Existing V2 smoke terminal read, then successor development | Only after the replacement is bound and with explicit authorization, read kernel `jahyee/arc2-trm-wandb-log-compat-smoke-v2` version 1 and download artifacts only if terminal; runtime evidence cannot establish generalization | ARC technical line |
| 3 | Genuine sealed holdout | Run exactly once after successor development interpretation freezes; same direction and ≥+1.0 pp if used for GO | ARC technical line |
| 4 | Current public evaluation | Frozen method on Kaggle 172 outputs; ≥3 net new exact outputs for Paper GO | ARC technical line |
| 5 | Selector mechanism | Same receipts; M3/M4/M5 benefit-harm and complete-task bootstrap | Paper analysis tools |
| 6 | Universality | Five grouped folds plus family/work/structure strata; no best-fold selection | Joint |
| 7 | Publication binding | Current team match and a frozen audited cover candidate exist; still require cover attachment, public notebook/version, ARC submission ID, source commit, author order, and permissions | Account owner + Paper task |

## Timeline

- [x] Initial 12-hour gate: directory, claim tree, evidence gaps, validation,
  data revision audit, and current negative controls created on 2026-09-09.
- [x] Initial 24-hour gate: v0.1 prose draft saved on 2026-09-09.
- [ ] 2026-10-12: architecture freeze (21 days before the November 2
  competition date).
- [ ] 2026-10-26: notebook and dependency freeze.
- [ ] 2026-10-30: validation and final selection only.
- [ ] 2026-11-02: competition notebook/submission date; the earlier Kaggle
  snapshot gives 23:59 UTC, while the public ARC Prize page gives no timezone.
- [ ] 2026-11-08: conservative internal Paper hard stop. The public ARC Prize
  page says November 8; both the current public Kaggle-page recheck and the
  earlier authenticated snapshot say November 9 at 23:59 UTC. Keep the earlier
  internal cutoff and recheck both submission surfaces before final binding.

## Low-score repair loop

After each evidence update, rescore all six dimensions from 0–5. Improve only
the lowest dimension's single most decisive missing item, then perform one
blind-review deletion pass separating facts, inferences, and future work. Two
updates without improvement trigger a narrative restructure, not more words.
Three recurrences of the same literature/writing gap are routed to research
group A. Experimental deficiencies remain with the technical line and cannot
be repaired by prose.
