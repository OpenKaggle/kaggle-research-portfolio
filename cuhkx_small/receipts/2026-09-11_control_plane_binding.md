# CUHK-X Small Track — control-plane binding

Bound: 2026-09-11 CST.

This Small-track workspace is governed by
`../../CUHK_X_CONTROL_PLANE.md`. The binding does not modify the frozen P2
hypothesis, folds, or promotion thresholds in
`2026-09-11_p2_tsm_preregistration.md`.

## Transport matrix

| Route | Access state | Allowed action | Stop condition |
|---|---|---|---|
| Google Drive, organizer-linked | Public, currently quota-blocked | Retry bounded range requests; cache only validated central-directory and selected members | Any non-206 response, geometry/inventory mismatch, CRC failure, or unsafe member |
| Baidu Wangpan, organizer-linked | Password/list/signing work; anonymous download yields client handoff rather than HTTP `dlink` | Retry only if the public route exposes a normal range-capable URL | Client-only/encrypted handoff, unverifiable redirect, or login/contact request |
| Hugging Face, organizer-linked | Browser gate granted after explicit user authorization; CLI token absent | Use only the commit-locked nine-volume manifest and an environment-only Bearer token after the user creates/exports it personally | Missing environment variable, HTTP 401/403, non-206 response, range/size/hash mismatch, or any request for the user's password |
| Unofficial mirrors | None accepted | Read-only discovery only | No traceable organizer provenance, public reproducibility, exact hash, or usable license |
| Full local archive | Insufficient working space | Do not assemble or extract the full split archive | Retained archive plus extraction and experiment headroom do not fit safely |

The only active acquisition target is the minimum official Thermal payload:
validate the complete 2,891-clip / 201,466-file inventory, then retain at most
eight preregistered midpoint frames per clip with size and CRC-32 checks.

## Public-asset and license control

- The selective reader and P2 implementation are original Apache-2.0 work.
- P2 currently uses no pretrained weights and incorporates no organizer or
  third-party TSM implementation.
- Installed runtime dependency licenses and versions are recorded in
  `2026-09-11_p2_tsm_scaffold.md`.
- Any future public dataset, pretrained weight, or code asset is fail-closed
  until its exact source URL, version, license, byte hash, public accessibility,
  and role are recorded. An unavailable or ambiguously licensed asset cannot be
  used for training, inference, or a submission package.

## P2 fast-kill control

- Thermal only; P3 and Depth/IR expansion remain locked.
- LOSO subjects run in the frozen order 6, 18, 5, 21 with zero subject and clip
  overlap.
- Stop after the first two folds if both P2-minus-B0 gains are below +0.01.
- Full promotion requires median gain at least +0.02, at least three of four
  gains nonnegative, and worst gain at least -0.02.
- A failed or incomplete run receives a rejection/blocker receipt and cannot
  authorize test inference or a Kaggle submission.

## Single-checkpoint control

- Every learned inference weight must be stored in exactly one checkpoint.
- FP32 promotion ceiling: strictly below 95,000,000 bytes.
- INT8 may be considered only after an accepted FP32 candidate; the single INT8
  checkpoint must be below 100,000,000 bytes with no more than 0.005 absolute
  validation loss.
- Two clean offline inference runs over the same frozen manifest must produce
  byte-identical prediction files.
- The current untrained P2 serialization audit is 6,376,779 bytes. It is an
  engineering check, not a trained candidate.

## Current decision

`PREREGISTERED_PAYLOAD_BLOCKED`.

The user explicitly authorized the official Hugging Face repository to receive
the current Hugging Face username and email, and browser access was granted.
No password or CLI token was handled by this task, no official Thermal member
was retained, no P2 fold was fit, no test data was opened, and no submission
was made.
