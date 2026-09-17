# Related work and claim boundaries

Checked against primary publication pages on 2026-09-09. The 1,500-word Kaggle
writeup should cite only the subset needed for the final argument; this file is
the longer claim-control record.

## Benchmark lineage

1. François Chollet, [On the Measure of Intelligence](https://arxiv.org/abs/1911.01547),
   2019. Use for ARC's motivation: intelligence evaluation should distinguish
   stored skill and priors from efficient acquisition on novel tasks. Do not
   infer that any single ARC score establishes general intelligence.
2. François Chollet, Mike Knoop, Gregory Kamradt, Bryan Landers, and Henry
   Pinkard, [ARC-AGI-2: A New Challenge for Frontier AI Reasoning Systems](https://arxiv.org/abs/2505.11831),
   arXiv v2, 2026. Use for ARC-AGI-2's continuity with the input/output-pair
   format and its goal of increasing task complexity and evaluation resolution.
   Competition mechanics still come from the current official rules, not this
   paper.
3. François Chollet, Mike Knoop, Gregory Kamradt, and Bryan Landers,
   [ARC Prize 2024: Technical Report](https://arxiv.org/abs/2412.04604), arXiv
   v2, 2025. Use to establish that test-time training and deep-learning-guided
   program synthesis were already central ARC approaches. This prevents a false
   novelty claim for merely combining neural and program candidates.

## Candidate-generator precedents

4. Ekin Akyürek et al., [The Surprising Effectiveness of Test-Time Training for
   Few-Shot Learning](https://arxiv.org/abs/2411.07279), arXiv v2, 2025. Use for
   per-instance parameter adaptation from few-shot examples and the precedent
   of neural/program ensembling on ARC. Its reported ARC-AGI-1 results do not
   validate our Qwen/NVARC implementation, current data revision, or score.
5. Guan Wang et al., [Hierarchical Reasoning Model](https://arxiv.org/abs/2506.21734),
   2025, and Alexia Jolicoeur-Martineau, [Less is More: Recursive Reasoning with
   Tiny Networks](https://arxiv.org/abs/2510.04871), 2025. Use as the architectural
   lineage for the recursive solver family. The local TRM checkpoint's accuracy,
   complementarity, and runtime require our own frozen receipts.
6. [Multi-Perspective Transformers in ARC-AGI-2 Challenge](https://arxiv.org/html/2605.01154v1),
   arXiv v1, 2026. Table 2 reports 21.7% evaluation accuracy for the
   pretrained-only TinyLM, while TTT, product-of-experts, and TTT+PoE each
   report 0% evaluation accuracy and 100% failed generations. The paper
   attributes the failure to row-major training mismatch and task-level
   overfitting. Use this only as negative evidence: alternate views and
   agreement are hypotheses to validate, not gains to inherit.

## Selection, calibration, and abstention precedents

7. Maria-Florina Balcan, Tuomas Sandholm, and Ellen Vitercik,
   [Generalization in Portfolio-Based Algorithm Selection](https://arxiv.org/abs/2012.13315),
   AAAI 2021. Use for the distinction between building a diverse portfolio and
   learning an instance-wise selector, and for the warning that larger
   portfolios can increase overfitting pressure. It does not establish that our
   evidence vector or selector generalizes.
8. Chuan Guo, Geoff Pleiss, Yu Sun, and Kilian Q. Weinberger,
   [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html),
   ICML 2017. Use for the need to test whether confidence corresponds to
   correctness probability. Do not call raw solver scores calibrated, and do
   not claim probabilistic validity beyond the out-of-fold diagnostics.
9. Yonatan Geifman and Ran El-Yaniv,
   [SelectiveNet: A Deep Neural Network with an Integrated Reject Option](https://proceedings.mlr.press/v97/geifman19a.html),
   ICML 2019. Use for selective prediction and risk-coverage terminology.
   Abstention is established prior art; our candidate novelty is the
   ARC-specific anchor-preserving, two-attempt override policy.

## High-score agentic systems outside the Kaggle compute envelope

10. [Confluence Labs' ARC-AGI-2 solver](https://github.com/confluence-labs/arc-agi-2)
    reports 97.92% on the public evaluation set using 12 Gemini CLI agents per
    test input, up to 10 refinement loops, 132 simultaneous sandboxes, and API
    credentials. [Symbolica ARCgentica](https://github.com/symbolica-ai/arcgentica)
    reports 85.28% with Claude Opus 4.6, two independent attempts, agent-written
    Python programs, provider APIs, and $6.94 per task. These are public-eval,
    cloud-agent results, not reproducible baselines for the Kaggle offline
    four-L4 envelope. Their architectural abstraction—generate a program,
    execute it on demonstrations, use feedback, regenerate, and preserve
    attempt diversity—may motivate future candidate generators only with the
    resource and exposure difference stated explicitly. Their public traces
    never enter the frozen holdout or selector fit.

11. [PoTRE](https://arxiv.org/html/2607.20268) reports, for its
    Gemini-3-Flash public-evaluation component table, 53/120 oracle coverage
    versus 46/120 final synthesis, with Spectrum Search contributing 17
    exclusive solves; its separately reported pass@2 result rises from 46 to
    54. This is unusually clear evidence that candidate diversity, synthesis,
    and second-attempt value are distinct measurements. It motivates our
    family-exclusive coverage, oracle regret, and gap-recovery metrics, but its
    Gemini-based public-evaluation results do not validate our offline selector.
12. [Compositional Neuro-Symbolic Reasoning](https://arxiv.org/html/2604.02434)
    reports a four-candidate pool from two independent pipelines and selects
    twice without replacement, improving its strongest single solver from
    26.6% to 30.8% on public evaluation. Its component table reports 24.4% for
    symbolic hints plus self-consistency, 20.5% for hints only, 17.5% for
    self-consistency only, and 15.0% for neither. This is a close precedent for
    distinct slot allocation and component isolation, not evidence for our
    residual model: the system uses external frontier-model services and
    public-evaluation experiments.

## Defensible novelty statement

The proposed contribution is not a new neural architecture, recursive solver,
program synthesizer, ensemble, generic calibrator, or generic reject option. It
is a tested interface and allocation policy for the two-attempt ARC setting:

- heterogeneous candidates enter through a common provenance-bearing receipt;
- all deployable evidence is recomputable from demonstrations and test inputs;
- slot two is allocated by estimated residual success conditional on slot one
  failing, rather than by independent rank;
- out-of-support or non-positive-gain overrides retain the frozen anchor;
- the claim is evaluated with identical candidate receipts, task-grouped outer
  folds, benefit/harm accounting, and an equal-compute anchor.

This statement becomes a result only if the preregistered prospective gates
pass. Until then it is a method proposal.

## Claims that require our own evidence

- Any ARC-AGI-2 accuracy, lift, runtime, calibration, or risk-coverage number.
- Any assertion that Qwen/NVARC and TRM errors are complementary on the current
  task revision.
- Any assertion that demonstration agreement, LOO stability, contracts, or
  support distance predict correctness out of task.
- Any assertion that the gate reduces harm or that residual allocation improves
  pass@2.
- Any assertion that the method runs within 12 hours on four Kaggle L4 GPUs.

Source papers may motivate these hypotheses, but only the frozen receipts,
outer-fold results, ablations, and Kaggle run can support them.

Alternate-view or TTT extensions are stopped unless a development receipt
first shows valid generation, representation diversity, and an association
between view consistency and exact success. A source paper's positive control
does not waive that gate.
