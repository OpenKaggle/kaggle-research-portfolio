# CUHK-X Small — top-down scientific and engineering strategy review

Reviewed: 2026-09-11 CST, while Transport=`BLOCKED`,
Scientific=`NOT_RUN_PAYLOAD_BLOCKED`, and
Release=`REJECT_NO_TEST_CANDIDATE`.

This review checks whether the frozen S1 → S2 → S3 plan is a defensible global
route rather than a local optimization around the first implementable model.
It changes no experiment gate and reports no model progress.

## 1. Problem definition

The target is 40-class activity recognition for subjects absent from training,
using synchronized non-RGB Depth, IR, Thermal, IMU, mmWave, and Skeleton data.
The primary scientific risk is cross-subject generalization, not ordinary
random-split fit. Secondary risks are long-tail classes, two-environment scale
shift, missing/corrupt modalities, sensor ordering, and a strict edge package.

The competition result must therefore be treated as a conjunction:

1. a representation that distinguishes appearance-similar actions by motion;
2. subject- and clip-disjoint evidence rather than public-rank tuning;
3. explicit missingness and scale/order handling;
4. one deterministic, offline, non-LLM checkpoint below 100 MB; and
5. reproducible source, license, data, and weight provenance.

Official first-hand sources:

- CUHK-X paper: https://arxiv.org/abs/2512.07136
- organizer repository: https://github.com/openaiotlab/CUHK-X
- competition: https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track

The organizer's published cross-trial baselines place Thermal (92.57%), Depth
(90.46%), and IR (90.22%) above Skeleton (79.08%), mmWave (46.63%), and IMU
(45.52%). These are not our LOSO metrics and cannot be used as a promotion
result, but they are a rational modality-priority prior.

## 2. Method-family review

| Family | Primary/official evidence | Fit to this campaign | Decision |
|---|---|---|---|
| 2D CNN + TSM | TSM exchanges temporal features with zero added parameters/compute; official implementation is MIT | Directly fits eight streamed frames, M4 training, and single-checkpoint budget | **S1 core** |
| Explicit temporal differences | TDN models short- and long-range differences; official code is Apache-2.0 | Addresses action direction/change missed by frame averaging; current clean-room P2 uses signed deltas | **S1 core** |
| Lightweight 3D video CNN | X3D expands a tiny 2D model efficiently; PyTorchVideo is Apache-2.0. MoViNet supports streaming video | Credible accuracy/efficiency alternative, but changes the backbone, raises compute and asset complexity, and weakens causal attribution under the current deadline | **Audited fallback, not scheduled** |
| Skeleton graph model | ST-GCN directly models joint-space and temporal edges | Compact and subject-oriented, but CUHK-X's published unimodal prior is lower and no accepted Skeleton payload exists | **Evidence parking lot** |
| IMU temporal model | Organizer baseline and multimodal literature support wearable motion features | Tiny payload and checkpoint, but CUHK-X's published unimodal prior is weak; metadata-only smoke already failed | **S2 complement only** |
| Attention/missing-modality reconstruction | HAMLET supports hierarchical multimodal attention; ActionMAE shows random modality dropping and learned reconstruction can reduce missing-modality degradation | Useful only after a strong single modality exists. Full ActionMAE adds transformer/reconstruction complexity that is not justified before S1 | **S2 principle, simplified implementation** |
| Depth/IR R(2+1)D + person crop | Public K-KUNO notebooks show this family can be competitive | Two weight files, incomplete fold lineage, and AGPL detector packaging prevent direct promotion | **Research-only; do not run/repack** |

Primary method sources:

