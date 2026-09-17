# Public-intelligence brief: Poker + Traffic Flow Bench

Snapshot date: **2026-09-09 (Asia/Shanghai)**. All resources below are public. No
private labels, generator artifacts, identity data, or unpublished submissions were
used. “Fact” means directly stated or executable in the linked source. “Inference”
means a proposed competition strategy derived from those facts.

## Immediate return-to-build conclusions

1. **Poker: complete evidence coverage before adding model complexity.** The official
   metric averages EvidenceMAP@5 over true target pairs; evidence attached to a
   non-target pair is not itself penalized. A missed target contributes zero. Therefore
   every evaluation pair with shared hands should receive five valid, pair-shared hand
   IDs, ranked with a family-conditioned scorer. The public PU notebook only applies
   its learned evidence ranker to the top 20,000 pairs and falls back to heuristics for
   the rest; the official starter only ranks evidence for the top 100. Removing those
   coverage bottlenecks is cheap and metric-aligned.
2. **Poker: PairAP is 70%; preserve a strict continuous ordering.** Do not threshold,
   round, or flatten `risk_score`. Elkan–Noto's probability rescaling alone is monotone
   and cannot change AP; PU work is useful only if it changes training/ranking. Compare
   trusted PN, biased-PU, and a proper PU-risk model under both pool-group and temporal
   validation rather than assuming `unknown_weight=.35` is calibrated.
3. **Poker: simulate the hidden fourth family with leave-one-behavior-out (LOBO).** The
   public fourth family has no positive labels. Hold out each disclosed family in turn,
   train the supervised family models on the other two, and test whether a generic
   counterfactual/anomaly score retrieves the held-out family over confirmed negatives.
   This is the closest legal validation of `other_coordination` available.
4. **Traffic: a queue-only patch cannot close the present gap.** The current third-place
   public score is 0.87742 versus 0.71846 for the only scored public pipeline. That
   pipeline's onset clock is also shifted: it measures from the last history sample
   (`T-5`) and activates `dt >= 30`, which means only official horizons `T+25` and
   `T+30`. Fix this, but prioritize topology-aware Task 1 because State (0.35) and
   Physics (0.15) share the same submission and Task 1 has honest local labels.
5. **Traffic: separate onset and ongoing models.** Ongoing should start with persistence
   plus upstream shockwave propagation. Onset needs a hazard/ranking model from demand /
   capacity, downstream speed slope, upstream density and ramp inflow. Optimize binary
   masks directly for window IoU on noisy train-derived pseudo-windows, not pointwise
   accuracy.

## Current competition snapshot

### Detect Suspicious Value Transfers in Poker

