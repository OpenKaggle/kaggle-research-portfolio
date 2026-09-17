# Kaggle Writeup skeleton

Target: 1,350–1,450 words, leaving margin below the 1,500-word platform limit.
Do not turn this into a chronological competition diary.

The first saved prose draft is `drafts/writeup_v0.1.md`. Keep this skeleton as
the word-budget contract; revise the draft rather than replacing evidence gaps
with projections.

Executable companion `manifests/writeup_evidence_contract_v1.json` binds the
current draft hash, required sections, six rubric dimensions, key numerical
claims, word limits, and final platform fields. Its `DRAFT` pass is structural
only; `FINAL_SUBMISSION_READY` additionally requires six supported dimensions,
zero placeholders, platform word-count evidence, and every public link/hash.

## Title

Evidence-Gated Attempt Allocation for Heterogeneous ARC Solvers

## Abstract — 100 words

- Problem: many heterogeneous candidates, only two exact-match attempts.
- Contribution: demonstration-only calibrated selection, conditional diversity,
  and anchor-preserving abstention.
- Result: insert only completed public-eval/Kaggle numbers and equal-compute
  deltas.
- Main conclusion: state which component caused the gain and its claim limit.

## Introduction — 170 words

- ARC measures rapid induction of novel transformations from few examples.
- Candidate generation has improved, but candidate selection under hidden-set
  shift is under-measured.
- Explain why pass@2 makes residual diversity and harm control central.
- State the research question and contributions, not the implementation history.

## Prior work — 170 words

- Cite ARC's skill-acquisition/generalization motivation and the ARC-AGI-2
  benchmark paper without claiming that a benchmark result measures general
  intelligence by itself.
- Cite the ARC Prize 2024 report and Akyürek et al. for test-time training and
  neural/program ensembles; these establish precedent, not our score.
- Cite HRM/TRM as recursive-solver precedents, while treating all source-model
  accuracy numbers as external until reproduced here.
- Cite portfolio selection, neural calibration, and selective prediction for
  the general machinery; do not claim to invent abstention or calibration.
- Distinguish this work: heterogeneous candidate receipts plus risk-controlled
  two-slot allocation with abstention, evaluated under equal compute.
- Use the exact sources and claim restrictions in
  `10_related_work_and_claim_boundaries.md`.

## Approach — 410 words

1. Candidate pool: NVARC/Qwen, TRM, typed object/program solver.
2. Demonstration-only evidence and valid task contracts.
3. Out-of-task calibrated correctness and support detection.
4. Conditional marginal utility for attempt 2.
5. Anchor-preserving safety gate.
6. Complexity and offline execution envelope.

Include one compact algorithm box or pipeline figure. Avoid unnecessary equations;
the marginal-utility expression is sufficient.

## Results — 320 words

- Exact public evaluation and Kaggle result with submission ID.
- A0/A2/A3/A4/A5/A6 compact table: anchor, union, calibration, diversity, gate,
  oracle ceiling.
- Paired interval, benefit/harm counts, coverage, and selector regret.
- One evidence ablation that isolates the core gain.
- One negative result: direct archived DSL transfer was 0/167; state why this
  motivated object reasoning rather than implying success.
- One shift result: the fixed V175 LOO selector had 28.53% retrospective
  training coverage at 100% direct precision but 0% current-evaluation
  coverage. Explain why this motivates grouped outer validation and support
  detection; do not present the training number as performance.
- One integrity result: the planned ID-disjoint 48-task V176 slice is not
  method-sealed because an earlier audit consumed all 1,000 source solutions
  and made zero V176 selection on that slice knowable before a run. Report it
  only as a blocked runtime/format fixture, never as generalization, Progress,
  Novelty, or Accuracy evidence.
- One corpus-eligibility result: the bundled parent already audited five
  corpora totaling 2,080 tasks/2,563 outputs, including complete ConceptARC.
  State that no eligible ARC-AGI-2 replacement corpus is currently verified
  and that 1D-ARC, MiniARC, community, or synthetic tasks are domain-shift
  mechanism tests only.
- Do not report training-set performance as the result.

## Why it works — 170 words

- Independent families enlarge the union but increase selection risk.
- LOO and valid contracts measure hypothesis stability from the task itself.
- Residual diversity matches pass@2 utility better than independent ranks.
- Calibration and abstention bound extrapolation; preserving the anchor converts
  uncertain novelty into low coverage rather than uncontrolled harm.
- State why these ideas can transfer beyond ARC to any small-feedback,
  multi-proposal exact-decision problem.

## Limitations and failure analysis — 100 words

- Demonstrations may underdetermine the task.
- Contract libraries are incomplete and task validity is inferred imperfectly.
- Calibration can shift between public and private distributions.
- Program coverage and 12-hour compute remain binding.
- Mention the dominant preregistered failure codes with actual counts.

## Conclusion — 80 words

- Restate the measured contribution and what remains between the deployed
  selector and oracle union.
- Link public code/notebook and exact reproduction manifest.

## Required media

- Cover image: clean candidate-pool → evidence → two attempts diagram.
- Figure 1: oracle union, deployed score, and selector-regret decomposition.
- Figure 2 only if space helps: risk-coverage curve or failure composition.
