# CUHK-X Small Track — P2 visual quick-kill preregistration

Frozen: 2026-09-11 12:43 CST, before any visual payload is acquired or any P2
model is fit.

## Hypothesis and comparison

P2 tests whether zero-parameter Temporal Shift Modules plus explicit frame
difference improve cross-subject recognition over the same lightweight 2D
backbone with temporal mean pooling. The first payload choice is Thermal;
Depth, then IR, may replace it only if the corresponding official members can
be selectively acquired sooner. Results from different modalities are never
mixed in the same gate decision.

- `B0`: one MobileNetV3-Small spatial encoder, eight raw frames, mean-pooled
  clip logits.
- `P2`: the same encoder, optimizer, augmentation, schedule, resolution, and
  frame indices; insert TSM before selected inverted-residual blocks and map
  grayscale raw/difference information to three input channels as
  `[frame, positive_delta, negative_delta]`.
- Initial weights may be public ImageNet weights only if their exact URL,
  version, license, and hash are recorded. Both arms must use the same initial
  weights. No additional training data or model is allowed in this quick kill.

## Frozen sampling and splits

Decode each clip in timestamp order and sample eight midpoint indices
`floor((2k+1) * N / 16)` for `k=0..7`, clipped to `[0, N-1]`. A one-frame clip
repeats its frame; an empty/corrupt clip is rejected and counted, never silently
assigned a label. Resize preserving aspect ratio, center-pad, then crop to
`112x112`. Delta at time zero is all zeros; later deltas use the current minus
previous sampled grayscale frame. All transforms are clip-consistent.

Run four single-subject holdouts in this order:

1. subject 6 — 196 indexed clips, 34 classes;
2. subject 18 — 184 indexed clips, 35 classes;
3. subject 5 — 83 indexed clips, 17 classes;
4. subject 21 — 129 indexed clips, 25 classes.

These deliberately cover both subject cohorts and the observed high/low clip
and class-coverage extremes. For every LOSO run, all clips from the held-out
subject are validation-only; all other subjects are training-only. Subject and
clip overlap must both equal zero. Selection, early stopping, and checkpoint
choice use training-only splits and never Kaggle scores.

## Frozen quick-kill and packaging gates

Measure P2 minus B0 absolute accuracy on each held-out subject. P2 advances
only if all conditions hold:

1. median improvement is at least +0.02;
2. at least three of four subject improvements are non-negative;
3. the worst-subject improvement is no worse than -0.02;
4. after subjects 6 and 18, stop immediately if both improvements are below
   +0.01;
5. report accuracy, macro recall, every present class, subject, cohort,
   corrupt/empty count, parameter count, latency, and peak memory;
6. all learned inference weights live in exactly one checkpoint: FP32 must be
   `<95,000,000` bytes, or INT8 `<100,000,000` bytes with no more than 0.005
   absolute validation loss versus its accepted FP32 source; and
7. two clean inference runs over the same frozen validation manifest must emit
   byte-identical output files.

No missing-modality token/fusion branch may begin until this single-modality P2
gate passes independently. Failure means `REJECT_P2`; it does not authorize a
test prediction or Kaggle submission.

## Current state

`PREREGISTERED_PAYLOAD_BLOCKED`. The selective ZIP/ZIP64 reader and its local
transport tests are complete, but no official raw visual member is present.
Google Drive currently returns its quota page, Baidu anonymous download returns
a client-handoff payload without an HTTP `dlink`, and the Hugging Face gate
would require contact-information transmission that was not authorized.