- **Fact, official page, accessed 2026-09-09:** [competition overview and metric](https://www.kaggle.com/competitions/detect-suspicious-value-transfers-in-poker/overview).
  Deadline from Kaggle CLI: **2026-09-20 22:00 UTC**; prize pool **USD 5,000**;
  the current account reports `userHasEntered=True`.
- **Fact:** 2,000,000 synthetic six-player NLHE hands, 12,000 players, 400
  persistent pools of 30, about 5,000 hands per pool; first 60% development and
  last 40% evaluation. Evaluation has 112,540 pairs.
- **Fact:** public labeled positives are incomplete. Unlisted development pairs are
  explicitly **UNKNOWN, not negative**. Confirmed non-targets are also supplied.
- **Fact:** target families are directed transfer, soft play, coordinated isolation,
  and an evaluation-only `other_coordination` family.
- **Fact:** score = `0.70 PairAP + 0.20 EvidenceMAP@5 + 0.10 BehaviorMAP`.
  BehaviorMAP is macro AP over the three disclosed families; `other_coordination`
  is excluded. Public/private is 30/70, stratified by behavior family. Equal risk
  ties are broken by `pair_id`.
- **Fact:** evidence must be evaluation-period hands shared by the pair, with no
  duplicates in a row. `NO_EVIDENCE` is ignored; bad/irrelevant hand IDs get zero.
- **Fact:** prize verification requires a <=1,500-word writeup, reproducible public
  notebook/repository and five case reviews within seven days of the private board.
  Gameplay inference is required; exploiting IDs/order/generator internals is banned.
- **Fact, public board queried 2026-09-09:** top three are **0.93601, 0.90098,
  0.89765**. This is a public-board snapshot, not an estimate of private rank.

### 2026 IEEE Big Data Traffic Flow Bench

- **Fact, official sources, accessed 2026-09-09:** [Kaggle competition](https://www.kaggle.com/competitions/2026-ieee-big-data-traffic-flow-bench)
  and [official MIT-licensed repository](https://github.com/jacky850/trafficflowbench-public).
  Local clone is pinned at commit `205faf1b78d6f73a5e55e1168d161dcbbdb86a58`
  dated **2026-09-04**. Deadline from Kaggle CLI: **2026-11-07 06:55 UTC**;
  prize pool **USD 3,500**; current account reports `userHasEntered=True`.
- **Fact:** ten directional freeway corridors, five-minute resolution, 11 months
  of synthetic data calibrated from real detectors. Train is 273 days with answers;
  validation is 31 days / five incidents; private is 30 days / seven independently
  generated incidents.
- **Fact:** score = `0.35 State + 0.30 Queue + 0.15 Physics + 0.20 ODME`.
  Official baseline components are 0.6903, 0.2518, 0.3467, 0.5904, total 0.4872.
- **Fact:** queue labels and organizer boundary flows are withheld on every split.
  Task 1 is locally scorable on train; Task 4 is only partly scorable. A local
  Physics score around 0.33 is an evaluator fallback and is not a useful ranking
  signal.
- **Fact, public board queried 2026-09-09:** top three are **0.92332, 0.92116,
  0.87742**. The only scored public notebook is 0.71846.

## Poker: official/public Kaggle material

### Public inventory (queried 2026-09-09)

- [Official starter: Pair Ranking & Evidence Retrieval](https://www.kaggle.com/code/florianderoofr/getting-started-pair-ranking-evidence-retrieval),
  last run **2026-09-05**, 7 votes at query time.
- [PU-Aware Evidence Ranker](https://www.kaggle.com/code/nomannic19/poker-collusion-pu-aware-evidence-ranker),
  last run **2026-09-06**, 11 votes.
- [Official reference metric](https://www.kaggle.com/code/florianderoofr/slash-poker-competition-metric),
  last run **2026-09-06**.
- [Clarifications, topic 739839](https://www.kaggle.com/competitions/detect-suspicious-value-transfers-in-poker/discussion/739839),
  posted **2026-09-06**. The organizer replied that public external data and
  pretrained models are permitted and linked the reference metric.

Downloaded public sources are under `traffic/intel/poker/notebooks/`.

### What the notebooks actually do

**Official starter — fact.** It builds eight pair features: shared-hand exposure,
gross/directional transfer, showdown/fold rates, contribution gap, and maximum
single-hand transfer; uses class-balanced logistic regression for pair risk and a
separate positive-only behavior classifier; retrieves evidence only for its top 100
pairs using a transfer/contribution heuristic. It explicitly leaves action order,
cards, chronological validation and partner-vs-outsider controls as extensions.

**Public PU ranker — fact.** It samples up to 60 unknown pairs per table (filtered
by evaluation-like exposure and excluding players belonging to public positive pairs),
builds BB-normalized hand/action/partner/outsider features and tail aggregates, then:

- trains XGBoost risk with weights positive 2, confirmed negative 1, unknown 0.35;
- uses `StratifiedGroupKFold` grouped by table;
- trains a three-family positive-only behavior model and selects the predicted-positive
  rate from a 0.1%-5% grid on a weighted proxy validation;
- trains an `XGBRanker(objective="rank:pairwise", eval_metric="map@5")` by pair;
- scores learned evidence only for the top 20,000 evaluation pairs and uses a family
  heuristic elsewhere.

**Inference:** this is a strong feature-engineering reference, but `.35` is a heuristic
biased-PU weight, not Elkan–Noto or nnPU. Grouping by table protects against pool leakage
but does not test the first-60% to last-40% temporal shift. Its positive-rate tuning is
also evaluated against proxy labels, so it can be sharply miscalibrated. The evidence
fallback creates an avoidable metric discontinuity at rank 20,000.

### Poker research that transfers

1. **PU learning.** [Elkan & Noto, KDD 2008](https://cseweb.ucsd.edu/~elkan/posonly.pdf)
   show that under selected-completely-at-random (SCAR) labeling, a classifier of
   labeled-positive vs unlabeled estimates the true class probability up to a constant.
   [Kiryo et al., NeurIPS 2017](https://papers.nips.cc/paper/6765-positive-unlabeled-learning-with-non-negative-risk-estimator)
   give a non-negative PU risk estimator that avoids the negative-risk overfitting of
   flexible models.
   - **Reproducible use:** estimate the PU class prior only inside each training fold;
     compare PN-only, Elkan–Noto/biased-PU, and nnPU. Retain confirmed negatives in an
     explicit supervised negative term.
   - **Risk:** the competition does not state SCAR. Public positives may be selected by
     family or evidence strength, invalidating Elkan–Noto calibration. Probability
     division by a constant is monotone and alone cannot improve AP.
   - **Stop:** abandon formal PU as the main model if it fails to improve mean temporal
     OOF AP by **>=0.01** and worst-family AP by **>=0.005** across three seeds.

2. **Metric-aligned hand ranking.** [XGBoost LTR 3.2 documentation, accessed
   2026-09-09](https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html)
   documents query grouping, `rank:map`, `rank:ndcg`, and `rank:pairwise`; with enough
   binary effective pairs, matching a MAP target with `rank:map` can be beneficial.
   - **Reproducible use:** `qid=pair_id`, relevance = listed development evidence,
     compare `rank:pairwise`, `rank:map`, and binary hand classifier; score the exact
     official MAP@5 in OOF pairs. Use `topk` with 6-10 pairs/sample for a top-five target
     and fixed seeds/platform.
   - **Risk:** evidence is sparse and pair query lengths vary. `rank:map` may have too few
     effective pairs, in which case pairwise/mean sampling can generalize better.
   - **Stop:** keep the simpler model unless exact OOF EvidenceMAP@5 gains **>=0.015**.

3. **Behavior-agnostic counterfactual signal.** [Mazrooei, Archibald & Bowling,
   AAAI 2013, published 2013-06-30](https://ojs.aaai.org/index.php/AAAI/article/view/8674)
   introduce a “collusion table” based on how each player's decisions affect others'
   utility, intentionally avoiding a fixed collusion pattern. The paper validates the
   idea in poker. [Greige et al., 2022](https://arxiv.org/abs/2203.05121) combine graph
   relationships with behavioral features and Isolation Forest in another multiplayer
   domain.
   - **Reproducible use:** estimate each player's normal action/value policy conditional
     on street, position, hand strength, pot odds, stack and opponents. For every dyad,
     aggregate signed residual utility effects `A->B`, `B->A`, both-vs-outsider, mutual
     information of sequential actions, and episodic top-k/burst features. Train an
     Isolation Forest or robust covariance score on confirmed negatives; validate with
     LOBO (each known family treated as the unknown fourth family).
   - **Risk:** generic anomalies also include the deliberately difficult benign cases
     (tilt, weak play, strategy change). Raw anomaly score should be a small blend, not
     replace supervised risk.
   - **Stop:** use it only if LOBO AP improves in at least **2 of 3** held-out families
     and full known-family OOF AP falls by **<0.01**.

4. **Pair/evidence multi-instance alignment — inference from the metric and data.** A
   coordinated pair is a bag of mostly normal hands with a few planted evidence hands.
   Train a hand scorer first, then derive pair features from max/top-3/top-5 evidence
   probabilities, noisy-OR, burst length and directional consistency. This makes the
   70% pair head and 20% evidence head share signal rather than compete.
   - **Minimal experiment:** add only OOF hand-score aggregates to the current pair
     matrix; do not feed in-sample evidence predictions. Compare pair AP and family AP.
   - **Risk:** leaked in-sample evidence logits will produce spectacular but false CV.
   - **Stop:** discard if group+time OOF PairAP gain is **<0.01** or seed spread > gain.

### Poker minimum implementation sequence

1. Remove evidence top-N limits and validate every row has five unique shared eval hands.
2. Recompute pair features in chronological quartiles; add top-k, recency, burstiness,
   partner-vs-outsider and action-sequence residual features.
3. Produce two validation reports: unseen-table GroupKFold and purged chronological
   early-to-late backtest. Optimize the exact official three-part score, never proxy AP
   alone.
4. Add OOF evidence logits to pair features; test `rank:map` vs pairwise.
5. Only then test hybrid PN+PU and a low-weight LOBO-validated unknown-family anomaly
   blend.

Expected benefit: **high** from coverage + pair/evidence alignment, **medium/high** from
conditional sequence features, **uncertain/medium** from formal PU, **uncertain** from
unknown-family anomaly detection. The 0.89765 third-place line implies that feature/CV
quality, not merely producing a valid submission, is required.

## Traffic: official/public Kaggle material

### Public inventory (queried 2026-09-09)

- [Official repository](https://github.com/jacky850/trafficflowbench-public), 24 commits
  visible at query time; local pinned commit dated **2026-09-04**.
- [Traffic Flow Bench Pipeline](https://www.kaggle.com/code/lamhuy8904/traffic-flow-bench-pipeline),
  last run **2026-09-08**; page reports runtime 28m56s and public/best **0.71846 V32**.
- [Traffic Flow Bench EDA Deep Dive](https://www.kaggle.com/code/lamhuy8904/traffic-flow-bench-eda-deep-dive),
  same public author; downloaded source retained locally.
- **Fact:** Kaggle topic API returned **no public discussion topics** on 2026-09-09.

### What the public 0.71846 pipeline actually does

**Fact from downloaded V32 source/output:**

- State: weekday/time historical profiles plus within-link temporal interpolation and
  same-timestamp pandas interpolation over frame row order; 0.85 temporal / 0.15 spatial;
  a three-step density smooth is blended 15% into flow, then capacity/free-speed bounds.
- Queue: two fixed “recurrent bottleneck” links per included panel; ongoing persistence;
  onset uses `dt >= 30` measured from the last history record. Because that record is
  `T-5`, official forecast times are interpreted as 10..35 minutes and only `T+25/T+30`
  are switched on. The downloaded queue output has 80 windows with four positive cells
  each (two links x two horizons).
- ODME: nonnegative least squares with weak-prior regularization. The notebook's local
  EDA substitutes the released weak prior for hidden `f*` when discussing unavailable
  metric components; that is a solver diagnostic, not an honest score.

**Inference:** the 0.71846 score proves the complete pipeline is valid, not which task
is good. The notebook's claimed queue “offline IoU” is not reproducible against official
labels because the organizer withholds them. Spatial interpolation over row order should
not be assumed to follow road topology without explicitly joining released topology.

## Traffic research that transfers

### A. Spatiotemporal state imputation (State 0.35, also drives Physics 0.15)

1. [GRIN / Filling the Gaps, ICLR 2022](https://github.com/Graph-Machine-Learning-Group/grin)
   is an official reproducible implementation of a bidirectional graph recurrent
   imputation network, including METR-LA and PEMS-BAY traffic configurations.
2. [ImputeFormer, KDD 2024](https://arxiv.org/abs/2312.01728) combines a low-rank
   inductive bias with a Transformer for generalizable spatiotemporal imputation;
   [official code](https://github.com/tongnie/ImputeFormer) includes block-missing traffic
   runs and GRIN/BRITS/SAITS/SPIN baselines.
3. [DSTGCN, submitted 2021-09-17](https://arxiv.org/abs/2109.08357) specifically studies
   traffic imputation under several complex missing patterns and combines recurrent
   temporal modeling with graph convolutions and dynamic graph estimation.

**Minimal experiment before deep models:** on official train, use the exact R1/R2/R3
masks and last 31 days as a temporal holdout. Replace row-order interpolation with an
oriented topology feature block: upstream/downstream values at lags based on link travel
time, same-link temporal interpolation, weekday/time profile, ramp availability flags,
and density/capacity ratios. Fit a per-variable LightGBM/CatBoost residual or ridge model.
Then run GRIN only if this graph baseline proves that adjacency helps.

- **Metric:** official macro State score, plus RMSE by regime/corridor/congestion and a
  surrogate conservation residual calculated on complete train states.
- **Risk:** random masks flatter deep models; official masks include daily R1/R2/R3
  regimes and temporal blocks. Validation/private incidents are independent, so random
  cell CV will overstate gain. Deep models can also smooth incident fronts, hurting LWR.
- **Expected benefit:** **high**, because one file covers 50% of total score.
- **Stop:** do not escalate to GRIN/ImputeFormer unless topology features improve State
  by **>=0.01** on the temporal holdout. Reject any learned model whose worst R3/corridor
  score drops or whose incident-period RMSE rises >3%.

### B. FD/LWR consistency (Physics 0.15 through Task 1)

- [Physics-Informed Deep Learning for Traffic State Estimation, submitted
  2021-01-17](https://arxiv.org/abs/2101.06580) jointly uses observed loop-detector data
  and LWR/fundamental-diagram residuals and reports better data efficiency than purely
  model- or data-driven baselines on NGSIM.
- [Nonlocal LWR PINN, submitted 2023-08-22](https://arxiv.org/abs/2308.11818) replaces
  purely local speed-density behavior with a downstream look-ahead density kernel and
  reports improvements over local-LWR PIDL on NGSIM/CitySim.
- [Official TrafficFlowBench scoring specification](https://github.com/jacky850/trafficflowbench-public/blob/main/docs/SCORING_SPEC.md)
  defines `Physics = 1/3 FD + 2/3 LWR`; the larger lever is conservation.

**Minimal experiment:** post-process only masked predictions with a sparse, corridor-day
constrained least-squares projection:

`data loss + lambda_lwr * conservation residual^2 + lambda_fd * triangular-FD violation^2`,

holding observed eligible cells fixed and treating unavailable ramp readings as missing,
never zero. Sweep lambdas on complete train masks. Use released link lengths/topology,
5-minute `dt`, and per-link FD parameters. Add a nonlocal one-link downstream kernel only
after the local projection succeeds.

- **Risk:** the true Physics anchors are hidden; minimizing an approximate residual can
  move away from the unknown noisy truth and lower State. A local evaluator value ~0.33
  is explicitly meaningless.
- **Expected benefit:** **medium/high** if a Pareto-safe projection is found.
- **Stop:** retain only candidates with State loss **<=0.003** and >=10% improvement in
  held-out train conservation residual. Do not tune against the 0.33 fallback.

### C. Queue onset and ongoing (Queue 0.30)

- [FHWA Recurring Traffic Bottlenecks primer, 2018](https://ops.fhwa.dot.gov/publications/fhwahop18013/appa.htm)
  explains that queue-forming shockwaves propagate backward and mark abrupt changes in
  speed, density and flow.
- [Cao, Fan & Liu, 2018](https://trid.trb.org/View/1571777) compare LWR-based local
  shockwave-speed estimation and aggregation variants for real-time end-of-queue
  detection, reporting the LWR+hybrid combination best in their NGSIM study.
- [Dynamic-capacity shockwave queue estimator, 2013](https://trid.trb.org/View/1322652)
  finds discharge flow after queue onset is dynamic and especially sensitive for queue
  length, supporting separate onset/ongoing state estimation.

**Reproducible queue method:**

- Build train pseudo-labels with hysteresis from observed speed/free-flow ratio (enter
  queue <=0.58, leave >=0.65) only at high-coverage cells. Sample historical windows that
  mimic the official onset/ongoing contract.
- Ongoing: persist the current queue, estimate free/congested states `(q,k)` near its
  boundary, compute shockwave velocity `w=(q2-q1)/(k2-k1)`, propagate upstream by released
  link lengths, and learn a small correction from slope/ramp/capacity features.
- Onset: fit discrete-time hazards for each bottleneck and each of six horizons using
  current demand/capacity, 15/30/60-min speed slopes, upstream density, downstream speed
  drop, ramp inflow and historical weekday/time hazard. Convert hazards to a connected
  link-time mask and tune threshold/dilation for IoU.
- Blend persistence, hazard and physics masks by optimizing mean of onset/ongoing IoU,
  not cell accuracy. Test recurrent bottleneck priors with leave-one-month and
  leave-one-incident backtests.

- **Risk:** pseudo-labels use noisy observations while official labels use latent state;
  threshold-adjacent cells are ambiguous. Fixed bottlenecks can overfit the five public
  incidents and fail on seven independent private incidents.
- **Expected benefit:** **high but weakly observable locally**; official persistence is
  only 0.2518 and Task 2 has the largest relative headroom.
- **Stop:** require pseudo-window IoU +**0.10 absolute** over persistence in both onset
  and ongoing, and stability across at least eight corridors. One queue-only public
  submission must move total score by >=0.02; otherwise pause rather than LB-tune.

### D. ODME (0.20)

- [Bell, Transportation Science 1983](https://pubsonline.informs.org/doi/10.1287/trsc.17.2.198)
  estimates an OD matrix from link counts by scaling a prior to reproduce measurements.
- [Hazelton, Transportation Research B 2012](https://www.sciencedirect.com/science/article/pii/S019126151100138X)
  describes likelihood/GLS connections for OD inference from link counts plus partial
  routing information and stresses the underdetermined nature of the problem.
- The official baseline solves nonnegative `||Af-c||^2 + 0.05||f-b||^2`. Note that
  **0.05 is the official repository constant**; any differently scaled public-notebook
  lambda is not directly comparable without feature scaling.

**Minimal experiment:** solve a small regularization family:

1. official quadratic prior;
2. relative quadratic `sum((f-b)^2/(b+eps))`;
3. KL/entropy prior `sum(f log(f/b)-f+b)`;
4. bootstrap counts within measurement uncertainty and median-ensemble path flows.

Tune with leave-one-measured-link-out prediction error and an L-curve, not same-link
fit. Preserve destination totals/shares from the weak prior as a soft group penalty.

- **Risk:** only `S_link` (25% of Task 4) is honestly computable. Exact count fitting can
  walk wildly in the nullspace and lose the larger hidden `S_od` term (45%) plus `S_dev`.
- **Expected benefit:** **medium**, inexpensive after data access.
- **Stop:** reject solvers that do not improve held-out link score by >=0.02 or whose
  path-flow solution changes >25% across count bootstraps. Never select lambda from the
  public leaderboard alone.

## Traffic minimum implementation sequence

1. Re-run the official baseline and 0.71846 public pipeline with the newly joined account;
   retain component files and exact hashes.
2. Fix the onset clock and produce an explicit six-horizon queue mask.
3. Build an honest Task 1 temporal-mask harness and topology-aware residual baseline.
4. Add the Pareto-constrained FD/LWR projection.
5. Build pseudo-windows and split onset/ongoing queue models.
6. Sweep ODME regularizers with link holdouts/bootstraps.
7. Use remote submissions only as predeclared ablations (one component changed at a
   time). Validation/private incident independence makes iterative public-LB fitting
   especially dangerous.

## Evidence retained locally

- Official Traffic repository: `traffic/official/`
- Public Traffic notebook sources/outputs: `traffic/public_notebooks/`
- Public Poker notebook sources: `traffic/intel/poker/notebooks/`
- Public V32 merged submission: `traffic/public_notebooks/traffic_flow_bench_pipeline_v32/output/submission.csv`
  (6,985,307 rows; SHA-256
  `7673146d855a153ee56e90ea5afd5dd5431299420d3e803df5e73396e7611e0c`).

The live leaderboard values and Kaggle inventories are dated snapshots and should be
re-queried before making a prize/effort decision.
