# CUHK-X Small Model Track: public baseline promotion-gate audit

Checked: `2026-09-11`.

## Superseding availability audit (2026-09-11 13:39 CST)

The model dataset referenced by the notebooks is currently readable through
the Kaggle API at
`phuongncn/k-kuno-lb-0-711-r2plus1d-model`; the earlier web label
`[Dataset no longer available]` is therefore stale. Its complete eight-file
inventory was listed and the two weight files were downloaded to an isolated
temporary audit directory. No inference was run.

- `ensemble_packed.pt`: 88,074,378 bytes; SHA-256
  `1bef2e215fc100acf571b90370a8353574fdad6951b0f75f6e3404521643322f`.
- `yolo11n.pt`: 5,613,764 bytes; SHA-256
  `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
- Total learned assets: 93,688,142 bytes, matching the model card.
- A `torch.load(..., weights_only=True)` schema audit confirmed that the first
  file contains two packed classifier states, folds `[0, 1]`, signed bit widths
  `[5, 6]`, equal weights, and reported parent accuracies `0.7155963` and
  `0.7187040`.
- The companion license ledger assigns the fine-tuned classifiers to CUHK-X
  competition/non-commercial terms, YOLO11n to AGPL-3.0, the pinned IG65M
  architecture source to MIT, and notebook code to Apache-2.0. Dataset-level
  metadata says only `other`.

Availability is now `PASS`, but promotion remains `FAIL`: the published
inference graph still loads two separate weight files rather than one
checkpoint; no frozen clip manifest, per-subject results, per-class results,
or independently reproducible training run is supplied; and the AGPL detector
creates an unresolved finalist Apache-2.0 packaging boundary. Repacking or
using these weights is not authorized by this audit. They remain research
context only, outside frozen P2.

This is a read-only audit of publicly visible Kaggle notebooks. No notebook was
forked, no inference was run, and no submission was made. The original audit
below predates the superseding availability check above.

## Candidates

Parent public notebook:
https://www.kaggle.com/code/phuongncn/lb-0-711-yolo-person-crop-r2plus1d-100mb

- Title: `LB 0.711 | YOLO Person Crop + R2Plus1D <100MB`.
- Author: `phuongncn` / Fususu.
- Public notebook license: Apache 2.0.
- Best visible score: `0.71144` on version 6; notebook version 7 is the latest.
- Reported runtime: 94.2 seconds on Kaggle T4 x2.
- Reported assets: two subject-fold R(2+1)D-34 classifiers in
  `ensemble_packed.pt` plus `yolo11n.pt`, totaling 93,688,142 bytes.
- Reported parent subject-validation accuracies: `0.7155963302752294` and
  `0.7187039764359352`.
- Reported modalities: Depth_Color + IR; fixed YOLO person crop; 16 frames;
  horizontal-flip TTA.

Derivative public notebook:
https://www.kaggle.com/code/kunaldesale2408/yolo-for-cuhk-x

- Title: `YOLO for CUHK-X`.
- Author: `kunaldesale2408` / Kunal Desale.
- Public notebook license: Apache 2.0.
- Best visible score: `0.71641` on version 7.
- Latest visible version: version 9, public score `0.67164`, runtime 297.1
  seconds on TPU v5e-8.
- It uses the same reported 93,688,142-byte classifier-plus-YOLO asset set and
  adds four-pass inference TTA plus a modified crop anchor.

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| Non-LLM inference | PASS | Visible graph is YOLO11n plus R(2+1)D-34 classifiers; no LLM is shown in inference. |
| Under 100 MB total | PASS by author assertion only | Notebook asserts exactly 93,688,142 bytes, but the assets were not independently downloaded and hashed. |
| Single checkpoint | FAIL as published | Learned inference weights are split between `ensemble_packed.pt` and `yolo11n.pt`, contrary to the current single-checkpoint operating gate. |
| Public/reproducible weights | FAIL | The parent notebook's model input is visibly marked `[Dataset no longer available]`; no durable public dataset URL or asset hashes are exposed. The derivative retains a named input association but does not expose a reproducible public asset location. |
| Subject-disjoint validation | UNVERIFIED | The author reports Subject-CV and two fold scores, but the public inference notebook does not include the training split manifest needed to independently prove subject isolation. |
| Clip-disjoint validation | UNVERIFIED | No frozen train/validation clip manifest is supplied with the inference notebook. |
| License/provenance | PARTIAL | Notebook code is Apache 2.0; it identifies YOLO11n as AGPL-3.0 and the IG65M architecture source as MIT at commit `fc749e2ee354c3e4ddbb144cf511bb868b008f61`. The unavailable model asset prevents a complete hash/license audit. |
| Promotion | FAIL | One hard gate fails and three required audits are incomplete. |

## Decision

Neither notebook is eligible for direct use or submission in its current form.
Do not fork it as a competition candidate, do not rely on its unavailable model
asset, and do not submit its prediction file.

The architecture and preprocessing descriptions may be treated as public
research context, with attribution, when designing an independently trained
candidate. Any future candidate must:

1. use a freshly documented public or participant-trained weight source;
2. pack every learned inference weight into one checkpoint below 100,000,000
   bytes and record its SHA-256;
3. publish or retain a frozen subject- and clip-disjoint fold manifest;
4. independently reproduce its offline metric on that manifest; and
5. pass the complete license/provenance inventory before Kaggle submission.

Submission action: **none**.
