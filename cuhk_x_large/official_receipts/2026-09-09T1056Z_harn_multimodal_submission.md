# HARn multimodal consensus submission receipt

Recorded: 2026-09-09 10:56 UTC / 2026-09-09 18:56 BJT

## Fixed subject-disjoint ablation

The official nonvisual supplement includes IMU, radar, and skeleton features for
HARn, although the first baseline used skeleton only. A fixed five-variant
ExtraTrees comparison was therefore run with 18 leave-one-subject-out folds:
IMU, radar, skeleton, early fusion, and late fusion. No test result selected the
variant.

The supplement omits 50 of the 562 HARn QA rows, representing 48 unique sensor
units. Those rows were explicitly marked missing and excluded from sensor evidence.
Among variants covering at least 90% of HARn single rows, early fusion was
selected by the predeclared rule.

- HARn single: 389 sensor-present rows; `0.8560411311` accuracy; worst subject
  `0.5714285714`.
- HARn object interaction: 123 sensor-present rows; `0.8780487805` accuracy;
  worst subject `0.5`.
- Model/report runtime: `87.265` seconds.
- Model SHA-256:
  `c13f654d5db6a5fa18ddec09fa2cea5a841b3a99c93ece8dd1a9fb0c4534e82e`.
- OOF SHA-256:
  `d86fc50215611202d20cf55ec73eb9fe24e022a39aed4d22654c11c03464b368`.
- Test-prediction SHA-256:
  `f50ba8ba31003d544d0c120ac5bb2f70f25e9747d04c2de8c721e40addadb1e9`.
- Report SHA-256:
  `3c13f12eed0c95ece27f765bf29a5e059301224b9155cbaec65faa2c624cf399`.
- Script SHA-256:
  `8b271e3c6b65e0f65e1e194f911e3586b717a3e31332ed1f169023eb930b9f4a`.

## Candidate gate

For HARn single questions only, the gate required:

1. Real early-fusion and skeleton inputs.
2. Exact agreement between the selected ExtraTrees expert and the frozen RF
   expert.
3. Disagreement with the frozen public parent.
4. If a valid zero-shot VLM output existed, VLM disagreement vetoed the sensor
   override; a VLM result could not create one.

Before the VLM veto, subject-disjoint validation contained 206 override rows:
176 expert-correct versus 17 parent-correct. The veto removed 22 weaker rows.
The accepted gate contained 184 rows, with `164/184 = 0.8913043478` expert
accuracy versus `12/184 = 0.0652173913` parent accuracy. All 18 subjects had
positive net delta; the minimum was `+3`.

The test gate accepted five rows already supported by the evidence. Three were
already present in submission `56116980`; the candidate added only
`test_0478` and `test_0499`. Two other sensor-agreement rows with available VLM
disagreement were vetoed.

- Candidate SHA-256:
  `ec88b07450e46e1e1c94e8e9365d5cfedd4fd55291677983d1f45a294b8cca6e`.
- Candidate MD5: `30f779196f7cc72f6dc6ce7a3308e4aa`.
- Candidate report SHA-256:
  `b2fa28d1896390c37fcf913fd2816f0550a1821896a9483cdbd9aeed12c84acc`.
- Candidate-builder SHA-256:
  `2e831bf63010daa323b507eaf2af7602170215ad52fe6f628d9ca47ae4838069`.
- Validator: PASS; 682 official IDs in exact order; all category grammars pass.
- Deterministic rebuild: same candidate and report hashes on the second run.

## Kaggle result and decision

- Submission reference: `56120755`.
- Submitted: 2026-09-09 10:55:49.060 UTC.
- Status: `COMPLETE`.
- Public score: `0.77777`.
- Current best comparison: submission `56116980`, public score `0.78070`.
- Aggregate change: `-0.00293`.

Decision: `REJECTED`. The strong sensor-consensus validation did not transport
well enough to justify replacing the visual-qualified candidate. The entire
two-row expansion is rejected. The public score is not used to infer which row
was public, which prediction was wrong, or any hidden label, and no follow-up
row probe or threshold-tuning submission will be made. Submission `56116980`
remains the current private-robustness candidate.

## Public notebook inventory follow-up

The official Kaggle kernel list currently contains seven notebooks. The only
previously unaudited entry, Chaitanya Jamble's public notebook, was downloaded
with source SHA-256
`8c4f2d8d3d680934b4fe95ce57cadddbb83f8945f75834f618703b9c307a2729`.
Its own run reports row-wise five-fold OOF `0.2388` (single `0.2899`, multi
`0.1001`, sequence `0.1104`) and therefore does not satisfy the campaign's
subject-disjoint validation rule or improve the anchor. Its valid 682-row output
SHA-256 is
`d65424095adc0db784eb81994ccf5c01325ee7494bdf469e543cdd5a67ad1897`;
it was audited only and not submitted.