- TSM paper: https://openaccess.thecvf.com/content_ICCV_2019/papers/Lin_TSM_Temporal_Shift_Module_for_Efficient_Video_Understanding_ICCV_2019_paper.pdf
- TSM official code: https://github.com/mit-han-lab/temporal-shift-module
- TDN paper: https://openaccess.thecvf.com/content/CVPR2021/html/Wang_TDN_Temporal_Difference_Networks_for_Efficient_Action_Recognition_CVPR_2021_paper.html
- TDN official code: https://github.com/MCG-NJU/TDN
- ActionMAE paper: https://ojs.aaai.org/index.php/AAAI/article/view/25378
- ActionMAE official code: https://github.com/sangminwoo/ActionMAE
- HAMLET paper: https://arxiv.org/abs/2008.01148
- X3D paper: https://ai.meta.com/research/publications/x3d-expanding-architectures-for-efficient-video-recognition/
- PyTorchVideo official code: https://github.com/facebookresearch/pytorchvideo
- MoViNet paper: https://openaccess.thecvf.com/content/CVPR2021/html/Kondratyuk_MoViNets_Mobile_Video_Networks_for_Efficient_Video_Recognition_CVPR_2021_paper.html
- ST-GCN paper: https://arxiv.org/abs/1801.07455

No third-party method code or pretrained weight was copied into P2 during this
review.

## 3. Kaggle evidence boundary

Two public Depth/IR + R(2+1)D notebooks are useful mechanism reports, not
admissible candidates:

- https://www.kaggle.com/code/phuongncn/lb-0-711-yolo-person-crop-r2plus1d-100mb
- https://www.kaggle.com/code/kunaldesale2408/yolo-for-cuhk-x

Their public scores suggest that person-centric visual modeling is relevant,
but do not identify which rows, folds, crops, ensemble states, or assets cause
the gain. The K-KUNO assets remain outside the experiment graph because the
published inference uses two learned-weight files, lacks independently frozen
four-LOSO evidence, and includes an AGPL YOLO component. The public Thermal
notebook similarly supplies a method description but no accepted training
payload or trained checkpoint.

No leaderboard row/subset was queried, and no public score is an optimization
target in the ladder.

## 4. Why the frozen route remains globally preferred

The review leaves the three-stage ladder unchanged:

1. **S1 — Thermal TSM + signed temporal differences.** This combines the
   strongest organizer-reported non-RGB modality with the lowest-risk temporal
   mechanism. B0 and S1 differ by one causal mechanism and use identical
   frames, initialization, optimizer, schedule, resolution, and folds.
2. **S2 — conditional Thermal + IMU.** Only after S1 passes, freeze the visual
   path and add a small IMU branch, explicit availability mask, gated fusion,
   and train-only modality dropout. This tests complementarity without paying
   for a second visual backbone.
3. **S3 — train-only robustness.** Only after S2 passes, freeze the inference
   graph and change clip-consistent visual and IMU augmentations. This targets
   subject/environment shift without adding inference weights.

X3D/MoViNet and Skeleton-first paths remain visible alternatives, which avoids
conceptual tunnel vision, but executing them now would consume the small
post-payload window and destroy the one-change-at-a-time attribution. They may
replace the ladder only through a new preregistration after a terminal S1
rejection or a material rule/data change, never through silent mid-run drift.

The visual route map is stored at:
`../../../../.codex/visualizations/2026/09/08/01a082ed-cf50-7c53-9373-b5ae4bd346c1/cuhkx-small-topdown-routes.svg`.

## 5. Data and privacy boundary

Current transport evidence remains terminal for this review:

- the Kaggle competition exposes only test/sample files;
- all nine organizer Google volumes return quota pages;
- Baidu ends in a client handoff without a verifiable range URL;
- the organizer object-store APIs list relevant directories but return empty
  file arrays; and
- the complete official Hugging Face mirror requires sharing the account
  username and email with the repository authors.

No Hugging Face agreement, login, access request, or contact transmission is
authorized. The quarantined third-party Kaggle Thermal partial archive remains
unextracted and excluded.

## 6. Execution and submission discipline

After a provenance-approved payload arrives:

1. validate the full official inventory, safe paths, size, hash, and CRC;
2. run S1 subjects 6 and 18 and apply the frozen fast-kill;
3. continue subjects 5 and 21 only if the two-fold screen passes;
4. keep subjects 9 and 24 untouched for confirmation after the ladder freezes;
5. advance S2 and S3 sequentially, one causal change per stage;
6. require one checkpoint, byte-identical replay, complete license inventory,
   and the Small boundary harness; and
7. allow at most one submission per independently qualified stage, at most
   three causal submissions across the ladder.

Until then, only legal transport diffs and harness improvements are modelled as
progress. Scientific and release states remain blocked/rejected.
